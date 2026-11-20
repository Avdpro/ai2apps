"""Messager fixed workflow owner over existing Todo lanes and AgentRuntime."""
import asyncio
import json
import logging
from uuid import uuid5,NAMESPACE_URL
from ai2apps.agents.models import CompleteAction,FailAction
from ai2apps.todo.execution import TodoExecutionAdapter
from ai2apps.todo.models import Schedule
from ai2apps.system_tasks.service import TaskHandler
from ai2apps.system_tasks.sessions import execution_principal
from .flash_workflows import REGISTRY
from .tasks import digest,execution_fields

KEY='ai2apps.messager.flash'
TERMINAL=('completed','failed','cancelled','interrupted','timed_out')


class FlashBots:
    def __init__(self,runtime,directory,registry=REGISTRY):
        self.runtime,self.directory,self.db,self.registry=runtime,directory,runtime.database,registry
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_flash_submissions(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,session_id TEXT NOT NULL,
                request_id TEXT NOT NULL,signature TEXT NOT NULL,payload_json TEXT NOT NULL,
                task_id TEXT,todo_run TEXT,agent_run TEXT,status TEXT NOT NULL,
                UNIQUE(session_id,request_id))''')
            db.execute('CREATE TABLE IF NOT EXISTS messager_flash_drafts(actor TEXT NOT NULL,id TEXT NOT NULL,value_json TEXT NOT NULL,PRIMARY KEY(actor,id))')
        runtime.agents.ensure_definition(agent_key=KEY,package_version='1',display_name='Flash-Bot workflow',
            executor_key=KEY,max_steps=24,timeout_seconds=600,manifest={'discoverable':False,'allowed_tools':[]})
        runtime.agent_runtime.bind_executor(KEY,self)
        adapter=TodoExecutionAdapter(KEY,self.validate,self.start,finished=self.finished,recover=self.recover,restore=self.restore)
        runtime.todo_execution_adapters[KEY]=adapter
        if runtime.todo:runtime.todo.register_execution_adapter(adapter)
        runtime.system_tasks.register(KEY,TaskHandler('ai2apps.messager',self.observe,self.cancel_observer,self.authorize_observer,resumable=True))
        logging.getLogger(__name__).info('Flash-Bot reviewed workflows v2 loaded; source=%s',__file__)

    def row(self,ref):
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_flash_submissions WHERE id=?',(ref,)).fetchone()
        if row is None:raise PermissionError('Flash request unavailable')
        value=dict(row);value['payload']=json.loads(value.pop('payload_json'));return value

    def link_receipt(self,row):
        """Repair an admitted launch receipt without launching or replaying work."""
        if row['todo_run'] or not row['task_id'] or not self.runtime.todo:return row
        receipt=self.runtime.todo.store.launch_receipt(row['actor'],'flash:'+row['id'])
        if receipt:
            if receipt['task_id']!=row['task_id']:raise PermissionError('Flash launch receipt mismatch')
            with self.db.transaction(write=True) as db:
                db.execute('UPDATE messager_flash_submissions SET todo_run=? WHERE id=? AND todo_run IS NULL',(receipt['run_id'],row['id']))
            return self.row(row['id'])
        return row

    def guard(self,row):
        self.directory.scope(row['actor'],{'bot_id':row['bot_id']})
        current=self.directory.definition(row['actor'],row['bot_id'])
        frozen=row['payload']['definition']
        if any(current[k]!=frozen[k] for k in ('execution_mode','audience','location')):raise PermissionError('Flash execution identity changed')
        b=self.runtime.app_chat.binding(row['session_id'])
        if not b or b['owner']!=row['actor'] or b['registration']!='ai2apps.messager.bots' or b['scope']!={'bot_id':row['bot_id']}:
            raise PermissionError('Original Flash conversation is no longer active')
        self.directory.permissions.validate(row['actor'],{'bot_id':row['bot_id']},row['payload']['authorization'],None,{})
        if row['status']=='cancelled':raise PermissionError('Flash request cancelled')
        return self.workflow(frozen['config'])

    def workflow(self,config):
        if config.get('plan') is not None:
            from .flash_plans import workflow
            return workflow(config)
        return self.registry.get(config)

    def submit(self,principal,bot,sid,request_id,text,attachments,task_session_id,language):
        with self.runtime.app_chat.lock:
            b=self.runtime.app_chat.access(principal,sid)
            if b['registration']!='ai2apps.messager.bots' or b['scope']!={'bot_id':bot}:raise PermissionError('Open the main Flash conversation')
            definition=self.directory.definition(b['owner'],bot)
            if definition['execution_mode']!='flash':raise PermissionError('Flash-Bot required')
            if task_session_id:raise ValueError('Flash 每次输入独立执行，不接受 Agent 任务续接 / Flash inputs run independently')
            workflow=self.workflow(definition['config'])
            signature=digest({'text':text,'attachments':attachments,'definition':definition})
            with self.db.transaction() as db:old=db.execute('SELECT id,signature FROM messager_flash_submissions WHERE session_id=? AND request_id=?',(sid,request_id)).fetchone()
            if old:
                if old['signature']!=signature:raise ValueError('Request changed; use a new request ID')
                return self.admit(old['id'])
            # Rejected input produces no message, execution or Task.
            # Resolve every attachment through the owning Session. Untrusted IDs
            # are never accepted as local paths or guessed cross-session files.
            files=attachments
            if definition['config'].get('plan') is not None:
                files=[]
                if len(set(attachments))!=len(attachments):raise ValueError('Choose distinct attachments')
                for aid in attachments:
                    item=self.runtime.documents.get(sid,aid)
                    if item.size_bytes>25*1024*1024:raise ValueError('Attachment exceeds 25 MiB')
                    artifact=self.runtime.workspace.import_artifact(sid,self.runtime.documents.source_path(sid,aid),name=item.filename,media_type=item.media_type,
                        metadata={'source_attachment_id':aid,'origin':'flash_input'})
                    files.append({'id':aid,'filename':item.filename,'artifact_id':artifact.id,'media_type':item.media_type})
            value=workflow.validate(text,files)
            payload={'definition':definition,'input':value,'text':text,'language':language,
                     'title':workflow.name if language.startswith('zh') else workflow.name_en,
                     'authorization':self.runtime.app_chat.owner(b).capture_authorization(b['owner'],{'bot_id':bot},'user')}
            ref=uuid5(NAMESPACE_URL,'flash:'+sid+':'+request_id).hex
            with self.db.transaction(write=True) as db:
                db.execute("INSERT INTO messager_flash_submissions VALUES(?,?,?,?,?,?,?,NULL,NULL,NULL,'queued')",(ref,b['owner'],bot,sid,request_id,signature,json.dumps(payload)))
            return self.admit(ref)

    def append(self,row,text,key,role='assistant'):
        artifacts=[]
        if key=='input' and role=='user':
            artifacts=[{'artifact_id':f['artifact_id'],'session_id':row['session_id']}
                for f in row['payload']['input'].get('files',[]) if isinstance(f,dict) and f.get('artifact_id')]
        if key=='result' and row.get('agent_run'):
            run=self.runtime.agents.get_run(row['agent_run'])
            artifacts=(run.output or {}).get('artifacts',[]) if run.status.value=='completed' else []
            if artifacts:
                from .presentation import public_content
                text=public_content(text,artifacts)
        self.runtime.messager_dialogue.append(row['session_id'],role,text,'flash:'+row['id']+':'+key,
            {'origin':'bot_flash','flash_submission_id':row['id'],'task_id':row['task_id'],
             **({'client_request_id':row['request_id']} if key=='input' and role=='user' else {}),
             **({'artifacts':artifacts} if artifacts else {})})

    def admit(self,ref):
        row=self.link_receipt(self.row(ref))
        if row['todo_run']:return ref
        workflow=self.guard(row)
        title=row['payload']['title']
        task_value={'title':title,'description':row['payload']['text'],'model':'fixed-workflow-no-model','executor':'managed','directory_id':'','schedule':Schedule().model_dump()}
        binding={'submission_id':ref,'bot_id':row['bot_id'],'execution_hash':digest(execution_fields(task_value))}
        task=self.runtime.todo.store.save(row['actor'],task_value,creation_key='flash:'+ref,create_inbox=True,
            execution_binding={'registration':KEY,'binding':binding},execution_lane='messager-bot:'+row['bot_id'])
        with self.db.transaction(write=True) as db:db.execute('UPDATE messager_flash_submissions SET task_id=? WHERE id=?',(task['id'],ref))
        row=self.row(ref);self.append(row,row['payload']['text'],'input','user')
        run=self.runtime.todo.launch(row['actor'],task['id'],principal=execution_principal(self.runtime,row['actor']),request_key='flash:'+ref)
        with self.db.transaction(write=True) as db:db.execute('UPDATE messager_flash_submissions SET todo_run=? WHERE id=?',(run['id'],ref))
        return ref

    def validate(self,actor,task,binding):
        row=self.row(binding['submission_id'])
        if row['actor']!=actor or row['bot_id']!=binding['bot_id'] or digest(execution_fields(task))!=binding['execution_hash']:raise PermissionError('Flash Task binding changed')
        self.guard(row)

    async def start(self,actor,todo_run,task,prompt,attachments,binding):
        with self.runtime.app_chat.lock:
            self.validate(actor,task,binding)
            if attachments:raise PermissionError('Unexpected Todo attachments')
            row=self.row(binding['submission_id'])
            with self.db.transaction(write=True) as db:
                run,_=self.runtime.agents.create_run(session_id=row['session_id'],agent_key=KEY,
                    input={'submission_id':row['id'],'model':row['payload']['definition']['config'].get('model'),
                           'prompt':row['payload']['text']},idempotency_key='flash:'+row['id'],connection=db)
                db.execute("UPDATE messager_flash_submissions SET agent_run=?,todo_run=?,status='running' WHERE id=?",(run.id,todo_run,row['id']))
                db.execute('INSERT OR IGNORE INTO app_chat_run_authorizations VALUES(?,?)',(run.id,json.dumps(row['payload']['authorization'])))
            self.runtime.todo.store.run_update(todo_run,'running',session_id=row['session_id'],agent_run_id=run.id)
            self.track(self.row(row['id']))
        self.runtime.agent_runtime.wake();return run.id

    def restore(self,actor,todo_run,data):
        row=self.row(data['execution_binding']['binding']['submission_id'])
        if row['actor']!=actor:raise PermissionError('Flash owner mismatch')
        if row['agent_run']:
            self.track(row);return {'agent_run_id':row['agent_run'],'session_id':row['session_id']}
        return {'requeue_unstarted':True}

    def recover(self):
        with self.db.transaction() as db:rows=[dict(r) for r in db.execute("SELECT id FROM messager_flash_submissions WHERE todo_run IS NULL OR status NOT IN ('completed','failed','cancelled','interrupted','timed_out')")]
        for item in rows:
            try:
                row=self.link_receipt(self.row(item['id']))
                if row['status'] in TERMINAL:continue
                if row['agent_run']:
                    self.settle(row);self.track(row)
                elif not row['todo_run']:self.admit(row['id'])
                else:self.reconcile(row)
            except (PermissionError,ValueError) as error:
                with self.db.transaction(write=True) as db:db.execute("UPDATE messager_flash_submissions SET status='failed' WHERE id=?",(item['id'],))
                logging.getLogger(__name__).warning('Flash recovery rejected: %s',error)

    def __call__(self,ctx):
        try:
            with self.runtime.app_chat.lock:
                row=self.row(ctx.run.input['submission_id']);workflow=self.guard(row)
                if row['agent_run']!=ctx.run.id or row['session_id']!=ctx.run.session_id:raise PermissionError('Flash execution identity mismatch')
                if self.runtime.agents.get_run(ctx.run.id).cancel_requested:return FailAction('flash_cancelled','Flash cancelled')
                if row['payload']['definition']['config'].get('plan') is not None:
                    from .flash_plans import execute
                    return execute(ctx,row,self.runtime)
                return CompleteAction(workflow.execute(row['payload']['input']))
        except (ValueError,PermissionError) as error:return FailAction('flash_failed',str(error))

    def settle(self,row,status=None,error=None):
        if row['status'] in TERMINAL:return
        run=self.runtime.agents.get_run(row['agent_run']) if row['agent_run'] else None
        state=run.status.value if run else status
        if state not in TERMINAL:return
        with self.runtime.app_chat.lock:
            # Clear/delete invalidates the original conversation; never resurrect its feed.
            b=self.runtime.app_chat.binding(row['session_id'])
            if b and b['registration']=='ai2apps.messager.bots':
                text=(run.output or {}).get('content','') if run and state=='completed' else failure_message(error or (run.error if run else state))
                self.append(row,text,'result')
            with self.db.transaction(write=True) as db:db.execute('UPDATE messager_flash_submissions SET status=? WHERE id=?',(state,row['id']))

    def reconcile(self,row):
        row=self.link_receipt(row)
        if row['agent_run']:
            self.settle(row)
        elif row['todo_run']:
            with self.runtime.todo.store.connect() as db:
                receipt=db.execute('SELECT status,data FROM runs WHERE owner=? AND id=? AND task_id=?',(row['actor'],row['todo_run'],row['task_id'])).fetchone()
            if receipt and receipt['status'] in TERMINAL:self.settle(row,receipt['status'],json.loads(receipt['data']).get('error'))

    def finished(self,actor,todo_run,status,data):
        row=self.row(data['execution_binding']['binding']['submission_id'])
        if row['actor']!=actor:raise PermissionError('Flash owner mismatch')
        self.settle(row,status,data.get('error'))

    def track(self,row):
        self.runtime.system_tasks.submit(row['actor'],'ai2apps.messager',KEY,'Flash · '+row['payload']['title'],
            {'submission_id':row['id'],'run_id':row['agent_run']},dedup_key='flash:'+row['id'],receipt_key='flash:'+row['id'])

    def authorize_observer(self,actor,payload):
        row=self.row(payload['submission_id'])
        if row['actor']!=actor or row['agent_run']!=payload['run_id']:raise PermissionError('Flash observer scope mismatch')

    async def observe(self,ctx):
        while True:
            row=self.row(ctx.payload['submission_id']);run=self.runtime.agents.get_run(row['agent_run'])
            if run.status.value in TERMINAL:
                self.settle(row)
                return {'_status':'completed' if run.status.value=='completed' else 'cancelled' if run.status.value=='cancelled' else 'failed','agent_run_id':run.id}
            await asyncio.sleep(.2)

    async def cancel_observer(self,ctx,force):
        row=self.row(ctx.payload['submission_id'])
        if row['todo_run']:await self.runtime.todo.cancel(row['actor'],row['todo_run'])
        return self.runtime.agents.get_run(row['agent_run']).status.value in TERMINAL

    async def cancel(self,actor,bot,ref):
        with self.runtime.app_chat.lock:
            row=self.row(ref);self.directory.scope(actor,{'bot_id':bot})
            if row['actor']!=actor or row['bot_id']!=bot:raise PermissionError('Flash request unavailable')
            if row['status'] in TERMINAL:return {'status':row['status']}
        if row['todo_run']:
            await self.runtime.todo.cancel(actor,row['todo_run'])
            self.settle(self.row(ref),'cancelled')
        else:
            with self.db.transaction(write=True) as db:db.execute("UPDATE messager_flash_submissions SET status='cancelled' WHERE id=?",(ref,))
        return {'status':'cancel_requested'}

    def snapshot(self,principal,bot,sid):
        b=self.runtime.app_chat.access(principal,sid)
        if b['registration']!='ai2apps.messager.bots' or b['scope']!={'bot_id':bot}:raise PermissionError('Main Flash conversation required')
        with self.db.transaction() as db:refs=[r[0] for r in db.execute('SELECT id FROM messager_flash_submissions WHERE actor=? AND bot_id=? AND session_id=? ORDER BY rowid DESC LIMIT 50',(b['owner'],bot,sid))]
        runs=[]
        for ref in reversed(refs):
            row=self.row(ref)
            self.reconcile(row);row=self.row(ref)
            run=self.runtime.agents.get_run(row['agent_run']) if row['agent_run'] else None
            interactions=[{'id':i.id,'prompt':i.prompt,'schema':i.response_schema,'response_schema':i.response_schema,'status':i.status.value,'kind':i.kind.value,'ui_hints':i.ui_hints,'request':i.request,'deadline_at':i.deadline_at.isoformat()} for i in self.runtime.agents.list_interactions(run.id) if i.status.value=='pending'] if run else []
            runs.append({'id':row['agent_run'] or ref,'job_id':ref,'status':run.status.value if run else row['status'],'text':'Flash · '+row['payload']['title'],'interactions':interactions,'dialogue':False,'error':{'message':failure_message(run.error)} if run and run.error else None,'error_details':run.error if run else None})
        return {'runs':runs,'task_sessions':[]}


def failure_message(error):
    code=error.get('code','') if isinstance(error,dict) else str(error or '')
    if isinstance(error, dict) and code in {'flash_missing_binding', 'flash_invalid_arguments', 'flash_provider_changed',
                'flash_step_failed', 'flash_repair_failed', 'flash_repair_invalid'} and error.get('message'):
        return error['message']
    if code in ('parameter_contract_mismatch','parameter_contract_required'):
        return '工作流的预设参数不符合应用当前要求，本次处理未完成。请重新生成并审阅工作流后再提交。 / Workflow settings need updating; regenerate and review the workflow before submitting again.'
    if 'cancel' in code:
        return '本次处理已取消。 / This run was cancelled.'
    return '工作流未能完成，后续步骤已停止。可展开错误详情查看原因。 / The workflow did not finish; later steps were stopped. See error details.'
