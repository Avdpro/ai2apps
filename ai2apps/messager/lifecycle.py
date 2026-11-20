"""Reversible Bot cleanup, using original execution and Hook authorities."""
import hashlib
import json
import logging
from uuid import uuid4

CHAT='ai2apps.messager.bots'
ARCHIVE=CHAT+'.archived'
ACTIVE=('queued','running','planning','waiting_input','waiting_capability')


class BotLifecycle:
    def __init__(self, runtime, directory):
        logging.getLogger(__name__).info('Bot lifecycle loaded; source=%s',__file__)
        self.runtime,self.directory,self.db=runtime,directory,directory.db
        with self.db.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_archive(bot_id TEXT PRIMARY KEY,actor TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,deleted INTEGER NOT NULL DEFAULT 0)')

    def archived(self, actor):
        with self.db.transaction() as db:
            return {'items':[dict(r) for r in db.execute('SELECT b.id,b.name,a.revision FROM messager_bots b JOIN messager_bot_archive a ON a.bot_id=b.id AND a.actor=b.actor WHERE b.actor=? AND a.deleted=1',(actor,))]}

    def review(self, actor, bot_id):
        self.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:
            runs=[r[0] for r in db.execute("SELECT r.id FROM agent_runs r JOIN app_chat_sessions s ON s.session_id=r.session_id WHERE s.owner=? AND s.registration IN (?,?) AND json_extract(s.scope_json,'$.bot_id')=? AND r.status NOT IN ('completed','failed','cancelled','timed_out','interrupted')",(actor,CHAT,'ai2apps.messager.task-execution',bot_id))]
            revision=db.execute('SELECT revision FROM messager_bot_archive WHERE bot_id=?',(bot_id,)).fetchone()
            sessions=[r[0] for r in db.execute('SELECT session_id FROM app_chat_sessions WHERE owner=? AND registration=? AND json_extract(scope_json,\'$.bot_id\')=? AND json_extract(scope_json,\'$.dialogue_job\') IS NULL',(actor,CHAT,bot_id))]
            archived=db.execute('SELECT count(*) FROM app_chat_sessions WHERE owner=? AND registration=? AND json_extract(scope_json,\'$.bot_id\')=?',(actor,ARCHIVE,bot_id)).fetchone()[0]
            proposals=[r[0] for r in db.execute("SELECT id FROM messager_task_proposals WHERE actor=? AND bot_id=? AND status IN ('pending','approving')",(actor,bot_id))]
        tasks=[]
        if self.runtime.todo:
            with self.runtime.todo.store.connect() as db:
                for row in db.execute('SELECT t.id,t.next_due,b.registration AS execution_owner FROM tasks t JOIN task_execution_lanes l ON l.task_id=t.id LEFT JOIN task_execution_bindings b ON b.task_id=t.id AND b.owner=t.owner WHERE t.owner=? AND l.owner=? AND l.lane=?',(actor,actor,'messager-bot:'+bot_id)):
                    tasks.append({'id':row['id'],'scheduled':row['next_due'] is not None,'owned':row['execution_owner'] in ('ai2apps.messager.todo-execution/v1','messager.bot-agent-chat','ai2apps.messager.flash')})
        hooks=[]
        for rule in self.runtime.event_hooks.rules(actor):
            spec=self.runtime.event_hooks.get(actor,rule['id'])['revisions'][-1]['spec']
            consumer=spec['consumer']
            if consumer['registration']=='messager.bot.observe' and consumer['binding'].get('bot_id')==bot_id:
                hooks.append({'id':rule['id'],'revision':rule['revision'],'status':rule['status']})
        notes=self.directory.memory.list(actor,bot_id)['items']
        communication=getattr(self.runtime,'messager_bot_communication',None)
        consultations=communication.review(actor,bot_id) if communication else []
        runs.extend(c['run_id'] for c in consultations if c['run_id'] and self.runtime.agents.get_run(c['run_id']).status.value not in ('completed','failed','cancelled','timed_out','interrupted'))
        value={'revision':revision[0] if revision else 0,'runs':sorted(runs),'tasks':tasks,'hooks':hooks,'sessions':sessions,'archived_conversations':archived,'proposals':proposals,'memory_revisions':[(r['id'],r['revision']) for r in notes],'memory_count':sum(not r['deleted'] for r in notes),'is_default':self.directory.ensure_default(actor)==bot_id}
        value['consultations']=consultations
        delegation=getattr(self.runtime,'messager_bot_delegation',None)
        value['delegations']=delegation.review(actor,bot_id) if delegation else []
        value['access_revision']=self.runtime.messager_bot_permissions.current(actor,bot_id)[0]
        access=getattr(self.runtime,'messager_bot_app_access',None)
        value['app_access_revision']=access.current(actor,bot_id)[0] if access else None
        value['review_hash']=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
        return value

    async def apply(self, actor, bot_id, action, review_hash, *, clear_memory=False, revoke_access=False, delete_tasks=False):
        if action not in ('clear_memory','clear_dialogue','restore_dialogue','archive','reset'):
            raise ValueError('Unknown Bot cleanup action')
        if type(clear_memory) is not bool or type(revoke_access) is not bool or type(delete_tasks) is not bool:
            raise ValueError('Cleanup options must be booleans')
        if action!='clear_dialogue' and (clear_memory or revoke_access or delete_tasks):
            raise ValueError('Optional cleanup choices require clear_dialogue')
        with self.runtime.app_chat.lock:
            review=self.review(actor,bot_id)
            if review['review_hash']!=review_hash:raise ValueError('Bot work changed; review again')
            if action=='archive' and review['is_default']:raise ValueError('Reset the default Bot instead of deleting it')
            # Read-only preflight: externally owned execution must be stopped by its owner.
            todo_runs=[]
            if self.runtime.todo:
                with self.runtime.todo.store.connect() as db:
                    for task in review['tasks']:
                        for r in db.execute("SELECT id,data FROM runs WHERE owner=? AND task_id=? AND status IN ('queued','running','planning','waiting_input','waiting_capability')",(actor,task['id'])):
                            data=json.loads(r['data'])
                            if data.get('desktop_native') or not data.get('execution_binding'):
                                raise ValueError('Stop manually linked or Desktop-owned work in its original App first')
                            todo_runs.append(r['id'])
            if action=='restore_dialogue' and not review['archived_conversations']:raise ValueError('No archived conversation')
            # Expire old context/proposals without deleting persistent access for content cleanup.
            self.runtime.messager_bot_permissions.invalidate(actor,bot_id,preserve_grants=True)
            for rule in review['hooks']:
                if rule['status']=='active':
                    self.runtime.event_hooks.change(actor,rule['id'],'pause',rule['revision'],'bot-cleanup:'+uuid4().hex)
                with self.db.transaction() as db:
                    hook_tasks=[r[0] for r in db.execute("SELECT e.task_id FROM hook_executions e JOIN hook_deliveries d ON d.id=e.delivery_id WHERE d.rule_id=? AND e.task_id IS NOT NULL AND e.state IN ('admitting','queued','running')",(rule['id'],))]
                for task_id in hook_tasks:self.runtime.system_tasks.cancel(actor,task_id)
            if self.runtime.todo:
                with self.runtime.todo.store.connect() as db:
                    for task in review['tasks']:db.execute('UPDATE tasks SET next_due=NULL WHERE owner=? AND id=?',(actor,task['id']))
            with self.db.transaction(write=True) as db:
                # Selected persistent changes commit together; cancellation/pausing above
                # is fail-closed and never resumes automatically if this commit fails.
                if action in ('archive','reset') or revoke_access:
                    self.runtime.messager_bot_permissions.revoke_all_grants(db,actor,bot_id)
                db.execute("UPDATE messager_task_proposals SET status='rejected' WHERE actor=? AND bot_id=? AND status IN ('pending','approving')",(actor,bot_id))
                db.execute("UPDATE messager_configuration_proposals SET status='rejected',result_json=? WHERE actor=? AND bot_id=? AND status='pending'",(json.dumps({'applied':False,'reason':'Bot cleanup'}),actor,bot_id))
                db.execute('INSERT INTO messager_bot_archive VALUES(?,?,1,0) ON CONFLICT(bot_id) DO UPDATE SET revision=revision+1',(bot_id,actor))
                maintenance=getattr(self.directory,'memory_tasks',None)
                if maintenance and (action in ('clear_dialogue','restore_dialogue','archive','reset','clear_memory') or clear_memory):maintenance.invalidate(db,actor,bot_id)
                if action in ('clear_dialogue','restore_dialogue','archive','reset'):
                    db.execute('UPDATE messager_voice_sessions SET closed=1 WHERE actor=? AND bot_id=?',(actor,bot_id))
                    restore=db.execute('SELECT session_id FROM app_chat_sessions WHERE owner=? AND registration=? AND json_extract(scope_json,\'$.bot_id\')=? ORDER BY rowid DESC LIMIT 1',(actor,ARCHIVE,bot_id)).fetchone() if action=='restore_dialogue' else None
                    for sid in review['sessions']:
                        db.execute('UPDATE app_chat_sessions SET registration=?,scope_json=? WHERE session_id=?',(ARCHIVE,json.dumps({'bot_id':bot_id,'archive_id':uuid4().hex}),sid))
                    if restore:db.execute('UPDATE app_chat_sessions SET registration=?,scope_json=? WHERE session_id=?',(CHAT,json.dumps({'bot_id':bot_id},sort_keys=True,separators=(',',':')),restore[0]))
                if action in ('clear_memory','reset') or clear_memory:
                    from datetime import datetime, UTC
                    db.execute('UPDATE messager_bot_memories SET deleted=1,revision=revision+1,updated_at=? WHERE actor=? AND bot_id=? AND deleted=0',(datetime.now(UTC).isoformat(),actor,bot_id))
                if action=='archive':db.execute('UPDATE messager_bot_archive SET deleted=1 WHERE bot_id=?',(bot_id,))
                if action=='reset':
                    db.execute('DELETE FROM messager_bot_avatars WHERE actor=? AND bot_id=?',(actor,bot_id))
                    db.execute('DELETE FROM messager_bot_voice WHERE actor=? AND bot_id=?',(actor,bot_id))
                    db.execute('DELETE FROM messager_bot_voice_last WHERE actor=? AND bot_id=?',(actor,bot_id))
                    db.execute('DELETE FROM messager_realtime_settings WHERE actor=? AND bot_id=?',(actor,bot_id))
                    if review['is_default']:db.execute('UPDATE messager_bots SET name=?,duty=? WHERE actor=? AND id=?',('AI2Apps',self.directory.default_duty,actor,bot_id))
        for rid in todo_runs:await self.runtime.todo.cancel(actor,rid)
        removed=0
        if self.runtime.todo and (action in ('archive','reset') or delete_tasks):
            for task in review['tasks']:
                if task['owned']:
                    self.runtime.todo.system_schedules().retire(actor,task['id'],bot_id,'bot_delete' if action=='archive' else 'dialogue_clear')
                    retired=self.runtime.todo.store.get(actor,task['id'])
                    if not retired.get('deleted_at') or retired.get('next_due') is not None:
                        raise ValueError('Background task cleanup did not complete')
                    # Task authority must retire with the owned Task. Ordinary Bot
                    # App Access remains governed by the explicit cleanup checkbox.
                    with self.db.transaction(write=True) as db:
                        db.execute("UPDATE messager_task_access_policies SET status='revoked' WHERE actor=? AND bot_id=? AND id IN (SELECT id FROM messager_task_proposals WHERE actor=? AND bot_id=? AND task_id=?)",(actor,bot_id,actor,bot_id,task['id']))
                    removed+=1
        return {'status':'archived' if action=='archive' else 'updated','recoverable':True,'stopped_runs':len(review['runs']),'paused_hooks':len(review['hooks']),'paused_tasks':len(review['tasks']),'deleted_tasks':removed}

    def restore(self, actor, bot_id, revision):
        with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            row=db.execute('SELECT * FROM messager_bot_archive WHERE actor=? AND bot_id=? AND deleted=1',(actor,bot_id)).fetchone()
            if not row or row['revision']!=revision:raise ValueError('Archived Bot changed')
            db.execute('UPDATE messager_bot_archive SET deleted=0,revision=revision+1 WHERE bot_id=?',(bot_id,))
        if self.runtime.todo:self.runtime.todo.system_schedules().restore_bot(actor,bot_id)
        # No grants, subscriptions, schedules or old executions are reactivated.
        return {'id':bot_id,'status':'restored'}
