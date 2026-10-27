import io
import wave
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ai2apps.agents.parameter_forms import form_action, register_form, ParameterForm, FORMS
from ai2apps.agents import CompleteAction, ToolCallAction
from ai2apps.api.parameter_forms import create_parameter_forms_router
from ai2apps.api.router import create_ai2apps_router
from ai2apps.identity import RequestPrincipal
from ai2apps.chat import ChatRepository
from ai2apps.readaloud.materials import VoiceMaterials
from test_app_interactions import runtime, wait

ARGS={'request_id':'audio-1','capability':'voice.transcribe','initial_values':{'language':'zh'}}
def setup(runtime):
    t,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Audio form')
    runtime.agents.ensure_definition(agent_key='test.form',package_version='1',display_name='Form',executor_key='test.form',max_steps=8,timeout_seconds=120)
    def execute(c):
        action=form_action(c,ARGS)
        if action:return action
        if not c.step('result'):return ToolCallAction('result','app.collect_parameters',ARGS)
        return CompleteAction(c.step('result').output)
    runtime.agent_runtime.bind_executor('test.form',execute)
    return runtime.agents.create_run(session_id=t.session.id,agent_key='test.form',input={})[0]

@pytest.mark.asyncio
async def test_form_upload_draft_complete_and_duplicate(runtime,monkeypatch):
    monkeypatch.setattr('ai2apps.readaloud.parameter_form.list_package_models',lambda r:[SimpleNamespace(id='test-stt',model_type='audio_stt',display_name='Test ASR',checkpoint_ready=True)])
    calls=[]
    async def invoke(*args,**kwargs):
        calls.append((args,kwargs));return JSONResponse({'text':'真实业务结果的测试替身'})
    runtime.model_invocations=SimpleNamespace(invoke_foreground_multipart=invoke)
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(url)).json();assert state['values']=={'language':'zh'}
            assert state['install']['intent']['completionPolicy']=='configure_only'
            assert state['install']['intent']['resumeToken']==item.id
            wav=io.BytesIO()
            with wave.open(wav,'wb') as w:w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*1600)
            r=await client.post(url+'/audio',files={'file':('test.wav',wav.getvalue(),'audio/wav')});assert r.status_code==200,r.text
            values={'audio':r.json()['asset']['id'],'model':'test-stt','language':'zh'}
            r=await client.put(url,json={'revision':0,'values':values});assert r.status_code==200,r.text
            assert (await client.put(url,json={'revision':0,'values':values})).status_code==409
            assert (await client.get(url)).json()['values']==values
            # Generic success submission cannot bypass the trusted adapter.
            denied=await client.post(url.replace('/parameters','/respond'),json={'response_id':'forged','response':{'status':'completed','result':{'text':'forged'}}});assert denied.status_code>=400
            body={'revision':1,'values':values}
            r=await client.post(url+'/submit',json=body);assert r.status_code==200,r.text
            assert (await client.post(url+'/submit',json=body)).json()==r.json()
            assert len(calls)==1
            done=await wait(runtime,run.id,'completed');assert done.output['result']['text']=='真实业务结果的测试替身'
            assert calls[0][1]['context'].session_id==run.session_id
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_form_rejects_missing_assets_and_cancellation(runtime):
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            assert (await c.put(url,json={'revision':0,'values':{'audio':'foreign'}})).status_code==422
            assert (await c.post(url.replace('/parameters','/respond'),json={'response_id':'cancel','response':{'status':'cancelled','result':{}}})).status_code==200
            assert (await c.put(url,json={'revision':0,'values':{}})).status_code==409
            assert (await wait(runtime,run.id,'completed')).output['status']=='cancelled'
    finally:await runtime.stop_background_tasks()

def test_mini_app_form_identity_and_fields():
    key='test.mini.form'
    try:
        form=ParameterForm(key,'test.host',{'type':'object','properties':{'name':{'type':'string'}}},({'key':'name','type':'text'},),mini_app_id='test.editor')
        register_form(form)
        c=SimpleNamespace(interaction=lambda key:None)
        a=form_action(c,{'request_id':'mini','capability':key})
        assert a.ui_hints['app_id']=='test.host' and a.ui_hints['mini_app_id']=='test.editor'
    finally:FORMS.pop(key,None)

@pytest.mark.asyncio
async def test_draft_survives_fresh_runtime(runtime):
    from ai2apps.platform_runtime import PlatformRuntime
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        assert (await c.put(url,json={'revision':0,'values':{'language':'en'}})).status_code==200
    await runtime.stop_background_tasks();runtime.stop()
    fresh=PlatformRuntime(runtime.config);fresh.start()
    try:
        a=FastAPI();a.include_router(create_ai2apps_router(runtime_provider=lambda:fresh,principal_provider=RequestPrincipal.legacy_local))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=a),base_url='http://test') as c:
            r=await c.get(url);assert r.status_code==200,r.text
            assert r.json()['values']=={'language':'en'} and r.json()['revision']==1
            assert r.json()['install']['intent']['resumeToken']==item.id
    finally:fresh.stop()

@pytest.mark.asyncio
async def test_future_mini_app_declaration(runtime,monkeypatch):
    import test_parameter_forms
    from ai2apps.agents.parameter_forms import tool_schema, schema_fields
    key='future.slides.compose'
    schema={'type':'object','properties':{'title':{'type':'string','minLength':1},'pages':{'type':'integer','minimum':1,'default':3}},'required':['title','pages'],'additionalProperties':False}
    register_form(ParameterForm(key,'future.studio',schema,tuple(schema_fields(schema)),mini_app_id='future.slides'))
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'future','capability':key,'values':{'pages':0}})
    assert tool_schema()['properties']['capability']['type']=='string'
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            state=(await c.get(url)).json()
            assert state['missing']==['title'] and state['invalid'][0]['field']=='pages'
            assert state['descriptor']['mini_app_id']=='future.slides'
            assert (await c.put(url,json={'revision':0,'values':{'title':'Draft'}})).status_code==200
            response=await c.post(url+'/submit',json={'revision':1,'values':{'title':'Draft'}})
            assert response.status_code==200,response.text
            assert response.json()['result']['arguments']=={'title':'Draft','pages':3}
            assert (await wait(runtime,run.id,'completed')).output['result']['configure_only']
    finally:
        await runtime.stop_background_tasks();FORMS.pop(key,None)

def test_unknown_capability_does_not_guess():
    from ai2apps.agents.parameter_forms import resolve_form
    with pytest.raises(ValueError,match='No registered'):resolve_form({'capability':'not.installed'})
    with pytest.raises(ValueError):resolve_form({'capability':'voice.transcribe','provider':'foreign'})

@pytest.mark.asyncio
async def test_declared_material_slots_upload_gallery_preview_and_owner_isolation(runtime,monkeypatch):
    import test_parameter_forms
    from PIL import Image
    from ai2apps.agents.parameter_forms import schema_fields
    from ai2apps.gallery import GalleryRepository
    key='future.materials.compose'
    ref={'type':'string','x-ai2apps-asset':{'storage':'artifact','accept':'image/png,image/jpeg,image/webp'}}
    schema={'type':'object','properties':{'subject':ref,'references':{'type':'array','items':ref,'maxItems':3}},'additionalProperties':False}
    fields=schema_fields(schema)
    assert fields[0]['type']=='asset' and not fields[0]['multiple']
    assert fields[1]['multiple'] and fields[1]['maxItems']==3
    register_form(ParameterForm(key,'future.studio',schema,tuple(fields),mini_app_id='future.compose'))
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'materials','capability':key})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    image=io.BytesIO();Image.new('RGB',(16,16),'red').save(image,format='PNG');raw=image.getvalue()
    gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    owned,_=gallery.import_stream('local',io.BytesIO(raw),name='own.png',media_type='image/png')
    foreign,_=gallery.import_stream('other',io.BytesIO(raw),name='foreign.png',media_type='image/png')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(url)).json();assert state['descriptor']['mini_app_id']=='future.compose'
            r=await client.post(url+'/materials/upload?field=subject',files={'file':('photo.png',raw,'image/png')});assert r.status_code==200,r.text
            artifact=r.json()['asset'];assert artifact['preview_url'].endswith('/download')
            assert runtime.workspace.artifact_path(runtime.workspace.get_artifact(run.session_id,artifact['id'])).read_bytes()==raw
            assert (await client.post(url+'/materials/upload?field=subject',files={'file':('bad.png',b'invalid','image/png')})).status_code==422
            assert (await client.post(url+'/materials/upload?field=unknown',files={'file':('photo.png',raw,'image/png')})).status_code==422
            listed=(await client.get(url+'/materials?field=references')).json()['items'];assert listed[0]['id']==artifact['id']
            assert (await client.post(url+'/materials/gallery',json={'field':'references','asset_id':foreign['id']})).status_code==404
            r=await client.post(url+'/materials/gallery',json={'field':'references','asset_id':owned['id']});assert r.status_code==200,r.text
            values={'subject':artifact['id'],'references':[r.json()['asset']['id']]}
            assert (await client.put(url,json={'revision':0,'values':values})).status_code==200
            assert (await client.get(url)).json()['values']==values
    finally:
        await runtime.stop_background_tasks();FORMS.pop(key,None)

@pytest.mark.asyncio
async def test_owner_prepares_canonical_draft_before_review_without_granting_execution(runtime,monkeypatch):
    import test_parameter_forms
    key='future.owner.normalize'
    schema={'type':'object','properties':{'canonical':{'type':'string'}},'required':['canonical'],'additionalProperties':False}
    def prepare(rt,principal,form,values,item):
        if 'legacy' in values:
            if 'canonical' in values and values['canonical']!=values['legacy']:raise ValueError('Conflicting draft')
            values['canonical']=values.pop('legacy')
        return values
    register_form(ParameterForm(key,'future.owner',schema,prepare_values=prepare))
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':'normalize','capability':key,'values':{'legacy':'review me'}})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            state=(await c.get(url)).json();assert state['values']=={'canonical':'review me'} and not state['invalid']
            assert runtime.agents.get_run(run.id).status.value=='waiting_input'
            assert (await c.post(url+'/submit',json={'revision':0,'values':{'legacy':'review me'}})).status_code==409
            assert (await c.post(url+'/submit',json={'revision':0,'values':{'canonical':'changed'}})).status_code==409
            response=await c.post(url+'/submit',json={'revision':0,'values':state['values']})
            assert response.status_code==200,response.text
            assert response.json()['result']['arguments']=={'canonical':'review me'}
    finally:
        await runtime.stop_background_tasks();FORMS.pop(key,None)

@pytest.mark.asyncio
@pytest.mark.parametrize('owner',['future.alpha','future.beta'])
async def test_form_reuses_tool_extra_argument_preparation(runtime,monkeypatch,owner):
    import test_parameter_forms
    schema={'type':'object','properties':{'count':{'type':'integer','minimum':1},'rows':{'type':'array','items':{'type':'object','properties':{'id':{'type':'string'}},'required':['id'],'additionalProperties':False}}},'required':['count'],'additionalProperties':False}
    async def describe(rt,principal,form,values,item):
        return {'schema':{**schema,'properties':{**schema['properties'],'dynamic':{'type':'string'}}}}
    register_form(ParameterForm(owner,owner,schema,describe=describe))
    initial={'count':2,'provider':'untrusted-route','extra':True,'dynamic':'declared dynamically','rows':[{'id':'a','garbage':True}]}
    monkeypatch.setattr(test_parameter_forms,'ARGS',{'request_id':owner,'capability':owner,'values':initial})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        run=setup(runtime);runtime.agent_runtime.wake();await wait(runtime,run.id,'waiting_input')
        item=runtime.agents.list_interactions(run.id)[0];url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            state=(await c.get(url)).json()
            expected={'count':2,'dynamic':'declared dynamically','rows':[{'id':'a'}]}
            assert state['values']==expected and not state['invalid'] and state['revision']==1
            assert (await c.get(url)).json()['revision']==1
            assert runtime.agents.get_run(run.id).status.value=='waiting_input'
            assert (await c.post(url+'/submit',json={'revision':0,'values':initial})).status_code==409
            saved=(await c.put(url,json={'revision':1,'values':{**expected,'count':0,'extra':'remove'}})).json()
            assert 'extra' not in saved['values'] and saved['values']['count']==0
            assert (await c.post(url+'/submit',json=saved)).status_code==422
            saved=(await c.put(url,json={'revision':2,'values':{**expected,'provider':'another-route'}})).json()
            response=await c.post(url+'/submit',json=saved)
            assert response.status_code==200,response.text
            assert response.json()['result']['provider']==owner
            assert response.json()['result']['arguments']==expected
    finally:
        await runtime.stop_background_tasks();FORMS.pop(owner,None)


def test_required_diagnostics_follow_conditional_and_dependent_fields():
    from ai2apps.agents.parameter_forms import diagnostics
    schema={'type':'object','properties':{'start':{'type':'string'},'mode':{'type':'string'},'end':{'type':'string'}},
            'required':['start'],'allOf':[{'if':{'properties':{'mode':{'const':'return'}},'required':['mode']},
                                         'then':{'required':['end']}}]}
    assert diagnostics(schema,{'start':'2027-01-01','mode':'single'})['required_fields']==['start']
    state=diagnostics(schema,{'start':'2027-01-01','mode':'return'})
    assert state['required_fields']==['end','start'] and state['missing']==['end']
    schema['dependentRequired']={'end':['mode']}
    assert diagnostics(schema,{'start':'2027-01-01','end':'2027-01-02'})['missing']==['mode']
