from types import SimpleNamespace
from dataclasses import replace
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.identity import RequestPrincipal
from ai2apps.images.parameters import from_options, describe, prepare, validate_size
from ai2apps.services.capability_routing import CapabilityProvider, ProviderIncompatible
from ai2apps.services import ToolCallContext
from ai2apps.api.router import create_ai2apps_router
from test_app_interactions import wait
from legacy_package_backend_fixture import runtime
from test_parameter_forms import setup

@pytest.fixture
def catalog(monkeypatch):
    items=[from_options('fixed','Fixed',{'size':{'mode':'fixed','default':'1024x1024','presets':['1024x1024']},'quality':['auto'],'outputFormat':['png']}),
           from_options('custom','Custom',{'size':{'mode':'bounded-custom','default':'2048x1024','width':{'min':64,'max':4096,'multipleOf':64},'height':{'min':64,'max':4096,'multipleOf':64},'maxPixels':8388608,'maxAspectRatio':4},'quality':['high'],'outputFormat':['webp']})]
    async def models(*args):return items,[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    return items

@pytest.mark.asyncio
async def test_model_schema_and_execution_share_constraints(runtime,catalog):
    p=RequestPrincipal.legacy_local()
    d=await describe(runtime,p,False,'fixed');assert d['effective_schema']['properties']['size']['enum']==['1024x1024']
    d=await describe(runtime,p,False,'custom');assert 'enum' not in d['effective_schema']['properties']['size']
    values=await prepare(runtime,p,{'prompt':'test','model':'custom','size':'4096x2048'})
    assert values['format']=='webp' and values['quality']=='high'
    for args in [{'model':'fixed','size':'4096x2048'}, {'model':'custom','size':'1000x1024'}, {'model':'custom','size':'4096x4096'}, {'model':'custom','size':'2048x1024','format':'png'}, {'model':'absent'}]:
        with pytest.raises(ProviderIncompatible):await prepare(runtime,p,{'prompt':'test',**args})

@pytest.mark.asyncio
async def test_incompatibility_skips_without_health_poison_or_changing_arguments(runtime):
    router=runtime.app_capability_router;seen=[]
    async def reject(args,c):
        args['size']='1024x1024'
        raise ProviderIncompatible('4K unsupported')
    async def execute(args,c):seen.append(args);return {'ok':True}
    router.register(CapabilityProvider('small','test.render','test',execute,priority=100,prepare=reject))
    router.register(CapabilityProvider('large','test.render','test',execute))
    c=ToolCallContext(caller_id='test',actor_user_id='local',installation_id='local')
    result=await router.invoke('test.render',{'size':'4096x2048'},c)
    assert result['provider']=='large' and seen==[{'size':'4096x2048'}]
    assert router.inspect('local','local')[-1]['cooldown_seconds']==0
    seen.clear()
    with pytest.raises(Exception):await router.invoke('test.render',{'provider':'small','size':'4096x2048'},c)
    assert not seen

@pytest.mark.asyncio
async def test_configure_form_returns_arguments_without_generation(runtime,catalog,monkeypatch):
    import test_parameter_forms
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'image-config','capability':'image.edit','provider':'ai2apps.imagine.image-edit','values':{'prompt':'make blue','artifact_id':'reference','model':'fixed'}})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            data=(await client.get(url)).json();assert data['configure_only'] and data['install']['appId']=='ai2apps.imagine-studio'
            values={**data['values'],'size':'4096x2048'}
            assert (await client.put(url,json={'revision':0,'values':values})).status_code==200
            assert (await client.post(url+'/submit',json={'revision':1,'values':values})).status_code==422
            values['model']='custom'
            assert (await client.put(url,json={'revision':1,'values':values})).status_code==200
            updated=(await client.get(url)).json();assert updated['descriptor']['schema']['properties']['format']['enum']==['webp']
            response=await client.post(url+'/submit',json={'revision':2,'values':values});assert response.status_code==200,response.text
            assert response.json()['result']['arguments']['provider']=='ai2apps.imagine.image-edit'
            assert response.json()['result']['arguments']['size']=='4096x2048'
            assert (await client.post(url+'/submit',json={'revision':2,'values':values})).json()==response.json()
        await wait(runtime,run.id,'completed')
        with runtime.database.transaction() as db:assert db.execute('select count(*) from studio_background_jobs').fetchone()[0]==0
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_missing_default_requires_selection_not_first_ready(runtime,catalog,monkeypatch):
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'missing-default')
    p=RequestPrincipal.legacy_local()
    d=await describe(runtime,p,True)
    assert d['model'] is None and d['selection_required']
    assert 'model' in d['effective_schema']['required']
    assert 'default' not in d['effective_schema']['properties']['model']
    with pytest.raises(ProviderIncompatible,match='Model selection required'):
        await prepare(runtime,p,{'prompt':'test','artifact_id':'ref'},True)
    from ai2apps.images import mini_parameters
    d=await mini_parameters.describe(runtime,p,'ai2apps.imagine.group-photo')
    assert d['selection_required'] and 'model' in d['effective_schema']['required']
    with pytest.raises(ProviderIncompatible,match='Model selection required'):
        await mini_parameters.prepare(runtime,p,'ai2apps.imagine.group-photo',{'person_artifact_ids':['a','b'],'background':'garden'})

@pytest.mark.asyncio
async def test_configured_default_selected_even_after_local_model(runtime,catalog,monkeypatch):
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'custom')
    d=await describe(runtime,RequestPrincipal.legacy_local(),True)
    assert d['model']=='custom'
    assert d['effective_schema']['properties']['model']['default']=='custom'


def test_gpt_image_edit_capability_and_explicit_denial():
    from ai2apps.model_capabilities import cloud_model_capabilities as caps
    assert 'image_edit' in caps({'id':'gpt-image-2.5-flare','capabilities':{}})
    assert 'image_edit' not in caps({'id':'gpt-image-2.5-flare','capabilities':{'imageEdit':False}})
    assert 'image_edit' not in caps({'id':'dall-e-3','capabilities':{}})

@pytest.mark.asyncio
async def test_agent_opens_model_form_before_execution_and_resumes(runtime,catalog,monkeypatch):
    import json
    from ai2apps.chat import ChatRepository
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'missing')
    original_context=runtime.tools.context_for_session
    monkeypatch.setattr(runtime.tools,'context_for_session',lambda **kwargs:replace(original_context(**kwargs),actor_user_id='local',installation_id='local'))
    calls=[]
    provider=runtime.app_capability_router.providers['ai2apps.imagine.group-photo']
    async def handler(values,context):
        calls.append(values);return {'ok':True}
    runtime.app_capability_router.providers[provider.id]=replace(provider,handler=handler)
    requests=[]
    async def model(request):
        requests.append(request)
        message={'role':'assistant','content':'done'}
        if not calls:
            alias=next(t['function']['name'] for t in request['tools'] if t['function']['name'].startswith('image__group_photo_'))
            message={'role':'assistant','content':None,'tool_calls':[{'id':'group','type':'function','function':{'name':alias,'arguments':json.dumps({'person_artifact_ids':['a','b'],'background':'garden'})}}]}
        return {'choices':[{'message':message,'finish_reason':'tool_calls' if message.get('tool_calls') else 'stop'}],'usage':{}}
    runtime.agent_runtime.bind_model_provider(model)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Model selection')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'make a group photo','tools':['image.group_photo']})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_input')
        assert not calls
        item=runtime.agents.list_interactions(run.id)[0]
        # Resume from the persisted interaction across scheduler restart.
        await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
            state=(await client.get(url)).json()
            assert 'model' in state['missing'] and state['warnings']
            values={**state['values'],'model':'custom'}
            assert (await client.put(url,json={'revision':0,'values':values})).status_code==200
            response=await client.post(url+'/submit',json={'revision':1,'values':values})
            assert response.status_code==200,response.text
        await wait(runtime,run.id,'waiting_capability')
        approval=next(i for i in runtime.agents.list_interactions(run.id) if i.status.value=='pending')
        runtime.agents.respond_interaction(run.id,approval.id,response={'decision':'approve'},response_id='approve-model-test')
        runtime.agent_runtime.wake()
        await wait(runtime,run.id,'completed')
        assert len(calls)==1 and calls[0]['model']=='custom'
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_legacy_default_matches_same_cloud_model_only(runtime,catalog,monkeypatch):
    catalog[1]['id']='cloud/ai2apps/openai/gpt-image-2.5-flare'
    monkeypatch.setattr('ai2apps.images.service._default_image_model',lambda store:'cloud/openai/gpt-image-2.5-flare')
    monkeypatch.setattr(runtime.model_manager,'list_cloud',lambda:[{'id':'openai','configured':False}])
    d=await describe(runtime,RequestPrincipal.legacy_local(),True)
    assert d['model']==catalog[1]['id']
    monkeypatch.setattr(runtime.model_manager,'list_cloud',lambda:[{'id':'openai','configured':True}])
    d=await describe(runtime,RequestPrincipal.legacy_local(),True)
    assert d['selection_required'] and d['model'] is None

@pytest.mark.asyncio
async def test_agent_failure_keeps_provider_identity_parameters_and_stage(runtime,monkeypatch):
    import json
    from ai2apps.chat import ChatRepository
    original_context=runtime.tools.context_for_session
    monkeypatch.setattr(runtime.tools,'context_for_session',lambda **kwargs:replace(original_context(**kwargs),actor_user_id='local',installation_id='local'))
    provider=runtime.app_capability_router.providers['ai2apps.imagine.group-photo']
    async def reject(values,context):raise ProviderIncompatible('Reference roles conflict')
    runtime.app_capability_router.providers[provider.id]=replace(provider,describe=None,prepare=reject)
    async def model(request):
        alias=next(t['function']['name'] for t in request['tools'] if t['function']['name'].startswith('image__group_photo_'))
        return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'group','type':'function','function':{'name':alias,'arguments':json.dumps({'person_artifact_ids':['art_a','art_b'],'background':'garden'})}}]},'finish_reason':'tool_calls'}],'usage':{}}
    runtime.agent_runtime.bind_model_provider(model)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Failure detail')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'make a group photo','tools':['image.group_photo']})
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_capability')
        approval=next(i for i in runtime.agents.list_interactions(run.id) if i.status.value=='pending')
        runtime.agents.respond_interaction(run.id,approval.id,response={'decision':'approve','scope':'run'},response_id='approve-failure-test')
        await wait(runtime,run.id,'failed')
        with runtime.database.transaction() as db:
            row=db.execute("SELECT input_json,error_json FROM run_steps WHERE run_id=? AND kind='tool' AND json_extract(error_json,'$.code')='provider_incompatible'",(run.id,)).fetchone()
        error=json.loads(row['error_json'])
        assert error['code']=='provider_incompatible'
        assert error['details']['mini_app_id']==provider.mini_app_id
        assert error['details']['app_id']==provider.app_id
        assert error['details']['phase']=='prepare'
        assert json.loads(row['input_json'])['person_artifact_ids']==['art_a','art_b']
        assert 'Reference roles conflict' in error['message']
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_agent_corrects_preflight_failure_then_continues(runtime,monkeypatch):
    import json
    from ai2apps.chat import ChatRepository
    original_context=runtime.tools.context_for_session
    monkeypatch.setattr(runtime.tools,'context_for_session',lambda **kwargs:replace(original_context(**kwargs),actor_user_id='local',installation_id='local'))
    provider=runtime.app_capability_router.providers['ai2apps.imagine.group-photo']
    prepared=[];executed=[];requests=[]
    async def prepare(values,context):
        prepared.append(values['background'])
        if values['background']=='invalid':raise ProviderIncompatible('Use a valid background description')
        return values
    async def handler(values,context):executed.append(values);return {'ok':True}
    runtime.app_capability_router.providers[provider.id]=replace(provider,describe=None,prepare=prepare,handler=handler)
    async def model(request):
        requests.append(request)
        if len(requests)>3:return {'choices':[{'message':{'role':'assistant','content':'done'},'finish_reason':'stop'}],'usage':{}}
        if len(requests)==3:
            failures=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
            assert failures[-1]['error']['phase']=='prepare'
            assert failures[-1]['error']['details']['provider']==provider.id
        alias=next(t['function']['name'] for t in request['tools'] if t['function']['name'].startswith('image__group_photo_'))
        return {'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'group-'+str(len(requests)),'type':'function','function':{'name':alias,'arguments':json.dumps({'person_artifact_ids':['art_a','art_b'],'background':'invalid' if len(requests)<=2 else 'garden'})}}]},'finish_reason':'tool_calls'}],'usage':{}}
    runtime.agent_runtime.bind_model_provider(model)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Correct provider arguments')
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key='ai2apps.general-agent',input={'model':'test','prompt':'make a group photo','tools':['image.group_photo']})
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_capability')
        approval=next(i for i in runtime.agents.list_interactions(run.id) if i.status.value=='pending')
        runtime.agents.respond_interaction(run.id,approval.id,response={'decision':'approve','scope':'run'},response_id='approve-recovery-test')
        await wait(runtime,run.id,'completed')
        assert prepared==['invalid','garden']
        assert len(executed)==1 and executed[0]['background']=='garden'
        assert len(requests)==4
    finally:await runtime.stop_background_tasks()


def test_legacy_providers_declare_user_facing_labels(runtime):
    # Alternates in the shared form list show Provider names, not raw ids.
    from ai2apps.agents.parameter_forms import FORMS
    router=runtime.app_capability_router
    catalog={p['id']:p for p in router.catalog()}
    inspected={p['id']:p for p in router.inspect('local','local')}
    for provider_id in ('ai2apps.images.generate','ai2apps.web-research.search','ai2apps.web-research.fetch',
                        'ai2apps.search-all.search','ai2apps.web-reader.fetch'):
        provider=router.providers[provider_id]
        assert {'zh','en'}<=set(provider.display_name)
        assert {'zh','en'}<=set(provider.summary)
        for view in (catalog,inspected):
            assert view[provider_id]['display_name']==provider.display_name
            assert view[provider_id]['summary']==provider.summary
        if provider_id in FORMS:
            assert FORMS[provider_id].display_name==provider.display_name
            assert FORMS[provider_id].summary==provider.summary


@pytest.mark.asyncio
async def test_app_discovery_exposes_provider_labels(runtime,catalog):
    bound=runtime.service_registry.bound_tool('app.describe')
    from test_builtin_app_aaat import context
    discovered=await bound.handler({},context(runtime))
    assert discovered['projection']=='summary' and discovered['forms']==[]
    for identifier in ('ai2apps.images.generate','ai2apps.imagine.group-photo','ai2apps.search-all.search','ai2apps.web-reader.fetch'):
        provider=runtime.app_capability_router.providers[identifier]
        forms={f['provider']:f for f in (await bound.handler({'capability':identifier},context(runtime)))['forms']}
        assert forms[identifier]['display_name']==provider.display_name
        assert forms[identifier]['summary']==provider.summary


@pytest.mark.asyncio
@pytest.mark.parametrize('explicit',[False,True])
@pytest.mark.parametrize('submitted',[False,True])
async def test_search_all_confirmation_and_failed_workflow_do_not_fall_back_to_http(runtime,monkeypatch,explicit,submitted):
    from ai2apps.chat import ChatRepository
    from ai2apps.core import ResourceNotFoundError
    from ai2apps.research.mini_apps import WebMiniAppAdapters
    from ai2apps.services import ToolProviderError
    from ai2apps.services.capability_routing import CapabilityInvocationError
    router=runtime.app_capability_router
    http=router.providers['ai2apps.web-research.search'];calls=[]
    async def legacy(arguments,context):calls.append('http');return {'results':[{'url':'https://example.com'}]}
    router.providers[http.id]=replace(http,handler=legacy)
    if submitted:
        async def failed(runtime,arguments,context):
            calls.append('submitted-mini');raise ToolProviderError('Confirmed search workflow failed after submission')
        monkeypatch.setattr('ai2apps.research.search_workflow.invoke',failed)
    else:
        def missing(*args,**kwargs):raise ResourceNotFoundError('mini_app','ai2apps.search-all')
        monkeypatch.setattr('ai2apps.browser.mini_apps.WebAgentMiniAppBroker.registered',missing)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Search boundary')
    context=ToolCallContext('test',actor_user_id='local',installation_id='local',session_id=thread.session.id)
    arguments={'query':'SQLite WAL'}
    if explicit:arguments['provider']='ai2apps.search-all.search'
    # An unconfirmed Agent invocation cannot fall through to HTTP, even if Search All is absent.
    with pytest.raises(CapabilityInvocationError):await router.invoke('web.search',arguments,context)
    assert 'http' not in calls
    if submitted:assert calls==['submitted-mini']
