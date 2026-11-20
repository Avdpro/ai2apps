"""App grants use real Run/Interaction guards; no live model, billing or generation."""
import json
from dataclasses import replace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.messager.bots import REGISTRATION
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response
from test_bot_capability_discovery import setup
from bot_access_fixtures import restricted_bot
P=RequestPrincipal.legacy_local


@pytest.mark.asyncio
@pytest.mark.parametrize(('mode', 'risk', 'special', 'expected'), [
    ('always', 'low', False, 'once'),
    ('ai', 'low', False, 'persisted'),
    ('ai', 'high', False, 'manual'),
    ('always', 'low', True, 'manual'),
    ('always', 'low', False, 'disabled'),
])
async def test_bot_approval_rule_uses_original_call_and_access_scope(runtime, mode, risk, special, expected):
    bot, session_id, calls, provider = setup(runtime, 'fixture.paint', 'ai2apps.knowledge')
    access = runtime.messager_bot_app_access
    if special:
        runtime.app_capability_router.providers[provider.id] = replace(provider, access_policy='confirm')
    if expected == 'disabled':
        catalog = access.catalog('local', bot['id'])
        access.save('local', bot['id'], catalog['revision'], catalog['review_hash'],
                    [{'app_id': provider.app_id, 'enabled': False}])
    app = FastAPI()
    app.include_router(create_messager_router(lambda: runtime, P))
    path = f'/messager/bots/{bot["id"]}/app-access'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get(path)).json()['approval_rule'] == {'mode': 'manual', 'revision': 0}
        body = {'mode': mode, 'revision': 0}
        assert (await client.put(path+'/approval-rule', json=body)).status_code == 403
        result = await client.put(path+'/approval-rule', json=body, headers={'Origin': 'http://test'})
        assert result.json() == {'mode': mode, 'revision': 1}
        assert (await client.put(path+'/approval-rule', json=body, headers={'Origin': 'http://test'})).status_code == 409
    reviews = []

    async def model(request):
        if request['messages'][0]['content'].startswith('Review a proposed Tool invocation'):
            reviews.append(request)
            return response(text=json.dumps({'risk': risk, 'necessary': True, 'reason': 'fixture'}))
        if calls:
            return response(text='Created')
        if not any(m.get('role') == 'tool' and 'providers' in m['content'] for m in request['messages']):
            return response('app.describe', {'capability': provider.capability})
        return response(provider.capability, {'prompt': 'fixture'})

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run_id = runtime.app_chat.submit(P(), session_id, 'mode-fixture', 'Create fixture', 'fixture')
        automatic = expected in ('once', 'persisted')
        await wait(runtime, run_id, 'completed' if automatic else 'waiting_capability')
        assert len(calls) == int(automatic)
        assert len(reviews) == int(mode == 'ai')
        row = next(x for x in access.catalog('local', bot['id'])['items'] if x['app_id'] == provider.app_id)
        assert row['selected'] == (expected in ('persisted', 'disabled'))
        assert row['enabled'] == (expected == 'persisted')
        if expected == 'persisted':
            access.set_approval_rule('local', bot['id'], 'manual', 1)
            async def next_model(request):
                return response(provider.capability, {'prompt': 'another fixture'}) if len(calls) == 1 else response(text='Created again')
            runtime.agent_runtime.bind_model_provider(next_model)
            next_run = runtime.app_chat.submit(P(), session_id, 'next-fixture', 'Create another fixture', 'fixture')
            await wait(runtime, next_run, 'completed')
            assert len(calls) == 2
            assert not runtime.agents.list_interactions(next_run)
    finally:
        await runtime.stop_background_tasks()


def save(r,bot,enabled=True):
    s=r.messager_bot_app_access;c=s.catalog('local',bot['id'])
    return s.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':'ai2apps.gallery','enabled':enabled}])


def test_app_access_toggle_isolation_snapshot_and_revocation(runtime):
    bot,sid,calls,provider=setup(runtime)
    s=runtime.messager_bot_app_access
    save(runtime,bot,False)
    assert not s.granted('local',bot['id'],provider)
    before=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    save(runtime,bot)
    assert s.granted('local',bot['id'],provider)
    other=restricted_bot(runtime,runtime.messager_bots.create('local','Other','Help'))
    assert not s.granted('local',other['id'],provider)
    with pytest.raises(PermissionError):s.catalog('other',bot['id'])
    frozen=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    assert provider.id in frozen['providers'] and provider.id not in before['providers']
    with pytest.raises(PermissionError):runtime.messager_bot_permissions.validate('local',{'bot_id':bot['id']},before,provider.capability,{})
    save(runtime,bot,False)
    with pytest.raises(PermissionError):runtime.messager_bot_permissions.validate('local',{'bot_id':bot['id']},frozen,None,{})


@pytest.mark.asyncio
@pytest.mark.parametrize('special',[False,True,'changed'])
@pytest.mark.parametrize('usage',[False,True])
async def test_allow_this_bot_saves_app_and_only_resumes_ordinary_original_call(runtime,special,usage):
    bot,sid,calls,provider=setup(runtime)
    if usage:
        tool=runtime.services.get_tool(provider.capability)
        runtime.services.ensure_tool(service_id=tool.service_id,qualified_name=tool.qualified_name,display_name=tool.display_name,description=tool.description,input_schema=tool.input_schema,output_schema=tool.output_schema,effects=('network','ai.usage','workspace.write','artifact.create'),required_capabilities=())
    if special:
        runtime.app_capability_router.providers[provider.id]=replace(provider,access_policy='confirm')
        runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results):return response(text='Created')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response(provider.capability,{'prompt':'fixture'})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.app_chat.submit(P(),sid,'app-grant','Create fixture','fixture');await wait(runtime,rid,'waiting_capability')
        item=runtime.agents.list_interactions(rid)[0];service=runtime.messager_bot_app_access
        if special=='changed':
            runtime.app_capability_router.providers[provider.id]=replace(runtime.app_capability_router.providers[provider.id],version='upgraded')
            with pytest.raises(PermissionError):service.request('local',bot['id'],rid,item.id)
            assert not service.current('local',bot['id'])[1] and not calls
            return
        with pytest.raises(PermissionError):service.request('other',bot['id'],rid,item.id)
        review=service.request('local',bot['id'],rid,item.id)
        assert review['app']['name'] and review['app']['icon'] and not review['access_granted']
        with pytest.raises(ValueError):service.allow('local',bot['id'],rid,item.id,'0'*64)
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        path=f'/messager/bots/{bot["id"]}/app-access/requests/{rid}/{item.id}'
        body={'request_hash':review['request_hash']}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            assert (await client.post(path,json=body)).status_code==403
            denied=await client.post(path,json={**body,'existing_access_only':True},headers={'Origin':'http://test'})
            assert denied.status_code==404 and not service.current('local',bot['id'])[1]
            result=await client.post(path,json=body,headers={'Origin':'http://test'})
            assert result.status_code==200,result.text
        if special:
            assert result.json()['requires_confirmation'] and not calls
            assert service.request('local',bot['id'],rid,item.id)['access_granted']
            runtime.agents.respond_interaction(rid,item.id,response_id='special-once',response={'decision':'approve','scope':'once'})
            runtime.agent_runtime.wake()
        await wait(runtime,rid,'completed');assert len(calls)==1
        assert service.catalog('local',bot['id'])['items'][0:]
        if not special:
            async def again(request):return response(provider.capability,{'prompt':'another fixture'}) if len(calls)==1 else response(text='Created again')
            runtime.agent_runtime.bind_model_provider(again)
            next_run=runtime.app_chat.submit(P(),sid,'already-granted','Create another','fixture');await wait(runtime,next_run,'completed')
            assert len(calls)==2 and not runtime.agents.list_interactions(next_run)
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize('name,app_id',[('fixture.create','ai2apps.gallery'),('arbitrary.compose','ai2apps.knowledge')])
async def test_pending_approval_reuses_app_access_granted_after_start(runtime,name,app_id):
    bot,sid,calls,provider=setup(runtime,name,app_id)
    async def model(request):
        return response(text='Created') if calls else response(provider.capability,{'prompt':'fixture'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.app_chat.submit(P(),sid,'late-grant','Create fixture','fixture')
        await wait(runtime,rid,'waiting_capability')
        item=runtime.agents.list_interactions(rid)[0]
        service=runtime.messager_bot_app_access
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        path=f'/messager/bots/{bot["id"]}/app-access/requests/{rid}/{item.id}'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            before=(await client.get(path)).json()
            assert not before['access_granted']
            with runtime.database.transaction(write=True) as db:
                service.grant_targets('local',bot['id'],{app_id},db)
            granted=service.current('local',bot['id'])
            review=(await client.get(path)).json()
            assert review['access_granted']
            result=await client.post(path,json={'request_hash':review['request_hash'],'existing_access_only':True},headers={'Origin':'http://test'})
            assert result.json()=={'continued':True}
        await wait(runtime,rid,'completed')
        assert len(calls)==1 and service.current('local',bot['id'])==granted
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.parametrize('effect',['billing','payment','purchase','publish','settings.network.write','unknown.fixture'])
def test_transaction_and_unknown_effects_cannot_be_promoted_by_app_write(runtime,effect):
    bot,sid,calls,p=setup(runtime)
    save(runtime,bot)
    assert runtime.messager_bot_app_access.granted('local',bot['id'],p)
    tool=runtime.services.get_tool(p.capability)
    if effect == 'unknown.fixture':
        # Simulate a descriptor persisted before vocabulary enforcement.
        with runtime.database.transaction(write=True) as db:
            db.execute('UPDATE tool_descriptors SET effects_json=? WHERE id=?',
                       (json.dumps(['workspace.write', effect]), tool.id))
    runtime.services.ensure_tool(service_id=tool.service_id,qualified_name=tool.qualified_name,display_name=tool.display_name,description=tool.description,input_schema=tool.input_schema,output_schema=tool.output_schema,effects=('workspace.write',effect),required_capabilities=())
    assert not runtime.messager_bot_app_access.granted('local',bot['id'],p)
    assert p.id not in runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')['providers']


def test_disabled_app_cannot_retain_scoped_tool_permissions(runtime):
    bot,sid,_,_=setup(runtime)
    permissions=runtime.messager_bot_permissions
    permissions.save('local',bot['id'],1,[{'id':'todo.inbox.create','foreground':True,'background':True}],review_hash=permissions.review_hash())
    frozen=permissions.capture('local',{'bot_id':bot['id']},'hook')
    access=runtime.messager_bot_app_access;c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':'ai2apps.todo','enabled':False}])
    current=permissions.capture('local',{'bot_id':bot['id']},'hook')
    assert 'ai2apps.todo.todo.inbox.create' not in current['providers']
    with pytest.raises(PermissionError):permissions.validate('local',{'bot_id':bot['id']},frozen,'todo.inbox.create',{})

@pytest.mark.parametrize('name,app',[('fixture.create','ai2apps.gallery'),('arbitrary.compose','ai2apps.knowledge')])
def test_single_grant_covers_ordinary_read_and_write_and_disabling_blocks_both(runtime,name,app):
    bot,sid,calls,write=setup(runtime,name,app)
    read=replace(write,id='arbitrary.read',capability='todo.get')
    runtime.app_capability_router.register(read)
    access=runtime.messager_bot_app_access;c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':app,'enabled':True}])
    assert access.granted('local',bot['id'],read) and access.granted('local',bot['id'],write)
    frozen=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    assert {read.id,write.id}<=set(frozen['providers'])
    c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':app,'enabled':False}])
    assert not access.granted('local',bot['id'],read) and not access.granted('local',bot['id'],write)
    with pytest.raises(PermissionError):runtime.messager_bot_permissions.validate('local',{'bot_id':bot['id']},frozen,None,{})

def test_settings_api_rejects_read_write_and_requires_one_boolean():
    from ai2apps.api.messager import BotAppChoice,BotAppAllow
    from pydantic import ValidationError
    assert BotAppChoice(app_id='arbitrary.app',enabled=False).enabled is False
    for value in ({'app_id':'arbitrary.app','read':True,'write':True},{'app_id':'arbitrary.app','enabled':'true'}):
        with pytest.raises(ValidationError):BotAppChoice(**value)
    with pytest.raises(ValidationError):BotAppAllow(request_hash='0'*64,read=True,write=True)
