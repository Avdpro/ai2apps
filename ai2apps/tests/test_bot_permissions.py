"""Real Bot authorization, with owner-scoped settings and no live accounts."""
from dataclasses import replace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install, REGISTRATION
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime
from bot_access_fixtures import restricted_bot
P = RequestPrincipal.legacy_local


def setup(runtime):
    install(runtime)
    bot = runtime.messager_bots.create('local', 'Access fixture', 'Read authorized data')
    restricted_bot(runtime,bot,legacy_read=True)
    return bot, runtime.messager_bot_permissions


def test_legacy_foreground_only_pins_interfaces_and_stays_revoked(runtime):
    bot, service = setup(runtime)
    scope = {'bot_id':bot['id']}
    catalog = service.catalog('local', bot['id'])
    assert catalog['revision'] == 1
    assert next(p for p in catalog['items'] if p['id']=='intelligence.read')['foreground']
    assert not next(p for p in catalog['items'] if p['id']=='todo.read')['foreground']
    assert service.capture('local', scope, 'hook')['providers'] == {}
    old = service.capture('local', scope, 'user')
    assert len(old['providers']) == 4
    assert service.save('local', bot['id'], 1, [], review_hash=service.review_hash())['revision'] == 2
    assert service.exported(scope) == ()
    service.ensure('local', bot['id'])
    assert service.catalog('local', bot['id'])['revision'] == 2
    assert service.save('local', bot['id'], 2, [{'id':'intelligence.read','foreground':True,'background':False}], review_hash=service.review_hash())['revision'] == 3
    with pytest.raises(PermissionError, match='changed'):
        service.validate('local', scope, old, 'intelligence.channels', {})
    service.validate('local', scope, service.capture('local', scope, 'user'), 'intelligence.channels', {})
    with pytest.raises(PermissionError):service.validate('other', scope, old, None, {})


def test_provider_upgrade_needs_review_and_background_is_separate(runtime):
    bot, service = setup(runtime)
    scope = {'bot_id':bot['id']}
    old = service.capture('local', scope, 'user')
    reviewed = service.review_hash()
    key = 'ai2apps.intelligence.intelligence.channels'
    runtime.app_capability_router.providers[key] = replace(runtime.app_capability_router.providers[key], version='upgraded')
    assert next(p for p in service.catalog('local', bot['id'])['items'] if p['id']=='intelligence.read')['needs_review']
    with pytest.raises(ValueError, match='interfaces changed'):service.save('local',bot['id'],1,[],review_hash=reviewed)
    with pytest.raises(PermissionError):service.validate('local', scope, old, 'intelligence.channels', {})
    service.save('local', bot['id'], 1, [{'id':'intelligence.read','foreground':False,'background':True}], review_hash=service.review_hash())
    assert service.capture('local', scope, 'user')['providers'] == {}
    frozen = service.capture('local', scope, 'hook')
    service.validate('local', scope, frozen, 'intelligence.channels', {})
    with pytest.raises(PermissionError):service.validate('local', scope, frozen, 'intelligence.refresh', {})


@pytest.mark.asyncio
async def test_access_api_ownership_revision_and_active_run_invalidation(runtime):
    bot, service = setup(runtime)
    foreign = runtime.messager_bots.create('other', 'Private', 'Private')
    sid = runtime.app_chat.open(P(), REGISTRATION, {'bot_id':bot['id']}, {})
    forged,_ = runtime.agents.create_run(session_id=sid,agent_key='ai2apps.app-chat-agent',input={'prompt':'forged','model':'fixture','owner_authorization':service.capture('local',{'bot_id':bot['id']},'user')})
    with pytest.raises(PermissionError):runtime.app_chat.validate_execution(runtime.app_chat.binding(sid),runtime.app_chat.owners[REGISTRATION],forged,'intelligence.channels',{})
    runtime.agents.request_cancel(forged.id)
    rid = runtime.app_chat.submit(P(), sid, 'old-authorization', 'Read later', 'fixture')
    frozen = runtime.app_chat.execution_authorization(rid)
    app = FastAPI();app.include_router(create_messager_router(lambda:runtime, P))
    base = '/messager/bots/'+bot['id']+'/access'
    review_hash=service.review_hash()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',headers={'Origin':'http://test'}) as client:
        assert (await client.put(base,json={'revision':1,'review_hash':review_hash,'grants':[]},headers={'Origin':'null'})).status_code == 403
        assert (await client.get('/messager/bots/'+foreign['id']+'/access')).status_code == 404
        assert (await client.put(base,json={'revision':1,'review_hash':review_hash,'grants':[{'id':'arbitrary.write','foreground':True,'background':True}]})).status_code == 409
        assert (await client.put(base,json={'revision':1,'review_hash':review_hash,'grants':[{'id':'todo.read','foreground':True,'background':False,'provider':'forged'}]})).status_code == 422
        saved = await client.put(base,json={'revision':1,'review_hash':review_hash,'grants':[{'id':'todo.read','foreground':True,'background':False}]})
        assert saved.status_code == 200, saved.text
        assert (await client.put(base,json={'revision':1,'review_hash':review_hash,'grants':[]})).status_code == 409
    assert runtime.agents.get_run(rid).status.value == 'cancelled'
    with pytest.raises(PermissionError):service.validate('local', {'bot_id':bot['id']}, frozen, None, {})
    assert runtime.app_chat.open(P(), REGISTRATION, {'bot_id':bot['id']}, {}) == sid
    current = runtime.app_chat.snapshot(P(), sid)['tools']
    assert 'todo.search' in current and 'todo.create' in current
    # Unselected interfaces remain discoverable but are not preauthorized.
    assert service.capture('local', {'bot_id':bot['id']}, 'user')['providers'] == {p.id:p.version for p in service.providers(service.profiles['todo.read'])}
