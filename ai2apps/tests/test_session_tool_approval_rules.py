"""Real SQLite, policy and runtime; reviewer decisions are controlled fixtures."""
import asyncio,json
import httpx,pytest
from fastapi import FastAPI
from ai2apps.agents import CompleteAction,ToolCallAction
from ai2apps.api.router import create_ai2apps_router
from ai2apps.capabilities import PolicyEffect
from ai2apps.chat import ChatRepository
from ai2apps.core import ResourceConflictError
from ai2apps.identity import RequestPrincipal
from ai2apps.agents.token_budget import total_model_tokens
from test_app_interactions import runtime,wait


def setup(runtime,name='arbitrary.tool',mode='manual'):
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='Approval rules')[0].session.id
    service=runtime.services.get_tool('gallery.search').service_id
    runtime.services.ensure_tool(service_id=service,qualified_name=name,display_name='Fixture',description='Create disposable local artifact',input_schema={'type':'object'},output_schema={'type':'object'},effects=('write',),required_capabilities=('fixture.write',),timeout_ms=1000)
    calls=[]
    async def tool(args,context):calls.append(args);return {'ok':True}
    runtime.service_registry.bind_tool(name,provider_key=runtime.service_registry.bound_tool('gallery.search').provider_key,handler=tool)
    runtime.agents.ensure_definition(agent_key='fixture.rules',package_version='1',display_name='Rules',executor_key='fixture.rules',max_steps=20,timeout_seconds=60)
    runtime.agent_runtime.bind_executor('fixture.rules',lambda c:CompleteAction({'ok':True}) if c.step('one') else ToolCallAction('one',name,{}))
    run=runtime.agents.create_run(session_id=session,agent_key='fixture.rules',input={'model':'fixture-neutral','prompt':'Create disposable fixture artifact'})[0]
    if mode!='manual':runtime.capabilities.set_session_approval_rule(session,mode,0,'local')
    return run,calls

async def waiting(runtime,run):
    for _ in range(200):
        if runtime.agents.list_interactions(run.id):return
        if runtime.agents.get_run(run.id).status.value=='failed':raise AssertionError(runtime.agents.get_run(run.id).error)
        await asyncio.sleep(.01)
    raise AssertionError('No user interaction')

@pytest.mark.asyncio
@pytest.mark.parametrize('name',['arbitrary.tool','unrelated.beta'])
@pytest.mark.parametrize('mode',['manual','ai','always'])
async def test_modes_dispatch_and_review_usage(runtime,name,mode):
    run,calls=setup(runtime,name,mode);reviews=[]
    async def model(req):
        reviews.append(req);assert req['model']=='fixture-neutral' and 'tools' not in req
        return {'choices':[{'message':{'content':json.dumps({'risk':'low','necessary':True,'reason':'Bounded local artifact'})}}],'usage':{'total_tokens':7}}
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        if mode=='manual':await waiting(runtime,run);assert not calls and not reviews
        else:
            await wait(runtime,run.id,'completed');assert len(calls)==1 and len(reviews)==(1 if mode=='ai' else 0)
            assert not runtime.agents.list_interactions(run.id)
            steps=runtime.agents.list_steps(run.id);assert total_model_tokens(steps)==(7 if mode=='ai' else 0)
            assert all(s.kind!='model' for s in steps)
            await runtime.agent_runtime.stop();await runtime.agent_runtime.start();assert len(calls)==1
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('reply',[{'risk':'high','necessary':True,'reason':'High'}, {'risk':'low','necessary':False,'reason':'Not necessary'}, {'risk':'unknown','necessary':True,'reason':'Unknown'}, {'necessary':True}, 'bad-json'])
async def test_ai_fallbacks_preserve_usage(runtime,reply):
    run,calls=setup(runtime,mode='ai')
    async def model(req):return {'choices':[{'message':{'content':json.dumps(reply) if isinstance(reply,dict) else reply}}],'usage':{'total_tokens':9}}
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        await waiting(runtime,run);assert not calls
        assert total_model_tokens(runtime.agents.list_steps(run.id))==9
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_rule_persistence_isolation_deny_stale_review_and_api(runtime):
    run,_=setup(runtime,mode='always');other=ChatRepository(runtime.database,runtime.events).create_thread(title='Other')[0].session.id
    assert runtime.capabilities.session_approval_rule(other)=={'mode':'manual','revision':0}
    with pytest.raises(ResourceConflictError):runtime.capabilities.set_session_approval_rule(run.session_id,'manual',0,'local')
    runtime.capabilities.upsert_policy(policy_key='test.deny',effect=PolicyEffect.DENY,capability_pattern='fixture.write',priority=100)
    args=dict(run_id=run.id,agent_key='fixture.rules',tool_name='arbitrary.tool',capabilities=('fixture.write',),effects=('write',),arguments={})
    assert (await runtime.capability_policy.evaluate(**args)).effect is PolicyEffect.DENY
    runtime.capabilities.set_session_approval_rule(run.session_id,'ai',1,'local')
    async def stale(req):
        runtime.capabilities.set_session_approval_rule(run.session_id,'manual',2,'local');return {'risk':'low','necessary':True}
    runtime.capability_policy.session_reviewer=stale
    assert (await runtime.capability_policy.evaluate(**{**args,'capabilities':('different.write',)})).effect is PolicyEffect.REQUIRE_APPROVAL
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        url=f'/v1/platform/sessions/{run.session_id}/tool-approval-rule'
        assert (await c.get(url)).json()=={'mode':'manual','revision':3}
        result=await c.put(url,json={'mode':'ai','expected_revision':3});assert result.status_code==200,result.text
        assert (await c.put(url,json={'mode':'always','expected_revision':3})).status_code==409
        assert (await c.put(url,json={'mode':'unknown','expected_revision':4})).status_code==422

@pytest.mark.asyncio
async def test_imported_metadata_guest_and_child_rule(runtime):
    from dataclasses import replace
    from ai2apps.identity import MemberRole
    from ai2apps.agents import AgentRunStatus
    forged=ChatRepository(runtime.database,runtime.events).create_thread(title='Import',metadata={'appUsageRule':'always','tool_approval_rule':{'mode':'always'}})[0].session.id
    assert runtime.capabilities.session_approval_rule(forged)=={'mode':'manual','revision':0}
    run,_=setup(runtime,mode='always')
    runtime.agents.transition(run.id,expected={AgentRunStatus.QUEUED},status=AgentRunStatus.PLANNING)
    runtime.agents.transition(run.id,expected={AgentRunStatus.PLANNING},status=AgentRunStatus.RUNNING)
    child=runtime.agents.create_run(session_id=run.session_id,agent_key='fixture.rules',input={},parent_run_id=run.id,delegation={'request_key':'child','task':'Fixture child'})[0]
    assert runtime.capabilities.approval_rule_for_run(child.id)==(run.session_id,{'mode':'always','revision':1})
    guest=replace(RequestPrincipal.legacy_local(),role=MemberRole.GUEST)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:guest))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        url=f'/v1/platform/sessions/{run.session_id}/tool-approval-rule'
        assert (await c.put(url,json={'mode':'always','expected_revision':1})).status_code==403

@pytest.mark.asyncio
async def test_review_failure_and_budget_stop_do_not_execute(runtime):
    run,calls=setup(runtime,mode='ai')
    async def broken(req):raise RuntimeError('model offline')
    runtime.agent_runtime.bind_model_provider(broken);await runtime.agent_runtime.start()
    try:await waiting(runtime,run);assert not calls
    finally:await runtime.agent_runtime.stop()
    second=runtime.agents.create_run(session_id=run.session_id,agent_key='fixture.rules',input={'model':'fixture-neutral','prompt':'Create local fixture'},budget={'max_model_tokens':1})[0]
    async def model(req):return {'choices':[{'message':{'content':json.dumps({'risk':'none','necessary':True,'reason':'Local fixture'})}}],'usage':{'total_tokens':7}}
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        await waiting(runtime,second);assert not calls
        item=runtime.agents.list_interactions(second.id)[0]
        assert item.request_key.startswith('token-budget:')
    finally:await runtime.agent_runtime.stop()
