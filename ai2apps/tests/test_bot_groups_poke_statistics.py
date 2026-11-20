import json
import pytest
from ai2apps.messager.bots import BotDirectory
from ai2apps.messager.statistics import statistics
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_app_chat_durable import response,bind_identity


def test_groups_defaults_moves_delete_and_isolation(runtime):
    bot,sid,*_=setup(runtime);d=runtime.messager_bots
    from ai2apps.messager.creation import create
    from test_bot_creation import draft
    flash=create(runtime,'local',draft(runtime,model_id=None,bot_type='flash',definition={'execution_mode':'flash','config':{'workflow_id':'calculator','workflow_version':'1'}}))
    assert next(b for b in d.list('local') if b['id']==flash['id'])['group_id']=='quick'
    group=d.groups.create('local','Work')
    d.set_order('local',[flash['id'],bot['id']],{'bot_id':flash['id'],'group_id':group})
    assert d.list('local')[0]['id']==flash['id']
    g=next(g for g in d.groups.list('local') if g['id']==group)
    d.groups.update('local',group,g['revision'],collapsed=True)
    assert next(g for g in BotDirectory(runtime.database).groups.list('local') if g['id']==group)['collapsed']
    with pytest.raises(ValueError):d.groups.update('local',group,g['revision'],delete=True)
    with pytest.raises(PermissionError):d.groups.move('other',bot['id'],group)
    g=next(g for g in d.groups.list('local') if g['id']==group)
    d.groups.update('local',group,g['revision'],delete=True)
    assert next(b for b in d.list('local') if b['id']==flash['id'])['group_id'] is None
    quick=next(g for g in d.groups.list('local') if g['id']=='quick')
    with pytest.raises(ValueError):d.groups.update('local','quick',quick['revision'],delete=True)
    assert d.identity('local',{'bot_id':flash['id']})['name']


@pytest.mark.asyncio
async def test_poke_is_one_durable_role_aware_activation(runtime):
    bot,sid,*_=setup(runtime);calls=[]
    async def model(request):
        calls.append(request)
        assert 'user pressed Poke' in request['messages'][0]['content']
        assert bot['duty'] in request['messages'][0]['content']
        return response(text=json.dumps({'kind':'reply','text':'Hello, how can I help?'}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'poke-once','👋 Poke','fixture',[],poke=True)
        assert runtime.messager_dialogue.submit(P(),bot['id'],sid,'poke-once','👋 Poke','fixture',[],poke=True)==rid
        with pytest.raises(ValueError):runtime.messager_dialogue.submit(P(),bot['id'],sid,'poke-once','👋 Poke','fixture',[])
        await wait(runtime,rid,'completed')
        assert len(calls)==1
        assert runtime.agents.get_run(rid).input['owner_context']['activation']=='poke'
        assert runtime.app_chat.message_page(P(),sid)['items'][0]['content']=='👋 Poke'
    finally:await runtime.agent_runtime.stop()


def test_statistics_owned_observations_points_and_currency(runtime):
    bot,sid,*_=setup(runtime)
    run,_=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.messager.dialogue',input={})
    for i in range(2):
        step,_=runtime.agents.create_step(run_id=run.id,action_key='model-'+str(i),kind='model',input={})
        from ai2apps.agents.models import RunStepStatus
        runtime.agents.settle_step(step.id,status=RunStepStatus.COMPLETED,output={'id':'same-result','usage':{'prompt_tokens':10,'completion_tokens':3,'providerCurrencyCost':{'currency':'USD','amount':'0.01'}},'ai2apps_cloud':{'requestId':'same-request','points':{'charged':'2'}}})
    result=statistics(runtime,'local',bot['id'])
    assert result['usage']['input_tokens']==20 and result['usage']['output_tokens']==6
    assert result['usage']['known_charged_points']=='2'
    assert result['usage']['currency_costs']=={'USD':'0.01'}
    with pytest.raises(PermissionError):statistics(runtime,'foreign',bot['id'])


def test_group_move_and_order_roll_back_together(runtime):
    bot,*_=setup(runtime);d=runtime.messager_bots
    before=[b['id'] for b in d.list('local')]
    with pytest.raises(PermissionError):d.set_order('local',before,{'bot_id':bot['id'],'group_id':'unknown'})
    assert [b['id'] for b in d.list('local')]==before
    assert next(b for b in d.list('local') if b['id']==bot['id'])['group_id'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('mobile',[False,True])
async def test_group_http_owner_paths_and_statistics(runtime,mobile):
    import httpx
    from dataclasses import replace
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from ai2apps.api.messager_mobile import create_messager_mobile_router
    bot,*_=setup(runtime)
    principal=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home') if mobile else P()
    app=FastAPI();app.include_router((create_messager_mobile_router if mobile else create_messager_router)(lambda:runtime,lambda:principal))
    prefix='/messager-mobile' if mobile else '/messager'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture',headers={'Origin':'http://fixture'}) as client:
        created=await client.post(prefix+'/bot-groups',json={'name':'Research'})
        assert created.status_code==200,created.text
        group=next(g for g in created.json()['items'] if not g['permanent'])
        moved=await client.put(prefix+'/bots-order',json={'ids':[bot['id']],'move':{'bot_id':bot['id'],'group_id':group['id']}})
        assert moved.status_code==200,moved.text
        assert next(b for b in moved.json()['items'] if b['id']==bot['id'])['group_id']==group['id']
        removed=await client.request('DELETE',prefix+'/bot-groups/'+group['id'],json={'revision':group['revision']})
        assert removed.status_code==200,removed.text
        assert next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])['group_id'] is None
        if not mobile:assert (await client.get(prefix+'/bots/'+bot['id']+'/statistics')).status_code==200


def test_flash_rejects_poke_without_messages_or_work(runtime):
    from test_flash_bots import prepare
    bot,sid=prepare(runtime)
    with pytest.raises(ValueError):runtime.messager_dialogue.submit(P(),bot['id'],sid,'poke-flash','👋 Poke','unused',[],poke=True)
    assert runtime.app_chat.message_page(P(),sid)['items']==[]
    assert runtime.todo.store.snapshot('local')['runs']==[]


@pytest.mark.asyncio
async def test_consecutive_pokes_quote_prose_history_as_data(runtime):
    bot,sid,*_=setup(runtime);calls=[]
    async def model(request):
        calls.append(request)
        assert len(request['messages'])==2
        activation=json.loads(request['messages'][-1]['content'])
        assert activation['activation']=='poke'
        if len(calls)>1:assert any(m['role']=='assistant' and m['content']=='Hello again' for m in activation['recent_conversation'])
        return response(text=json.dumps({'kind':'reply','text':'Hello again'}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        for key in ('first','second','third'):
            rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,key,'👋 Poke','fixture',[],poke=True)
            await wait(runtime,rid,'completed')
        assert len(calls)==3
    finally:await runtime.agent_runtime.stop()


def test_statistics_timezones_periods_and_billed_failed_format(runtime):
    from datetime import UTC,datetime,timedelta
    from ai2apps.agents.models import RunStepStatus
    from ai2apps.messager.statistics import time_window
    bot,sid,*_=setup(runtime);clock=datetime(2026,11,7,3,tzinfo=UTC)
    run,_=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.messager.dialogue',input={})
    for days in (0,2,12,40):
        step,_=runtime.agents.create_step(run_id=run.id,action_key='period-'+str(days),kind='model',input={})
        stamp=(clock-timedelta(days=days)).isoformat()
        runtime.agents.settle_step(step.id,status=RunStepStatus.COMPLETED,output={'usage':{'prompt_tokens':10,'completion_tokens':1}})
        with runtime.database.transaction(write=True) as db:db.execute('UPDATE run_steps SET started_at=?,finished_at=? WHERE id=?',(stamp,stamp,step.id))
    for period,count in [('today',1),('7d',2),('30d',3),('all',4)]:
        result=statistics(runtime,'local',bot['id'],period=period,timezone_name='Asia/Shanghai',now=clock)
        assert result['usage']['input_tokens']==count*10
    start,_=time_window('today','Asia/Shanghai',clock)
    assert start.astimezone(UTC).isoformat()=='2026-11-06T16:00:00+00:00'
    failed,_=runtime.agents.create_step(run_id=run.id,action_key='bad-format',kind='model',input={})
    runtime.agents.settle_step(failed.id,status=RunStepStatus.FAILED,error={'code':'AI_STRUCTURED_OUTPUT_INVALID','details':{'requestId':'billed-error','usage':{'inputTokens':17,'outputTokens':2},'points':{'charged':'1'}}})
    with runtime.database.transaction(write=True) as db:db.execute('UPDATE run_steps SET started_at=?,finished_at=? WHERE id=?',(clock.isoformat(),clock.isoformat(),failed.id))
    v=statistics(runtime,'local',bot['id'],period='today',now=clock)
    assert v['usage']['input_tokens']==27 and v['usage']['output_tokens']==3
    assert v['usage']['known_charged_points']=='1' and v['usage']['failed_billed_calls']==1
    for period,zone in [('invalid','UTC'),('today','not-a-zone')]:
        with pytest.raises(ValueError):time_window(period,zone,clock)


def test_task_statistics_include_only_exact_logical_task_planning_and_workers(runtime):
    from ai2apps.agents.models import RunStepStatus
    bot,sid,*_=setup(runtime);service=runtime.messager_dialogue
    runs=[]
    for n in range(3):
        run,_=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.messager.dialogue',input={})
        step,_=runtime.agents.create_step(run_id=run.id,action_key='task-usage',kind='model',input={})
        runtime.agents.settle_step(step.id,status=RunStepStatus.COMPLETED,output={'usage':{'prompt_tokens':10,'completion_tokens':1}});runs.append(run.id)
    with runtime.database.transaction(write=True) as db:db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,?,NULL)",('usage-task','local',bot['id'],sid,runs[0],'Owned task',runs[1]))
    service.sessions.link(service.row('usage-task'))
    assert statistics(runtime,'local',bot['id'],task_session_id='usage-task')['usage']['input_tokens']==20
    assert statistics(runtime,'local',bot['id'])['usage']['input_tokens']==30
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):statistics(runtime,'local',other['id'],task_session_id='usage-task')
    with pytest.raises(PermissionError):statistics(runtime,'local',bot['id'],todo_task_id='foreign-task')


@pytest.mark.asyncio
@pytest.mark.parametrize('mobile',[False,True])
async def test_statistics_http_period_timezone_and_task_guard(runtime,mobile):
    import httpx
    from dataclasses import replace
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from ai2apps.api.messager_mobile import create_messager_mobile_router
    bot,*_=setup(runtime)
    principal=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home') if mobile else P()
    app=FastAPI();app.include_router((create_messager_mobile_router if mobile else create_messager_router)(lambda:runtime,lambda:principal))
    prefix=('/messager-mobile' if mobile else '/messager')+'/bots/'+bot['id']+'/statistics'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        value=await client.get(prefix+'?period=today&timezone_name=Asia%2FShanghai')
        assert value.status_code==200,value.text
        assert value.json()['period']=='today' and value.json()['start'].endswith('00:00:00+08:00')
        assert (await client.get(prefix+'?period=not-a-period')).status_code==(409 if mobile else 422)
        assert (await client.get(prefix+'?timezone_name=not-a-zone')).status_code==409
        assert (await client.get(prefix+'?todo_task_id=foreign')).status_code in (403,404)


def test_group_order_survives_reopen_and_rejects_stale_or_foreign_ids(runtime):
    groups=runtime.messager_bots.groups
    a=groups.create('local','A');b=groups.create('local','B')
    groups.reorder('local',[b,'quick',a])
    reopened=BotDirectory(runtime.database).groups
    assert [g['id'] for g in reopened.list('local')]==[b,'quick',a]
    for ids in ([b,b,a],[b,a],['foreign','quick',a]):
        with pytest.raises(ValueError):groups.reorder('local',ids)
    assert [g['id'] for g in reopened.list('local')]==[b,'quick',a]
    c=groups.create('local','C')
    assert [g['id'] for g in reopened.list('local')]==[b,'quick',a,c]
    assert [g['id'] for g in reopened.list('other')]==['quick']
    row=next(g for g in reopened.list('local') if g['id']==a)
    groups.update('local',a,row['revision'],delete=True)
    assert [g['id'] for g in reopened.list('local')]==[b,'quick',c]


def test_task_usage_rolls_up_delegations_and_tool_receipts_once(runtime):
    from ai2apps.agents.models import RunStepStatus
    from ai2apps.services.models import ToolInvocationStatus

    bot, sid, *_ = setup(runtime)
    child = runtime.messager_bots.create('local', 'Child', 'Help')
    grandchild = runtime.messager_bots.create('local', 'Grandchild', 'Help')
    child_sid = runtime.app_chat.open(P(), 'ai2apps.messager.bots', {'bot_id': child['id']}, {})
    grandchild_sid = runtime.app_chat.open(P(), 'ai2apps.messager.bots', {'bot_id': grandchild['id']}, {})

    def new_run(session):
        return runtime.agents.create_run(session_id=session, agent_key='ai2apps.messager.dialogue', input={})[0]

    def job(ref, owner, session, worker):
        source = new_run(session)
        with runtime.database.transaction(write=True) as db:
            db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,?,NULL)",
                       (ref, 'local', owner['id'], session, source.id, ref, worker.id))
        runtime.messager_dialogue.sessions.link(runtime.messager_dialogue.row(ref))

    def link(ref, source, target, run, child_job, actor='local'):
        with runtime.database.transaction(write=True) as db:
            db.execute("INSERT INTO messager_bot_delegations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,NULL,NULL)",
                       (ref, actor, source['id'], target['id'], run.session_id, run.id, 'parent', ref,
                        '{}', 'hash', 'resumed', '2099-01-01', child_job))

    def model(run, output):
        step, _ = runtime.agents.create_step(run_id=run.id, action_key='inference', kind='model', input={})
        runtime.agents.settle_step(step.id, status=RunStepStatus.COMPLETED, output=output)

    def tool(run, name, output=None, error=None):
        tool = runtime.services.get_tool(name)
        record = runtime.services.create_invocation(tool=tool, provider_key='test', caller_id='agent:test',
            session_id=run.session_id, trace_id=run.id, arguments={}, timeout_ms=100)
        runtime.services.settle_invocation(record.id, status=ToolInvocationStatus.FAILED if error else ToolInvocationStatus.COMPLETED,
                                           duration_ms=0, output=output, error=error)

    parent_run, child_run, grandchild_run, unrelated = map(new_run, (sid, child_sid, grandchild_sid, child_sid))
    job('usage-parent', bot, sid, parent_run)
    job('usage-child', child, child_sid, child_run)
    job('usage-grandchild', grandchild, grandchild_sid, grandchild_run)
    job('usage-unrelated', child, child_sid, unrelated)
    link('first', bot, child, parent_run, 'usage-child')
    link('duplicate-edge', bot, child, parent_run, 'usage-child')
    link('nested', child, grandchild, child_run, 'usage-grandchild')
    link('foreign', bot, child, parent_run, 'usage-unrelated', actor='foreign')

    model(parent_run, {'usage': {'prompt_tokens': 12, 'completion_tokens': 3},
                       'ai2apps_cloud': [{'requestId': 'parent-model', 'points': {'charged': 2}}]})
    model(child_run, {'usage': {'total_tokens': 13}, 'ai2apps_cloud': [{'requestId': 'child-model', 'points': {'charged': '1.5'}}]})
    model(unrelated, {'usage': {'total_tokens': 999}})
    tool(parent_run, 'image.generate', {'usage': {'total_tokens': 25}, 'ai2apps_cloud': [
        {'requestId': 'image', 'points': {'charged': '3.75'}},
        {'requestId': 'image', 'usage': {'inputTokens': 20, 'outputTokens': 5}},
    ]})
    tool(parent_run, 'image.generate', {'requestId': 'image', 'usage': {'totalTokens': 25}})
    tool(parent_run, 'agent.read_tool_result', {'content': {'usage': {'total_tokens': 999}}})
    tool(child_run, 'image.generate', {'artifact': {'metadata': {'usage': {'total_tokens': 999}}}})
    tool(grandchild_run, 'todo.get', error={'details': {'requestId': 'failed-billed',
        'usage': {'inputTokens': 4, 'outputTokens': 0, 'imageOutputTokens': 3}, 'points': {'charged': 0}}})
    stats = statistics(runtime, 'local', bot['id'], task_session_id='usage-parent')['task_usage']
    assert (stats['task']['tokens'], stats['task']['points']) == (15, '2')
    assert (stats['aaat']['tokens'], stats['aaat']['points']) == (25, '3.75')
    assert (stats['delegated']['tokens'], stats['delegated']['points']) == (None, None)
    assert (stats['delegated']['known_tokens'], stats['delegated']['known_points']) == (20, '1.5')
    assert (stats['total']['tokens'], stats['total']['points']) == (None, None)
    assert (stats['total']['known_tokens'], stats['total']['known_points']) == (60, '7.25')
    assert stats['total']['unreported_tokens'] == stats['total']['unreported_points'] == 1
    assert 'task_usage' not in statistics(runtime, 'local', bot['id'])
