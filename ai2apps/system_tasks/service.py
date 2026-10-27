"""Local task admission; Browser/model schedulers retain resource ownership.

Only trusted host code registers handlers. Payloads are data, never executable
Python, commands or arbitrary URLs to fetch on behalf of another App.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Awaitable, Callable

log = logging.getLogger(__name__)
TERMINAL = ('completed', 'partial', 'failed', 'cancelled', 'interrupted')
EXECUTING = ('running', 'waiting_resource', 'waiting_user', 'cancelling')


@dataclass(frozen=True)
class TaskHandler:
    app_id: str
    execute: Callable[['TaskContext'], Awaitable[dict | None]]
    # Must confirm only owned resources have stopped/been retained safely.
    cancel: Callable[['TaskContext', bool], Awaitable[bool]] | None = None
    authorize: Callable[[str, dict], None] | None = None
    resumable: bool = False
    retry_payload: Callable[[dict], dict] | None = None
    # One owner presentation is shared by task observers, including AaAT.
    progress_view: Callable[[dict], dict] | None = None


class TaskContext:
    def __init__(self, service, task):
        self.service, self.task = service, task
        self.owner, self.id, self.payload = task['owner'], task['id'], task['payload']

    @property
    def checkpoint(self):
        return self.service.get(self.owner, self.id)['checkpoint']

    def report(self, *, state='running', message='', checkpoint=None, progress=None):
        if state not in ('running', 'waiting_resource', 'waiting_user'):
            raise ValueError('Invalid execution state')
        changes = dict(status=state, message=str(message)[:2000])
        if checkpoint is not None: changes['checkpoint_json'] = json.dumps(checkpoint)
        if progress is not None: changes['progress_json'] = json.dumps(progress)
        self.service._update(self.owner, self.id, changes, unless_cancelling=True)


class SystemTaskService:
    poll_seconds = 1

    def __init__(self, runtime, *, clock=time.time, max_running=4, max_per_app=2, max_per_owner=2):
        self.runtime, self.database, self.clock = runtime, runtime.database, clock
        self.max_running, self.max_per_app, self.max_per_owner = max_running, max_per_app, max_per_owner
        self.handlers: dict[str, TaskHandler] = {}
        self.jobs: dict[str, asyncio.Task] = {}
        self.loop_task = None
        self.stopping = False

    def register(self, kind, handler):
        if kind in self.handlers: raise ValueError('Task handler already registered')
        self.handlers[kind] = handler

    def _wake(self):
        self.runtime.notifications.notify()

    @staticmethod
    def _decode(row):
        item = dict(row)
        for name in ('payload', 'checkpoint', 'progress', 'result'):
            item[name] = json.loads(item.pop(name+'_json'))
        return item

    def get(self, owner, id):
        with self.database.transaction() as db:
            row = db.execute('SELECT * FROM system_tasks WHERE owner=? AND id=?', (owner,id)).fetchone()
        if row is None: raise KeyError('System Task not found')
        return self._present(self._decode(row))

    def _present(self, task):
        handler=self.handlers.get(task['kind'])
        default={
            'text':task.get('message') or task['name'],'phase':task['status'],
            'content':{'task_progress':{'schema':'ai2apps.task-progress/v1','metrics':[]}}}
        try:
            update=handler.progress_view(task) if handler and handler.progress_view else default
            if not isinstance(update,dict):raise ValueError('Invalid task presentation')
            if not isinstance(update.get('content',{}),dict) or not isinstance(update.get('content',{}).get('task_progress',{}),dict):
                raise ValueError('Invalid task snapshot')
        except Exception:
            update=default
        snapshot=dict(update.get('content',{}).get('task_progress') or {})
        state=task['status']
        snapshot.update(schema='ai2apps.task-progress/v1',task_id=task['id'],
            state='waiting' if state in ('waiting_resource','waiting_user') else 'failed' if state=='interrupted' else 'running' if state=='cancelling' else state,
            requires_user=state=='waiting_user',
            wait_reason=str(task.get('message') or '')[:500] if state in ('waiting_resource','waiting_user') else '')
        update={**update,'content':{'task_progress':snapshot,'system_task_id':task['id']}}
        from ai2apps.services.models import validate_progress_update
        try:validate_progress_update(update)
        except (ValueError,TypeError,AttributeError,OverflowError):
            # A broken presentation cannot make the real task inaccessible to
            # status reads or cancellation, and must not reflect owner errors.
            snapshot['metrics']=[]
            snapshot['stage']=state
            update={**default,'content':{'task_progress':{k:v for k,v in snapshot.items()
                if k in {'schema','state','stage','task_id','requires_user','wait_reason','metrics'}},
                'system_task_id':task['id']}}
            validate_progress_update(update)
        return {**task,'progress_snapshot':update}

    async def follow(self, owner, id, context, *, app_id, timeout=840):
        """Observe an existing task. Never submit, retry or cancel work here."""
        if owner!=context.actor_user_id or not context.session_id or not context.installation_id:
            raise PermissionError('Task observer requires the owning Session identity')
        deadline=asyncio.get_running_loop().time()+timeout
        seen=None
        async with self.runtime.notifications.subscribe() as wake:
            while True:
                task=await asyncio.to_thread(self.get,owner,id)
                if task['app_id']!=app_id:raise PermissionError('Task App binding changed')
                update=task['progress_snapshot']
                current=json.dumps(update,sort_keys=True,ensure_ascii=False)
                if current!=seen:
                    await context.report_progress(**update)
                    seen=current
                if task['status'] in TERMINAL:return task
                remaining=deadline-asyncio.get_running_loop().time()
                if remaining<=0:raise TimeoutError('System Task is still running: '+id)
                try:await asyncio.wait_for(wake.get(),timeout=min(remaining,2))
                except TimeoutError:pass

    def active_for(self, owner, app_id, key):
        with self.database.transaction() as db:
            row=db.execute("SELECT * FROM system_tasks WHERE owner=? AND app_id=? AND dedup_key=? AND status IN ('queued','running','waiting_resource','waiting_user','cancelling')",(owner,app_id,key)).fetchone()
        return self._decode(row) if row else None

    def disable_missing_schedules(self, owner, app_id, keys):
        with self.database.transaction(write=True) as db:
            for row in db.execute('SELECT id FROM system_task_schedules WHERE owner=? AND app_id=?',(owner,app_id)).fetchall():
                if row['id'] not in keys:
                    db.execute('UPDATE system_task_schedules SET enabled=0 WHERE owner=? AND app_id=? AND id=?',(owner,app_id,row['id']))

    def _update(self, owner, id, changes, *, unless_cancelling=False):
        allowed = {'status','message','checkpoint_json','progress_json','result_json','priority','force_cancel','run_after','started_at','finished_at','attempt'}
        if not changes or set(changes)-allowed: raise ValueError('Invalid Task update')
        with self.database.transaction(write=True) as db:
            before=db.execute('SELECT * FROM system_tasks WHERE owner=? AND id=?',(owner,id)).fetchone()
            if before is None or all(before[key]==value for key,value in changes.items()):return
            if unless_cancelling and before['status'] in TERMINAL:return
            result = db.execute('UPDATE system_tasks SET '+','.join(k+'=?' for k in changes)+',updated_at=? WHERE owner=? AND id=?'+(" AND status!='cancelling'" if unless_cancelling else ''), (*changes.values(),self.clock(),owner,id))
            if result.rowcount: self._event(db, owner, id)
        self._wake()

    def _event(self, db, owner, id):
        self.runtime.events.append_in_transaction(db, event_type='system.task.changed',
            subject_id='system-tasks:'+owner, payload={'task_id':id})

    def submit(self, owner, app_id, kind, name, payload, *, dedup_key='', priority=0, run_after=None, checkpoint=None, trigger='manual'):
        handler = self.handlers.get(kind)
        if handler is None or handler.app_id != app_id: raise ValueError('Unregistered Task kind for App')
        if trigger not in ('manual','schedule'):raise ValueError('Invalid Task trigger')
        # JSON round-trip freezes input and rejects process-local objects.
        frozen = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        if len(frozen.encode()) > 1024*1024: raise ValueError('Task input exceeds 1 MiB')
        if handler.authorize: handler.authorize(owner, json.loads(frozen))
        now=self.clock(); id='stask_'+uuid.uuid4().hex
        with self.database.transaction(write=True) as db:
            if dedup_key:
                existing=db.execute("SELECT * FROM system_tasks WHERE owner=? AND app_id=? AND dedup_key=? AND status IN ('queued','running','waiting_resource','waiting_user','cancelling')",(owner,app_id,dedup_key)).fetchone()
                if existing: return self._decode(existing)
            count=db.execute("SELECT count(*) FROM system_tasks WHERE owner=? AND status='queued'",(owner,)).fetchone()[0]
            if count>=1000: raise ValueError('System Task queue is full')
            db.execute('INSERT INTO system_tasks(id,owner,app_id,kind,name,payload_json,checkpoint_json,status,dedup_key,priority,run_after,created_at,updated_at,trigger) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (id,owner,app_id,kind,str(name)[:500],frozen,json.dumps(checkpoint or {}),'queued',dedup_key,int(priority),run_after or now,now,now,trigger))
            self._event(db,owner,id)
        self._wake()
        return self.get(owner,id)

    def schedule(self, owner, app_id, key, kind, name, payload, *, next_run, interval_seconds=None, enabled=True):
        handler=self.handlers.get(kind)
        if handler is None or handler.app_id!=app_id: raise ValueError('Unregistered Task kind for App')
        if interval_seconds is not None and interval_seconds<60: raise ValueError('Schedule interval must be at least 60 seconds')
        if handler.authorize: handler.authorize(owner,payload)
        with self.database.transaction(write=True) as db:
            db.execute('INSERT INTO system_task_schedules(id,owner,app_id,kind,name,payload_json,next_run,interval_seconds,enabled,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(owner,app_id,id) DO UPDATE SET kind=excluded.kind,name=excluded.name,payload_json=excluded.payload_json,next_run=excluded.next_run,interval_seconds=excluded.interval_seconds,enabled=excluded.enabled,updated_at=excluded.updated_at',
                (key,owner,app_id,kind,name,json.dumps(payload),next_run,interval_seconds,int(enabled),self.clock()))
        self._wake()

    def prune_history(self):
        cutoff = self.clock() - 48 * 60 * 60
        with self.database.transaction(write=True) as db:
            rows = db.execute("SELECT id,owner,COALESCE(finished_at,updated_at) AS ended FROM system_tasks WHERE status IN ('completed','partial','failed','cancelled','interrupted') ORDER BY ended DESC,id DESC").fetchall()
            counts = {}
            for row in rows:
                counts[row['owner']] = counts.get(row['owner'], 0) + 1
                if row['id'] in self.jobs or (row['ended'] >= cutoff and counts[row['owner']] <= 100):
                    continue
                db.execute('DELETE FROM system_task_attempts WHERE task_id=?', (row['id'],))
                db.execute('UPDATE system_task_schedules SET last_task_id=NULL WHERE last_task_id=?', (row['id'],))
                db.execute('DELETE FROM system_tasks WHERE id=?', (row['id'],))

    def snapshot(self, owner, *, limit=200):
        self.prune_history()
        with self.database.transaction() as db:
            rows=db.execute("SELECT * FROM system_tasks WHERE owner=? AND status IN ('queued','running','waiting_resource','waiting_user','cancelling') ORDER BY created_at DESC LIMIT ?",(owner,limit)).fetchall()
            rows+=db.execute("SELECT * FROM system_tasks WHERE owner=? AND status IN ('completed','partial','failed','cancelled','interrupted') ORDER BY COALESCE(finished_at,updated_at) DESC,id DESC LIMIT 100",(owner,)).fetchall()
            schedules=[dict(row) for row in db.execute('SELECT id,app_id,kind,name,next_run,interval_seconds,enabled,last_task_id,error FROM system_task_schedules WHERE owner=? AND enabled=1 ORDER BY next_run LIMIT ?',(owner,limit))]
        # Input and checkpoints can contain private evidence. UI receives metadata only.
        tasks=[]
        for row in rows:
            item=self._present(self._decode(row))
            for key in ('payload','checkpoint','result'):item.pop(key)
            tasks.append(item)
        apps = {}
        with self.database.transaction() as db:
            for app_id in {item['app_id'] for item in [*tasks, *schedules]}:
                row = db.execute('SELECT manifest_json FROM app_definitions WHERE package_id=? ORDER BY created_at DESC LIMIT 1', (app_id,)).fetchone()
                manifest = json.loads(row['manifest_json']) if row else {}
                apps[app_id] = {'name': manifest.get('name') or app_id, 'icon': (manifest.get('navigation') or {}).get('icon') or 'app-window'}
        return {'tasks':tasks,'schedules':schedules,'limit':limit,'apps':apps}

    def attempts(self, owner, id):
        self.get(owner,id)
        with self.database.transaction() as db:
            return [dict(r) for r in db.execute('SELECT * FROM system_task_attempts WHERE owner=? AND task_id=? ORDER BY number DESC LIMIT 20',(owner,id))]

    def start(self, owner, id):
        task=self.get(owner,id)
        if task['status']=='queued':
            self._update(owner,id,dict(priority=max(task['priority'],100),run_after=self.clock(),message=''))
            return self.get(owner,id)
        if task['status'] in TERMINAL:
            handler=self.handlers.get(task['kind'])
            if task['status']=='interrupted' and not (handler and handler.resumable):
                raise ValueError('Interrupted Task requires App-specific verification before retry')
            payload=handler.retry_payload(task['payload']) if handler and handler.retry_payload else task['payload']
            return self.submit(owner,task['app_id'],task['kind'],task['name'],payload,
                dedup_key=task['dedup_key'],checkpoint=task['checkpoint'] if handler and handler.resumable and not handler.retry_payload else {})
        return task

    def start_schedule(self, owner, id, *, scheduled=False):
        with self.database.transaction() as db:
            row=db.execute('SELECT * FROM system_task_schedules WHERE owner=? AND id=?',(owner,id)).fetchone()
        if row is None:raise KeyError('Schedule not found')
        # Manual invocation does not move or disable the recurring schedule.
        return self.submit(owner,row['app_id'],row['kind'],row['name'],json.loads(row['payload_json']),dedup_key='schedule:'+id,trigger='schedule' if scheduled else 'manual')

    def cancel(self, owner, id, *, force=False):
        task=self.get(owner,id)
        if task['status'] in TERMINAL:return task
        needs_cleanup=task['status']!='queued' or bool(self.handlers.get(task['kind']) and self.handlers[task['kind']].cancel)
        self._update(owner,id,dict(status='cancelling' if needs_cleanup else 'cancelled',
            force_cancel=int(force),finished_at=self.clock() if task['status']=='queued' else None,
            message='强制中断请求已提交' if force else '正在中断并清理资源'))
        self._wake()
        return self.get(owner,id)

    async def startup(self):
        if self.loop_task is not None:return
        self.stopping=False
        with self.database.transaction() as db:
            rows=[self._decode(r) for r in db.execute("SELECT * FROM system_tasks WHERE status IN ('running','waiting_resource','waiting_user')")]
        for task in rows:
            handler=self.handlers.get(task['kind'])
            self._finish_attempt(task,'interrupted','Local restarted')
            self._update(task['owner'],task['id'],dict(status='queued' if handler and handler.resumable else 'interrupted',
                message='Local 重启，等待从检查点恢复' if handler and handler.resumable else 'Local 重启；执行结果需核查'))
        log.info('System Task service loaded from %s',__file__)
        self.loop_task=asyncio.create_task(self._loop(),name='system-task-service')

    async def shutdown(self):
        self.stopping=True
        if self.loop_task:
            self.loop_task.cancel();await asyncio.gather(self.loop_task,return_exceptions=True)
            self.loop_task=None
        for job in list(self.jobs.values()):job.cancel()
        await asyncio.gather(*list(self.jobs.values()),return_exceptions=True)
        self.jobs.clear()

    async def _run(self, task):
        context=TaskContext(self,task); handler=self.handlers[task['kind']]
        try:
            if handler.authorize:handler.authorize(task['owner'],task['payload'])
            result=await handler.execute(context) or {}
            current=self.get(task['owner'],task['id'])
            if current['status']=='cancelling':return
            status=result.pop('_status','completed')
            if status not in ('completed','partial','failed'):raise ValueError('Invalid Task result state')
            self._update(task['owner'],task['id'],dict(status=status,result_json=json.dumps(result),finished_at=self.clock()))
            self._finish_attempt(task,status)
        except asyncio.CancelledError:
            if self.stopping:
                # Leave a durable recoverable state. Do not cancel shared resources
                # just because the Local process is shutting down.
                return
            raise
        except Exception as error:
            log.exception('System Task failed: %s',task['id'])
            self._update(task['owner'],task['id'],dict(status='failed',message=str(error)[:2000],finished_at=self.clock()))
            self._finish_attempt(task,'failed',str(error)[:2000])
        finally:
            self.jobs.pop(task['id'],None)
            self._wake()

    def _finish_attempt(self, task, status, error=''):
        with self.database.transaction(write=True) as db:
            db.execute('UPDATE system_task_attempts SET status=?,finished_at=?,error=? WHERE owner=? AND task_id=? AND number=?',(status,self.clock(),error,task['owner'],task['id'],task['attempt']))

    async def tick(self):
        now=self.clock()
        if now - getattr(self, '_last_history_cleanup', 0) >= 60:
            self.prune_history()
            self._last_history_cleanup = now
        with self.database.transaction() as db:
            due=[dict(r) for r in db.execute('SELECT * FROM system_task_schedules WHERE enabled=1 AND next_run<=?',(now,))]
        for schedule in due:
            try:
                task=self.start_schedule(schedule['owner'],schedule['id'],scheduled=True)
                interval=schedule['interval_seconds']
                # Coalesce missed slots into one run, never replay a catch-up storm.
                next_run=schedule['next_run']+(int((now-schedule['next_run'])//interval)+1)*interval if interval else schedule['next_run']
                with self.database.transaction(write=True) as db:
                    db.execute("UPDATE system_task_schedules SET next_run=?,enabled=?,last_task_id=?,error='' WHERE owner=? AND app_id=? AND id=? AND next_run=?",(next_run,int(bool(interval)),task['id'],schedule['owner'],schedule['app_id'],schedule['id'],schedule['next_run']))
            except Exception as error:
                with self.database.transaction(write=True) as db:
                    db.execute('UPDATE system_task_schedules SET error=?,next_run=? WHERE owner=? AND app_id=? AND id=?',(str(error)[:500],now+60,schedule['owner'],schedule['app_id'],schedule['id']))
        with self.database.transaction() as db:
            cancelling=[self._decode(r) for r in db.execute("SELECT * FROM system_tasks WHERE status='cancelling'")]
        for task in cancelling:
            job=self.jobs.get(task['id'])
            if job is not None:
                job.cancel()
            handler=self.handlers.get(task['kind'])
            if handler is None:continue
            try:
                async with asyncio.timeout(2):
                    clean=await handler.cancel(TaskContext(self,task),bool(task['force_cancel'])) if handler.cancel else True
                # The adapter may be what releases an in-flight browser/model
                # wait. Never wait for the coroutine before signalling resources.
                if job is not None:
                    done,_=await asyncio.wait({job},timeout=2)
                    if not done:continue
                if clean:
                    self._update(task['owner'],task['id'],dict(status='cancelled',finished_at=now))
                    self._finish_attempt(task,'cancelled')
            except (Exception, TimeoutError) as error:
                self._update(task['owner'],task['id'],dict(message='等待资源清理：'+str(error)[:500]))
        if self.stopping:return
        with self.database.transaction(write=True) as db:
            active=[dict(r) for r in db.execute("SELECT owner,app_id FROM system_tasks WHERE status IN ('running','waiting_resource','waiting_user','cancelling')")]
            queued=db.execute("SELECT * FROM system_tasks WHERE status='queued' AND run_after<=? ORDER BY (priority + CAST((?-created_at)/60 AS INTEGER)) DESC,created_at",(now,now)).fetchall()
            admitted=[]
            for row in queued:
                task=self._decode(row)
                if task['kind'] not in self.handlers:continue
                if len(active)>=self.max_running:break
                if sum(t['app_id']==task['app_id'] for t in active)>=self.max_per_app:continue
                if sum(t['owner']==task['owner'] for t in active)>=self.max_per_owner:continue
                number=task['attempt']+1
                db.execute("UPDATE system_tasks SET status='running',attempt=?,started_at=?,updated_at=?,message='' WHERE id=? AND status='queued'",(number,now,now,task['id']))
                db.execute('INSERT INTO system_task_attempts(task_id,owner,number,status,started_at) VALUES(?,?,?,?,?)',(task['id'],task['owner'],number,'running',now))
                task.update(status='running',attempt=number);admitted.append(task);active.append(task)
                self._event(db,task['owner'],task['id'])
        for task in admitted:
            self.jobs[task['id']]=asyncio.create_task(self._run(task),name='system-'+task['id'])

    async def _loop(self):
        while not self.stopping:
            try:await self.tick()
            except Exception:log.exception('System Task dispatch failed')
            await asyncio.sleep(self.poll_seconds)
