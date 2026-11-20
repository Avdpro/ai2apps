"""One System clock with durable Todo runs; fixture providers, no live effects."""
import asyncio,json
from datetime import UTC,datetime
import pytest
from test_app_interactions import runtime,wait
from test_bot_plan_access import prepare
from test_bot_todo_execution import P,until
from test_app_chat_durable import bind_identity,response
from ai2apps.todo.system_schedules import KIND


@pytest.mark.asyncio
async def test_bot_plan_is_in_system_directory_and_only_system_clock_triggers(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    system=runtime.system_tasks
    listed=[s for s in system.snapshot('local')['schedules'] if s['kind']==KIND]
    assert len(listed)==1 and listed[0]['name']=='Fixture plan' and listed[0]['can_disable']
    assert not system.snapshot('other')['schedules']
    scheduled=listed[0];now=datetime.fromtimestamp(scheduled['next_run']+1,UTC)
    runtime.todo.tick(now)
    assert runtime.todo.store.snapshot('local')['runs']==[]
    async def model(request):return response(text='Done')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    system.clock=lambda:now.timestamp()
    await system.tick();await asyncio.sleep(.1)
    with runtime.todo.store.connect() as db:rows=db.execute('SELECT * FROM runs WHERE owner=? AND task_id=?',('local',saved['task_id'])).fetchall()
    assert len(rows)==1,([(t['kind'],t['status'],t['message']) for t in system.snapshot('local')['tasks']],[(s['next_run'],s['error']) for s in system.snapshot('local')['schedules']])
    def actual_run():
        with runtime.todo.store.connect() as db:row=db.execute('SELECT data FROM runs WHERE id=?',(rows[0]['id'],)).fetchone()
        return json.loads(row[0]).get('agent_run_id')
    agent_id=await until(actual_run)
    await wait(runtime,agent_id,'completed')
    def finished():
        with runtime.todo.store.connect() as db:return db.execute('SELECT status FROM runs WHERE id=?',(rows[0]['id'],)).fetchone()[0]=='completed'
    await until(finished)
    await system.tick();await asyncio.sleep(.1)
    with runtime.todo.store.connect() as db:assert db.execute('SELECT count(*) FROM runs WHERE task_id=?',(saved['task_id'],)).fetchone()[0]==1
    updated=next(s for s in system.snapshot('local')['schedules'] if s['id']==scheduled['id'])
    assert updated['next_run']>now.timestamp()
    await runtime.todo.shutdown();await runtime.system_tasks.shutdown();await runtime.agent_runtime.stop()


def test_system_disable_does_not_revoke_bot_access(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    schedule=next(s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND)
    with pytest.raises(KeyError):runtime.system_tasks.disable_schedule('other',schedule['id'])
    runtime.system_tasks.disable_schedule('local',schedule['id'])
    assert not [s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['id']==schedule['id']]
    assert runtime.todo.store.get('local',saved['task_id'])['schedule']['frequency']=='off'
    assert runtime.messager_bot_app_access.granted('local',bot['id'],p)
    runtime.todo.system_schedules().sync()
    assert not [s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['id']==schedule['id']]


@pytest.mark.asyncio
async def test_queued_system_admission_keeps_original_plan_snapshot(runtime):
    bot,sid,calls,p,tasks,item,saved,old=prepare(runtime)
    schedule=next(s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND)
    queued=runtime.system_tasks.start_schedule('local',schedule['id'])
    d=runtime.messager_dialogue;rid=d.submit(P(),bot['id'],sid,'change','Run at seven instead','fixture',[])
    review=d.plans.prepare('local',bot['id'],runtime.agents.get_run(rid),saved['task_id'],{'hour':7})
    d.plans.decide('local',bot['id'],review['id'],review['review_hash'],'approve','fixed',[p.app_id])
    await runtime.system_tasks.tick();await asyncio.sleep(.1)
    result=runtime.system_tasks.get('local',queued['id'])['result']
    with runtime.todo.store.connect() as db:run=json.loads(db.execute('SELECT data FROM runs WHERE id=?',(result['todo_run_id'],)).fetchone()[0])
    assert run['execution_binding']['binding']['proposal_id']==old['proposal_id']
    assert run['snapshot']['schedule']['hour']==6
    assert runtime.todo.store.get('local',saved['task_id'])['schedule']['hour']==7
    await runtime.todo.shutdown();await runtime.system_tasks.shutdown();await runtime.agent_runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('action,delete_tasks',[('archive',False),('clear_dialogue',True),('clear_dialogue',False)])
async def test_bot_cleanup_task_deletion_and_restore_stays_disabled(runtime,action,delete_tasks):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    lifecycle=runtime.messager_bot_lifecycle
    review=lifecycle.review('local',bot['id'])
    await lifecycle.apply('local',bot['id'],action,review['review_hash'],delete_tasks=delete_tasks)
    task=runtime.todo.store.get('local',saved['task_id'])
    assert bool(task.get('deleted_at'))==(action=='archive' or delete_tasks)
    with runtime.database.transaction() as db:
        policy=db.execute('SELECT status FROM messager_task_access_policies WHERE id=?',(item['id'],)).fetchone()
    assert policy['status']==('revoked' if action=='archive' or delete_tasks else 'approved')
    if action=='clear_dialogue' and delete_tasks:
        with runtime.database.transaction(write=True) as db:
            db.execute("UPDATE messager_task_access_policies SET status='approved' WHERE id=?",(item['id'],))
        tasks.recover()
        assert tasks.access.audit('local',bot['id'])[0]['status']=='revoked'
    if action=='clear_dialogue':
        new=runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id']},{})
        assert new!=sid and runtime.app_chat.message_page(P(),new)['items']==[]
    assert not [s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND]
    if action=='archive':
        archived=next(x for x in lifecycle.archived('local')['items'] if x['id']==bot['id'])
        lifecycle.restore('local',bot['id'],archived['revision'])
        restored=runtime.todo.store.get('local',saved['task_id'])
        assert not restored['deleted_at'] and restored['status']=='paused' and restored['next_due'] is None
        runtime.todo.system_schedules().sync()
        assert not [s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND]
    else:assert runtime.messager_bot_app_access.granted('local',bot['id'],p)


@pytest.mark.asyncio
async def test_unreviewed_project_edit_cannot_use_old_timer_definition(runtime):
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    schedule=next(s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND)
    with runtime.todo.store.connect() as db:
        data=json.loads(db.execute('SELECT data FROM tasks WHERE id=?',(saved['task_id'],)).fetchone()[0]);data['description']='Unreviewed changed instructions'
        db.execute('UPDATE tasks SET data=?,revision=revision+1 WHERE id=?',(json.dumps(data),saved['task_id']))
    runtime.system_tasks.clock=lambda:schedule['next_run']+1
    await runtime.system_tasks.tick()
    with runtime.todo.store.connect() as db:assert db.execute('SELECT count(*) FROM runs WHERE task_id=?',(saved['task_id'],)).fetchone()[0]==0
    runtime.todo.system_schedules().sync()
    assert not [s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND]
    await runtime.system_tasks.shutdown()


@pytest.mark.asyncio
async def test_cancel_recovers_child_from_original_launch_receipt_before_checkpoint(runtime):
    from ai2apps.system_tasks.service import TaskContext
    from ai2apps.system_tasks.sessions import execution_principal
    bot,sid,calls,p,tasks,item,saved,b=prepare(runtime)
    bridge=runtime.todo.system_schedules();schedule=next(s for s in runtime.system_tasks.snapshot('local')['schedules'] if s['kind']==KIND)
    parent=runtime.system_tasks.start_schedule('local',schedule['id'])
    child=runtime.todo.launch('local',saved['task_id'],principal=execution_principal(runtime,'local'),request_key='system-todo:'+parent['id'],admitted=parent['payload'])
    assert not parent['checkpoint'].get('todo_run_id')
    await bridge.cancel(TaskContext(runtime.system_tasks,parent),False)
    with runtime.todo.store.connect() as db:assert db.execute('SELECT status FROM runs WHERE id=?',(child['id'],)).fetchone()[0]=='cancelled'
    await runtime.todo.shutdown()
