from dataclasses import replace
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext, ToolProviderError
from ai2apps.services.capability_routing import CapabilityProvider, CapabilityRouter
from ai2apps.agents.parameter_forms import resolve_form
from ai2apps.api.router import create_ai2apps_router
from test_app_interactions import runtime

@pytest.mark.asyncio
async def test_disabled_provider_is_durable_scoped_and_cannot_be_forced(runtime):
    from ai2apps.identity import IdentityRepository, OrganizationType
    IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='test-device',organization_id='test-org',organization_type=OrganizationType.HOUSEHOLD,core_user_id='other',billing_account_id='billing',access_epoch=1)
    router=runtime.app_capability_router;calls=[]
    async def execute(args,ctx):calls.append(ctx.actor_user_id);return {'ok':True}
    async def describe(*args):return {'effective_schema':{'type':'object','properties':{},'additionalProperties':False}}
    router.register(CapabilityProvider('test.toggle','test.toggle','test',execute,describe=describe))
    ctx=ToolCallContext(caller_id='test',actor_user_id='local',installation_id='local')
    router.set_enabled('local','local','test.toggle',False)
    assert CapabilityRouter(runtime.database).disabled('local','local')=={'test.toggle'}
    item=next(p for p in router.inspect('local','local') if p['id']=='test.toggle')
    assert not item['enabled'] and item['rank'] is None and item['status']=='disabled'
    for args in [{},{'provider':'test.toggle'}]:
        with pytest.raises(ToolProviderError):await router.invoke('test.toggle',args,ctx)
    with pytest.raises(ValueError):resolve_form({'capability':'test.toggle'},database=runtime.database,scope=ctx)
    assert not calls
    await router.invoke('test.toggle',{},replace(ctx,actor_user_id='other'))
    router.set_enabled('local','local','test.toggle',True)
    await router.invoke('test.toggle',{},ctx)
    assert calls==['other','local']

@pytest.mark.asyncio
async def test_enabled_api_catalog_and_pending_form_guard(runtime):
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    provider='ai2apps.imagine.reference-creation'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        url='/v1/platform/capability-providers/'+provider+'/enabled'
        assert (await client.put(url,json={'enabled':False})).status_code==200
        data=(await client.get('/v1/platform/capability-catalog')).json()
        assert next(p for p in data['providers'] if p['id']==provider)['enabled'] is False
        from ai2apps.agents.provider_forms import complete
        from ai2apps.agents.parameter_forms import FORMS
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            await complete(runtime,RequestPrincipal.legacy_local(),FORMS[provider],{},None)
        assert e.value.status_code==409
        assert (await client.put(url,json={'enabled':True})).status_code==200
        assert (await client.put('/v1/platform/capability-providers/absent/enabled',json={'enabled':False})).status_code==404
