"""Identity isolation, immutable appearance revisions and shared Gallery references."""
from io import BytesIO
import pytest
from ai2apps.gallery.characters import Characters, CharacterInput
from ai2apps.gallery.repository import GalleryRepository, GalleryError
from test_app_interactions import runtime


def test_character_variants_and_revision_guards(runtime):
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    # A valid raster file is imported through Gallery's normal validation.
    from PIL import Image
    stream=BytesIO();Image.new('RGB',(16,16),'red').save(stream,'PNG');stream.seek(0)
    image,_=repo.import_stream('local',stream,name='ref.png',media_type='image/png')
    store=Characters(repo,'local')
    value={'name':'本人','appearances':[{'id':'chibi','name':'大头卡通','style_id':'chibi','proportions':'three heads','reference_ids':[image['id']],'definition_image_id':image['id'],'summary':'Three-head chibi guide','approved':True},{'id':'hero','name':'超级英雄'}],'default_appearance_id':'chibi'}
    first=store.save(CharacterInput(**value))
    assert first['revision']==1 and len(store.list())==1
    assert first['appearances'][0]['proportions']=='three heads'
    assert first['appearances'][0]['style_id']=='chibi'
    assert repo.list_assets('local',kind='character')[0]['kind']=='character'
    assert Characters(repo,'someone-else').list()==[]
    with pytest.raises(Exception): Characters(repo,'someone-else').get(first['id'])
    value['revision']=1;value['appearances'][0]['outfit']='red suit'
    second=store.save(CharacterInput(**value),first['id'])
    assert second['appearances'][0]['revision']==2
    assert second['appearances'][0]['approved'] is False
    assert second['appearances'][1]['revision']==1
    assert second['history'][0]['appearances'][0]['approved'] is True
    with pytest.raises(GalleryError,match='Reload'): store.save(CharacterInput(**value),first['id'])
    value['revision']=2;value['appearances'][0]['approved']=True
    third=store.save(CharacterInput(**value),first['id'])
    assert third['appearances'][0]['approved'] is True
    assert third['appearances'][0]['revision']==2
    value['revision']=3;value['appearances'][0]['reference_ids']=['private']
    with pytest.raises(Exception): store.save(CharacterInput(**value),first['id'])
    assert store.get(first['id'])['revision']==3


def test_character_rejects_invalid_defaults_and_unconfirmed_reference(runtime):
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    store=Characters(repo,'local')
    with pytest.raises(GalleryError):store.save(CharacterInput(name='A',default_appearance_id='missing'))
    with pytest.raises(GalleryError):store.save(CharacterInput(name='A',appearances=[{'id':'x','name':'X','approved':True}]))


@pytest.mark.asyncio
async def test_character_http_and_builtin_entry(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.gallery import create_gallery_router
    from ai2apps.api.imagine_studio import MINI_APP_BY_ID
    from ai2apps.identity import RequestPrincipal
    app=FastAPI();app.include_router(create_gallery_router(lambda:runtime,RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        r=await client.post('/gallery/characters',json={'name':'Panda','appearances':[{'id':'hero','name':'Hero'}]})
        assert r.status_code==201,r.text
        value=r.json();identifier=value.pop('id');value.pop('schema');value.pop('updated_at');value['appearances'][0].pop('revision')
        value['description']='Distinctive black ears'
        saved=await client.put('/gallery/characters/'+identifier,json=value)
        assert saved.status_code==200,saved.text
        assert saved.json()['revision']==2
        listing=(await client.get('/gallery/characters')).json()['items']
        assert listing[0]['id']==identifier
        stale=await client.put('/gallery/characters/'+identifier,json=value)
        assert stale.status_code==422 and 'conflict' in stale.text
    assert MINI_APP_BY_ID['ai2apps.imagine.character-design']['entry']['kind']=='host-adapter'


@pytest.mark.asyncio
async def test_character_generation_uses_shared_durable_output(runtime,monkeypatch):
    import asyncio,base64,httpx
    from fastapi import FastAPI
    from PIL import Image
    from ai2apps.api.imagine_studio import create_imagine_studio_router
    from ai2apps.identity import RequestPrincipal
    gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    character=Characters(gallery,'local').save(CharacterInput(name='Mug',appearances=[{'id':'hero','name':'Hero','summary':'A red mug with a cape.'}]))
    calls=[];png=BytesIO();Image.new('RGB',(32,32),'red').save(png,'PNG')
    async def transport(body,**kwargs):
        calls.append((body,kwargs))
        return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(png.getvalue()).decode(),'format':'png'}}
    monkeypatch.setattr('ai2apps.images.cloud_gateway.request_cloud_image',transport)
    monkeypatch.setattr(runtime,'cloud_ai_authorization_headers',lambda principal: {})
    principal=RequestPrincipal.legacy_local()
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=principal)
    app=FastAPI();app.include_router(create_imagine_studio_router(lambda:runtime,lambda:principal))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture',headers={'X-AI2Apps-App-Instance':instance.id}) as client:
            run=await client.post('/imagine-studio/runs',json={'miniAppId':'ai2apps.imagine.character-design','title':'Hero reference','input':{'characterDesignTarget':{'character_id':character['id'],'appearance_id':'hero','appearance_revision':1}}})
            assert run.status_code==201,run.text
            identifier=run.json()['id']
            submitted=await client.post(f'/imagine-studio/runs/{identifier}/execute',json={'model':'cloud/openai/gpt-image-2.5-flare','prompt':'Consistent red mug character, front and side.','size':'1024x1024'})
            assert submitted.status_code==202,submitted.text
            for _ in range(100):
                result=await client.get('/imagine-studio/runs')
                assert result.status_code==200,result.text
                value=next(r for r in result.json()['items'] if r['id']==identifier)
                if value['status'] in ['succeeded','failed']:break
                await asyncio.sleep(.05)
            assert value['status']=='succeeded',value.get('error') or value.get('steps') or value
            assert value['artifacts'] and calls
            assert value['miniAppId']=='ai2apps.imagine.character-design'
            collected=await client.post('/imagine-studio/characters/runs/'+identifier+'/collect')
            assert collected.status_code==200,collected.text
            profile=collected.json();images=profile['appearances'][0]['generated_images']
            assert len(images)==1 and images[0]['run_id']==identifier
            again=await client.post('/imagine-studio/characters/runs/'+identifier+'/collect')
            assert again.json()['revision']==profile['revision']
            assert len(again.json()['appearances'][0]['generated_images'])==1
            missing=await client.post('/imagine-studio/characters/'+character['id']+'/export',json={'appearance_id':'hero','revision':profile['revision']})
            assert missing.status_code==422
            other=BytesIO();Image.new('RGB',(16,16),'blue').save(other,'PNG');other.seek(0)
            original,_=gallery.import_stream('local',other,name='original.png',media_type='image/png')
            selected=Characters(gallery,'local').save(CharacterInput(name='Mug',revision=profile['revision'],appearances=[{'id':'hero','name':'Hero','summary':'A red mug with a cape.','definition_image_id':images[0]['asset_id'],'reference_ids':[original['id']]}]),character['id'])
            exported=await client.post('/imagine-studio/characters/'+character['id']+'/export',json={'appearance_id':'hero','revision':selected['revision']})
            assert exported.status_code==201,exported.text
            output=exported.json()['artifacts'][0]
            assert output['name'].endswith('.charector.json')
            imported=await client.post('/imagine-studio/artifacts/'+output['id']+'/gallery',json={'collectionId':None})
            assert imported.status_code==201,imported.text
            assert imported.json()['asset']['name'].endswith('.charector.json')
            meta=exported.json()['artifacts'][0]['metadata']
            artifact=runtime.workspace.get_artifact(meta['workspaceSessionId'],meta['workspaceArtifactId'])
            import json
            document=json.loads(runtime.workspace.artifact_path(artifact).read_text())
            assert document['appearance']=={'name':'Hero','summary':'A red mug with a cape.'}
            assert len(document['images'])==1
            assert 'generated_images' not in document['appearance']
            assert document['character']=={'name':'Mug'}
            assert document['images'][0]['data_url'].startswith('data:image/png;base64,')
            assert base64.b64decode(document['images'][0]['data_url'].split(',')[1])==png.getvalue()
            # Normal form edits cannot accidentally remove generated images.
            current=Characters(gallery,'local').get(character['id'])
            update={'name':'Mug','revision':current['revision'],'appearances':[{'id':'hero','name':'Hero','summary':'Edited guide.'}]}
            updated=Characters(gallery,'local').save(CharacterInput(**update),character['id'])
            assert len(updated['appearances'][0]['generated_images'])==1
            image=updated['appearances'][0]['generated_images'][0]
            url='/imagine-studio/characters/'+character['id']+'/appearances/hero/images/'+image['artifact_id']
            conflict=await client.request('DELETE',url,json={'revision':updated['revision']-1})
            assert conflict.status_code==422
            deleted=await client.request('DELETE',url,json={'revision':updated['revision']})
            assert deleted.status_code==200,deleted.text
            assert deleted.json()['appearances'][0]['generated_images']==[]
            assert gallery.get_asset('local',image['asset_id'])['status']=='active'
            assert runtime.workspace.artifact_path(artifact).exists()
            # Refresh/reopening and normal saves must not resurrect removed image links.
            current=deleted.json()
            saved=Characters(gallery,'local').save(CharacterInput(name='Mug',revision=current['revision'],appearances=[{'id':'hero','name':'Hero','summary':'Edited guide.'}]),character['id'])
            recollected=await client.post('/imagine-studio/characters/runs/'+identifier+'/collect')
            assert recollected.status_code==200,recollected.text
            assert recollected.json()['appearances'][0]['generated_images']==[]
            assert recollected.json()['revision']==saved['revision']


    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_workflow_character_read_checks_mounted_capability(runtime,monkeypatch):
    from types import SimpleNamespace
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.studio_image_workflow import create_image_workflow_router
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    from ai2apps.identity import RequestPrincipal
    principal=RequestPrincipal.legacy_local()
    instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=principal)
    capabilities=['image.workflow']
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**kw:SimpleNamespace(capabilities=capabilities,mount={'app_key':'fixture.package','context':{'studioInstanceId':instance.id}},declaration={'id':'fixture.mini'}))
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    from PIL import Image
    image=BytesIO();Image.new('RGB',(16,16),'red').save(image,'PNG');image.seek(0)
    asset,_=repo.import_stream('local',image,name='definition.png',media_type='image/png')
    Characters(repo,'local').save(CharacterInput(name='Visible',appearances=[{'id':'final','name':'Final','definition_image_id':asset['id'],'summary':'Final guide','approved':True}]))
    Characters(repo,'other').save(CharacterInput(name='Private'))
    app=FastAPI();app.include_router(create_image_workflow_router(lambda:runtime,lambda:principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        path='/ai2apps.imagine-studio/mini-app-mounts/fixture/image-workflow/characters'
        result=await client.get(path)
        assert result.status_code==200,result.text
        assert [c['name'] for c in result.json()['items']]==['Visible']
        capabilities.clear()
        assert (await client.get(path)).status_code==403


@pytest.mark.asyncio
async def test_character_ai_description_uses_parameters_and_refuses_truncation(runtime,monkeypatch):
    from ai2apps.images.character_design import describe,DescriptionInput
    from ai2apps.identity import RequestPrincipal
    monkeypatch.setattr('ai2apps.images.character_design.resolve_task_model',lambda *a:'fixture/text')
    calls=[]
    async def model(payload,**kwargs):
        calls.append(payload)
        return {'choices':[{'finish_reason':'stop','message':{'content':'A cheerful red mug wearing a cape.'}}]}
    monkeypatch.setattr(runtime.model_invocations,'invoke_chat_json',model)
    body=DescriptionInput(name='Mug',identity='Ceramic mug',appearance={'id':'hero','name':'Hero','style':'cartoon','proportions':'three heads','outfit':'red cape','summary':'Old editable text'})
    result=await describe(runtime,RequestPrincipal.legacy_local(),'fixture-instance',body)
    assert result['summary']=='A cheerful red mug wearing a cape.'
    assert 'three heads' in calls[0]['messages'][1]['content']
    assert 'Old editable text' not in calls[0]['messages'][1]['content']
    assert 'reasoning_effort' not in calls[0]
    async def truncated(*a,**k):return {'choices':[{'finish_reason':'length','message':{'content':'Partial'}}]}
    monkeypatch.setattr(runtime.model_invocations,'invoke_chat_json',truncated)
    with pytest.raises(GalleryError,match='not completed'):await describe(runtime,RequestPrincipal.legacy_local(),'fixture-instance',body)
    assert body.appearance.summary=='Old editable text'


@pytest.mark.asyncio
@pytest.mark.parametrize('route,can_disable,expected',[
    ('cloud/ai2apps/standard',True,None),
    ('cloud/byok-text',False,None),
    ('cloud/byok-text',True,'none'),
])
async def test_character_description_honors_route_reasoning_capability(runtime,monkeypatch,route,can_disable,expected):
    from ai2apps.images.character_design import describe,DescriptionInput
    from ai2apps.identity import RequestPrincipal
    monkeypatch.setattr('ai2apps.images.character_design.resolve_task_model',lambda *a:route)
    monkeypatch.setattr(runtime.model_manager,'enabled_cloud_models',lambda:[{
        'gateway_id':route,'capabilities':{'reasoningControl':{'can_disable':can_disable}}}])
    calls=[]
    async def strict_transport(payload,**kwargs):
        calls.append(payload)
        if route.startswith('cloud/ai2apps/'):
            assert 'reasoning_effort' not in payload
        assert payload.get('reasoning_effort')==expected
        return {'choices':[{'finish_reason':'stop','message':{'content':'A red mug.'}}]}
    monkeypatch.setattr(runtime.model_invocations,'invoke_chat_json',strict_transport)
    body=DescriptionInput(name='Mug',appearance={'id':'daily','name':'Daily'})
    assert (await describe(runtime,RequestPrincipal.legacy_local(),'fixture-instance',body))['model']==route
    assert len(calls)==1

@pytest.mark.asyncio
async def test_reusable_character_definition_is_image_and_prose_only(runtime):
    from PIL import Image
    from test_material_handoff import execution_session
    from ai2apps.identity import IdentityRepository,OrganizationType
    IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='local-device',organization_id='local',organization_type=OrganizationType.HOUSEHOLD,core_user_id='local',billing_account_id='local',access_epoch=1)
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    image=BytesIO();Image.new('RGB',(16,16),'green').save(image,'PNG');image.seek(0)
    asset,_=repo.import_stream('local',image,name='definition.png',media_type='image/png')
    store=Characters(repo,'local')
    with pytest.raises(GalleryError,match='definition image'):
        store.save(CharacterInput(name='No definition',appearances=[{'id':'bad','name':'Bad','reference_ids':[asset['id']],'summary':'Guide','approved':True}]))
    c=store.save(CharacterInput(name='Hero',appearances=[{'id':'final','name':'Final','definition_image_id':asset['id'],'summary':'One definitive guide','approved':True,'outfit':'private authoring detail','reference_ids':[asset['id']]},{'id':'draft','name':'Draft'}]))
    session=execution_session(runtime,'local','ai2apps.messager')
    scope=runtime.tools.context_for_session(caller_id='character-definition-test',session_id=session)
    result=await runtime.tools.execute('gallery.character_definitions',{'character_id':c['id']},context=scope)
    values=result.output['items'];assert len(values)==1
    a=values[0]['appearances'][0]
    assert a['definition_image_id']==asset['id'] and a['summary']=='One definitive guide'
    assert set(a)=={'id','name','revision','definition_image_id','summary','approved'}
    assert Characters(repo,'other').definitions()==[]
