"""Reviewed versions of existing Bot-owned recurring plans, with durable CAS receipts."""
import json
import logging
from datetime import UTC,datetime,timedelta
from uuid import uuid5,NAMESPACE_URL
from .tasks import ADAPTER,digest,execution_fields
from ai2apps.core.clock import parse_utc
from ai2apps.todo.models import resolve_schedule, upcoming_schedule_time


class PlanChanges:
    def __init__(self,dialogue):
        self.dialogue,self.runtime,self.db=dialogue,dialogue.runtime,dialogue.db
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_plan_changes(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,session_id TEXT NOT NULL,source_run TEXT NOT NULL UNIQUE,
                task_id TEXT NOT NULL,before_json TEXT NOT NULL,value_json TEXT NOT NULL,authorization_json TEXT NOT NULL,
                review_hash TEXT NOT NULL,expires_at TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT)''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_plan_versions(
                actor TEXT NOT NULL,task_id TEXT NOT NULL,version INTEGER NOT NULL,proposal_id TEXT NOT NULL,
                definition_json TEXT NOT NULL,PRIMARY KEY(actor,task_id,version))''')

    def before(self,actor,bot_id,task_id):
        self.dialogue.directory.scope(actor,{'bot_id':bot_id})
        todo=self.runtime.todo
        if todo is None:raise ValueError('Todo unavailable')
        binding=todo.store.execution_binding(actor,task_id)
        if not binding or binding['registration']!=ADAPTER or binding['binding']['bot_id']!=bot_id:raise PermissionError('Choose an existing schedule owned by this Bot')
        task=todo.store.get(actor,task_id)
        if task.get('deleted_at') or task.get('archived_at'):raise PermissionError('Plan unavailable')
        return {'contract':'ai2apps.bot-plan-review/v1','task':{k:task[k] for k in ('id','title','description','model','executor','schedule','revision')},'binding':binding}

    def prepare(self,actor,bot_id,run,task_id,schedule=None,access_requirements=None,*,instruction_change=None,replacement_instructions=None,plan_title=None):
        if schedule is not None and not isinstance(schedule,dict):raise ValueError('Schedule changes must be an object')
        before=self.before(actor,bot_id,task_id);task=before['task']
        self.dialogue.directory.permissions.validate(actor,{'bot_id':bot_id},run.input['authorization'],None,{})
        old=before['binding']['binding']['proposal_id']
        original=json.loads(self.runtime.messager_task_execution.proposal(actor,bot_id,old)['proposal_json'])
        for edit in (instruction_change, replacement_instructions):
            if edit is not None and (not isinstance(edit, str) or not edit.strip()):
                raise ValueError('Execution instruction edit must be non-empty text')
        if instruction_change is not None and replacement_instructions is not None:
            raise ValueError('Choose one execution instruction edit')
        title = task['title']
        if plan_title is not None:
            if not isinstance(plan_title, str) or not 1 <= len(plan_title.strip()) <= 200:
                raise ValueError('Plan title must be 1–200 characters')
            title = plan_title.strip()
        if title == task['title'] and not schedule and instruction_change is None and replacement_instructions is None and access_requirements is None:
            raise ValueError('Specify a title, schedule, execution instruction, or access change')
        prompt=original['prompt']
        if replacement_instructions is not None:
            prompt = replacement_instructions.strip()
        if instruction_change is not None:
            prompt += '\n\n执行要求变更 / Execution instruction change:\n'+instruction_change.strip()
        if len(prompt)>12000:raise ValueError('Plan instructions are too long; review a shorter replacement')
        request_time = run.input.get('request_time')
        resolved = resolve_schedule(schedule or {}, previous=task['schedule'],
            reference=parse_utc(request_time['utc']) if request_time else run.created_at)
        if schedule and resolved.frequency == 'once' and upcoming_schedule_time(resolved.model_dump()) is None:
            raise ValueError('Choose a future scheduled-once time')
        value={'title':title,'prompt':prompt,'model':task['model'],'schedule':resolved.model_dump(),'notify':original['notify'],
            'identity':{**self.dialogue.directory.identity(actor,{'bot_id':bot_id}),'long_term_memory':self.dialogue.directory.memory.context(actor,bot_id),'model_preferences':self.dialogue.directory.model_memories.snapshot(actor,bot_id)}}
        frozen=self.dialogue.directory.permissions.capture(actor,{'bot_id':bot_id},'hook')
        value['access_requirements']=access_requirements if access_requirements is not None else original.get('access_requirements',[])
        value['access_preflight']=self.runtime.messager_task_execution.access.preflight(actor,bot_id,value['access_requirements'],frozen)
        prior=before['binding']['binding']['authorization'].get('task_access',{}).get('apps',[])
        for app in value['access_preflight']['apps']:
            if app['app_id'] in prior:
                app['predicted']=True;app['reasons'].append('Previously reviewed plan access; review again for this amendment')
        ref=uuid5(NAMESPACE_URL,'bot-plan-change:'+run.id).hex;expires=(datetime.now(UTC)+timedelta(hours=24)).isoformat()
        with self.db.transaction(write=True) as db:
            existing=db.execute('SELECT * FROM messager_plan_changes WHERE source_run=?',(run.id,)).fetchone()
            if existing:return dict(existing)
            if db.execute("SELECT count(*) FROM messager_plan_changes WHERE actor=? AND bot_id=? AND status IN ('pending','applying')",(actor,bot_id)).fetchone()[0]>=10:raise ValueError('Review existing plan changes first')
            review=digest({'before':before,'value':value,'authorization':frozen,'actor':actor,'bot_id':bot_id,'expires':expires})
            db.execute("INSERT INTO messager_plan_changes VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',NULL)",(ref,actor,bot_id,run.session_id,run.id,task_id,json.dumps(before),json.dumps(value),json.dumps(frozen),review,expires))
            db.execute('INSERT OR IGNORE INTO messager_plan_versions VALUES(?,?,?,?,?)',(actor,task_id,1,old,json.dumps(original)))
        return {'id':ref,'review_hash':review,'status':'pending'}

    def pending(self,actor,bot_id):
        self.dialogue.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:rows=db.execute("SELECT * FROM messager_plan_changes WHERE actor=? AND bot_id=? AND status IN ('pending','applying') ORDER BY rowid LIMIT 20",(actor,bot_id)).fetchall()
        items = []
        for row in rows:
            value = json.loads(row['value_json'])
            items.append({'id':row['id'],'review_hash':row['review_hash'],'status':row['status'],
                'before':json.loads(row['before_json'])['task'],'value':value,'expires_at':row['expires_at'],
                'next_due':upcoming_schedule_time(value['schedule'])})
        return items

    def decide(self,actor,bot_id,ref,review_hash,decision,access_mode=None,access_apps=None,access_bots=None):
        with self.runtime.app_chat.lock:
            self.dialogue.directory.scope(actor,{'bot_id':bot_id})
            with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_plan_changes WHERE id=? AND actor=? AND bot_id=?',(ref,actor,bot_id)).fetchone()
            if not row or row['review_hash']!=review_hash:raise PermissionError('Plan review unavailable')
            choice=json.loads(row['authorization_json']).get('task_access')
            if choice and self.runtime.messager_task_execution.access.changed_choice(choice,access_mode,access_apps,access_bots):raise ValueError('Original plan access choice is already committed')
            if row['status'] in ('applied','rejected'):
                result=json.loads(row['result_json']);self.project(row,result,row['status'])
                return {'status':row['status'],'result':result}
            if decision not in ('approve','reject'):raise ValueError('Unknown plan decision')
            binding=self.runtime.app_chat.binding(row['session_id'])
            if not binding or binding['owner']!=actor or binding['registration']!='ai2apps.messager.bots' or binding['scope'].get('bot_id')!=bot_id:raise PermissionError('Original Bot conversation unavailable')
            before,value,frozen=(json.loads(row[k]) for k in ('before_json','value_json','authorization_json'))
            with self.runtime.todo.store.connect() as db:receipt=db.execute('SELECT result_json FROM execution_plan_receipts WHERE owner=? AND request_key=?',(actor,'bot-plan:'+ref)).fetchone()
            if receipt:result=json.loads(receipt[0]);status='applied'
            elif decision=='reject':result={'task_id':row['task_id'],'changed':False};status='rejected'
            else:
                if datetime.fromisoformat(row['expires_at'])<=datetime.now(UTC):raise ValueError('Plan review expired')
                if digest(self.before(actor,bot_id,row['task_id']))!=digest(before):raise ValueError('Plan changed; prepare a new review')
                if before['task']['schedule'] != value['schedule'] and value['schedule']['frequency'] == 'once' and upcoming_schedule_time(value['schedule']) is None:
                    raise ValueError('The scheduled time has passed; prepare a new review')
                self.runtime.messager_task_execution.authorization(actor,bot_id,frozen)
                if row['status']=='pending' and value.get('access_preflight'):
                    frozen=self.runtime.messager_task_execution.access.seal(actor,bot_id,ref,value['access_preflight'],frozen,access_mode,access_apps,access_bots)
                task_value={'title':value['title'],'description':value['prompt'],'model':value['model'],'executor':'managed','schedule':value['schedule']}
                binding={'proposal_id':ref,'bot_id':bot_id,'authorization':frozen,'identity':value['identity'],'execution_hash':digest(execution_fields(task_value)),'notify':value['notify']}
                with self.db.transaction(write=True) as db:
                    db.execute("UPDATE messager_plan_changes SET status='applying',authorization_json=? WHERE id=?",(json.dumps(frozen),ref))
                    db.execute("INSERT OR IGNORE INTO messager_task_proposals VALUES(?,?,?,?,?,?,?,?,?,'approved',?,NULL,?)",(ref,actor,bot_id,row['source_run'],row['session_id'],'bot-plan:'+ref,json.dumps(value),json.dumps(frozen),review_hash,row['task_id'],datetime.now(UTC).isoformat()))
                result=self.runtime.todo.store.update_execution_plan(actor,row['task_id'],before['task']['revision'],ADAPTER,task_value,binding,'bot-plan:'+ref);status='applied'
            with self.db.transaction(write=True) as db:
                if status=='applied':
                    version=db.execute('SELECT version FROM messager_plan_versions WHERE actor=? AND task_id=? AND proposal_id=?',(actor,row['task_id'],ref)).fetchone()
                    version=version[0] if version else db.execute('SELECT COALESCE(max(version),0)+1 FROM messager_plan_versions WHERE actor=? AND task_id=?',(actor,row['task_id'])).fetchone()[0]
                    db.execute('INSERT OR IGNORE INTO messager_plan_versions VALUES(?,?,?,?,?)',(actor,row['task_id'],version,ref,json.dumps(value)));result['plan_version']=version
                db.execute('UPDATE messager_plan_changes SET status=?,result_json=? WHERE id=?',(status,json.dumps(result),ref))
            if status=='applied':self.runtime.todo.system_schedules().publish(actor,row['task_id'])
            self.project(row,result,status)
            return {'status':status,'result':result}

    def project(self,row,result,status):
        value=json.loads(row['value_json'])
        text=('计划「'+value['title']+'」已更新为版本 '+str(result.get('plan_version'))+'，从下一次新执行生效；已启动或已入队的执行保持原规则。') if status=='applied' else '已取消本次计划修改，继续使用原规则。'
        self.dialogue.append(row['session_id'],'assistant',text,'bot-plan-result:'+row['id'],{'origin':'bot_plan_feedback','plan_id':row['task_id'],'plan_version':result.get('plan_version'),'status':status})

    def recover(self):
        with self.db.transaction() as db:rows=db.execute("SELECT * FROM messager_plan_changes WHERE status IN ('applied','rejected','applying')").fetchall()
        for row in rows:
            try:
                if row['status']=='applying':self.decide(row['actor'],row['bot_id'],row['id'],row['review_hash'],'approve')
                else:self.project(row,json.loads(row['result_json']),row['status'])
            except (ValueError,PermissionError,KeyError):logging.getLogger(__name__).info('Bot plan receipt unavailable: %s',row['id'])
