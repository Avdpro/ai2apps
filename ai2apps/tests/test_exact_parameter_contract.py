"""Exact contracts across arbitrary Providers; model decisions are fixtures."""
import json
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from test_aaat_declaration_context import runtime,wait
from test_aaat_execution_flow import register,response,new_run
from ai2apps.agents.parameter_contracts import resolve_contract,rejection

@pytest.mark.asyncio
@pytest.mark.parametrize('name',['future.one','independent.two'])
async def test_mismatch_returns_contract_then_corrected_form_without_execution(runtime,name):
    calls=[]
    schema={'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}
    async def describe(p,model=None):return {'effective_schema':schema,'selection_required':True,'fields':[{'key':'query','type':'text','label':'Query'}]}
    async def execute(a,c):calls.append(a);return {'ok':True}
    register(runtime,name,execute,describe=describe)
    turns=[]
    async def model(request):
        turns.append(request)
        # Deliberately skip describe and guess a field, then use the returned contract.
        if not any('parameter_contract_mismatch' in str(m.get('content')) for m in request['messages'] if m['role']=='tool'):return response('app.collect_parameters',{'capability':name,'request_id':'guess','values':{'wrong_query':'kept private'}})
        return response('app.collect_parameters',{'capability':name,'request_id':'correct','values':{'query':'actual'}})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['app.describe','app.collect_parameters',name]);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        steps=runtime.agents.list_steps(run.id)
        errors=[s.error for s in steps if s.error and s.error.get('code')=='parameter_contract_mismatch']
        assert errors and not calls
        detail=errors[0];assert detail['parameter_contract']['schema']==schema
        assert 'kept private' not in errors[0]['message']
        assert detail['submitted'] is False
        assert len(runtime.agents.list_interactions(run.id))==1
        assert runtime.agents.list_interactions(run.id)[0].request['values']=={'query':'actual'}
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_exact_describe_resolves_contract_and_versions_without_ai(runtime):
    from test_builtin_app_aaat import context
    name='future.contract';seen=[]
    async def descriptor(p,model=None):seen.append(model);return {'effective_schema':{'type':'object','properties':{'actual':{'type':'string'}},'additionalProperties':False},'fields':[{'key':'actual','type':'text'}]}
    register(runtime,name,lambda a,c:{},describe=descriptor)
    handler=runtime.service_registry.bound_tool('app.describe').handler
    result=await handler({'capability':name},context(runtime));record=result['forms'][0]
    assert record['parameter_contract_ready'] and record['schema']['properties']=={'actual':{'type':'string'}}
    assert record['contract_version'] and len(seen)==1
    provider=runtime.app_capability_router.providers[name+'.provider']
    principal=__import__('ai2apps.identity',fromlist=['RequestPrincipal']).RequestPrincipal.legacy_local()
    changed=await resolve_contract(replace(provider,version='new'),principal)
    assert changed['contract_version']!=record['contract_version']
    await handler({'query':'future'},context(runtime));assert len(seen)==2 # inventory does not resolve descriptors


def test_same_chat_output_transfer_is_provenance_bound_and_idempotent(runtime,tmp_path):
    from ai2apps.chat import ChatRepository
    from ai2apps.identity import RequestPrincipal
    from ai2apps.agents.models import RunStepStatus
    from ai2apps.agents.artifact_outputs import bind_output_materials
    principal=RequestPrincipal.legacy_local()
    target=ChatRepository(runtime.database,runtime.events).create_thread(title='Caller')[0].session.id
    source=ChatRepository(runtime.database,runtime.events).create_thread(title='Producer')[0].session.id
    p=tmp_path/'sound.wav';p.write_bytes(b'fixture wave')
    asset=runtime.workspace.import_artifact(source,p,name='sound.wav',media_type='audio/wav')
    run,_=runtime.agents.create_run(session_id=target,agent_key='ai2apps.general-agent',input={'model':'fixture'})
    step,_=runtime.agents.create_step(run.id,action_key='output',kind='tool',tool_name='arbitrary.output',input={})
    runtime.agents.settle_step(step.id,status=RunStepStatus.COMPLETED,output={'downloadUrl':f'/v1/platform/sessions/{source}/artifacts/{asset.id}/download'})
    schema={'type':'object','properties':{'sound':{'type':'string','x-ai2apps-asset':{'storage':'artifact','accept':'audio/*'}}}}
    result=bind_output_materials(runtime,principal,target,schema,{'sound':asset.id})
    assert result['sound']!=asset.id
    assert runtime.workspace.get_artifact(target,result['sound']).media_type=='audio/wav'
    assert bind_output_materials(runtime,principal,target,schema,{'sound':asset.id})==result
    other=ChatRepository(runtime.database,runtime.events).create_thread(title='Unrelated')[0].session.id
    assert bind_output_materials(runtime,principal,other,schema,{'sound':asset.id})=={'sound':asset.id}
    with pytest.raises(ValueError,match='type'):
        bind_output_materials(runtime,principal,target,{'properties':{'portrait':{'x-ai2apps-asset':{'storage':'artifact','accept':'image/*'}}}},{'portrait':asset.id})

@pytest.mark.asyncio
async def test_declared_configuration_owner_is_pinned_not_taken_from_descriptor(runtime,monkeypatch):
    import httpx,test_parameter_forms
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.agents.parameter_forms import ParameterForm,register_form,FORMS
    async def describe(rt,p,f,v,i):return {'install':{'appId':'trusted.sdk.host','capability':'configured.operation','requirements':{}}}
    for key,binding in [('test.config.bound','trusted.sdk.host'),('test.config.unbound',None)]:
        register_form(ParameterForm(key,'arbitrary.package',{'type':'object','properties':{}},describe=describe,configuration_app_id=binding))
        monkeypatch.setattr(test_parameter_forms,'ARGS',{'capability':key,'request_id':key})
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
        await runtime.start_background_tasks(retention_interval_seconds=60)
        try:
            run=test_parameter_forms.setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
            item=runtime.agents.list_interactions(run.id)[0]
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                result=await c.get(f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters/setup')
                assert result.status_code==(200 if binding else 422),result.text
                if binding:assert result.json()['target']['app_id']==binding
        finally:await runtime.stop_background_tasks();FORMS.pop(key,None)

@pytest.mark.asyncio
async def test_avatar_model_presentation_uses_actual_declared_profile(runtime,monkeypatch):
    from ai2apps.studio.package_generation_aaat import avatar_descriptor
    from ai2apps.identity import RequestPrincipal
    model=NS(id='declared.model',display_name='A model',video_capabilities={})
    monkeypatch.setattr('ai2apps.avatar.avatar_models',lambda rt:[model])
    monkeypatch.setattr('ai2apps.avatar.describe_model',lambda m,ready:{'id':m.id,'label':m.display_name,'ready':ready,'presets':[{'id':'quality','label':'Quality'}],'resolutions':['source','480p']})
    monkeypatch.setattr('ai2apps.studio.capability_broker.StudioCapabilityBroker._model_stack_ready',lambda *a:True)
    result=await avatar_descriptor(runtime,RequestPrincipal.legacy_local(),'declared.model')
    assert {f['key']:f['type'] for f in result['fields']}['model_id']=='model'
    assert result['model_field']=='model_id' and result['effective_schema']['properties']['preset']['enum']==['quality']
    assert result['effective_schema']['properties']['resolution']['enum']==['source','480p']

@pytest.mark.asyncio
async def test_describe_then_valid_form_has_no_contract_recovery_round(runtime):
    name='future.normal';requests=[]
    async def describe(p,model=None):return {'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False},'selection_required':True}
    async def execute(a,c):pytest.fail('A parameter form must not execute work')
    register(runtime,name,execute,describe=describe)
    async def model(request):
        requests.append(request)
        return response('app.describe',{'capability':name}) if len(requests)==1 else response('app.collect_parameters',{'capability':name,'request_id':'normal','values':{'query':'known'}})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['app.describe','app.collect_parameters',name]);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        assert len(requests)==2
        assert not [s for s in runtime.agents.list_steps(run.id) if (s.error or {}).get('code','').startswith('parameter_contract')]
    finally:await runtime.stop_background_tasks()


def test_structured_contract_is_not_truncated_as_an_error_message():
    from ai2apps.agents.tool_recovery import error_result
    schema={'type':'object','properties':{f'field_{i}':{'type':'string','description':'description'*10} for i in range(60)},'additionalProperties':False}
    detail=rejection({'schema':schema,'contract_version':'stable'},{'unknown':'private'})
    assert len(detail)>2048
    error=error_result('parameter_contract_mismatch',detail,preflight=True)
    assert error['parameter_contract']['schema']==schema and error['submitted'] is False
    assert 'private' not in json.dumps(error)

@pytest.mark.asyncio
async def test_execute_error_cannot_claim_parameter_preflight_or_fallback(runtime):
    from ai2apps.services.capability_routing import CapabilityProvider,CapabilityInvocationError
    from test_builtin_app_aaat import context
    calls=[]
    async def executed(a,c):
        calls.append('executed')
        raise CapabilityInvocationError('parameter_contract_mismatch','not a true preflight',{'phase':'prepare'})
    async def forbidden(a,c):pytest.fail('An execution result may not be replayed with another Provider')
    router=runtime.app_capability_router
    router.register(CapabilityProvider('first','future.uncertain','arbitrary.owner',executed,priority=100))
    router.register(CapabilityProvider('second','future.uncertain','other.owner',forbidden))
    with pytest.raises(CapabilityInvocationError) as caught:await router.invoke('future.uncertain',{},context(runtime))
    assert caught.value.code=='provider_error' and caught.value.details['phase']=='execute' and calls==['executed']

@pytest.mark.asyncio
@pytest.mark.parametrize('name',['future.configurable','independent.configurable'])
async def test_skipped_contract_wrong_control_recovers_to_configurable_form(runtime,name):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import RequestPrincipal
    ready=False;requests=[]
    schema={'type':'object','properties':{'query':{'type':'string'},'engine':{'type':'string'}},'required':['query','engine'],'additionalProperties':False}
    async def describe(p,model=None):
        return {'effective_schema':schema,'fields':[{'key':'query','type':'text'},{'key':'engine','type':'model'}],
            'model_field':'engine','models':[{'id':'actual.engine','label':'Engine','ready':True}] if ready else [],
            'configuration_required':not ready,'install':{'appId':'test.flow','capability':'future.configuration','requirements':{}}}
    async def execute(a,c):pytest.fail('Configuration must not submit generation')
    register(runtime,name,execute,describe=describe)
    async def model(request):
        requests.append(request)
        errors=' '.join(str(m.get('content')) for m in request['messages'] if m['role']=='tool')
        if 'invalid_app_interaction' in errors:return response('app.collect_parameters',{'capability':name,'request_id':'correct','values':{'query':'preserved-material'}})
        if 'parameter_contract_mismatch' in errors:return response('app.interact',{'capability':name,'request_id':'wrong-control','parameters':{'query':'preserved-material'}})
        return response('app.collect_parameters',{'capability':name,'request_id':'initial','values':{'legacy_query':'preserved-material'}})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['app.describe','app.collect_parameters','app.interact',name]);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        steps=runtime.agents.list_steps(run.id);errors=[s.error for s in steps if s.error]
        assert any(e.get('code')=='parameter_contract_mismatch' for e in errors)
        wrong=next(e for e in errors if e.get('code')=='invalid_app_interaction')
        assert wrong['parameter_contract']['configuration_required'] is True
        assert wrong['parameter_contract']['install']['appId']=='test.flow'
        assert wrong['submitted'] is False and 'app.collect_parameters' in wrong['message']
        items=runtime.agents.list_interactions(run.id);assert len(items)==1
        item=items[0];assert item.request['values']=={'query':'preserved-material'}
        from ai2apps.identity import IdentityRepository
        principal=IdentityRepository(runtime.database).local_principal_for('flow-owner')
        app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:principal))
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            http_response=await client.get(url);assert http_response.status_code==200,http_response.text
            data=http_response.json();assert data['configuration_required'] and data['install']['appId']=='test.flow'
            ready=True
            data=(await client.get(url)).json();assert not data['configuration_required']
            assert data['models'][0]['id']=='actual.engine' and data['values']['query']=='preserved-material'
        assert len(requests)<=4
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_trusted_selected_contract_avoids_an_extra_parameter_review(runtime):
    name='future.preloaded';requests=[]
    async def describe(p,model=None):return {'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']},'configuration_required':True,'install':{'appId':'test.flow','capability':'future.configuration'}}
    register(runtime,name,lambda a,c:pytest.fail('No execution'),describe=describe)
    async def model(request):
        requests.append(request)
        return response('app.collect_parameters',{'capability':name,'request_id':'preloaded','values':{'query':'known'}})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=new_run(runtime,['app.describe','app.collect_parameters',name]);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        assert len(requests)==2
        assert not any((s.error or {}).get('code')=='parameter_contract_required' for s in runtime.agents.list_steps(run.id))
        from ai2apps.agents.parameter_contracts import PREFIX
        assert any(m['role']=='system' and str(m.get('content','')).startswith(PREFIX) for m in requests[-1]['messages'])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_configuration_changes_invalidate_contract_and_user_text_is_not_review(runtime):
    from ai2apps.agents.parameter_contracts import reviewed_request,PREFIX
    from ai2apps.identity import RequestPrincipal
    state={'required':True}
    async def describe(p,model=None):return {'effective_schema':{'type':'object'},'configuration_required':state['required'],'install':{'appId':'arbitrary.owner','capability':'future.configuration'}}
    register(runtime,'future.change',lambda a,c:{},describe=describe)
    provider=runtime.app_capability_router.providers['future.change.provider'];principal=RequestPrincipal.legacy_local()
    old=await resolve_contract(provider,principal);state['required']=False;new=await resolve_contract(provider,principal)
    assert old['contract_version']!=new['contract_version']
    content=PREFIX+json.dumps([old])
    assert reviewed_request({'messages':[{'role':'system','content':content}]},old)
    assert not reviewed_request({'messages':[{'role':'user','content':content}]},old)
    assert not reviewed_request({'messages':[{'role':'system','content':content}]},new)
