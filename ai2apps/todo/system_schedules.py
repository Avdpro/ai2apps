"""Todo-owned bridge to the system schedule directory; one timer, existing run queue."""
import json
from datetime import UTC,datetime
from ai2apps.system_tasks.service import TaskHandler
from ai2apps.system_tasks.sessions import execution_principal
from .models import next_due

APP='ai2apps.todo'
KIND='todo.managed_schedule'


class SystemTodoSchedules:
    def __init__(self,runtime):
        self.runtime=runtime
        runtime.system_tasks.register(KIND,TaskHandler(APP,self.execute,self.cancel,self.authorize,
            resumable=True,next_schedule=self.next,disable_schedule=self.disable))

    @property
    def todo(self):return self.runtime.todo

    @staticmethod
    def key(owner,task_id):
        from uuid import uuid5,NAMESPACE_URL
        return 'todo-schedule:'+uuid5(NAMESPACE_URL,owner+':'+task_id).hex

    def authorize(self,owner,payload):
        task,binding=payload['task'],payload['binding']
        current=self.todo.store.get(owner,task['id'])
        if current.get('deleted_at') or current.get('archived_at'):raise ValueError('Task is deleted or archived')
        self.todo.execution_adapter(binding).validate(owner,task,binding['binding'])

    def publish(self,owner,task_id):
        task=self.todo.store.get(owner,task_id);binding=self.todo.store.execution_binding(owner,task_id)
        if not binding or task['executor']!='managed':raise ValueError('A reviewed managed Task is required')
        key=self.key(owner,task_id)
        with self.todo.store.connect() as db:db.execute('INSERT OR IGNORE INTO task_system_schedules VALUES(?,?)',(owner,task_id))
        enabled=bool(task['next_due'] and task['schedule']['frequency']!='off' and not task.get('deleted_at') and not task.get('archived_at'))
        if not enabled:
            with self.runtime.database.transaction(write=True) as db:db.execute('UPDATE system_task_schedules SET enabled=0 WHERE owner=? AND id=?',(owner,key))
            return key
        payload={'task':task,'binding':binding}
        self.authorize(owner,payload)
        # Progress revisions do not reset a clock. A reviewed binding change does.
        with self.runtime.database.transaction() as db:old=db.execute('SELECT payload_json FROM system_task_schedules WHERE owner=? AND id=?',(owner,key)).fetchone()
        if old and json.loads(old[0])['binding']==binding:return key
        self.runtime.system_tasks.schedule(owner,APP,key,KIND,task['title'],payload,next_run=datetime.fromisoformat(task['next_due']).timestamp())
        return key

    def sync(self):
        with self.todo.store.connect() as db:rows=db.execute('SELECT owner,task_id FROM task_system_schedules').fetchall()
        for row in rows:
            try:self.publish(row['owner'],row['task_id'])
            except (ValueError,PermissionError,KeyError):
                with self.runtime.database.transaction(write=True) as db:db.execute('UPDATE system_task_schedules SET enabled=0 WHERE owner=? AND id=?',(row['owner'],self.key(row['owner'],row['task_id'])))

    def next(self,owner,payload,now):
        self.authorize(owner,payload)
        task=payload['task']
        binding=self.todo.store.execution_binding(owner,task['id'])
        if binding!=payload['binding']:raise ValueError('Plan changed before timer admission')
        self.todo.execution_adapter(binding).validate(owner,self.todo.store.get(owner,task['id']),binding['binding'])
        future=next_due(task['schedule'],datetime.fromtimestamp(now,UTC))
        binding=self.todo.store.execution_binding(owner,task['id'])
        with self.todo.store.connect() as db:
            if binding==payload['binding']:db.execute('UPDATE tasks SET next_due=? WHERE owner=? AND id=?',(future.isoformat() if future else None,owner,task['id']))
        return future.timestamp() if future else None

    def disable(self,owner,payload):
        task=self.todo.store.get(owner,payload['task']['id'])
        if self.todo.store.execution_binding(owner,task['id'])!=payload['binding']:raise ValueError('Plan changed; refresh its schedule')
        if task['schedule']['frequency']!='off':self.todo.store.disable_schedule(owner,task['id'],task['revision'],'system-disable:'+self.key(owner,task['id'])+':'+str(task['revision']))

    async def execute(self,ctx):
        # Queue admission has its own receipt; the actual Agent Run remains the
        # existing Todo/AppChat execution, not a second system-owned Agent.
        value=self.todo.launch(ctx.owner,ctx.payload['task']['id'],principal=execution_principal(self.runtime,ctx.owner),
            request_key='system-todo:'+ctx.id,admitted=ctx.payload)
        ctx.report(message='已加入 Todo 执行队列 / Added to Todo execution queue',progress={'phase':'启动记录 / Dispatch'},checkpoint={**ctx.checkpoint,'todo_run_id':value['id']})
        return {'todo_run_id':value['id'],'task_id':ctx.payload['task']['id']}

    async def cancel(self,ctx,force):
        rid=ctx.checkpoint.get('todo_run_id')
        if not rid:
            receipt=self.todo.store.launch_receipt(ctx.owner,'system-todo:'+ctx.id)
            if receipt:
                if receipt['task_id']!=ctx.payload['task']['id']:raise PermissionError('Execution receipt belongs to another Task')
                rid=receipt['run_id']
        if rid:await self.todo.cancel(ctx.owner,rid)
        return True

    def retire(self,owner,task_id,bot_id,reason):
        key=self.key(owner,task_id)
        with self.runtime.database.transaction(write=True) as db:
            db.execute('UPDATE system_task_schedules SET enabled=0 WHERE owner=? AND id=?',(owner,key))
            pending=db.execute("SELECT id FROM system_tasks WHERE owner=? AND kind=? AND json_extract(payload_json,'$.task.id')=? AND status IN ('queued','running','waiting_user','waiting_resource')",(owner,KIND,task_id)).fetchall()
        for row in pending:self.runtime.system_tasks.cancel(owner,row['id'])
        with self.todo.store.connect() as db:
            row=db.execute('SELECT data FROM tasks WHERE owner=? AND id=?',(owner,task_id)).fetchone()
            if not row:return
            value=json.loads(row[0])
            if value.get('deleted_at'):return
            value.update(deleted_at=datetime.now(UTC).isoformat(),status='paused',bot_cleanup={'bot_id':bot_id,'reason':reason})
            db.execute('UPDATE tasks SET data=?,next_due=NULL,revision=revision+1 WHERE owner=? AND id=?',(json.dumps(value),owner,task_id))

    def restore_bot(self,owner,bot_id):
        with self.todo.store.connect() as db:
            for row in db.execute("SELECT id,data FROM tasks WHERE owner=? AND json_extract(data,'$.bot_cleanup.bot_id')=? AND json_extract(data,'$.bot_cleanup.reason')='bot_delete'",(owner,bot_id)).fetchall():
                value=json.loads(row['data']);value.update(deleted_at=None,status='paused');value.pop('bot_cleanup',None)
                db.execute('UPDATE tasks SET data=?,next_due=NULL,revision=revision+1 WHERE owner=? AND id=?',(json.dumps(value),owner,row['id']))
