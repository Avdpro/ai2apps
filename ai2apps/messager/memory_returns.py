"""Evidence-bound memory proposals on one reviewed delegation edge.

No bulk private-memory synchronization and no implicit parent authority.
"""
import json
import logging
from datetime import UTC,datetime
from uuid import uuid5,NAMESPACE_URL
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from ai2apps.services.capability_routing import CapabilityProvider, CapabilityInvocationError
from ai2apps.core.errors import ResourceNotFoundError
from .memory_records import encoded,signature

RETURN='messager.memory.return'
CHAT='ai2apps.messager.bots'


class Offer(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    subject:str=Field(min_length=1,max_length=120)
    predicate:str=Field(min_length=1,max_length=120)
    text:str=Field(min_length=1,max_length=600)
    value:str=Field(min_length=1,max_length=2000)
    kind:Literal['fact','preference','resource']='fact'
    variant:str=Field(default='',max_length=120)
    evidence_kind:Literal['tool_step','memory_change','return']
    evidence_id:str=Field(min_length=1,max_length=256)
    quote:str=Field(default='',max_length=2000)
    artifact_id:str|None=Field(default=None,max_length=256)


class Offers(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    items:list[Offer]=Field(min_length=1,max_length=3)


class MemoryReturns:
    def __init__(self,runtime,directory):
        self.runtime,self.directory,self.db=runtime,directory,directory.db
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_returns(
                id TEXT PRIMARY KEY,actor TEXT,parent_bot TEXT,child_bot TEXT,delegation_id TEXT,
                child_job TEXT,worker_run TEXT,parent_session TEXT,source_epoch INTEGER,parent_epoch INTEGER,
                value_json TEXT,proof_json TEXT,path_json TEXT,origin_key TEXT,state TEXT,
                candidate_id TEXT,memory_id TEXT,revision INTEGER,created_at TEXT,
                UNIQUE(actor,parent_bot,origin_key))''')
            db.execute('CREATE INDEX IF NOT EXISTS memory_return_source ON messager_memory_returns(actor,child_bot,state)')
        source=runtime.services.get_tool('messager.bot.delegate');instance=runtime.services.get_instance_for_service(source.service_id)
        runtime.services.ensure_tool(service_id=source.service_id,qualified_name=RETURN,display_name='回传子任务记忆候选 / Return task memory candidates',
            description='Offer up to three exact, evidenced findings from this delegated task to its immediate parent. The host delivers proposals only on successful completion. Parent user review is required before memory is saved. No private-memory inventory is shared.',
            input_schema=Offers.model_json_schema(),output_schema={'type':'object'},effects=('workspace.write',),required_capabilities=())
        async def invoke(args,ctx):return self.offer(args,ctx)
        async def prepare(args,ctx):
            # Validate evidence and the active child role before any write.
            # offer() repeats these checks at execution to preserve race safety.
            try:
                items=Offers.model_validate(args).items
                with self.runtime.app_chat.lock:
                    edge,job,run=self.edge(ctx)
                    for item in items:self.proof(item,edge,job,run)
            except (PermissionError,ValueError) as error:
                code='capability_denied' if isinstance(error,PermissionError) else 'invalid_tool_arguments'
                raise CapabilityInvocationError(code,str(error),{'phase':'prepare'}) from error
            return args
        provider=CapabilityProvider('ai2apps.messager.'+RETURN,RETURN,'ai2apps.messager',invoke,prepare=prepare,version='2',access_policy='write',agent_context={
            'schema':'ai2apps.aaat-declaration/v1','instructions':[
                'Use only while executing a reviewed delegated child task, for findings useful to its immediate parent. Proposals do not save parent memory and do not grant App access.',
                'evidence_id may be the exact step ID or a Tool name uniquely matching the quoted completed result in this Run. tool_step evidence must be a completed business Tool step from this exact Run, with an exact quote. Literal fact values must equal that quote; resource IDs must occur in the step output and resolve to this Session. Task findings are not verified user identity.',
                'memory_change evidence must be an effective memory change with a user source actually imported into this exact Task, or explicitly bound to this logical Task. Never export identity/duty or unrelated private memory.',
                'Forwarding a previously accepted return requires its exact return ID, unchanged content, the same delegation root and a non-repeating Bot path. No automatic forwarding or all-to-all sync.',
                'Return only bounded relevant findings. The parent sees source/task/evidence and must explicitly confirm before its independent maintenance Task applies them. Cancelled, failed or uncertain tasks do not deliver proposals.']})
        runtime.app_capability_router.register(provider);self.provider=runtime.app_capability_router.providers[provider.id]
        async def route(args,ctx):return await runtime.app_capability_router.invoke(RETURN,args,ctx)
        runtime.service_registry.bind_tool(RETURN,provider_key=instance.provider_key,handler=route)
        logging.getLogger(__name__).info('Delegated memory returns loaded; source=%s',__file__)

    def row(self,ref,db=None):
        if db is None:
            with self.db.transaction() as c:return self.row(ref,c)
        r=db.execute('SELECT * FROM messager_memory_returns WHERE id=?',(ref,)).fetchone()
        if not r:raise PermissionError('Memory return unavailable')
        return dict(r)

    def edge(self,ctx):
        binding=self.runtime.app_chat.binding(ctx.session_id)
        run=self.runtime.agents.get_run(ctx.trace_id)
        if not ctx.invocation_id or not binding or binding['registration']!=CHAT or binding['owner']!=ctx.actor_user_id or run.session_id!=ctx.session_id or run.cancel_requested or run.status.value not in ('running','planning'):raise PermissionError('An active delegated execution is required')
        auth=self.runtime.app_chat.execution_authorization(run.id)
        self.directory.permissions.validate(ctx.actor_user_id,binding['scope'],auth,None,{})
        if auth.get('controls',{}).get(self.provider.id)!=self.provider.version:raise PermissionError('Memory return control is not admitted')
        with self.db.transaction() as db:
            job=db.execute("SELECT * FROM messager_dialogue_jobs WHERE worker_run=? OR id=(SELECT substr(request_id,9) FROM app_chat_turns WHERE run_id=? AND request_id LIKE 'bot-job:%')",(run.id,run.id)).fetchone()
        if not job:raise PermissionError('Current child task unavailable')
        edge=self.runtime.messager_bot_delegation.child(job['id'])
        if not edge or edge['actor']!=ctx.actor_user_id or edge['target_bot']!=binding['scope']['bot_id'] or edge['status']!='running':raise PermissionError('Only the active immediate child may return memory')
        self.runtime.messager_bot_delegation.validate(edge)
        return edge,dict(job),run

    def proof(self,item,edge,job,run):
        actor,bot=edge['actor'],edge['target_bot'];logical=self.runtime.messager_dialogue.sessions.for_job(job['id'])
        value={k:getattr(item,k) for k in ('subject','predicate','value','text','kind','variant')}
        if item.subject.strip().casefold() in ('bot','self','assistant',bot.casefold()):raise ValueError('Bot identity/duty is private, not an inherited user memory')
        path=[bot];proof={'kind':item.evidence_kind,'id':item.evidence_id,'root':self.runtime.messager_bot_delegation.graph.edge(edge['id'])['root']}
        if item.evidence_kind=='tool_step':
            matches=[s for s in self.runtime.agents.list_steps(run.id) if (s.id==item.evidence_id or s.tool_name==item.evidence_id) and s.kind=='tool' and s.status.value=='completed' and item.quote and item.quote in encoded(s.output)]
            step=matches[0] if len(matches)==1 else None
            if not step or step.kind!='tool' or step.status.value!='completed' or step.tool_name in (RETURN,'agent.ask_user') or step.tool_name.startswith(('messager.','agent.','app.')):raise PermissionError('Use an actual completed task result, not a memory-control receipt')
            raw=encoded(step.output)
            if not item.quote or item.quote not in raw:raise ValueError('Evidence quote must occur in this exact Tool result')
            if item.kind!='resource' and item.value!=item.quote:raise ValueError('Task observations must preserve the exact evidence value')
            proof.update(id=step.id,quote=item.quote,tool=step.tool_name)
            value['text']=item.quote if item.kind!='resource' else item.text
            if item.kind=='resource':
                if not item.artifact_id or item.artifact_id not in raw:raise PermissionError('Resource was not returned by this step')
                ref={'session_id':run.session_id,'artifact_id':item.artifact_id}
                if not self.directory.history.resource(actor,bot,ref)['available']:raise ValueError('Task resource unavailable')
                value['value']=ref
        elif item.evidence_kind=='memory_change':
            note=self.directory.memory.records.detail(actor,bot,item.evidence_id)
            if not note['can_undo'] or note['after']['deleted'] or not note['metadata']:raise ValueError('Select a current, effective structured memory change')
            source=note['source'];sid=source.get('session_id');mid=source.get('message_id')
            if source.get('kind')!='user_selected':raise PermissionError('Private/manual or inherited notes need their original evidence, not a new origin')
            with self.db.transaction() as db:
                imported=db.execute('SELECT 1 FROM messages WHERE session_id=? AND idempotency_key=?',(run.session_id,'bot-job-context:'+str(mid))).fetchone()
                user=db.execute("SELECT 1 FROM messages m JOIN app_chat_sessions s ON s.session_id=m.session_id WHERE m.id=? AND m.session_id=? AND m.role='user' AND s.owner=? AND json_extract(s.scope_json,'$.bot_id')=?",(mid,sid,actor,bot)).fetchone()
            if not user or not (imported or source.get('task_id')==logical['id']):raise PermissionError('This memory is not evidenced in the current task')
            metadata=note['metadata']
            for key in ('subject','predicate','kind','variant'):
                if value[key]!=metadata.get(key,''):raise ValueError('Return the original memory field without relabelling')
            actual=metadata['value']
            if item.kind!='resource' and item.value!=actual:raise ValueError('Return the exact memory value')
            value.update(value=actual,text=note['after']['text'])
            if item.kind=='resource':value['value']={k:actual[k] for k in ('session_id','artifact_id')}
            proof.update(memory_id=note['memory_id'],revision=note['revision'],source=source)
        else:
            prior=self.row(item.evidence_id)
            if prior['actor']!=actor or prior['parent_bot']!=bot or prior['state'] not in ('queued','applied') or not self.valid(prior):raise PermissionError('Only an accepted valid return may be forwarded')
            prior_edge=self.runtime.messager_bot_delegation.row(prior['delegation_id'])
            prior_parent=self.runtime.messager_dialogue.sessions.for_job(prior_edge['parent_job'])
            if prior_parent['id']!=logical['id'] or json.loads(prior['proof_json'])['root']!=proof['root']:raise PermissionError('Return belongs to a different task or root')
            original=json.loads(prior['value_json'])
            if any(value[k]!=original[k] for k in ('subject','predicate','kind','variant')) or (item.kind!='resource' and item.value!=original['value']):raise ValueError('Forward the unchanged original field')
            value=original;path=json.loads(prior['path_json']);proof={'kind':'return','id':prior['id'],'root':proof['root'],'memory_id':prior['memory_id'],'revision':prior['revision']}
        if edge['source_bot'] in path or len(path)>=4:raise ValueError('Memory return path would repeat a Bot or exceed its bound')
        return value,proof,path+[edge['source_bot']]

    def offer(self,args,ctx):
        items=Offers.model_validate(args).items
        with self.runtime.app_chat.lock:
            edge,job,run=self.edge(ctx);prepared=[self.proof(item,edge,job,run) for item in items]
            refs=[]
            with self.db.transaction(write=True) as db:
                epoch=self.directory.memory_tasks.epoch(db,edge['actor'],edge['target_bot'])['epoch']
                parent_session=self.directory.memory.records._main(db,edge['actor'],edge['source_bot'])
                if not parent_session:raise PermissionError('Parent dialogue unavailable')
                count=db.execute('SELECT count(*) FROM messager_memory_returns WHERE delegation_id=?',(edge['id'],)).fetchone()[0]
                for value,proof,path in prepared:
                    if proof['kind']=='return':origin=self.row(proof['id'],db)['origin_key']
                    else:origin=signature([edge['actor'],proof['root'],proof['kind'],proof['id'],self.directory.memory_tasks.slot(value),value['value']])
                    old=db.execute('SELECT id FROM messager_memory_returns WHERE actor=? AND parent_bot=? AND origin_key=?',(edge['actor'],edge['source_bot'],origin)).fetchone()
                    if old:refs.append(old[0]);continue
                    if count>=6:raise ValueError('At most six memory returns per delegated task')
                    count+=1
                    ref=uuid5(NAMESPACE_URL,'memory-return:'+edge['id']+':'+origin).hex
                    db.execute("INSERT INTO messager_memory_returns VALUES(?,?,?,?,?,?,?,?,?,NULL,?,?,?,?, 'offered',NULL,NULL,NULL,?)",(ref,edge['actor'],edge['source_bot'],edge['target_bot'],edge['id'],job['id'],run.id,parent_session,epoch,encoded(value),encoded(proof),encoded(path),origin,datetime.now(UTC).isoformat()))
                    refs.append(ref)
        return {'status':'offered','return_ids':refs,'parent_memory_saved':False,'requires_parent_user_review':True}

    def valid(self,row,*,require_success=True,seen=()):
        if row['id'] in seen or len(seen)>=4 or row['state'] in ('withdrawn','stale'):return False
        try:
            self.directory.scope(row['actor'],{'bot_id':row['child_bot']});self.directory.scope(row['actor'],{'bot_id':row['parent_bot']})
            edge=self.runtime.messager_bot_delegation.row(row['delegation_id'])
            run=self.runtime.agents.get_run(row['worker_run'])
            if edge['status'] not in ('running','resumed') or run.cancel_requested or (require_success and run.status.value!='completed'):return False
            if edge['actor']!=row['actor'] or edge['source_bot']!=row['parent_bot'] or edge['target_bot']!=row['child_bot']:return False
            with self.db.transaction() as db:
                epoch=db.execute('SELECT epoch FROM messager_memory_epochs WHERE actor=? AND bot_id=?',(row['actor'],row['child_bot'])).fetchone()
            if (epoch[0] if epoch else 0)!=row['source_epoch']:return False
            proof=json.loads(row['proof_json']);value=json.loads(row['value_json'])
            if self.runtime.messager_bot_delegation.graph.root(proof['root'])['status']=='stopped':return False
            if proof['kind']=='return':
                if not self.valid(self.row(proof['id']),seen=(*seen,row['id'])):return False
            if proof['kind']=='memory_change' or (proof['kind']=='return' and proof.get('memory_id')):
                with self.db.transaction() as db:m=db.execute('SELECT revision,deleted FROM messager_bot_memories WHERE id=? AND actor=? AND bot_id=?',(proof['memory_id'],row['actor'],row['child_bot'])).fetchone()
                if not m or m['deleted'] or m['revision']!=proof['revision']:return False
            if row['state']=='applied':
                # A same-value merge adds evidence, not a withdrawal of prior evidence.
                with self.db.transaction() as db:
                    current=db.execute('SELECT m.deleted,f.metadata_json FROM messager_bot_memories m LEFT JOIN messager_memory_fields f ON f.memory_id=m.id WHERE m.id=? AND m.actor=? AND m.bot_id=?',(row['memory_id'],row['actor'],row['parent_bot'])).fetchone()
                    evidence=db.execute("SELECT 1 FROM messager_memory_evidence WHERE memory_id=? AND json_extract(source_json,'$.return_id')=?",(row['memory_id'],row['id'])).fetchone()
                if not current or current['deleted'] or not current['metadata_json'] or not evidence:return False
                metadata=json.loads(current['metadata_json'])
                if any(metadata.get(k)!=value.get(k) for k in ('subject','predicate','variant','kind')):return False
                if value['kind']!='resource' and metadata.get('value')!=value['value']:return False
                if value['kind']=='resource':
                    original=self.directory.history.resource(row['actor'],json.loads(row['path_json'])[0],value['value'])
                    if not original.get('content_hash') or metadata['value'].get('content_hash')!=original['content_hash']:return False
            if value['kind']=='resource':
                source_bot=json.loads(row['path_json'])[0]
                if not self.directory.history.resource(row['actor'],source_bot,value['value'])['available']:return False
            return True
        except (PermissionError,ValueError,KeyError,OSError,ResourceNotFoundError):return False

    def publish(self,edge,child):
        # Called only by the trusted successful-result path; no Bot-written packet dispatch.
        with self.db.transaction() as db:rows=[dict(r) for r in db.execute("SELECT * FROM messager_memory_returns WHERE delegation_id=? AND state='offered'",(edge['id'],))]
        for row in rows:
            if not self.valid(row):continue
            with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
                row=self.row(row['id'],db)
                if row['state']!='offered' or not self.valid(row):continue
                epoch=self.directory.memory_tasks.epoch(db,row['actor'],row['parent_bot'])['epoch']
                self.directory.history.session(row['actor'],row['parent_bot'],row['parent_session'])
                ref='return:'+row['id'];value=json.loads(row['value_json'])
                value.update(mode='merge',source={'delegation_memory_id':row['id']})
                count=db.execute("SELECT count(*) FROM messager_memory_candidates WHERE actor=? AND bot_id=? AND state IN ('queued','running','review')",(row['actor'],row['parent_bot'])).fetchone()[0]
                if count>=24:continue
                db.execute("INSERT OR IGNORE INTO messager_memory_candidates VALUES(?,?,?,?,?,?,?,?,?,'review',NULL,NULL,NULL,?)",(ref,row['actor'],row['parent_bot'],row['parent_session'],edge['source_run'],'return:'+row['id'],epoch,encoded(value),signature(value),datetime.now(UTC).isoformat()))
                db.execute("UPDATE messager_memory_returns SET state='review',candidate_id=?,parent_epoch=? WHERE id=? AND state='offered'",(ref,epoch,row['id']))
                self.db.after_commit(db,lambda row=row:self.notice(row,'子 Bot 回传了与本任务相关的记忆候选，尚未保存。请在“待整理记忆”中查看来源并确认或取消。','ready'))

    def for_candidate(self,ref,db):
        r=db.execute('SELECT * FROM messager_memory_returns WHERE candidate_id=?',(ref,)).fetchone()
        return dict(r) if r else None

    def guard(self,db,candidate):
        row=self.for_candidate(candidate['id'],db)
        if not row or row['state']!='queued' or row['parent_epoch']!=self.directory.memory_tasks.epoch(db,row['actor'],row['parent_bot'])['epoch'] or not self.valid(row):raise ValueError('Returned memory source expired or was withdrawn')
        self.directory.history.session(row['actor'],row['parent_bot'],row['parent_session'])
        return row

    def decide(self,db,candidate,decision):
        row=self.for_candidate(candidate['id'],db)
        if not row:return False
        if decision=='confirm':
            if row['state'] in ('queued','applied'):return True
            if row['state']!='review' or not self.valid(row):raise ValueError('Returned memory is no longer available for review')
            if row['parent_epoch']!=self.directory.memory_tasks.epoch(db,row['actor'],row['parent_bot'])['epoch']:raise ValueError('Parent memory was cleared')
            db.execute("UPDATE messager_memory_returns SET state='queued' WHERE id=?",(row['id'],))
            db.execute("UPDATE messager_memory_candidates SET state='queued',batch_id=NULL,error=NULL WHERE id=?",(candidate['id'],))
        else:
            db.execute("UPDATE messager_memory_returns SET state='withdrawn' WHERE id=? AND state IN ('review','queued')",(row['id'],))
            db.execute("UPDATE messager_memory_candidates SET state='cancelled' WHERE id=? AND state IN ('review','queued','running')",(candidate['id'],))
        return True

    def prepare(self,candidate,value):
        row=self.row(value['source']['delegation_memory_id'])
        if not self.valid(row) or row['state']!='queued':raise ValueError('Return is not approved')
        if value['kind']=='resource':
            ref=value['value'];a=self.runtime.workspace.get_artifact(ref['session_id'],ref['artifact_id'])
            if self.runtime.workspace.artifact_path(a).stat().st_size>16*1024*1024:raise ValueError('Memory resource exceeds 16 MiB')
            copy=next((x for x in self.runtime.workspace.list_artifacts(row['parent_session']) if x.metadata.get('memory_return')==row['id'] and x.content_hash==a.content_hash),None)
            a=copy or self.runtime.workspace.import_artifact(row['parent_session'],self.runtime.workspace.artifact_path(a),name=a.name,media_type=a.media_type,metadata={'memory_return':row['id']})
            value={**value,'value':{'session_id':row['parent_session'],'artifact_id':a.id}}
        return value

    def evidence(self,actor,bot,ref):
        row=self.row(ref)
        if row['actor']!=actor or row['parent_bot']!=bot or row['state']!='queued' or not self.valid(row):raise PermissionError('Memory return evidence is not approved for this Bot')
        return {'kind':'delegated_memory','return_id':row['id'],'delegation_id':row['delegation_id'],'origin_bot':json.loads(row['path_json'])[0],'path':json.loads(row['path_json'])}

    def applied(self,db,candidate,result):
        db.execute("UPDATE messager_memory_returns SET state='applied',memory_id=?,revision=? WHERE candidate_id=? AND state='queued'",(result['memory_id'],result['revision'],candidate['id']))

    def notice(self,row,text,event):
        try:self.directory.history.session(row['actor'],row['parent_bot'],row['parent_session'])
        except PermissionError:return
        message=self.runtime.messager_dialogue.append(row['parent_session'],'assistant',text,'memory-return:'+event+':'+row['id'],{'origin':'bot_memory_status','memory_return_id':row['id']})
        if event=='ready':
            with self.db.transaction(write=True) as db:db.execute('UPDATE messager_memory_candidates SET message_id=? WHERE id=?',(message.value.message.id, 'return:'+row['id']))

    def invalidate(self,db,actor,bot,memory_id=None,revision=None):
        rows=db.execute("SELECT * FROM messager_memory_returns WHERE actor=? AND state NOT IN ('withdrawn','stale')",(actor,)).fetchall()
        invalid=set()
        for r in rows:
            proof=json.loads(r['proof_json'])
            if memory_id is None and r['parent_bot']==bot and r['state'] in ('offered','review','queued'):invalid.add(r['id'])
            if r['child_bot']==bot and (memory_id is None or (proof['kind'] in ('memory_change','return') and proof.get('memory_id')==memory_id and proof['revision']!=revision)):invalid.add(r['id'])
        for _ in range(4):
            for r in rows:
                proof=json.loads(r['proof_json'])
                if proof['kind']=='return' and proof['id'] in invalid:invalid.add(r['id'])
        for r in rows:
            if r['id'] not in invalid:continue
            db.execute("UPDATE messager_memory_returns SET state='stale' WHERE id=?",(r['id'],))
            db.execute("UPDATE messager_memory_candidates SET state='cancelled',error='Delegated source withdrawn' WHERE id=? AND state IN ('queued','running','review')",(r['candidate_id'],))
            if r['state']=='applied':self.db.after_commit(db,lambda row=dict(r):self.notice(row,'这条继承记忆的来源已变更或撤回。没有覆盖你后来的修改；仅依赖该来源的内容已停止用于新上下文，请查看记忆版本。','stale'))

    def usable(self,actor,bot,memory_id):
        with self.db.transaction() as db:rows=db.execute('SELECT source_json FROM messager_memory_evidence WHERE actor=? AND bot_id=? AND memory_id=?',(actor,bot,memory_id)).fetchall()
        sources=[json.loads(r[0]) for r in rows]
        for source in sources:
            if source.get('kind')!='delegated_memory':return True
            try:
                if self.valid(self.row(source['return_id'])):return True
            except PermissionError:pass
        return not sources

    def describe(self,actor,bot,ref):
        row=self.row(ref)
        if row['actor']!=actor or row['parent_bot']!=bot:raise PermissionError('Memory return unavailable')
        edge=self.runtime.messager_bot_delegation.row(row['delegation_id'])
        return {'title':json.loads(edge['value_json'])['title'],'return_id':ref,'source_bot':self.bot_name(actor,row['child_bot']),'delegation_id':row['delegation_id'],'path':json.loads(row['path_json']),'state':row['state'],'source_valid':self.valid(row),'proof':json.loads(row['proof_json'])}

    def bot_name(self,actor,bot):
        with self.db.transaction() as db:row=db.execute('SELECT name FROM messager_bots WHERE actor=? AND id=?',(actor,bot)).fetchone()
        return row[0] if row else 'Unavailable Bot'

    def recover(self):
        # Retry durable projections, never re-execute child work or effectful tools.
        with self.db.transaction() as db:rows=[dict(r) for r in db.execute("SELECT * FROM messager_memory_returns WHERE state IN ('offered','review') ORDER BY rowid LIMIT 100")]
        for row in rows:
            try:
                run=self.runtime.agents.get_run(row['worker_run'])
                if run.status.value not in ('completed','failed','cancelled','interrupted','timed_out'):continue
                if not self.valid(row):
                    with self.db.transaction(write=True) as db:
                        db.execute("UPDATE messager_memory_returns SET state='stale' WHERE id=? AND state IN ('offered','review')",(row['id'],))
                        db.execute("UPDATE messager_memory_candidates SET state='cancelled',error='Delegated source unavailable' WHERE id=? AND state='review'",(row['candidate_id'],))
                elif row['state']=='offered':
                    edge=self.runtime.messager_bot_delegation.row(row['delegation_id'])
                    if edge['status']=='resumed':self.publish(edge,None)
                else:self.notice(row,'子 Bot 回传了与本任务相关的记忆候选，尚未保存。请在“待整理记忆”中查看来源并确认或取消。','ready')
            except (PermissionError,ValueError,ResourceNotFoundError):continue
