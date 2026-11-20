"""MVP evidence: fixture providers and real Local handlers, no live model calls."""
from dataclasses import replace
import io
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext
from ai2apps.services.channels import ChannelBinding, ChannelDirectory
from ai2apps.services.capability_routing import CapabilityProvider, CapabilityInvocationError
from ai2apps.services.builtin_apps import gallery
from ai2apps.api.capabilities import create_capability_router
from legacy_package_backend_fixture import runtime


def context(runtime):
    thread, _ = ChatRepository(runtime.database, runtime.events).create_thread(title='Channel MVP')
    return ToolCallContext.from_principal(RequestPrincipal.legacy_local(), caller_id='api:channels', session_id=thread.session.id)


@pytest.mark.asyncio
async def test_builtin_gateway_owner_isolation_and_audit(runtime):
    ctx = context(runtime)
    directory = ChannelDirectory(runtime)
    rows = directory.catalog(ctx)['items']
    row = next(r for r in rows if r['ref']['owner'] == 'ai2apps.gallery')
    own, _ = gallery(runtime).import_stream('local', io.BytesIO(b'owned'), name='owned.txt', media_type='text/plain')
    foreign, _ = gallery(runtime).import_stream('other', io.BytesIO(b'private'), name='secret.txt', media_type='text/plain')
    op = next(o for o in row['operations'] if o['role'] == 'read')
    args = dict(owner=row['ref']['owner'], local_id=row['ref']['local_id'], interface_version='1',
                provider_id=op['provider'], provider_version=op['provider_version'], role='read')
    with runtime.database.transaction() as db:
        health_before = [tuple(r) for r in db.execute('SELECT * FROM capability_provider_health')]
    result = await directory.invoke(ctx, **args, arguments={'asset_id': own['id']})
    with runtime.database.transaction() as db:
        assert [tuple(r) for r in db.execute('SELECT * FROM capability_provider_health')] == health_before
    assert result['output']['asset']['id'] == own['id']
    assert runtime.services.get_invocation(result['invocation_id']).session_id == ctx.session_id
    with pytest.raises(Exception):
        await directory.invoke(ctx, **args, arguments={'asset_id': foreign['id']})
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke(ctx, **{**args, 'provider_version': 'stale'}, arguments={'asset_id': own['id']})
    assert caught.value.code == 'version_conflict'
    with pytest.raises(CapabilityInvocationError):
        await directory.invoke(ctx, **args, arguments={'provider': op['provider']})
    runtime.app_capability_router.set_enabled('local', 'local', op['provider'], False)
    with pytest.raises(CapabilityInvocationError):
        await directory.invoke(ctx, **args, arguments={'asset_id': own['id']})


def test_catalog_pagination_filter_and_no_legacy_projection_change(runtime):
    ctx = context(runtime)
    before = runtime.app_capability_router.catalog()
    directory = ChannelDirectory(runtime)
    first = directory.catalog(ctx, limit=1)
    assert first['total'] >= 2 and first['next_offset'] == 1
    assert directory.catalog(ctx, offset=1, limit=1)['items'] != first['items']
    assert directory.catalog(ctx, query='素材')['items'][0]['ref']['owner'] == 'ai2apps.gallery'
    assert runtime.app_capability_router.catalog() == before
    # New host fields are absent on legacy calls unless explicitly supplied.
    assert ctx.pinned_provider is None
    with pytest.raises(CapabilityInvocationError):
        directory.catalog(replace(ctx, actor_user_id=None))


@pytest.mark.asyncio
async def test_arbitrary_providers_version_race_and_no_fallback(runtime):
    router = runtime.app_capability_router
    calls = []
    async def execute(args, ctx):
        calls.append('executed')
        return {'ok': True}
    async def prepare(args, ctx):
        router.providers['alpha'] = replace(router.providers['alpha'], version='2')
        return args
    p = CapabilityProvider('alpha', 'arbitrary.read', 'owner-a', execute, version='1', prepare=prepare,
                           channels=(ChannelBinding('records', 'Records', 'read'),))
    router.register(p)
    router.register(CapabilityProvider('beta', 'arbitrary.read', 'owner-b', execute))
    ctx = replace(context(runtime), pinned_provider=('arbitrary.read', 'alpha', '1'))
    with pytest.raises(CapabilityInvocationError):
        await router.invoke('arbitrary.read', {'provider': 'alpha'}, ctx)
    assert not calls
    with pytest.raises(CapabilityInvocationError) as caught:
        await router.invoke('arbitrary.read', {'provider': 'beta'}, ctx)
    assert caught.value.code == 'version_conflict'
    # An old invocation with no channel pin retains its existing behavior.
    result = await router.invoke('arbitrary.read', {'provider': 'beta'}, replace(ctx, pinned_provider=None))
    assert result['provider'] == 'beta'


@pytest.mark.asyncio
async def test_selection_required_stops_before_handler(runtime):
    calls = []
    async def execute(a, c): calls.append(a); return {}
    async def describe(p, model=None):
        return {'effective_schema': {'type':'object'}, 'selection_required': True}
    runtime.app_capability_router.register(CapabilityProvider('review', 'arbitrary.review', 'owner', execute, describe=describe))
    ctx = replace(context(runtime), pinned_provider=('arbitrary.review', 'review', '1'))
    with pytest.raises(CapabilityInvocationError) as caught:
        await runtime.app_capability_router.invoke('arbitrary.review', {'provider':'review'}, ctx)
    assert caught.value.code == 'confirmation_required' and not calls


@pytest.mark.asyncio
async def test_http_session_guard_and_read(runtime):
    ctx = context(runtime)
    app = FastAPI()
    app.include_router(create_capability_router(lambda: runtime, RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        assert (await client.get('/channels', params={'session_id':'foreign'})).status_code in (403, 404)
        response = await client.get('/channels', params={'session_id':ctx.session_id})
        assert response.status_code == 200, response.text
        row = next(r for r in response.json()['items'] if r['ref']['owner'] == 'ai2apps.gallery')
        op = next(o for o in row['operations'] if o['role'] == 'search')
        body = {**row['ref'], 'session_id':ctx.session_id, 'provider_id':op['provider'],
                'provider_version':op['provider_version'], 'role':'search', 'arguments':{}}
        response = await client.post('/channels/read', json=body)
        assert response.status_code == 200, response.text
        body['actor_user_id'] = 'other'
        assert (await client.post('/channels/read', json=body)).status_code == 422


@pytest.mark.parametrize('role', ['add', 'delete', 'refresh'])
def test_read_contract_rejects_effect_roles(role):
    with pytest.raises(ValueError): ChannelBinding('records', 'Records', role)


def test_arbitrary_channel_bindings_visibility_and_revocation(runtime, monkeypatch):
    async def execute(a, c): return {}
    router = runtime.app_capability_router
    for key, owner, types in [('omega', 'vendor-x', ('note',)), ('delta', 'vendor-y', ('image',))]:
        router.register(CapabilityProvider(key, key + '.read', owner, execute,
            channels=(ChannelBinding('root', key, 'read', types),)))
    tools = [SimpleNamespace(qualified_name=key + '.read', effects=('read',)) for key in ('omega','delta')]
    monkeypatch.setattr(runtime.tools, 'list_tools', lambda ctx: tools)
    directory = ChannelDirectory(runtime)
    ctx = context(runtime)
    assert directory.catalog(ctx)['total'] == 2
    router.set_enabled('local','local','omega',False)
    assert directory.catalog(ctx)['items'][0]['ref']['owner'] == 'vendor-y'
    # Provider settings remain scoped to actor/Installation, not process-wide.
    assert directory.catalog(replace(ctx, actor_user_id='another'))['total'] == 2
    router.unregister('delta')
    assert directory.catalog(ctx)['total'] == 0
    tools.clear()
    assert directory.catalog(replace(ctx, actor_user_id='another'))['total'] == 0


@pytest.mark.asyncio
async def test_http_management_permission_required(runtime):
    from ai2apps.identity import MemberRole
    principal = replace(RequestPrincipal.legacy_local(), role=MemberRole.MEMBER)
    app = FastAPI()
    app.include_router(create_capability_router(lambda:runtime, lambda:principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/channels', params={'session_id':'anything'})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_intelligence_and_knowledge_reuse_owner_handlers(runtime):
    from ai2apps.intelligence.aaat import store
    from ai2apps.intelligence.models import ChannelInput
    ctx = context(runtime)
    own = store(runtime).save_channel('local', ChannelInput(name='Owned topic', interests='AI').model_dump())
    store(runtime).save_channel('other', ChannelInput(name='Private topic', interests='Private').model_dump())
    await runtime.app_capability_router.invoke('knowledge.add_text',
        {'title':'MVP reference', 'text':'A unique zephyr notebook'}, ctx)
    directory = ChannelDirectory(runtime)
    rows = directory.catalog(ctx)['items']
    for capability, arguments in [('intelligence.channels', {}), ('knowledge.search', {'query':'zephyr'})]:
        row, op = next((r, o) for r in rows for o in r['operations'] if o['capability'] == capability)
        response = await directory.invoke(ctx, **row['ref'], provider_id=op['provider'],
            provider_version=op['provider_version'], role=op['role'], arguments=arguments)
        if capability == 'intelligence.channels':
            assert [c['id'] for c in response['output']['channels']] == [own['id']]
        else:
            assert response['output']['items'][0]['item']['citation']['uri'].startswith('knowledge://')
