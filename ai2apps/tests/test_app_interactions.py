"""Behavioral acceptance of durable App handoffs (no UI or LLM simulation claims)."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from jsonschema import ValidationError

from ai2apps.agents import CompleteAction, ToolCallAction
from ai2apps.agents.app_interactions import interaction_action
from ai2apps.api.router import create_ai2apps_router
from ai2apps.api.intelligence import create_intelligence_router
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.identity import RequestPrincipal
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.platform_runtime import PlatformRuntime

ARGS={'request_id':'channel-1','capability':'intelligence.create_channel','parameters':{'name':'AI news','interests':'Research'}}

async def wait(runtime, rid, status):
    for _ in range(300):
        run=runtime.agents.get_run(rid)
        if run.status.value==status:return run
        if run.status.value=='failed':raise AssertionError(run.error)
        await asyncio.sleep(.01)
    raise AssertionError(run.status)

@pytest.fixture
def runtime(tmp_path):
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));runtime.start()
    yield runtime
    runtime.stop()


def setup_run(runtime, principal=None):
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Channel handoff')
    runtime.agents.ensure_definition(agent_key='test.handoff',package_version='1',display_name='Handoff',executor_key='test.handoff',max_steps=10,timeout_seconds=60)
    def execute(c):
        action=interaction_action(c,ARGS)
        if action:return action
        if not c.step('channel'):return ToolCallAction('channel','app.interact',ARGS)
        result=c.step('channel').output
        if result['status']=='cancelled':return CompleteAction({'cancelled':True})
        articles=result['result']['articles']
        return CompleteAction({'brief':'\n'.join(a['title']+': '+a['summary'] for a in articles), 'channel_id':result['result']['channel']['id']})
    runtime.agent_runtime.bind_executor('test.handoff',execute)
    return runtime.agents.create_run(session_id=thread.session.id,agent_key='test.handoff',input={})[0]


def client_app(runtime, principal=RequestPrincipal.legacy_local):
    app=FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=principal))
    app.include_router(create_intelligence_router(lambda:runtime,principal),prefix='/v1/platform')
    return app

@pytest.mark.asyncio
async def test_channel_creation_resume_and_duplicate_completion(runtime,monkeypatch):
    # Only section/taxonomy LLM planning is deterministic; APIs, DB, scheduler and Tool are production code.
    async def plan(*args):return []
    monkeypatch.setattr('ai2apps.intelligence.service.plan_sections',plan)
    monkeypatch.setattr('ai2apps.intelligence.entity_categories.plan',plan)
    run=setup_run(runtime)
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0]
        from ai2apps.core import ResourceConflictError
        with pytest.raises(ResourceConflictError):
            runtime.agents.respond_interaction(run.id,item.id,response={'status':'completed','result':{}},response_id='bypass')
        # Stop/restart scheduling while the interaction is persisted.
        await runtime.agent_runtime.stop()
        await runtime.agent_runtime.start()
        assert runtime.agents.list_interactions(run.id)[0].id==item.id
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as client:
            base=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}'
            context=await client.get(base+'/handoff')
            assert context.status_code==200,context.text
            assert context.json()['origin']['session_id']==run.session_id
            forged=await client.post(base+'/respond',json={'response_id':'forged','response':{'status':'completed','result':{}}})
            assert forged.status_code==409
            url=f'/v1/platform/intelligence/channels?handoff_run={run.id}&handoff_id={item.id}'
            body={'name':'Research','interests':'AI','interval_hours':0}
            created=await client.post(url,json=body)
            assert created.status_code==200,created.text
            duplicate=await client.post(url,json=body)
            assert duplicate.json()['id']==created.json()['id']
            assert runtime.agents.get_run(run.id).status.value=='waiting_input'
            store=IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence')
            store.import_article('local',created.json()['id'],{'title':'Acceptance fixture','summary':'A supplied test article, not real news.','sources':[{'url':'https://example.org/fixture'}]},'fixture-1')
            end=f'/v1/platform/intelligence/handoffs/{run.id}/{item.id}/complete'
            completed=await client.post(end)
            assert completed.status_code==200,completed.text
            final=await wait(runtime,run.id,'completed')
            assert 'supplied test article' in final.output['brief']
            assert final.session_id==run.session_id
            replay=await client.post(end)
            assert replay.json()==completed.json()
            assert len(store.snapshot('local')['channels'])==1
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_cancelled_origin_cannot_resume(runtime):
    run=setup_run(runtime);await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        runtime.agents.request_cancel(run.id)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as client:
            response=await client.post(f'/v1/platform/intelligence/handoffs/{run.id}/{item.id}/complete')
            assert response.status_code==409
            assert runtime.agents.get_run(run.id).status.value=='cancelled'
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_user_cancel_returns_to_original_agent(runtime):
    run=setup_run(runtime);await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as client:
            response=await client.post(f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/respond',json={'response_id':'cancel','response':{'status':'cancelled','result':{}}})
            assert response.status_code==200,response.text
        assert (await wait(runtime,run.id,'completed')).output=={'cancelled':True}
    finally:await runtime.agent_runtime.stop()


def test_parameters_and_identity_are_not_model_controlled():
    context=SimpleNamespace(interaction=lambda key:None)
    with pytest.raises(ValidationError):interaction_action(context,{**ARGS,'session_id':'foreign'})
    with pytest.raises(ValidationError):interaction_action(context,{**ARGS,'capability':'https://evil.test/'})
    action=interaction_action(context,ARGS)
    assert action.ui_hints['app_id']=='ai2apps.intelligence'
    existing=SimpleNamespace(request=action.request,status=None)
    with pytest.raises(ValueError):interaction_action(SimpleNamespace(interaction=lambda key:existing),{**ARGS,'parameters':{'name':'changed'}})


def test_creation_key_is_owner_scoped(tmp_path):
    store=IntelligenceStore(tmp_path)
    data={'name':'Channel','interests':'Research','interval_hours':0}
    a=store.save_channel('alice',data,creation_key='same')
    b=store.save_channel('bob',data,creation_key='same')
    assert a['id']!=b['id']
    assert store.save_channel('alice',data,creation_key='same')['id']==a['id']
    with pytest.raises(KeyError):store.get('channels','bob',a['id'])


def test_mini_app_uses_host_target_and_shared_durable_contract(monkeypatch):
    from ai2apps.agents import InteractionStatus
    from ai2apps.agents.app_interactions import CAPABILITIES, InteractionCapability, register_capability
    from ai2apps.agents import app_interactions
    monkeypatch.setattr(app_interactions,'CAPABILITIES',dict(CAPABILITIES))
    register_capability(InteractionCapability('test.mini.configure','ai2apps.voice-studio',
        {'type':'object','properties':{'text':{'type':'string'}},'required':['text'],'additionalProperties':False},
        mini_app_id='test.voice-mini'))
    args={'request_id':'mini-1','capability':'test.mini.configure','parameters':{'text':'Hello'}}
    action=interaction_action(SimpleNamespace(interaction=lambda key:None),args)
    assert action.ui_hints=={'control':'app_handoff','app_id':'ai2apps.voice-studio','mini_app_id':'test.voice-mini','prompt_labels':{'zh':'请在目标应用完成操作，然后返回继续任务。','en':'Complete the action in the target App, then return.'}}
    assert action.prompt=='Complete the action in the target App, then return.'
    restored=SimpleNamespace(request=action.request,status=InteractionStatus.SUBMITTED)
    assert interaction_action(SimpleNamespace(interaction=lambda key:restored),args) is None
    with pytest.raises(ValidationError):interaction_action(SimpleNamespace(interaction=lambda key:None),{**args,'parameters':{'url':'https://example.org'}})

@pytest.mark.asyncio
async def test_expired_handoff_cannot_create_channel(runtime):
    run=setup_run(runtime);await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        with runtime.database.transaction(write=True) as db:
            db.execute("UPDATE agent_interactions SET deadline_at='2000-01-01T00:00:00.000000Z' WHERE id=?",(item.id,))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as client:
            response=await client.post(f'/v1/platform/intelligence/channels?handoff_run={run.id}&handoff_id={item.id}',json={'name':'Research','interests':'AI'})
            assert response.status_code==409
        assert not IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence').snapshot('local')['channels']
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_foreign_user_cannot_read_or_complete_handoff(runtime):
    from ai2apps.identity import IdentityRepository, OrganizationType
    identities=IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='handoff-test',cloud_device_id='test-device',organization_id='test-org',organization_type=OrganizationType.HOUSEHOLD,core_user_id='alice',billing_account_id='billing',access_epoch=1)
    principal=identities.principal_for('alice')
    run=setup_run(runtime,principal);await runtime.agent_runtime.start()
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        foreign=replace(principal,actor_user_id='bob')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime,lambda:foreign)),base_url='http://test') as client:
            response=await client.get(f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/handoff')
            assert response.status_code==404,response.text
            response=await client.post(f'/v1/platform/intelligence/handoffs/{run.id}/{item.id}/complete')
            assert response.status_code==404,response.text
        assert runtime.agents.get_run(run.id).status.value=='waiting_input'
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_general_agent_preserves_tool_call_across_full_runtime_restart(runtime):
    import json
    calls=[]
    def model(request):
        calls.append(request)
        if len(calls)==1:
            alias=next(t['function']['name'] for t in request['tools'] if t['function']['name'].startswith('app__interact_'))
            return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'create-channel-call','type':'function','function':{'name':alias,'arguments':json.dumps(ARGS)}}]},'finish_reason':'tool_calls'}]}
        reply=request['messages'][-1]
        assert reply['tool_call_id']=='create-channel-call'
        result=json.loads(reply['content'])
        assert result['status']=='completed'
        assert result['result']['articles'][0]['title']=='Supplied fixture'
        return {'choices':[{'message':{'role':'assistant','content':'Fixture briefing: supplied article. Source: https://example.org/fixture'},'finish_reason':'stop'}]}
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='General handoff')
    runtime.agent_runtime.bind_model_provider(model)
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'Create a news channel, then prepare a briefing.'})
    await runtime.agent_runtime.start()
    await wait(runtime,run.id,'waiting_input')
    interaction=runtime.agents.list_interactions(run.id)[0]
    await runtime.agent_runtime.stop();runtime.stop()
    restored=PlatformRuntime(runtime.config);restored.start()
    restored.agent_runtime.bind_model_provider(model)
    await restored.agent_runtime.start()
    try:
        assert restored.agents.list_interactions(run.id)[0].id==interaction.id
        store=IntelligenceStore(restored.config.paths.artifacts_path/'intelligence')
        channel=store.save_channel('local',{'name':'Fixture','interests':'AI','interval_hours':0},creation_key=interaction.id)
        store.import_article('local',channel['id'],{'title':'Supplied fixture','summary':'Test content','sources':[{'url':'https://example.org/fixture'}]},'fixture')
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(restored)),base_url='http://test') as client:
            response=await client.post(f'/v1/platform/intelligence/handoffs/{run.id}/{interaction.id}/complete')
            assert response.status_code==200,response.text
        completed=await wait(restored,run.id,'completed')
        assert completed.session_id==thread.session.id
        assert len(calls)==2
        assert len(restored.agents.list_interactions(run.id))==1
    finally:
        await restored.agent_runtime.stop();restored.stop()
