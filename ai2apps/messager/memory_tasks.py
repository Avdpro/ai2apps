"""Bot-owned bounded memory maintenance; no business Tools or model calls."""
import json
import asyncio
import logging
from datetime import UTC,datetime
from uuid import uuid4,uuid5,NAMESPACE_URL
from ai2apps.agents.models import CompleteAction,FailAction
from ai2apps.todo.execution import TodoExecutionAdapter
from ai2apps.todo.models import Schedule
from .memory_records import encoded,signature

KEY='ai2apps.messager.memory-maintenance'


class MemoryTasks:
    def __init__(self,runtime,directory):
        self.runtime,self.directory,self.db=runtime,directory,runtime.database
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_epochs(actor TEXT,bot_id TEXT,epoch INTEGER NOT NULL DEFAULT 0,floor INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(actor,bot_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_candidates(id TEXT PRIMARY KEY,actor TEXT,bot_id TEXT,session_id TEXT,source_run TEXT,message_id TEXT,epoch INTEGER,value_json TEXT,signature TEXT,state TEXT,batch_id TEXT,change_id TEXT,error TEXT,created_at TEXT,UNIQUE(source_run,signature))''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_batches(id TEXT PRIMARY KEY,actor TEXT,bot_id TEXT,session_id TEXT,epoch INTEGER,state TEXT,task_id TEXT,run_id TEXT,created_at TEXT)''')
            db.execute('CREATE TABLE IF NOT EXISTS messager_memory_blocks(actor TEXT,bot_id TEXT,source_key TEXT,PRIMARY KEY(actor,bot_id,source_key))')
            db.execute('CREATE INDEX IF NOT EXISTS memory_candidate_owner_state ON messager_memory_candidates(actor,bot_id,state)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_memory_usage(job_id TEXT PRIMARY KEY,value_json TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_memory_costs(run_id TEXT PRIMARY KEY,actor TEXT,bot_id TEXT,context_characters INTEGER,dialogue_total_tokens INTEGER,recall_rounds INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_memory_recalls(run_id TEXT PRIMARY KEY,value_json TEXT NOT NULL)')
        runtime.agents.ensure_definition(agent_key=KEY,package_version='1',display_name='整理 Bot 记忆',executor_key=KEY,max_steps=2,timeout_seconds=30,manifest={'discoverable':False,'allowed_tools':[]})
        runtime.agent_runtime.bind_executor(KEY,self)
        self.adapter=TodoExecutionAdapter(KEY,self.validate,self.start,finished=self.finished,recover=self.recover,restore=self.restore,queue_class='maintenance')
        runtime.todo_execution_adapters[KEY]=self.adapter
        if runtime.todo:runtime.todo.register_execution_adapter(self.adapter)
        logging.getLogger(__name__).info('Bot queued memory maintenance loaded; source=%s',__file__)

    def epoch(self,db,actor,bot):
        db.execute('INSERT OR IGNORE INTO messager_memory_epochs(actor,bot_id) VALUES(?,?)',(actor,bot))
        return dict(db.execute('SELECT * FROM messager_memory_epochs WHERE actor=? AND bot_id=?',(actor,bot)).fetchone())

    def invalidate(self,db,actor,bot):
        self.epoch(db,actor,bot)
        floor=db.execute("SELECT COALESCE(MAX(m.rowid),0) FROM messages m JOIN app_chat_sessions s ON s.session_id=m.session_id WHERE s.owner=? AND json_extract(s.scope_json,'$.bot_id')=?",(actor,bot)).fetchone()[0]
        db.execute('UPDATE messager_memory_epochs SET epoch=epoch+1,floor=? WHERE actor=? AND bot_id=?',(floor,actor,bot))
        db.execute("UPDATE messager_memory_candidates SET state='cancelled',error='Memory cleared' WHERE actor=? AND bot_id=? AND state IN ('queued','running','review')",(actor,bot))
        returns=getattr(self.directory,'memory_returns',None)
        if returns:returns.invalidate(db,actor,bot)

    @staticmethod
    def slot(value):return signature([value.get('subject','').strip(),value.get('predicate','').strip(),value.get('variant','')])

    def block(self,db,actor,bot,source,slot=None):
        db.execute('INSERT OR IGNORE INTO messager_memory_blocks VALUES(?,?,?)',(actor,bot,signature([source,slot]) if slot else signature(source)))

    def field_allowed(self,db,actor,bot,value):
        source={'kind':'user_selected',**value['source']}
        if db.execute('SELECT 1 FROM messager_memory_blocks WHERE actor=? AND bot_id=? AND source_key=?',(actor,bot,signature([source,self.slot(value)]))).fetchone():raise ValueError('This source contribution was cancelled or undone')

    def source(self,db,actor,bot,sid,message,epoch,run_id=None):
        self.directory.history.session(actor,bot,sid)
        stamp=self.epoch(db,actor,bot)
        if run_id:
            parent=db.execute('SELECT r.status,r.cancel_requested FROM agent_runs r JOIN messager_dialogue_turns t ON t.run_id=r.id WHERE r.id=? AND t.actor=? AND t.bot_id=? AND t.session_id=?',(run_id,actor,bot,sid)).fetchone()
            if not parent or parent['cancel_requested'] or parent['status'] in ('cancelled','failed','interrupted','timed_out'):raise ValueError('The original user turn is no longer valid')
        row=db.execute("SELECT m.rowid,m.sequence FROM messages m WHERE m.session_id=? AND m.id=? AND m.role='user'",(sid,message)).fetchone()
        source={'kind':'user_selected','session_id':sid,'message_id':message}
        if not row or epoch!=stamp['epoch'] or row['rowid']<=stamp['floor'] or db.execute('SELECT 1 FROM messager_memory_blocks WHERE actor=? AND bot_id=? AND source_key=?',(actor,bot,signature(source))).fetchone():raise ValueError('Memory source was cleared or revoked')
        return row

    def enqueue(self,run,b,values):
        if not values:return []
        if not isinstance(values,list) or len(values)>3:raise ValueError('At most three memory candidates per conversation')
        actor,bot,sid=b['owner'],b['scope']['bot_id'],run.session_id
        with self.db.transaction(write=True) as db:
            message=db.execute("SELECT id FROM messages WHERE session_id=? AND idempotency_key=?",(sid,'agent-run:'+run.id+':user')).fetchone()
            if not message:raise ValueError('Memory needs its persisted user message')
            epoch=run.input.get('owner_context',{}).get('memory_epoch',-1);self.source(db,actor,bot,sid,message[0],epoch,run.id)
            pending=db.execute("SELECT count(*) FROM messager_memory_candidates WHERE actor=? AND bot_id=? AND state IN ('queued','running','review')",(actor,bot)).fetchone()[0]
            refs=[]
            for v in values:
                if not isinstance(v,dict) or set(v)-{'subject','predicate','value','text','kind','variant','mode','revision','intent','question_id','attachment_id','artifact_id'}:raise ValueError('Invalid memory candidate')
                if v.get('intent') not in ('explicit','answer','candidate'):raise ValueError('Memory intent is required')
                value={k:v[k] for k in ('subject','predicate','value','text') if k in v}
                if len(value)!=4 or not all(isinstance(value[k],str) and 1<=len(value[k])<=120 for k in ('subject','predicate')) or not isinstance(value['text'],str) or not 1<=len(value['text'])<=2000 or len(encoded(value['value']))>4000:raise ValueError('Invalid bounded memory content')
                value.update(kind=v.get('kind','fact'),variant=v.get('variant',''),mode=v.get('mode','merge'))
                if value['kind'] not in ('fact','preference','resource') or value['mode'] not in ('merge','replace') or not isinstance(value['variant'],str) or len(value['variant'])>120:raise ValueError('Invalid memory kind or mode')
                if value['kind']=='resource':
                    aid=v.get('attachment_id');files=run.input.get('selected_materials',{}).get('files',[])
                    if aid:
                        if aid not in {f['id'] for f in files}:raise PermissionError('Only this message selected attachment can become a resource memory')
                        value['value']={'session_id':sid,'attachment_id':aid}
                    else:
                        observed=run.input['owner_context'].get('memory_resources',[])+(run.input['owner_context'].get('memory_recall') or {}).get('resources',[])
                        matches=list({(r['session_id'],r['artifact_id']):r for r in observed if r['artifact_id']==v.get('artifact_id')}.values())
                        if v['intent']!='explicit' or len(matches)!=1:raise PermissionError('Remember an exact observed output only on explicit user request')
                        value['value']={k:matches[0][k] for k in ('session_id','artifact_id')}
                        if not self.directory.history.resource(actor,bot,value['value'])['available']:raise ValueError('Selected output unavailable')
                elif not isinstance(value['value'],str):raise ValueError('Fact memory requires literal text')
                if v['intent']=='answer':
                    q=db.execute("SELECT sequence FROM messages WHERE session_id=? AND id=? AND role='assistant'",(sid,v.get('question_id'))).fetchone()
                    current=db.execute('SELECT sequence FROM messages WHERE id=?',(message[0],)).fetchone()[0]
                    if not q or q[0]>=current or db.execute("SELECT 1 FROM messages WHERE session_id=? AND role='user' AND sequence>? AND sequence<?",(sid,q[0],current)).fetchone():raise ValueError('Question/answer binding is ambiguous')
                value['source']={'session_id':sid,'message_id':message[0]}
                value['_restore']=v['intent'] in ('explicit','answer')
                if value['mode']=='replace':
                    if v['intent']!='explicit' or type(v.get('revision')) is not int:raise ValueError('Replacement requires explicit intent and observed revision')
                    value['expected_revision']=v['revision']
                self.field_allowed(db,actor,bot,value)
                sig=signature(value);ref=uuid5(NAMESPACE_URL,'memory-candidate:'+run.id+':'+sig).hex
                old=db.execute('SELECT id FROM messager_memory_candidates WHERE source_run=? AND signature=?',(run.id,sig)).fetchone()
                if old:refs.append(old[0]);continue
                if pending>=24:raise ValueError('Review the pending memory queue first')
                state='review' if v['intent']=='candidate' else 'queued'
                db.execute('INSERT INTO messager_memory_candidates VALUES(?,?,?,?,?,?,?,?,?,?,NULL,NULL,NULL,?)',(ref,actor,bot,sid,run.id,message[0],epoch,encoded(value),sig,state,datetime.now(UTC).isoformat()))
                refs.append(ref);pending+=1
        self.recover()
        return refs

    def recover(self):
        if not self.runtime.todo:return
        returns=getattr(self.directory,'memory_returns',None)
        if returns:returns.recover()
        # Seal a bounded batch. Its candidate set cannot change once created.
        with self.db.transaction(write=True) as db:
            rows=db.execute("SELECT * FROM messager_memory_candidates WHERE state='queued' AND batch_id IS NULL ORDER BY rowid LIMIT 48").fetchall()
            groups={}
            for r in rows:groups.setdefault((r['actor'],r['bot_id'],r['session_id'],r['epoch']),[]).append(r['id'])
            for (actor,bot,sid,epoch),ids in groups.items():
                for offset in range(0,len(ids),8):
                    ref=uuid4().hex
                    db.execute("INSERT INTO messager_memory_batches VALUES(?,?,?,?,?,'queued',NULL,NULL,?)",(ref,actor,bot,sid,epoch,datetime.now(UTC).isoformat()))
                    for cid in ids[offset:offset+8]:db.execute('UPDATE messager_memory_candidates SET batch_id=? WHERE id=?',(ref,cid))
            batches=[dict(r) for r in db.execute("SELECT * FROM messager_memory_batches WHERE state='queued' AND run_id IS NULL LIMIT 20")]
        from .tasks import digest,execution_fields
        from ai2apps.system_tasks.sessions import execution_principal
        for batch in batches:
            try:
                value={'title':'整理 Bot 记忆','description':'合并已验证的记忆候选；不调用业务工具。','model':'owner-memory-no-model','executor':'managed','directory_id':'','schedule':Schedule().model_dump()}
                binding={'batch_id':batch['id'],'bot_id':batch['bot_id'],'execution_hash':digest(execution_fields(value))}
                task=self.runtime.todo.store.save(batch['actor'],value,creation_key='bot-memory:'+batch['id'],create_inbox=True,execution_binding={'registration':KEY,'binding':binding},execution_lane='messager-bot:'+batch['bot_id'])
                with self.db.transaction(write=True) as db:db.execute('UPDATE messager_memory_batches SET task_id=? WHERE id=?',(task['id'],batch['id']))
                self.runtime.todo.launch(batch['actor'],task['id'],principal=execution_principal(self.runtime,batch['actor']),request_key='bot-memory-start:'+batch['id'])
            except (ValueError,PermissionError) as e:
                with self.db.transaction(write=True) as db:
                    db.execute("UPDATE messager_memory_batches SET state='failed' WHERE id=?",(batch['id'],))
                    db.execute("UPDATE messager_memory_candidates SET state='failed',error=? WHERE batch_id=? AND state='queued'",(str(e)[:300],batch['id']))

    def batch(self,ref):
        with self.db.transaction() as db:r=db.execute('SELECT * FROM messager_memory_batches WHERE id=?',(ref,)).fetchone()
        if not r:raise PermissionError('Memory batch unavailable')
        return dict(r)

    def validate(self,actor,task,binding):
        from .tasks import digest,execution_fields
        batch=self.batch(binding['batch_id']);self.directory.scope(actor,{'bot_id':binding['bot_id']})
        if batch['actor']!=actor or batch['bot_id']!=binding['bot_id'] or digest(execution_fields(task))!=binding['execution_hash']:raise PermissionError('Memory maintenance binding changed')
        with self.db.transaction(write=True) as db:
            if self.epoch(db,actor,batch['bot_id'])['epoch']!=batch['epoch']:raise ValueError('Memory batch expired')
        self.directory.history.session(actor,batch['bot_id'],batch['session_id'])

    async def start(self,actor,todo_run,task,prompt,attachments,binding):
        self.validate(actor,task,binding);b=self.batch(binding['batch_id'])
        if attachments:raise PermissionError('Memory maintenance cannot take arbitrary Todo files')
        with self.db.transaction(write=True) as db:
            run,_=self.runtime.agents.create_run(session_id=b['session_id'],agent_key=KEY,input={'batch_id':b['id'],'actor':actor,'bot_id':b['bot_id']},idempotency_key='memory-batch:'+b['id'],connection=db)
            db.execute("UPDATE messager_memory_batches SET run_id=?,state='running' WHERE id=?",(run.id,b['id']))
            db.execute("UPDATE messager_memory_candidates SET state='running' WHERE batch_id=? AND state='queued'",(b['id'],))
        self.runtime.agent_runtime.wake();return run.id

    def restore(self,actor,todo_run,data):
        b=self.batch(data['execution_binding']['binding']['batch_id'])
        if b['actor']!=actor:raise PermissionError('Memory owner changed')
        return {'agent_run_id':b['run_id'],'session_id':b['session_id']} if b['run_id'] else {'requeue_unstarted':True}

    def finished(self,actor,todo_run,status,data):
        ref=data['execution_binding']['binding']['batch_id']
        with self.db.transaction(write=True) as db:
            db.execute('UPDATE messager_memory_batches SET state=? WHERE id=?',(status,ref))
            if status!='completed':db.execute("UPDATE messager_memory_candidates SET state='failed',error=? WHERE batch_id=? AND state IN ('queued','running')",(status,ref))
        self.recover()

    async def __call__(self,ctx):
        return await asyncio.to_thread(self.process,ctx)

    def commit_guard(self,db,row,rid):
        run=db.execute('SELECT cancel_requested,status FROM agent_runs WHERE id=?',(rid,)).fetchone()
        state=db.execute('SELECT state FROM messager_memory_candidates WHERE id=?',(row['id'],)).fetchone()
        if not run or run['cancel_requested'] or run['status'] in ('cancelled','failed','interrupted','timed_out') or not state or state[0] not in ('queued','running'):raise ValueError('Memory processing was cancelled')
        returns=getattr(self.directory,'memory_returns',None)
        if returns and returns.for_candidate(row['id'],db):
            returns.guard(db,row);return
        self.source(db,row['actor'],row['bot_id'],row['session_id'],row['message_id'],row['epoch'],row['source_run'])
        self.field_allowed(db,row['actor'],row['bot_id'],json.loads(row['value_json']))

    def process(self,ctx):
        b=self.batch(ctx.run.input['batch_id']);actor,bot=b['actor'],b['bot_id']
        if b['run_id']!=ctx.run.id or b['session_id']!=ctx.run.session_id or ctx.run.input.get('actor')!=actor or ctx.run.input.get('bot_id')!=bot:
            return FailAction('memory_binding_changed','Only the bound maintenance Task may process this batch')
        if ctx.run.cancel_requested:return FailAction('memory_cancelled','Memory maintenance cancelled')
        with self.db.transaction() as db:rows=[dict(r) for r in db.execute("SELECT * FROM messager_memory_candidates WHERE batch_id=? AND state IN ('queued','running') ORDER BY rowid LIMIT 8",(b['id'],))]
        for row in rows:
            if self.runtime.agents.get_run(ctx.run.id).cancel_requested:return FailAction('memory_cancelled','Memory maintenance cancelled')
            try:
                with self.db.transaction(write=True) as db:self.commit_guard(db,row,ctx.run.id)
                value=json.loads(row['value_json'])
                returns=getattr(self.directory,'memory_returns',None)
                if 'delegation_memory_id' in value.get('source',{}):value=returns.prepare(row,value)
                if value.get('kind')=='resource' and self.directory.history.resource(actor,bot,value['value']).get('size_bytes',0)>16*1024*1024:raise ValueError('Memory resource exceeds 16 MiB')
                self.directory.memory.records.apply(actor,bot,request_id='candidate:'+row['id'],_guard=lambda db:self.commit_guard(db,row,ctx.run.id),_committed=lambda db,result:self.committed(db,row,result),**value)
            except (ValueError,PermissionError) as e:
                with self.db.transaction(write=True) as db:updated=db.execute("UPDATE messager_memory_candidates SET state='review',error=? WHERE id=? AND state IN ('queued','running')",(str(e)[:300],row['id'])).rowcount
                if updated:self.feedback(row,"这条记忆尚未保存，需要在记忆面板核对来源或版本："+json.loads(row['value_json'])['text'])
        return CompleteAction({'content':'Memory maintenance finished','batch_id':b['id'],'model_calls':0})

    def committed(self,db,row,result):
        db.execute("UPDATE messager_memory_candidates SET state='applied',change_id=? WHERE id=?",(result['change_id'],row['id']))
        returns=getattr(self.directory,'memory_returns',None)
        if returns:returns.applied(db,row,result)

    def feedback(self,row,text):
        try:self.directory.history.session(row['actor'],row['bot_id'],row['session_id'])
        except PermissionError:return
        self.runtime.messager_dialogue.append(row['session_id'],'assistant',text,'memory-candidate-feedback:'+row['id'],{'origin':'bot_memory_status','memory_candidate_id':row['id']})

    def index(self,actor,bot,limit=16):
        self.directory.scope(actor,{'bot_id':bot})
        with self.db.transaction() as db:
            rows=db.execute('''SELECT m.id,m.text,m.revision,f.metadata_json FROM messager_bot_memories m LEFT JOIN messager_memory_fields f ON f.memory_id=m.id WHERE m.actor=? AND m.bot_id=? AND m.deleted=0 ORDER BY m.updated_at DESC LIMIT ?''',(actor,bot,limit)).fetchall()
        rows=[r for r in rows if not getattr(self.directory,'memory_returns',None) or self.directory.memory_returns.usable(actor,bot,r['id'])]
        return [{**{k:r[k] for k in ('id','revision')},'text':r['text'][:80],**{k:v for k,v in json.loads(r['metadata_json'] or '{}').items() if k in ('subject','predicate','variant','kind')}} for r in rows]

    def recall(self,run,b,query):
        if not isinstance(query,str) or not 1<=len(query)<=160:raise ValueError('Recall query must be bounded')
        with self.db.transaction() as db:old=db.execute('SELECT value_json FROM messager_memory_recalls WHERE run_id=?',(run.id,)).fetchone()
        if old:return json.loads(old[0])
        tokens=query.lower().split()[:6]
        notes=[m for m in self.index(b['owner'],b['scope']['bot_id'],50) if any(t in encoded(m).lower() for t in tokens)][:8]
        found=self.directory.history.search(b['owner'],b['scope']['bot_id'],query,limit=5)
        resources=[]
        for task in found['items']:
            detail=self.directory.history.detail(b['owner'],b['scope']['bot_id'],task['id'])
            for step in detail['steps'][-2:]:
                for output in step['outputs'][:2]:
                    if output['available']:resources.append({**{k:output[k] for k in ('session_id','artifact_id','name','media_type')},'task_id':task['id'],'step':step['label'],'summary':step['summary'][:300]})
        value={'memories':notes,'history':found,'resources':resources[:8],'model_calls':0}
        with self.db.transaction(write=True) as db:db.execute('INSERT OR IGNORE INTO messager_memory_recalls VALUES(?,?)',(run.id,encoded(value)))
        return value

    def selected(self,run,b,ids):
        if not isinstance(ids,list) or len(ids)>4 or not all(isinstance(i,str) for i in ids):raise ValueError('Select at most four observed memories')
        observed={m['id']:m for m in run.input['owner_context'].get('memory_index',[])}
        for item in (run.input['owner_context'].get('memory_recall') or {}).get('memories',[]):observed[item['id']]=item
        if any(i not in observed for i in ids):raise ValueError('Memory was not observed in this conversation')
        # Keep the exact version selected by this foreground decision; no live default drift.
        return [{'id':i,'revision':observed[i]['revision']} for i in dict.fromkeys(ids)]

    def hydrate(self,job,source,sid):
        with self.db.transaction() as db:old=db.execute('SELECT value_json FROM messager_memory_usage WHERE job_id=?',(job['id'],)).fetchone()
        if old:
            values=json.loads(old[0]);self.check_usage(job['actor'],job['bot_id'],values);return values
        selection=source.input.get('memory_selection',[]);values=[]
        for choice in selection:
            with self.db.transaction() as db:r=db.execute('''SELECT m.*,f.metadata_json FROM messager_bot_memories m LEFT JOIN messager_memory_fields f ON f.memory_id=m.id WHERE m.actor=? AND m.bot_id=? AND m.id=? AND m.deleted=0''',(job['actor'],job['bot_id'],choice['id'])).fetchone()
            if not r or (getattr(self.directory,'memory_returns',None) and not self.directory.memory_returns.usable(job['actor'],job['bot_id'],r['id'])) or r['revision']!=choice['revision']:raise ValueError('Selected memory changed before task admission; ask the user to reselect it')
            value={'id':r['id'],'revision':r['revision'],'text':r['text']}
            metadata=json.loads(r['metadata_json'] or '{}')
            if metadata.get('kind')=='resource':
                ref={k:metadata['value'][k] for k in ('session_id','artifact_id')}
                if not self.directory.history.resource(job['actor'],job['bot_id'],ref,retained=True)['available']:raise ValueError('Remembered resource is no longer available')
                a=self.runtime.workspace.get_artifact(ref['session_id'],ref['artifact_id'])
                copy=next((x for x in self.runtime.workspace.list_artifacts(sid) if x.metadata.get('memory_source_artifact')==a.id and x.content_hash==a.content_hash),None)
                a=copy or self.runtime.workspace.import_artifact(sid,self.runtime.workspace.artifact_path(a),name=a.name,media_type=a.media_type,metadata={'memory_source_artifact':a.id,'memory_id':r['id']})
                value['resource']={'session_id':sid,'artifact_id':a.id,'filename':a.name,'media_type':a.media_type}
            values.append(value)
        with self.db.transaction(write=True) as db:db.execute('INSERT OR IGNORE INTO messager_memory_usage VALUES(?,?)',(job['id'],encoded(values)))
        return values

    def check_usage(self,actor,bot,values):
        for value in values:
            with self.db.transaction() as db:r=db.execute('SELECT deleted FROM messager_bot_memories WHERE actor=? AND bot_id=? AND id=?',(actor,bot,value['id'])).fetchone()
            if not r or r[0] or (getattr(self.directory,'memory_returns',None) and not self.directory.memory_returns.usable(actor,bot,value['id'])):raise PermissionError('A selected memory was forgotten or its source withdrawn')
            if 'resource' in value:
                ref={k:value['resource'][k] for k in ('session_id','artifact_id')}
                if not self.directory.history.resource(actor,bot,ref)['available']:raise PermissionError('A selected memory resource is unavailable')

    def record_cost(self,run,b,steps):
        context=run.input.get('owner_context',{})
        size=len(encoded({k:context[k] for k in ('memory_index','memory_questions','memory_resources','memory_recall') if k in context}))
        usage=[((s.output or {}).get('usage') or {}).get('total_tokens') if isinstance((s.output or {}).get('usage'),dict) else None for s in steps]
        total=sum(v for v in usage if type(v) is int) if any(type(v) is int for v in usage) else None
        with self.db.transaction(write=True) as db:db.execute('INSERT OR REPLACE INTO messager_memory_costs VALUES(?,?,?,?,?,?)',(run.id,b['owner'],b['scope']['bot_id'],size,total,max(0,len(steps)-1)))

    def recall_count(self,actor,bot):
        with self.db.transaction() as db:return db.execute("SELECT count(*) FROM messager_memory_recalls c JOIN messager_dialogue_turns t ON t.run_id=c.run_id WHERE t.actor=? AND t.bot_id=?",(actor,bot)).fetchone()[0]

    def pending(self,actor,bot,*,feed=False):
        self.directory.scope(actor,{'bot_id':bot})
        with self.db.transaction() as db:
            rows=db.execute("SELECT id,state,value_json,error,created_at,message_id FROM messager_memory_candidates WHERE actor=? AND bot_id=? AND state IN ('queued','running','review') ORDER BY rowid LIMIT 24",(actor,bot)).fetchall()
            if feed:return {'items':[{'id':r['id'],'message_id':r['message_id'],'state':r['state'],'value':{'text':json.loads(r['value_json'])['text'][:300]}} for r in rows]}
            stats=db.execute('SELECT state,count(*) n FROM messager_memory_candidates WHERE actor=? AND bot_id=? GROUP BY state',(actor,bot)).fetchall()
            cost=db.execute('SELECT COALESCE(SUM(context_characters),0),SUM(dialogue_total_tokens) FROM messager_memory_costs WHERE actor=? AND bot_id=?',(actor,bot)).fetchone()
        return {'items':[{**{k:r[k] for k in ('id','state','error','created_at','message_id')},'value':json.loads(r['value_json']),**({'provenance':self.directory.memory_returns.describe(actor,bot,json.loads(r['value_json'])['source']['delegation_memory_id'])} if 'delegation_memory_id' in json.loads(r['value_json']).get('source',{}) else {})} for r in rows],'counts':{r['state']:r['n'] for r in stats},'maintenance_model_calls':0,'recall_rounds':self.recall_count(actor,bot),'memory_context_characters':cost[0],'dialogue_total_tokens':cost[1],'incremental_tokens':None}

    def decide(self,actor,bot,ref,decision):
        if decision not in ('confirm','cancel'):raise ValueError('Unknown memory decision')
        with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            self.directory.scope(actor,{'bot_id':bot})
            r=db.execute('SELECT * FROM messager_memory_candidates WHERE actor=? AND bot_id=? AND id=?',(actor,bot,ref)).fetchone()
            if not r:raise PermissionError('Memory candidate unavailable')
            returns=getattr(self.directory,'memory_returns',None)
            if returns and returns.decide(db,dict(r),decision):pass
            elif decision=='cancel':
                self.block(db,actor,bot,{'kind':'user_selected','session_id':r['session_id'],'message_id':r['message_id']},self.slot(json.loads(r['value_json'])))
                db.execute("UPDATE messager_memory_candidates SET state='cancelled' WHERE id=? AND state IN ('queued','running','review')",(ref,))
            elif r['state']=='review':
                self.source(db,actor,bot,r['session_id'],r['message_id'],r['epoch'],r['source_run'])
                db.execute("UPDATE messager_memory_candidates SET state='queued',batch_id=NULL,error=NULL WHERE id=?",(ref,))
        self.recover();return {'status':'updated'}
