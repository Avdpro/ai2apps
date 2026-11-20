"""Bot-owned local Inbox and projections onto the existing notification outbox.

Content stays local. Transport previews are fixed text and resolve an opaque,
re-authorized local notice; neither a model nor notice text supplies a route.
"""
import json
import logging
from datetime import datetime, UTC
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field
from ai2apps.core import utc_now_text, RepositoryError
from ai2apps.remote.notification_host import routes
from ai2apps.services.capability_routing import CapabilityProvider
from .tasks import APP, CHAT, TASK_CHAT, ADAPTER, TERMINAL

CAPABILITY='messager.notice.create'
log=logging.getLogger(__name__)


class Reminder(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title:str=Field(min_length=1,max_length=120)
    body:str=Field(default='',max_length=4000)


class NotificationPolicy(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    success:bool=True
    failure:bool=True
    waiting:bool=True
    reminder:bool=True


class BotNotifications:
    def __init__(self,runtime,directory):
        self.runtime,self.directory,self.db=runtime,directory,runtime.database
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_local_notices(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,operation_key TEXT NOT NULL,
                kind TEXT NOT NULL,content_json TEXT NOT NULL,source_session_id TEXT NOT NULL,
                todo_run_id TEXT,interaction_id TEXT,source_run_id TEXT,created_at TEXT NOT NULL,read_at TEXT,
                muted INTEGER NOT NULL DEFAULT 0,transport_event TEXT,UNIQUE(actor,operation_key))''')
            db.execute('CREATE INDEX IF NOT EXISTS messager_notice_owner ON messager_local_notices(actor,created_at)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_notification_policies(bot_id TEXT PRIMARY KEY,actor TEXT NOT NULL,revision INTEGER NOT NULL,value_json TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_notification_baseline(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO messager_notification_baseline VALUES(1,?)',(utc_now_text(),))
        routes(runtime).register(APP,'bot-notice',self.authorize_route)
        runtime.remote.notifications.register_source(self.reconcile_and_enqueue)
        runtime.remote.notifications.register_delivery_guard(self.delivery_guard)
        self.register_tool()
        log.info('Bot local notification bridge loaded; source=%s',__file__)

    def policy(self,actor,bot_id):
        self.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_notification_policies WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()
        return {'revision':row['revision'] if row else 0,'policy':json.loads(row['value_json']) if row else NotificationPolicy().model_dump()}

    def save_policy(self,actor,bot_id,revision,value):
        value=NotificationPolicy.model_validate(value).model_dump()
        with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            self.directory.scope(actor,{'bot_id':bot_id})
            row=db.execute('SELECT revision FROM messager_notification_policies WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()
            if (row[0] if row else 0)!=revision:raise ValueError('Notification settings changed; reload before saving')
            db.execute('INSERT INTO messager_notification_policies VALUES(?,?,?,?) ON CONFLICT(bot_id) DO UPDATE SET revision=excluded.revision,value_json=excluded.value_json',(bot_id,actor,revision+1,json.dumps(value)))
            rows=db.execute('SELECT kind,transport_event FROM messager_local_notices WHERE actor=? AND bot_id=? AND transport_event IS NOT NULL',(actor,bot_id)).fetchall()
            self.runtime.remote.notifications.cancel_pending([r['transport_event'] for r in rows if not value[r['kind']]],expected_owner_id=actor,connection=db)
        return self.policy(actor,bot_id)

    def _source(self,actor,bot_id,sid):
        b=self.runtime.app_chat.binding(sid)
        if not b or b['owner']!=actor or b['registration']!=CHAT or b['scope'].get('bot_id')!=bot_id:raise PermissionError('Original Bot conversation is unavailable')
        with self.db.transaction() as db:
            active=db.execute("SELECT 1 FROM sessions WHERE id=? AND status='active'",(sid,)).fetchone()
        if not active:raise PermissionError('Original Bot conversation is unavailable')
        self.runtime.app_chat.owner(b)

    def create(self,actor,bot_id,key,kind,content,sid,*,todo_run_id=None,interaction_id=None,source_run_id=None,muted=False):
        self.directory.scope(actor,{'bot_id':bot_id});self._source(actor,bot_id,sid)
        body=json.dumps(content,ensure_ascii=False,sort_keys=True)
        with self.db.transaction(write=True) as db:
            old=db.execute('SELECT * FROM messager_local_notices WHERE actor=? AND operation_key=?',(actor,key)).fetchone()
            if old:
                if (old['bot_id'],old['kind'],old['content_json'],old['source_session_id'],old['todo_run_id'],old['interaction_id'],old['source_run_id'])!=(bot_id,kind,body,sid,todo_run_id,interaction_id,source_run_id):raise ValueError('Notification receipt belongs to different parameters')
                return {'status':'saved','notification_id':old['id'],'receipt_id':old['id'],'muted':bool(old['muted'])}
            current_policy=db.execute('SELECT value_json FROM messager_notification_policies WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()
            if current_policy and not json.loads(current_policy[0])[kind]:muted=True
            ref='bn_'+uuid4().hex
            db.execute('INSERT INTO messager_local_notices VALUES(?,?,?,?,?,?,?,?,?,?,?,NULL,?,NULL)',(ref,actor,bot_id,key,kind,body,sid,todo_run_id,interaction_id,source_run_id,utc_now_text(),int(muted)))
        return {'status':'saved','notification_id':ref,'receipt_id':ref,'muted':muted}

    def register_tool(self):
        async def create(args,ctx):
            value=Reminder.model_validate(args).model_dump()
            if not value['title'].strip():raise ValueError('Reminder title required')
            with self.runtime.app_chat.lock:
                self.runtime.app_chat.require_authorized(ctx,CAPABILITY,args)
                if not ctx.invocation_id:raise PermissionError('An original Tool invocation is required')
                b=self.runtime.app_chat.binding(ctx.session_id)
                if not b or b['registration'] not in (CHAT,TASK_CHAT):raise PermissionError('Bot conversation or reviewed task required')
                bot_id=b['scope']['bot_id'];sid=b['session_id'];todo_run=None
                if b['registration']==TASK_CHAT:
                    todo_run=b['scope']['todo_run_id']
                    with self.db.transaction() as db:
                        row=db.execute('SELECT p.source_session_id FROM messager_task_runs r JOIN messager_task_proposals p ON p.id=r.proposal_id WHERE r.actor=? AND r.bot_id=? AND r.todo_run_id=?',(ctx.actor_user_id,bot_id,todo_run)).fetchone()
                    if row is None:raise PermissionError('Task notification source unavailable')
                    sid=row[0]
                muted=not self.policy(ctx.actor_user_id,bot_id)['policy']['reminder']
                return self.create(ctx.actor_user_id,bot_id,'reminder:'+ctx.invocation_id,'reminder',value,sid,todo_run_id=todo_run,source_run_id=ctx.trace_id,muted=muted)
        source=self.runtime.services.get_tool('todo.get');instance=self.runtime.services.get_instance_for_service(source.service_id)
        self.runtime.services.ensure_tool(service_id=source.service_id,qualified_name=CAPABILITY,display_name='创建站内提醒 / Create in-app reminder',
            description='Save a local reminder for the current Bot owner only. Destination is the original Bot conversation/task; cannot send to friends, Cloud messages, WeChat or arbitrary URLs.',
            input_schema=Reminder.model_json_schema(),output_schema={'type':'object'},effects=('workspace.write',),required_capabilities=())
        self.runtime.app_capability_router.register(CapabilityProvider(APP+'.'+CAPABILITY,CAPABILITY,APP,create,version='1',agent_context={
            'schema':'ai2apps.aaat-declaration/v1','instructions':['Create only the requested self reminder within the granted foreground/background scope. Title and body stay in the local Inbox; transport previews contain fixed generic text.',
                'The host binds the destination to the original Bot/task. Never supply a recipient, App, URL or task target. saved/receipt_id proves local persistence, not external delivery; muted means notification alerts are disabled by the user.'],
            'result_semantics':{'saved':'one local self reminder; not proof of Cloud delivery or an external message'}}))
        async def route(args,ctx):return await self.runtime.app_capability_router.invoke(CAPABILITY,args,ctx)
        self.runtime.service_registry.bind_tool(CAPABILITY,provider_key=instance.provider_key,handler=route)

    def _task(self,actor,bot_id,run_id):
        if self.runtime.todo is None:raise ValueError('Todo unavailable')
        with self.runtime.todo.store.connect() as db:row=db.execute('SELECT * FROM runs WHERE owner=? AND id=?',(actor,run_id)).fetchone()
        if not row:raise PermissionError('Task Run unavailable')
        data=json.loads(row['data']);binding=data.get('execution_binding') or {}
        if binding.get('registration')!=ADAPTER or binding['binding'].get('bot_id')!=bot_id:raise PermissionError('Task does not belong to this Bot')
        return row['status'],data

    def resolve(self,actor,ref):
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_local_notices WHERE actor=? AND id=?',(actor,ref)).fetchone()
        if not row or row['muted']:raise PermissionError('Reminder unavailable')
        self.directory.scope(actor,{'bot_id':row['bot_id']});self._source(actor,row['bot_id'],row['source_session_id'])
        task=None
        if row['todo_run_id']:
            status,data=self._task(actor,row['bot_id'],row['todo_run_id'])
            task={'id':data['snapshot']['id'],'title':data['snapshot']['title'],'run_id':row['todo_run_id'],'status':status}
            proposal=self.runtime.messager_task_execution.proposal(actor,row['bot_id'],data['execution_binding']['binding']['proposal_id'])
            if proposal['source_session_id']!=row['source_session_id']:raise PermissionError('Task source changed')
            if row['kind']=='success' and status!='completed' or row['kind']=='failure' and status not in TERMINAL-{'completed'}:raise PermissionError('Task outcome changed')
        if row['interaction_id']:
            with self.db.transaction() as db:
                pending=db.execute("SELECT x.id FROM agent_interactions x JOIN agent_runs r ON r.id=x.run_id JOIN messager_task_runs t ON t.agent_run_id=r.id WHERE x.id=? AND t.actor=? AND t.bot_id=? AND t.todo_run_id=? AND x.status='pending' AND x.deadline_at>? AND r.status IN ('waiting_input','waiting_capability') AND r.cancel_requested=0 AND r.deadline_at>?",(row['interaction_id'],actor,row['bot_id'],row['todo_run_id'],utc_now_text(),utc_now_text())).fetchone()
            if not pending:raise PermissionError('This task no longer needs this response')
        return {'bot_id':row['bot_id'],'source_session_id':row['source_session_id'],'todo_run_id':row['todo_run_id'],'interaction_id':row['interaction_id'],'task':task,'content':json.loads(row['content_json'])}

    def authorize_route(self,principal,ref):
        self.resolve(principal.actor_user_id,ref)
        return {'notification-route':'bot-notice','notification-resource':ref}

    def inbox(self,actor):
        with self.db.transaction() as db:rows=db.execute('SELECT * FROM messager_local_notices WHERE actor=? AND muted=0 ORDER BY created_at DESC,id LIMIT 100',(actor,)).fetchall()
        items=[]
        for row in rows:
            try:self.resolve(actor,row['id'])
            except (PermissionError,ValueError,KeyError,RepositoryError):continue
            items.append({'id':row['id'],'bot_id':row['bot_id'],'kind':row['kind'],'content':json.loads(row['content_json']),'created_at':row['created_at'],'read_at':row['read_at']})
        return {'items':items,'unread_count':sum(r['read_at'] is None for r in items),'has_more':len(rows)==100}

    def read(self,actor,ref):
        result=self.resolve(actor,ref)
        with self.db.transaction(write=True) as db:
            db.execute('UPDATE messager_local_notices SET read_at=COALESCE(read_at,?) WHERE actor=? AND id=?',(utc_now_text(),actor,ref))
            event=db.execute('SELECT transport_event FROM messager_local_notices WHERE actor=? AND id=?',(actor,ref)).fetchone()[0]
            if event:self.runtime.remote.notifications.cancel_pending([event],expected_owner_id=actor,connection=db)
        return result

    def read_all(self,actor):
        with self.db.transaction(write=True) as db:
            db.execute('UPDATE messager_local_notices SET read_at=COALESCE(read_at,?) WHERE actor=?',(utc_now_text(),actor))
            events=[r[0] for r in db.execute('SELECT transport_event FROM messager_local_notices WHERE actor=? AND transport_event IS NOT NULL',(actor,))]
            self.runtime.remote.notifications.cancel_pending(events,expected_owner_id=actor,connection=db)
        return {'read':True}

    def alert_allowed(self,actor,row):
        self.resolve(actor,row['id'])
        if row['read_at'] or not self.policy(actor,row['bot_id'])['policy'][row['kind']]:return False
        if row['kind']=='reminder':
            run=self.runtime.agents.get_run(row['source_run_id'])
            if run.cancel_requested:return False
            frozen=self.runtime.app_chat.execution_authorization(run.id)
            self.runtime.messager_bot_permissions.validate(actor,{'bot_id':row['bot_id']},frozen,CAPABILITY,{})
        return True

    def observe(self,actor,run_id,status,data):
        """Projection of original Todo/Agent state; never launches or resumes work."""
        binding=data['execution_binding']['binding'];bot_id=binding['bot_id']
        with self.db.transaction() as db:
            baseline=db.execute('SELECT created_at FROM messager_notification_baseline WHERE id=1').fetchone()[0]
            proposal=db.execute('SELECT source_session_id FROM messager_task_proposals WHERE actor=? AND bot_id=? AND id=?',(actor,bot_id,binding['proposal_id'])).fetchone()
        if not proposal:return
        try:
            policy=self.policy(actor,bot_id)['policy'];sid=proposal[0]
            if status in TERMINAL:
                finished=data.get('finished_at')
                if not finished or datetime.fromisoformat(finished.replace('Z','+00:00'))<datetime.fromisoformat(baseline.replace('Z','+00:00')):return
                kind='success' if status=='completed' else 'failure'
                muted=not policy[kind] or kind=='success' and not binding['notify']
                self.create(actor,bot_id,'task-result:'+run_id,kind,{'title':'Bot 任务已完成' if kind=='success' else 'Bot 任务未完成','body':'打开原 Bot 对话查看任务结果。'},sid,todo_run_id=run_id,muted=muted)
            elif status in ('waiting_input','waiting_capability'):
                with self.db.transaction() as db:
                    pending=db.execute("SELECT x.id,x.kind FROM agent_interactions x JOIN messager_task_runs t ON t.agent_run_id=x.run_id JOIN agent_runs r ON r.id=x.run_id WHERE t.actor=? AND t.todo_run_id=? AND x.status='pending' AND x.created_at>=? AND x.deadline_at>? AND r.status IN ('waiting_input','waiting_capability') AND r.cancel_requested=0 AND r.deadline_at>?",(actor,run_id,baseline,utc_now_text(),utc_now_text())).fetchall()
                for item in pending:self.create(actor,bot_id,'task-wait:'+item['id'],'waiting',{'title':'Bot 任务等待确认' if item['kind']=='approval' else 'Bot 任务等待回复','body':'打开原 Bot 对话查看并处理，提醒不会替你提交或批准。'},sid,todo_run_id=run_id,interaction_id=item['id'],muted=not policy['waiting'])
        except (PermissionError,ValueError,KeyError,RepositoryError):return

    def reconcile_and_enqueue(self):
        if self.runtime.todo:
            with self.runtime.todo.store.connect() as db:
                rows=db.execute("SELECT owner,id,status,data FROM runs WHERE json_extract(data,'$.execution_binding.registration')=? ORDER BY rowid DESC LIMIT 200",(ADAPTER,)).fetchall()
            for row in rows:self.observe(row['owner'],row['id'],row['status'],json.loads(row['data']))
        producer=self.runtime.remote.notifications
        try:owner=producer.identity()['owner_id']
        except (ValueError,RuntimeError):return
        if not producer.supports_custom('app_route'):return
        from datetime import timedelta
        cutoff=(datetime.now(UTC)-timedelta(hours=24)).isoformat().replace('+00:00','Z')
        with self.db.transaction() as db:rows=db.execute('SELECT * FROM messager_local_notices WHERE actor=? AND muted=0 AND read_at IS NULL AND transport_event IS NULL AND created_at>=? ORDER BY created_at LIMIT 50',(owner,cutoff)).fetchall()
        for row in rows:
            try:
                allowed=self.alert_allowed(owner,row)
            except (PermissionError,ValueError,KeyError,RepositoryError):allowed=False
            if not allowed:
                with self.db.transaction(write=True) as db:db.execute("UPDATE messager_local_notices SET transport_event='suppressed' WHERE id=? AND transport_event IS NULL",(row['id'],))
                continue
            try:
                with self.db.transaction(write=True) as db:
                    current=db.execute('SELECT read_at,transport_event FROM messager_local_notices WHERE id=?',(row['id'],)).fetchone()
                    policy=db.execute('SELECT value_json FROM messager_notification_policies WHERE actor=? AND bot_id=?',(owner,row['bot_id'])).fetchone()
                    enabled=json.loads(policy[0])[row['kind']] if policy else True
                    if current['transport_event']:continue
                    if current['read_at'] or not enabled:
                        db.execute("UPDATE messager_local_notices SET transport_event='suppressed' WHERE id=?",(row['id'],))
                        continue
                    event='messager.notice:'+row['id']
                    producer.enqueue_custom(event_id=event,content={'title':'Bot 有一条新提醒','body':'打开原 Bot 对话查看并处理。','locale':'zh-CN'},target={'type':'app_route','app_id':APP,'route':'bot-notice','id':row['id']},group_key='bot:'+row['bot_id'],metadata={},expected_owner_id=owner,connection=db)
                    db.execute('UPDATE messager_local_notices SET transport_event=? WHERE id=?',(event,row['id']))
            except (PermissionError,ValueError,KeyError,RepositoryError):continue

    def delivery_guard(self,body):
        if not str(body.get('event_id','')).startswith('messager.notice:'):return True
        ref=body['event_id'].removeprefix('messager.notice:')
        if body.get('target')!={'type':'app_route','app_id':APP,'route':'bot-notice','id':ref}:return False
        owner=self.runtime.remote.notifications.identity()['owner_id']
        try:
            with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_local_notices WHERE actor=? AND id=?',(owner,ref)).fetchone()
            return bool(row and self.alert_allowed(owner,row))
        except (PermissionError,ValueError,KeyError,RepositoryError):return False
