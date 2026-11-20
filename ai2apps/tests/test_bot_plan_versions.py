import json
from types import SimpleNamespace
import pytest
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime
from test_bot_todo_execution import setup,P


def plan_fixture(runtime):
    bot,sid,tasks=setup(runtime)
    from ai2apps.todo.service import TodoService
    if runtime.todo is None:runtime.todo=TodoService(runtime)
    source=runtime.app_chat.submit(P(),sid,'schedule-original','Create a daily plan','fixture')
    proposed=tasks.propose({'title':'Clean logs','prompt':'Remove old logs only.','schedule':{'frequency':'daily','hour':0,'timezone':'Asia/Shanghai'}},SimpleNamespace(actor_user_id='local',session_id=sid,trace_id=source,invocation_id='plan-original'))
    review=next(p for p in tasks.work('local',bot['id'])['proposals'] if p['id']==proposed['proposal_id'])
    saved=tasks.decide('local',bot['id'],review['id'],review['review_hash'],'approve')
    return bot,sid,saved['task_id']


def test_plan_revision_keeps_task_identity_and_old_run_binding_while_future_uses_new_version(runtime):
    bot,sid,task_id=plan_fixture(runtime);dialogue=runtime.messager_dialogue;store=runtime.todo.store
    old=store.get('local',task_id);old_binding=store.execution_binding('local',task_id)
    rid=dialogue.submit(P(),bot['id'],sid,'modify-plan','Also remove archived instances older than five days.','fixture',[])
    proposal=dialogue.plans.prepare('local',bot['id'],runtime.agents.get_run(rid),task_id,instruction_change='Remove archived instances older than five days.')
    assert store.get('local',task_id)['description']==old['description']
    result=dialogue.plans.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve');assert result['result']['plan_version']==2
    assert result['result']['task_id']==task_id and result['result']['active_runs_changed'] is False
    current=store.get('local',task_id);binding=store.execution_binding('local',task_id)
    assert current['revision']==old['revision']+1 and 'five days' in current['description']
    assert binding['binding']['proposal_id']!=old_binding['binding']['proposal_id']
    runtime.messager_task_execution.validate_task('local',old,old_binding['binding'])
    runtime.messager_task_execution.validate_task('local',current,binding['binding'])
    assert dialogue.plans.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')==result
    messages=runtime.app_chat.message_page(P(),sid)['items'];assert sum('版本 2' in m['content'] for m in messages)==1


def test_rejected_conflicting_or_revoked_plan_does_not_change_original(runtime):
    bot,sid,task_id=plan_fixture(runtime);d=runtime.messager_dialogue;store=runtime.todo.store;old=store.get('local',task_id)
    rid=d.submit(P(),bot['id'],sid,'reject-plan','Rename this to Log maintenance','fixture',[])
    p=d.plans.prepare('local',bot['id'],runtime.agents.get_run(rid),task_id,plan_title='Log maintenance')
    pending=d.plans.pending('local',bot['id'])[0]
    assert pending['value']['title']=='Log maintenance' and pending['value']['schedule']==old['schedule']
    assert pending['value']['prompt']==old['description']
    d.plans.decide('local',bot['id'],p['id'],p['review_hash'],'reject');assert store.get('local',task_id)==old
    next_run=d.submit(P(),bot['id'],sid,'revoked-plan','Add another rule','fixture',[]);p=d.plans.prepare('local',bot['id'],runtime.agents.get_run(next_run),task_id,instruction_change='Keep current logs.')
    runtime.messager_bot_permissions.invalidate('local',bot['id'])
    with pytest.raises(PermissionError):d.plans.decide('local',bot['id'],p['id'],p['review_hash'],'approve')
    assert all(store.get('local',task_id)[key]==old[key] for key in ('description','schedule','revision'))
    assert store.get('local',task_id)['next_due'] is None  # revocation independently freezes the existing plan


def test_plan_projection_recovers_after_commit_and_partial_schedule_preserves_original(runtime,monkeypatch):
    bot,sid,task_id=plan_fixture(runtime);d=runtime.messager_dialogue
    rid=d.submit(P(),bot['id'],sid,'recover-plan','Run at six instead','fixture',[])
    p=d.plans.prepare('local',bot['id'],runtime.agents.get_run(rid),task_id,{'hour':6})
    pending=d.plans.pending('local',bot['id'])[0]
    assert pending['value']['prompt']=='Remove old logs only.'
    assert pending['value']['schedule']['hour']==6 and pending['value']['schedule']['frequency']=='daily'
    project=d.plans.project
    def crash(*args):raise RuntimeError('fixture after commit before feedback')
    monkeypatch.setattr(d.plans,'project',crash)
    with pytest.raises(RuntimeError):d.plans.decide('local',bot['id'],p['id'],p['review_hash'],'approve')
    monkeypatch.setattr(d.plans,'project',project);d.plans.recover();d.plans.recover()
    saved=runtime.todo.store.get('local',task_id)
    assert saved['revision']==2 and saved['description']=='Remove old logs only.'
    assert saved['schedule']['hour']==6
    assert sum('版本 2' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items'])==1


@pytest.mark.asyncio
async def test_dialogue_routes_existing_plan_amendment_to_review_without_creating_new_task(runtime):
    from test_app_chat_durable import response
    from test_app_interactions import wait
    bot,sid,task_id=plan_fixture(runtime);d=runtime.messager_dialogue
    async def model(request):
        return response(text=json.dumps({
            'kind':'plan_update','task_id':task_id,'text':'review','schedule':{'hour':6},
            'plan_title':'Clean archived logs (daily at 06:00)','replacement_instructions':'Remove only archived logs.',
        }))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=d.submit(P(),bot['id'],sid,'route-plan','Run at six and remove only archived logs.','fixture',[])
        await wait(runtime,rid,'completed')
        result=runtime.agents.get_run(rid).output
        assert result['kind']=='plan_update' and result['job_id'] is None
        pending=d.plans.pending('local',bot['id'])
        assert len(pending)==1
        assert pending[0]['before']['title']=='Clean logs'
        assert pending[0]['value']['title']=='Clean archived logs (daily at 06:00)'
        assert pending[0]['value']['prompt']=='Remove only archived logs.'
        assert runtime.todo.store.get('local',task_id)['title']=='Clean logs'
        receipt=d.plans.decide('local',bot['id'],pending[0]['id'],pending[0]['review_hash'],'approve')
        saved=runtime.todo.store.get('local',task_id)
        assert saved['description']=='Remove only archived logs.' and saved['schedule']['hour']==6
        assert saved['title']==receipt['result']['title']==pending[0]['value']['title']
        with runtime.database.transaction() as db:
            schedule=db.execute("SELECT name FROM system_task_schedules WHERE json_extract(payload_json,'$.task.id')=?",(task_id,)).fetchone()
        assert schedule['name']==saved['title']
        assert len(runtime.todo.store.snapshot('local')['tasks'])==1
        assert any('等待你确认' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items'])
    finally:await runtime.stop_background_tasks()
