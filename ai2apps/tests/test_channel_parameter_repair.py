"""Only new channel reads repair parameters; model replies are controlled fixtures."""
from copy import deepcopy
from dataclasses import replace
import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from ai2apps.api.capabilities import create_capability_router
from ai2apps.identity import RequestPrincipal
from ai2apps.services.capability_routing import CapabilityProvider, CapabilityInvocationError
from ai2apps.services.channels import ChannelBinding, ChannelDirectory, RepairField
from ai2apps.services.parameter_repair import RepairOptions
from test_channels import context
from legacy_package_backend_fixture import runtime


def binding(directory, ctx, capability='gallery.search'):
    row, op = next((r,o) for r in directory.catalog(ctx)['items'] for o in r['operations'] if o['capability']==capability)
    return {**row['ref'], 'provider_id':op['provider'], 'provider_version':op['provider_version'], 'role':op['role']}


def fake_model(runtime, monkeypatch, patch, *, callback=None):
    calls=[]
    async def invoke(model, operation, payload, **kwargs):
        calls.append((deepcopy(payload), kwargs))
        if callback: await callback()
        content=patch if isinstance(patch,str) else json.dumps(patch)
        return JSONResponse({'choices':[{'message':{'content':content},'finish_reason':'stop'}],
                             'usage':{'prompt_tokens':12,'completion_tokens':4,'total_tokens':16}})
    monkeypatch.setattr(runtime,'model_manager',SimpleNamespace(resolve_default_model=lambda *a,**kw:'fixture-normalizer'))
    monkeypatch.setattr(runtime,'model_invocations',SimpleNamespace(invoke_foreground_json=invoke))
    return calls


def arbitrary(runtime, *, schema=None, prepare=None, error=None, count_cap=5):
    schema=schema or {'type':'object','properties':{'count':{'type':'integer','minimum':1,'maximum':10},
        'resource_id':{'type':'string'}},'required':['count'],'additionalProperties':False}
    seen=[]
    async def describe(*a):return {'effective_schema':deepcopy(schema)}
    async def execute(args,ctx):
        seen.append(deepcopy(args))
        if error:raise error
        return {'seen':args}
    pid='unrelated.provider';cap='arbitrary.records'
    provider=CapabilityProvider(pid,cap,'vendor.alpha',execute,describe=describe,prepare=prepare,
        channels=(ChannelBinding('root','Records','search'),), read_repair=(RepairField('count',('amount',),ai=True,ai_maximum=count_cap),))
    runtime.app_capability_router.register(provider)
    base=runtime.services.get_tool('gallery.search');tool_schema=deepcopy(schema)
    tool_schema['properties']['provider']={'type':'string'}
    runtime.services.ensure_tool(service_id=base.service_id,qualified_name=cap,display_name=cap,description='Fixture read',
        input_schema=tool_schema,output_schema={'type':'object'},effects=('read',),timeout_ms=1000)
    async def routed(a,c):return await runtime.app_capability_router.invoke(cap,a,c)
    runtime.service_registry.bind_tool(cap,provider_key=runtime.service_registry.bound_tool('gallery.search').provider_key,handler=routed)
    return cap,seen,schema


@pytest.mark.asyncio
async def test_deterministic_alias_and_numeric_format_keep_original(runtime):
    ctx=context(runtime);directory=ChannelDirectory(runtime);args={'query':'private query','max_results':'2'};original=deepcopy(args)
    result=await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx),arguments=args)
    assert args==original and result['schema']=='ai2apps.channels/v2'
    assert result['repair']['attempts'][0]['method']=='deterministic'
    assert not result['repair']['ai_used']
    invocation=runtime.services.get_invocation(result['invocation_id'])
    assert invocation.arguments['limit']==2 and invocation.arguments['query']=='private query'
    assert 'max_results' not in invocation.arguments


@pytest.mark.asyncio
async def test_ai_patch_is_bounded_private_and_owner_revalidated(runtime,monkeypatch):
    cap,seen,_=arbitrary(runtime)
    calls=fake_model(runtime,monkeypatch,{'count':2})
    ctx=context(runtime);directory=ChannelDirectory(runtime)
    result=await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),
        arguments={'count':'a couple','resource_id':'PRIVATE_RESOURCE'})
    assert seen==[{'count':2,'resource_id':'PRIVATE_RESOURCE'}] and len(calls)==1
    assert 'PRIVATE_RESOURCE' not in json.dumps(calls[0][0])
    assert calls[0][1]['context'].session_id==ctx.session_id
    assert calls[0][0]['max_tokens']==256 and not calls[0][0].get('tools')
    assert result['repair']['ai_used'] and result['repair']['model_usage']['total_tokens']==16
    assert result['repair']['model']=='fixture-normalizer'
    with runtime.database.transaction() as db:
        events=[r[0] for r in db.execute("select payload_json from events where type like 'channel.parameter_repair.%'")]
    assert events and all('PRIVATE_RESOURCE' not in e and 'a couple' not in e for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize('patch',[{'count':2,'resource_id':'replacement'}, {'count':6}, {}, '{"count":2,"count":3}', '{"count":NaN}', 'not json'])
async def test_model_cannot_change_identity_exceed_owner_cap_or_loop(runtime,monkeypatch,patch):
    cap,seen,_=arbitrary(runtime);calls=fake_model(runtime,monkeypatch,patch)
    ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(CapabilityInvocationError):
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':'a couple','resource_id':'original'})
    assert not seen and len(calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('args',[{'query':'x','unknown':'2'}, {'limit':2,'max_results':3}, {'limit':999}])
async def test_unknown_conflicting_and_explicit_out_of_range_values_are_not_guessed(runtime,monkeypatch,args):
    calls=fake_model(runtime,monkeypatch,{'limit':2});ctx=context(runtime);directory=ChannelDirectory(runtime);before=deepcopy(args)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx),arguments=args)
    assert args==before and not calls
    assert caught.value.details['submitted'] is False


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['off','deterministic'])
async def test_modes_never_invoke_ai(runtime,monkeypatch,mode):
    calls=fake_model(runtime,monkeypatch,{'limit':2});ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(Exception):
        await directory.invoke_repaired(ctx,options=RepairOptions(mode=mode),**binding(directory,ctx),arguments={'limit':'a couple'})
    assert not calls


@pytest.mark.asyncio
async def test_provider_or_contract_change_during_model_stops_dispatch(runtime,monkeypatch):
    cap,seen,schema=arbitrary(runtime)
    async def change():schema['properties']['count']['maximum']=4
    calls=fake_model(runtime,monkeypatch,{'count':2},callback=change)
    ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':'two'})
    assert caught.value.code=='version_conflict' and not seen and len(calls)==1


@pytest.mark.asyncio
async def test_revoke_during_model_stops_dispatch(runtime,monkeypatch):
    cap,seen,_=arbitrary(runtime);ctx=context(runtime);directory=ChannelDirectory(runtime)
    async def revoke():runtime.app_capability_router.set_enabled(ctx.actor_user_id,ctx.installation_id,'unrelated.provider',False)
    fake_model(runtime,monkeypatch,{'count':2},callback=revoke)
    with pytest.raises(CapabilityInvocationError):
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':'two'})
    assert not seen


@pytest.mark.asyncio
async def test_handler_validation_error_does_not_enter_repair_or_repeat(runtime,monkeypatch):
    cap,seen,_=arbitrary(runtime,error=ValidationError('business validation after submission'))
    calls=fake_model(runtime,monkeypatch,{'count':2});ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(Exception):
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':2})
    assert len(seen)==1 and not calls


@pytest.mark.asyncio
async def test_permission_denial_and_interaction_requirement_stop_before_model(runtime,monkeypatch):
    async def deny(a,c):raise PermissionError('owner denied')
    cap,seen,_=arbitrary(runtime,prepare=deny);calls=fake_model(runtime,monkeypatch,{'count':2})
    ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':2})
    assert caught.value.code=='permission_denied' and not seen and not calls
    p=runtime.app_capability_router.providers['unrelated.provider']
    async def describe(*a):return {'effective_schema':{'type':'object'},'selection_required':True}
    runtime.app_capability_router.providers[p.id]=replace(p,describe=describe)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':'two'})
    assert caught.value.code=='confirmation_required' and not calls


@pytest.mark.asyncio
async def test_deadline_and_cancellation_do_not_dispatch(runtime,monkeypatch):
    cap,seen,_=arbitrary(runtime)
    async def hang():await asyncio.Event().wait()
    calls=fake_model(runtime,monkeypatch,{'count':2},callback=hang);ctx=context(runtime);directory=ChannelDirectory(runtime);req=binding(directory,ctx,cap)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(timeout_ms=100),**req,arguments={'count':'two'})
    assert caught.value.details['execution_state']=='not_started' and not seen
    task=asyncio.create_task(directory.invoke_repaired(ctx,options=RepairOptions(),**req,arguments={'count':'two'}))
    await asyncio.sleep(.05);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert not seen and len(calls)==2


@pytest.mark.asyncio
async def test_legacy_router_and_v1_do_not_repair_or_call_model(runtime,monkeypatch):
    calls=fake_model(runtime,monkeypatch,{'limit':2});ctx=context(runtime);directory=ChannelDirectory(runtime)
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('gallery.search',{'limit':'two'},ctx)
    with pytest.raises(Exception):await directory.invoke(ctx,**binding(directory,ctx),arguments={'limit':'two'})
    assert not calls
    result=await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx),arguments={'limit':2})
    assert not result['repair']['ai_used'] and not result['repair']['attempts']


@pytest.mark.asyncio
async def test_http_v2_is_explicit_and_v1_remains_strict(runtime):
    ctx=context(runtime);directory=ChannelDirectory(runtime);req=binding(directory,ctx)
    app=FastAPI();app.include_router(create_capability_router(lambda:runtime,RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        body={**req,'session_id':ctx.session_id,'arguments':{'max_results':'2'}}
        assert (await client.post('/channels/read',json=body)).status_code==422
        assert (await client.post('/channels/read-with-repair',json=body)).status_code==422
        body['protocol']='ai2apps.channels/v2'
        result=await client.post('/channels/read-with-repair',json=body)
        assert result.status_code==200,result.text
        assert result.json()['repair']['attempts'][0]['method']=='deterministic'
        body['max_repair_attempts']=3
        assert (await client.post('/channels/read-with-repair',json=body)).status_code==422


@pytest.mark.asyncio
async def test_no_model_and_attempt_budget_are_explicit(runtime,monkeypatch):
    ctx=context(runtime);directory=ChannelDirectory(runtime);req=binding(directory,ctx)
    monkeypatch.setattr(runtime,'model_manager',None)
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(),**req,arguments={'limit':'two'})
    assert caught.value.code=='repair_model_unavailable'
    result=await directory.invoke_repaired(ctx,options=RepairOptions(),**req,arguments={'limit':2})
    assert not result['repair']['ai_used']
    calls=fake_model(runtime,monkeypatch,{'limit':2})
    with pytest.raises(CapabilityInvocationError) as caught:
        await directory.invoke_repaired(ctx,options=RepairOptions(max_attempts=0),**req,arguments={'limit':'two'})
    assert not calls and caught.value.details['reason']=='repair_budget_exhausted'


@pytest.mark.asyncio
async def test_explicit_owner_default_and_old_path_survive_repair_failure(runtime,monkeypatch):
    cap,seen,schema=arbitrary(runtime);schema['properties']['count']['default']=2
    ctx=context(runtime);directory=ChannelDirectory(runtime);req=binding(directory,ctx,cap)
    result=await directory.invoke_repaired(ctx,options=RepairOptions(mode='deterministic'),**req,arguments={})
    assert seen==[{'count':2}] and result['repair']['attempts']
    import ai2apps.services.parameter_repair as repair
    class Broken:
        def __init__(self,*a):raise RuntimeError('new system unavailable')
    monkeypatch.setattr(repair,'ReadParameterRepair',Broken)
    # Initializer failures of the new host cannot intercept an existing Agent call.
    old=await runtime.app_capability_router.invoke(cap,{'count':2},ctx)
    assert old['seen']=={'count':2}
    old=await directory.invoke(ctx,**req,arguments={'count':2})
    assert old['schema']=='ai2apps.channels/v1'


@pytest.mark.asyncio
async def test_fingerprint_guard_is_checked_again_inside_router(runtime):
    cap,seen,_=arbitrary(runtime);ctx=context(runtime)
    pinned=replace(ctx,pinned_provider=(cap,'unrelated.provider','1'),pinned_parameter_contract='stale')
    with pytest.raises(CapabilityInvocationError) as caught:
        await runtime.app_capability_router.invoke(cap,{'provider':'unrelated.provider','count':2},pinned)
    assert caught.value.code=='version_conflict' and not seen


@pytest.mark.asyncio
async def test_cloud_transport_uses_host_identity_and_privacy_route(runtime,monkeypatch):
    cap,seen,_=arbitrary(runtime);calls=[];routes=[]
    def resolve(purpose,**kw):routes.append((purpose,kw));return 'cloud/fixture/normalizer'
    async def cloud(payload,*,context):
        calls.append((payload,context))
        return {'choices':[{'message':{'content':'{"count":2}'},'finish_reason':'stop'}]}
    monkeypatch.setattr(runtime,'model_manager',SimpleNamespace(resolve_default_model=resolve))
    monkeypatch.setattr(runtime,'model_invocations',SimpleNamespace(invoke_agent_cloud_json=cloud))
    monkeypatch.setattr(runtime,'privacy_mode',True,raising=False)
    ctx=context(runtime);directory=ChannelDirectory(runtime)
    result=await directory.invoke_repaired(ctx,options=RepairOptions(),**binding(directory,ctx,cap),arguments={'count':'two'})
    assert seen==[{'count':2}] and len(calls)==1
    assert routes==[('work_simple',{'profile':'privacy'})]
    assert calls[0][1].actor_user_id==ctx.actor_user_id and calls[0][1].session_id==ctx.session_id
    assert result['repair']['model_usage'] is None  # Never invent usage when absent.


@pytest.mark.asyncio
async def test_deterministic_and_ai_share_attempt_budget(runtime,monkeypatch):
    calls=fake_model(runtime,monkeypatch,{'limit':2});ctx=context(runtime);directory=ChannelDirectory(runtime);req=binding(directory,ctx)
    with pytest.raises(CapabilityInvocationError):
        await directory.invoke_repaired(ctx,options=RepairOptions(max_attempts=1),**req,arguments={'max_results':'two'})
    assert not calls
    result=await directory.invoke_repaired(ctx,options=RepairOptions(max_attempts=2),**req,arguments={'max_results':'two'})
    assert [a['method'] for a in result['repair']['attempts']]==['deterministic','ai'] and len(calls)==1
