"""C03 owner flow: real durable jobs with fixture image transport, no paid calls."""
import base64
import io
from dataclasses import replace
from types import SimpleNamespace
import pytest
from PIL import Image
from ai2apps.chat import ChatRepository
from ai2apps.services import ToolCallContext
from ai2apps.images import mini_parameters as params
from ai2apps.images.parameters import from_options
from ai2apps.images.byok_capabilities import image_options
from test_app_interactions import runtime

MODEL='cloud/openai/gpt-image-2.5-flare'

@pytest.mark.asyncio
async def test_c03_extraction_try_on_product_chain(runtime,monkeypatch):
    image=io.BytesIO();Image.new('RGB',(32,32),'yellow').save(image,format='PNG')
    calls=[]
    async def transport(body,**kwargs):
        calls.append(body)
        assert body['model']==MODEL and body['size']=='1536x1152'
        return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode(),'format':'png'}}
    monkeypatch.setattr('ai2apps.images.cloud_gateway.request_cloud_image',transport)
    async def catalog(*args):return [from_options(MODEL,'BYOK fixture',image_options('gpt-image-2.5-flare'))],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',catalog)
    monkeypatch.setattr(runtime,'cloud_ai_authorization_headers',lambda p:{})
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='C03 fixture')[0].session.id
    refs=[]
    for i,color in enumerate(('blue','yellow')):
        path=runtime.config.paths.base_path/f'commerce-{i}.png';Image.new('RGB',(32,32),color).save(path)
        refs.append(runtime.workspace.import_artifact(session,path,name=path.name,media_type='image/png').id)
    ctx=ToolCallContext(caller_id='test',session_id=session,actor_user_id='local',installation_id='local',invocation_id='c03-extract')
    common={'model':MODEL,'size':'1536x1152'}
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        extracted=await runtime.app_capability_router.invoke('image.extract_items',dict(common,artifact_id=refs[1],target='custom',target_description='yellow jacket with two green pockets and five black buttons'),ctx)
        item=extracted['artifact']['id']
        worn=await runtime.app_capability_router.invoke('image.try_on',dict(common,person_artifact_id=refs[0],item_artifact_id=item),replace(ctx,invocation_id='c03-wear'))
        poster=await runtime.app_capability_router.invoke('image.product_photo',dict(common,artifact_id=worn['artifact']['id'],scene='stone'),replace(ctx,invocation_id='c03-product'))
        assert [r['mini_app_id'] for r in (extracted,worn,poster)]==['ai2apps.imagine.extract-items','ai2apps.imagine.try-on','ai2apps.imagine.product-poster']
        assert [len(c['imageDataUrls']) for c in calls]==[1,2,1]
        assert 'five black buttons' in calls[0]['prompt']
        assert 'Image 1 is the ONLY identity reference' in calls[1]['prompt']
        assert 'preserve that person' in calls[2]['prompt']
        expected=[[refs[1]],[refs[0],item],[worn['artifact']['id']]]
        for result,sources in zip((extracted,worn,poster),expected):
            artifact=runtime.workspace.get_artifact(session,result['artifact']['id'])
            assert runtime.workspace.artifact_path(artifact).is_file()
            assert artifact.metadata['sourceArtifactIds']==sources
            with runtime.database.transaction() as db:
                row=db.execute('select mini_app_id,status from studio_runs where id=?',(result['studio_run_id'],)).fetchone()
            assert row['status']=='succeeded' and row['mini_app_id']==result['mini_app_id']
        before=len(calls)
        with pytest.raises(Exception):
            await runtime.app_capability_router.invoke('image.try_on',dict(common,person_artifact_id=refs[0],item_artifact_id=refs[0]),replace(ctx,invocation_id='bad-roles'))
        with pytest.raises(Exception):
            await runtime.app_capability_router.invoke('image.extract_items',dict(common,artifact_id='not-owned'),replace(ctx,invocation_id='bad-source'))
        assert len(calls)==before
    finally:await runtime.stop_background_tasks()


def test_c03_declarations_forms_and_ui_catalog(runtime):
    from ai2apps.agents.parameter_forms import FORMS
    from ai2apps.api.imagine_studio import MINI_APPS
    for mini in ('extract-items','try-on','product-poster'):
        mid='ai2apps.imagine.'+mini;provider=runtime.app_capability_router.providers[mid]
        assert provider.describe and provider.prepare and provider.continuation
        assert FORMS[mid].agent_context==provider.agent_context
        assert next(m for m in MINI_APPS if m['id']==mid)['agentCapabilities']==[params.WORKFLOWS[mid]]
        assert params.WORKFLOWS[mid] in [t.qualified_name for t in runtime.services.list_tools()]


def test_c03_handoff_keeps_person_and_item_slot_identity(runtime):
    from ai2apps.images.app_continuation import begin
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='slots')[0].session.id
    ids=[]
    for i in range(2):
        path=runtime.config.paths.base_path/f'slot-{i}.png';Image.new('RGB',(8,8)).save(path)
        ids.append(runtime.workspace.import_artifact(session,path,name=path.name,media_type='image/png').id)
    data=begin(runtime,None,SimpleNamespace(session_id=session),None,SimpleNamespace(capability='image.try_on',key='provider'),{'person_artifact_id':ids[0],'item_artifact_id':ids[1]})
    assert [(r['slot'],r['artifact_id']) for r in data['references']]==list(enumerate(ids))

@pytest.mark.asyncio
async def test_bot_discovers_each_commerce_owner(runtime):
    from test_builtin_app_aaat import context
    describe=runtime.service_registry.bound_tool('app.describe').handler
    for capability in ('image.extract_items','image.try_on','image.product_photo'):
        summary=await describe({'query':capability},context(runtime))
        assert any(p['capability']==capability for p in summary['providers'])
        details=await describe({'capability':capability},context(runtime))
        provider=next(p for p in details['providers'] if p['capability']==capability)
        assert provider['agent_context']['instructions']
