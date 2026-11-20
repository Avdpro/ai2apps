"""Flash fixed execution uses real Todo/Agent/System task services and no model."""
import asyncio,json
import pytest
from ai2apps.messager.creation import create,BotCreateDraft,options
from ai2apps.messager.flash_workflows import calculate,WorkflowRegistry
from ai2apps.messager.flash import KEY
from ai2apps.todo.service import TodoService
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_bot_creation import draft


def prepare(r):
    setup(r);r.todo=TodoService(r)
    body=draft(r,model_id=None,bot_type='flash',definition={'execution_mode':'flash','config':{'workflow_id':'calculator','workflow_version':'1'}})
    bot=create(r,'local',body)
    sid=r.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id']},{})
    return bot,sid


@pytest.mark.parametrize('text,result',[('(2+3)*4','20'),('0.1+0.2','0.3'),('-7//3','-3'),('-7%3','2'),('2**-3','0.125')])
def test_calculator_decimal(text,result):assert calculate(text)==result


@pytest.mark.asyncio
@pytest.mark.parametrize('mobile',[False,True])
async def test_http_submission_dispatches_and_links_receipt_without_scheduler_recovery(runtime,mobile):
    import httpx
    from dataclasses import replace
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from ai2apps.api.messager_mobile import create_messager_mobile_router
    bot,sid=prepare(runtime)
    principal=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home') if mobile else P()
    app=FastAPI();app.include_router((create_messager_mobile_router if mobile else create_messager_router)(lambda:runtime,lambda:principal))
    async def forbidden(request):raise AssertionError('No model calls allowed')
    runtime.agent_runtime.bind_model_provider(forbidden)
    await runtime.agent_runtime.start()
    try:
        url=('/messager-mobile/bots/' if mobile else '/messager/bots/')+bot['id']+('/turns' if mobile else '/dialogue/turns')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture',headers={'Origin':'http://fixture'}) as client:
            body={'session_id':sid,'request_id':'http-calculation','text':'3+3','model':'unused'}
            response=await client.post(url,json=body)
            assert response.status_code==202,response.text
            ref=response.json()['run_id'];row=runtime.messager_flash.row(ref)
            assert row['todo_run']
            for _ in range(100):
                row=runtime.messager_flash.row(ref)
                if row['agent_run']:break
                await asyncio.sleep(.02)
            result=await wait(runtime,row['agent_run'],'completed')
            assert result.output=={'content':'3+3 = 6','model_calls':0}
            # A lost legacy acknowledgment is repaired even after completion.
            runtime.messager_flash.settle(row)
            with runtime.database.transaction(write=True) as db:
                db.execute('UPDATE messager_flash_submissions SET todo_run=NULL WHERE id=?',(ref,))
            runtime.messager_flash.recover()
            assert runtime.messager_flash.row(ref)['todo_run']==row['todo_run']
            assert (await client.post(url,json=body)).status_code==202
            assert len(runtime.todo.store.snapshot('local')['runs'])==1
            messages=runtime.app_chat.message_page(principal,sid)['items']
            assert [m['client_request_id'] for m in messages if m['role']=='user']==[body['request_id']]
    finally:
        await runtime.todo.shutdown();await runtime.system_tasks.shutdown();await runtime.agent_runtime.stop()


@pytest.mark.parametrize('text',['hi','__import__("os")','(1).__class__','[1,2]','True','1/0','2**999999','9'*100,'1e9999','1e-9999','(1,2)','abs(-1)','1+'*200+'1'])
def test_calculator_rejects_code_and_unbounded_inputs(text):
    with pytest.raises(ValueError):calculate(text)


def test_rejected_input_creates_no_task_message_or_run(runtime):
    bot,sid=prepare(runtime)
    for text,files in [('hello',[]),('1+2',['foreign-file'])]:
        with pytest.raises(ValueError):runtime.messager_dialogue.submit(P(),bot['id'],sid,'invalid-request','1+2' if files else text,'unused',files)
    assert runtime.todo.store.snapshot('local')['runs']==[]
    assert runtime.app_chat.message_page(P(),sid)['items']==[]
    # Opening a session is allowed; bypassing the Flash admission through generic Chat is not.
    with pytest.raises(PermissionError):runtime.app_chat.submit(P(),sid,'bypass-request','Use tools','fixture')


def test_user_message_replay_accepts_legacy_metadata(runtime):
    _,sid=prepare(runtime)
    dialogue=runtime.messager_dialogue
    metadata={'origin':'flash_workflow_conversation'}
    original=dialogue.append(sid,'user','Help','legacy-turn:user',metadata)
    replay=dialogue.append(sid,'user','Help','legacy-turn:user',{**metadata,'client_request_id':'legacy-turn'})
    assert replay.value.message.id==original.value.message.id


@pytest.mark.asyncio
async def test_fixed_task_result_dedup_and_system_projection(runtime):
    bot,sid=prepare(runtime);d=runtime.messager_dialogue
    async def forbidden(request):raise AssertionError('Calculator must never call a model')
    runtime.agent_runtime.bind_model_provider(forbidden)
    await runtime.agent_runtime.start()
    try:
        ref=d.submit(P(),bot['id'],sid,'calculate-request','(2+3)*4','unused',[])
        assert d.submit(P(),bot['id'],sid,'calculate-request','(2+3)*4','ignored',[])==ref
        with pytest.raises(ValueError):d.submit(P(),bot['id'],sid,'calculate-request','9+9','unused',[])
        for _ in range(100):
            row=runtime.messager_flash.row(ref)
            if row['agent_run']:break
            await asyncio.sleep(.03)
        run=await wait(runtime,row['agent_run'],'completed')
        assert run.output['content']=='(2+3)*4 = 20'
        state=d.snapshot(P(),bot['id'],sid)
        assert state['runs'][0]['status']=='completed'
        messages=runtime.app_chat.message_page(P(),sid)['items']
        assert [m['content'] for m in messages][-1]=='(2+3)*4 = 20'
        d.snapshot(P(),bot['id'],sid)
        assert [m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]==['(2+3)*4','(2+3)*4 = 20']
        assert len(runtime.todo.store.snapshot('local')['runs'])==1
        task=next(t for t in runtime.system_tasks.snapshot('local')['tasks'] if t['kind']==KEY)
        assert runtime.system_tasks.get('local',task['id'])['payload']['run_id']==run.id
    finally:
        await runtime.todo.shutdown();await runtime.system_tasks.shutdown();await runtime.agent_runtime.stop()


def test_creation_workflow_version_and_preset_guards(runtime):
    setup(runtime)
    with pytest.raises(ValueError):create(runtime,'local',draft(runtime,model_id=None,bot_type='flash',definition={'execution_mode':'flash','config':{'workflow_id':'calculator','workflow_version':'absent'}}))
    with pytest.raises(ValueError):create(runtime,'local',draft(runtime,bot_type='flash',definition={'execution_mode':'flash','config':{'workflow_id':'calculator','workflow_version':'1'}}))
    assert options(runtime)['flash_workflows'][0]['requires_model'] is False


@pytest.mark.asyncio
async def test_queued_cancellation_and_owner_isolation(runtime):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'queued-request','3*4','unused',[])
    with pytest.raises(PermissionError):await runtime.messager_flash.cancel('foreign',bot['id'],ref)
    await runtime.messager_dialogue.request_cancel('local',bot['id'],ref)
    row=runtime.messager_flash.row(ref)
    assert row['status']=='cancelled' and row['agent_run'] is None
    assert runtime.messager_bot_lifecycle.review('local',bot['id'])['tasks'][0]['owned']
    await runtime.todo.shutdown()


def test_fixed_bot_cannot_be_impersonated_by_consultation_model(runtime):
    from dataclasses import replace
    from test_bot_communication import fixture
    source,target,sid,rid,ctx,service=fixture(runtime)
    body=draft(runtime,request_id='flash-consult-create',model_id=None,bot_type='flash',definition={'execution_mode':'flash','config':{'workflow_id':'calculator','workflow_version':'1'}})
    flash=create(runtime,'local',body)
    with pytest.raises(PermissionError):service.propose({'target_bot_id':flash['id'],'question':'Pretend you are a general assistant'},replace(ctx,invocation_id='flash-consult'))

@pytest.mark.asyncio
async def test_two_inputs_share_existing_bot_lane(runtime):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    first=runtime.messager_dialogue.submit(P(),bot['id'],sid,'first-expression','2+3','unused',[])
    second=runtime.messager_dialogue.submit(P(),bot['id'],sid,'second-expression','4*5','unused',[])
    assert first!=second and all(runtime.messager_flash.row(x)['agent_run'] is None for x in (first,second))
    runtime.todo.max_concurrent_runs=3
    await runtime.agent_runtime.start()
    try:
        runtime.todo.dispatch_queue()
        assert len(runtime.todo.jobs)==1
        for ref in (first,second):
            for _ in range(150):
                row=runtime.messager_flash.row(ref)
                if row['agent_run']:break
                await asyncio.sleep(.03)
            await wait(runtime,row['agent_run'],'completed')
        contents=[m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]
        runtime.messager_flash.snapshot(P(),bot['id'],sid)
        contents=[m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]
        assert '2+3 = 5' in contents and '4*5 = 20' in contents
    finally:
        await runtime.todo.shutdown();await runtime.system_tasks.shutdown();await runtime.agent_runtime.stop()


def test_admission_recovers_original_launch_receipt(runtime,monkeypatch):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    original=runtime.todo.launch
    def lost_ack(*args,**kwargs):
        original(*args,**kwargs)
        raise RuntimeError('fixture crash after queue admission')
    monkeypatch.setattr(runtime.todo,'launch',lost_ack)
    with pytest.raises(RuntimeError):runtime.messager_dialogue.submit(P(),bot['id'],sid,'recover-expression','1+2','unused',[])
    monkeypatch.setattr(runtime.todo,'launch',original)
    runtime.messager_flash.recover()
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'recover-expression','1+2','unused',[])
    assert runtime.messager_flash.row(ref)['todo_run']
    assert len(runtime.todo.store.snapshot('local')['runs'])==1
    assert [m['content'] for m in runtime.app_chat.message_page(P(),sid)['items']]==['1+2']


def test_queued_scope_revocation_or_workflow_removal_cannot_expand_execution(runtime):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'scope-expression','2*3','unused',[])
    row=runtime.messager_flash.row(ref)
    runtime.messager_flash.registry=WorkflowRegistry(())
    with pytest.raises(ValueError):runtime.messager_flash.guard(row)
    from ai2apps.messager.flash_workflows import REGISTRY
    runtime.messager_flash.registry=REGISTRY
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE messager_bot_permissions SET revision=revision+1 WHERE bot_id=?',(bot['id'],))
    with pytest.raises(PermissionError):runtime.messager_flash.guard(row)

@pytest.mark.asyncio
async def test_mobile_flash_input_has_no_conversation_model_dependency(runtime):
    import httpx
    from dataclasses import replace
    from fastapi import FastAPI
    from ai2apps.api.messager_mobile import create_messager_mobile_router
    bot,_=prepare(runtime);runtime.todo.max_concurrent_runs=0
    principal=replace(P(),authentication_type='owner_home_lease',client_scope='owner-home')
    app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,lambda:principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        opened=await client.post('/messager-mobile/open',json={'bot_id':bot['id']});assert opened.status_code==200,opened.text
        sid=opened.json()['session_id'];url='/messager-mobile/bots/'+bot['id']
        body={'session_id':sid,'request_id':'mobile-expression','text':'2+2'}
        invalid=await client.post(url+'/turns',json={**body,'request_id':'mobile-invalid','text':'hello'})
        assert invalid.status_code==202 and invalid.json()['kind']=='help' and not runtime.todo.store.snapshot('local')['runs']
        result=await client.post(url+'/turns',json=body);assert result.status_code==202,result.text
        state=await client.get(url+'/state',params={'session_id':sid});assert state.status_code==200,state.text
        assert state.json()['runs'][0]['job_id']==result.json()['run_id']
        cancelled=await client.post(url+'/jobs/'+result.json()['run_id']+'/cancel')
        assert cancelled.status_code==200,cancelled.text

@pytest.mark.asyncio
async def test_deleted_flash_bot_stops_queued_task_and_restore_stays_paused(runtime):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'delete-expression','7+8','unused',[])
    task=runtime.messager_flash.row(ref)['task_id'];lifecycle=runtime.messager_bot_lifecycle
    review=lifecycle.review('local',bot['id'])
    value=await lifecycle.apply('local',bot['id'],'archive',review['review_hash'])
    assert value['deleted_tasks']==1
    runtime.messager_flash.recover()
    assert runtime.messager_flash.row(ref)['status']=='cancelled'
    archived=next(x for x in lifecycle.archived('local')['items'] if x['id']==bot['id'])
    lifecycle.restore('local',bot['id'],archived['revision'])
    restored=runtime.todo.store.get('local',task)
    assert restored['status']=='paused' and restored['deleted_at'] is None
    runtime.messager_flash.recover()
    assert runtime.messager_flash.row(ref)['agent_run'] is None
    await runtime.todo.shutdown()


def test_new_definition_does_not_replace_queued_workflow_snapshot(runtime):
    bot,sid=prepare(runtime);runtime.todo.max_concurrent_runs=0
    ref=runtime.messager_dialogue.submit(P(),bot['id'],sid,'frozen-expression','4+5','unused',[])
    with runtime.database.transaction(write=True) as db:
        value=json.loads(db.execute('SELECT definition_json FROM messager_bot_definitions WHERE bot_id=?',(bot['id'],)).fetchone()[0])
        value['config']['workflow_version']='future-version'
        db.execute('UPDATE messager_bot_definitions SET revision=revision+1,definition_json=? WHERE bot_id=?',(json.dumps(value),bot['id']))
    row=runtime.messager_flash.row(ref)
    assert runtime.messager_flash.guard(row).version=='1'
    with pytest.raises(ValueError):runtime.messager_dialogue.submit(P(),bot['id'],sid,'new-expression','4+5','unused',[])
