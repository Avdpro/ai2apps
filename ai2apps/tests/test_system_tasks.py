import asyncio
from types import SimpleNamespace as NS
import pytest
from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient
from ai2apps.storage import PlatformDatabase
from ai2apps.events import EventStore, EventNotificationBus
from ai2apps.system_tasks import SystemTaskService, TaskHandler
from ai2apps.identity import RequestPrincipal
from ai2apps.api.system_tasks import install_system_task_routes

@pytest.fixture
def service(tmp_path):
    database=PlatformDatabase(tmp_path/'platform.sqlite3');database.initialize()
    runtime=NS(database=database,events=EventStore(database),notifications=EventNotificationBus())
    value=SystemTaskService(runtime);runtime.system_tasks=value
    return value

def register(service,execute=None,**kwargs):
    async def default(ctx):return {'done':True}
    service.register('test.job',TaskHandler('test.app',execute or default,**kwargs))

def submit(service,owner='alice',**kwargs):
    return service.submit(owner,'test.app','test.job','Work',{'value':1},**kwargs)

async def drain(service):
    await asyncio.sleep(0)
    await asyncio.gather(*list(service.jobs.values()))

def test_frozen_inputs_active_dedup_and_owner_isolation(service):
    register(service);payload={'items':[1]}
    one=service.submit('alice','test.app','test.job','Work',payload,dedup_key='resource')
    payload['items'].append(2)
    assert service.get('alice',one['id'])['payload']=={'items':[1]}
    assert service.submit('alice','test.app','test.job','Again',{},dedup_key='resource')['id']==one['id']
    assert submit(service,'bob',dedup_key='resource')['id']!=one['id']
    with pytest.raises(KeyError):service.cancel('bob',one['id'])
    with pytest.raises(ValueError):service.submit('alice','other.app','test.job','Bad',{})
    assert not {'payload','checkpoint','result'} & service.snapshot('alice')['tasks'][0].keys()

@pytest.mark.asyncio
async def test_admission_limits_and_queue(service):
    gate=asyncio.Event();started=[]
    async def execute(ctx):started.append(ctx.id);await gate.wait();return {}
    register(service,execute);tasks=[submit(service) for _ in range(3)]
    await service.tick();await asyncio.sleep(0)
    assert len(started)==2 and service.get('alice',tasks[2]['id'])['status']=='queued'
    gate.set();await drain(service);await service.tick();await drain(service)
    assert all(service.get('alice',t['id'])['status']=='completed' for t in tasks)

@pytest.mark.asyncio
async def test_schedule_coalesces_missed_slots_manual_keeps_next_due(service):
    register(service);service.clock=lambda:1000
    service.schedule('alice','test.app','schedule','test.job','Scheduled',{},next_run=100,interval_seconds=100)
    task=service.start_schedule('alice','schedule')
    assert service.snapshot('alice')['schedules'][0]['next_run']==100
    await service.tick();await drain(service)
    schedule=service.snapshot('alice')['schedules'][0]
    assert schedule['next_run']==1100 and schedule['last_task_id']==task['id']
    assert len(service.snapshot('alice')['tasks'])==1
    service.disable_missing_schedules('alice','test.app',[])
    assert not service.snapshot('alice')['schedules']

@pytest.mark.asyncio
async def test_cancel_waits_for_cleanup_and_force_is_scoped(service):
    gate=asyncio.Event();clean=[False];calls=[]
    async def execute(ctx):ctx.report(checkpoint={'saved':1});await gate.wait()
    async def cancel(ctx,force):calls.append((ctx.id,force,ctx.checkpoint));return clean[0]
    register(service,execute,cancel=cancel,resumable=True)
    task=submit(service);await service.tick();await asyncio.sleep(0)
    service.cancel('alice',task['id']);await service.tick()
    assert service.get('alice',task['id'])['status']=='cancelling'
    service.cancel('alice',task['id'],force=True);clean[0]=True;await service.tick()
    assert service.get('alice',task['id'])['status']=='cancelled'
    assert calls[-1]==(task['id'],True,{'saved':1})
    assert service.attempts('alice',task['id'])[0]['status']=='cancelled'

@pytest.mark.asyncio
async def test_restart_preserves_checkpoint_and_attempts(service):
    gate=asyncio.Event()
    async def execute(ctx):ctx.report(checkpoint={'saved':1});await gate.wait();return {}
    register(service,execute,resumable=True)
    task=submit(service);await service.tick();await asyncio.sleep(0);await service.shutdown()
    replacement=SystemTaskService(service.runtime);register(replacement,execute,resumable=True)
    await replacement.startup()
    try:
        assert replacement.get('alice',task['id'])['checkpoint']=={'saved':1}
        assert replacement.get('alice',task['id'])['status']=='queued'
        assert replacement.attempts('alice',task['id'])[0]['status']=='interrupted'
        await replacement.tick();gate.set();await drain(replacement)
        assert [a['status'] for a in replacement.attempts('alice',task['id'])]==['completed','interrupted']
    finally:await replacement.shutdown()

@pytest.mark.asyncio
async def test_unsafe_restart_and_reauthorization(service):
    called=[]
    async def execute(ctx):called.append(ctx.id);return {}
    register(service,execute);task=submit(service)
    service._update('alice',task['id'],{'status':'running'})
    await service.startup()
    try:
        assert service.get('alice',task['id'])['status']=='interrupted'
        with pytest.raises(ValueError):service.start('alice',task['id'])
        assert not called
    finally:await service.shutdown()
    allowed=[True]
    def authorize(owner,payload):
        if not allowed[0]:raise ValueError('Permission revoked')
    service.handlers.clear();register(service,execute,authorize=authorize)
    task=submit(service);allowed[0]=False
    service.stopping=False
    await service.tick();await drain(service)
    assert service.get('alice',task['id'])['status']=='failed' and not called

def test_control_api_owner_scope_and_safe_projection(service):
    register(service);principal=RequestPrincipal.legacy_local();task=submit(service,principal.actor_user_id)
    submit(service,'other');app=FastAPI();router=APIRouter()
    install_system_task_routes(router,lambda:service.runtime,lambda:principal);app.include_router(router)
    with TestClient(app) as client:
        result=client.get('/system-tasks');assert result.status_code==200
        assert len(result.json()['tasks'])==1
        detail=client.get('/system-tasks/'+task['id']).json()
        assert not {'payload','checkpoint','result'} & detail['task'].keys()
        assert client.post('/system-tasks/'+task['id']+'/cancel',json={'force':False}).json()['status']=='cancelled'
        assert client.get('/system-tasks/missing').status_code==404

@pytest.mark.asyncio
async def test_manual_retry_is_new_task_with_handler_inputs(service):
    register(service,resumable=True,retry_payload=lambda payload:{'value':2})
    task=submit(service);await service.tick();await drain(service)
    retry=service.start('alice',task['id'])
    assert retry['id']!=task['id'] and retry['payload']=={'value':2}
    assert service.get('alice',task['id'])['status']=='completed'


def test_mobile_gateway_exposes_only_existing_owner_controls():
    from ai2apps.web.owner_home_gateway import public_allowed
    assert public_allowed('GET','/v1/mobile/todo/system-tasks')
    assert public_allowed('GET','/v1/mobile/todo/system-tasks/stask_ab12')
    assert public_allowed('POST','/v1/mobile/todo/system-tasks/stask_ab12/cancel')
    assert public_allowed('POST','/v1/mobile/todo/system-schedules/intelligence:abc/start')
    assert not public_allowed('POST','/v1/mobile/todo/system-tasks')
    assert not public_allowed('DELETE','/v1/mobile/todo/system-tasks/stask_ab12')
    assert not public_allowed('POST','/v1/mobile/todo/system-tasks/stask_ab12/shell')


@pytest.mark.asyncio
async def test_global_and_app_limits_are_shared_across_submitters(service):
    gate=asyncio.Event()
    async def execute(ctx):await gate.wait();return {}
    for app in ['a','b','c']:
        service.register(app,TaskHandler(app,execute))
    tasks=[service.submit(owner,app,app,app,{}) for app in ['a','b','c'] for owner in ['alice','bob','carol']]
    await service.tick()
    active=[service.get(t['owner'],t['id']) for t in tasks if service.get(t['owner'],t['id'])['status']=='running']
    assert len(active)==4
    assert all(sum(t['app_id']==app for t in active)<=2 for app in ['a','b','c'])
    gate.set();await drain(service)


def test_unchanged_progress_does_not_emit_heartbeat_or_change_timestamp(service):
    from ai2apps.system_tasks import TaskContext
    register(service);task=submit(service);ctx=TaskContext(service,task)
    ctx.report(message='Reading',progress={'pages':1})
    updated=service.get('alice',task['id'])['updated_at']
    service.clock=lambda:updated+900
    ctx.report(message='Reading',progress={'pages':1})
    assert service.get('alice',task['id'])['updated_at']==updated


@pytest.mark.asyncio
async def test_cancel_signals_owned_resources_before_awaiting_coroutine_exit(service):
    released=asyncio.Event();called=[]
    async def execute(ctx):
        try:await asyncio.Event().wait()
        except asyncio.CancelledError:await released.wait()
        return {}
    async def cancel(ctx,force):
        called.append(ctx.id);released.set();return True
    register(service,execute,cancel=cancel)
    task=submit(service);await service.tick();await asyncio.sleep(0)
    service.cancel('alice',task['id']);await service.tick()
    assert called==[task['id']]
    assert service.get('alice',task['id'])['status']=='cancelled'
    assert task['id'] not in service.jobs


@pytest.mark.parametrize('has_trigger',[False,True])
def test_v94_trigger_variants_upgrade_without_losing_tasks_or_schedules(tmp_path,has_trigger):
    import sqlite3
    from ai2apps.storage.migrations import MIGRATIONS, apply_migrations
    path=tmp_path/'platform.sqlite3'
    db=sqlite3.connect(path)
    apply_migrations(db,MIGRATIONS[:94])
    if has_trigger:
        db.execute("ALTER TABLE system_tasks ADD COLUMN trigger TEXT NOT NULL DEFAULT 'manual'")
    db.execute("INSERT INTO system_tasks(id,owner,app_id,kind,name,status,payload_json,run_after,created_at,updated_at) VALUES('saved','alice','test.app','test.job','Saved','queued','{}',1,1,1)")
    if has_trigger:db.execute("UPDATE system_tasks SET trigger='schedule' WHERE id='saved'")
    db.execute("INSERT INTO system_task_schedules(id,owner,app_id,kind,name,payload_json,next_run,updated_at) VALUES('daily','alice','test.app','test.job','Daily','{}',9999999999,1)")
    db.commit();db.close()
    database=PlatformDatabase(path);assert database.initialize().schema_version==98
    runtime=NS(database=database,events=EventStore(database),notifications=EventNotificationBus())
    service=SystemTaskService(runtime);register(service)
    assert service.get('alice','saved')['trigger']==('schedule' if has_trigger else 'manual')
    assert service.snapshot('alice')['schedules'][0]['id']=='daily'
    assert service.start_schedule('alice','daily')['status']=='queued'
    assert database.initialize().schema_version==98


def test_history_retention_age_count_owner_and_active(service):
    register(service)
    now=service.clock()
    ids=[]
    for i in range(105):
        task=submit(service);ids.append(task['id'])
        service._update('alice',task['id'],{'status':'completed','finished_at':now-i})
    old=submit(service,'bob')
    service._update('bob',old['id'],{'status':'failed','finished_at':now-48*3600-1})
    keep=submit(service,'bob')
    service._update('bob',keep['id'],{'status':'partial','finished_at':now})
    active=submit(service)
    service.prune_history()
    history=[t for t in service.snapshot('alice')['tasks'] if t['status']=='completed']
    assert len(history)==100
    assert [t['id'] for t in history]==ids[:100]
    assert service.get('alice',active['id'])['status']=='queued'
    with pytest.raises(KeyError):service.get('bob',old['id'])
    assert service.get('bob',keep['id'])['status']=='partial'


def test_snapshot_source_app_identity(service):
    from ai2apps.apps.system import ensure_system_apps
    ensure_system_apps(service.database,service.runtime.events)
    async def run(ctx): return {}
    service.register('intel.test',TaskHandler('ai2apps.intelligence',run))
    service.submit('alice','ai2apps.intelligence','intel.test','Refresh',{})
    register(service);submit(service)
    apps=service.snapshot('alice')['apps']
    assert apps['ai2apps.intelligence']['icon']=='satellite-dish'
    assert apps['ai2apps.intelligence']['name']=='Intel Center'
    assert apps['test.app']=={'name':'test.app','icon':'app-window'}
    assert service.snapshot('bob')['apps']=={}
