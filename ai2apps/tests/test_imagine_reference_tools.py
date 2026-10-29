import base64
import io
from dataclasses import replace
import pytest
from PIL import Image
from ai2apps.chat import ChatRepository
from ai2apps.services import ToolCallContext
from test_app_interactions import runtime

@pytest.mark.asyncio
async def test_reference_workflows(runtime,monkeypatch):
    image=io.BytesIO();Image.new('RGB',(16,16),'blue').save(image,format='PNG')
    calls=[]
    async def cloud(body,**kwargs):
        calls.append(body)
        return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode(),'format':'png'}}
    monkeypatch.setattr('ai2apps.cloud_gateway.request_cloud_image',cloud)
    from ai2apps.images.parameters import from_options
    async def catalog(*args):return [from_options('cloud/ai2apps/openai/gpt-image-2','GPT Image',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',catalog)
    monkeypatch.setattr(runtime,'cloud_ai_authorization_headers',lambda p:{})
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='Reference workflow')[0].session.id
    refs=[]
    for i,color in enumerate(['red','green','blue']):
        path=runtime.config.paths.base_path/f'fixture-{i}.png';Image.new('RGB',(16,16),color).save(path)
        refs.append(runtime.workspace.import_artifact(session,path,name=path.name,media_type='image/png').id)
    ctx=ToolCallContext(caller_id='test',session_id=session,actor_user_id='local',installation_id='local',invocation_id='group-test')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        result=await runtime.app_capability_router.invoke('image.group_photo',{'person_artifact_ids':refs[:2],'background_artifact_id':refs[2]},ctx)
        assert result['mini_app_id']=='ai2apps.imagine.group-photo'
        assert len(calls[-1]['imageDataUrls'])==3
        assert 'first 2 input images' in calls[-1]['prompt'] and 'last input image is the background' in calls[-1]['prompt']
        result=await runtime.app_capability_router.invoke('image.style_transfer',{'artifact_id':refs[0],'style':'watercolor'},replace(ctx,invocation_id='style-test'))
        assert result['mini_app_id']=='ai2apps.imagine.style-transfer' and 'watercolor' in calls[-1]['prompt']
        styled=result['artifact']['id']
        edited=await runtime.app_capability_router.invoke('image.edit',{'artifact_id':styled,'prompt':'Change only the subject action; preserve watercolor style and the background'},replace(ctx,invocation_id='content-edit-after-style'))
        assert edited['mini_app_id']=='ai2apps.imagine.image-edit'
        assert len(calls[-1]['imageDataUrls'])==1
        assert calls[-1]['prompt']=='Change only the subject action; preserve watercolor style and the background'
        assert edited['artifact']['id']!=styled
        result=await runtime.app_capability_router.invoke('image.reference_creation',{'artifact_ids':refs[:2],'prompt':'a composition'},replace(ctx,invocation_id='reference-test'))
        assert result['mini_app_id']=='ai2apps.imagine.reference-creation'
        shared=await runtime.app_capability_router.invoke('image.group_photo',{'person_artifact_ids':refs[:2],'background_artifact_id':refs[1]},replace(ctx,invocation_id='shared-background'))
        assert shared['mini_app_id']=='ai2apps.imagine.group-photo'
        assert len(calls[-1]['imageDataUrls'])==2
        assert 'Input image 2 also supplies the background scenery' in calls[-1]['prompt']
        assert 'people, animals or characters' in calls[-1]['prompt']
        assert 'last input image is the background' not in calls[-1]['prompt']
        count=len(calls)
        for args in [{'person_artifact_ids':refs[:1],'background':'park'}, {'person_artifact_ids':refs[:2]}, {'person_artifact_ids':[refs[0],refs[0]],'background':'park'}]:
            with pytest.raises(Exception):await runtime.app_capability_router.invoke('image.group_photo',args,replace(ctx,invocation_id='invalid'))
        assert len(calls)==count
        other=ChatRepository(runtime.database,runtime.events).create_thread(title='other')[0].session.id
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('image.group_photo',{'person_artifact_ids':refs[:2],'background':'park'},replace(ctx,session_id=other,invocation_id='foreign'))
        assert len(calls)==count
    finally:await runtime.stop_background_tasks()

def test_new_mini_app_image_is_included_in_agent_completion():
    from types import SimpleNamespace as N
    from ai2apps.agents.general import GeneralAgentExecutor
    from ai2apps.agents.models import RunStepStatus
    executor=GeneralAgentExecutor.__new__(GeneralAgentExecutor)
    executor.capability_router=None
    executor.workspace=None
    steps=[N(kind='tool',status=RunStepStatus.COMPLETED,tool_name='image.group_photo',output={'artifact':{'id':'art_test','media_type':'image/png','download_url':'/image.png'}}),N(kind='model',status=RunStepStatus.COMPLETED,output={'usage':{}})]
    action=executor._complete(N(steps=steps,run=N(parent_run_id='parent',session_id='fixture')),{'content':'done'},'stop')
    assert action.output['content'][-1]['image_url']['artifact_id']=='art_test'


def test_content_and_style_scope_reaches_summary_and_trusted_owner_context(runtime):
    from ai2apps.agents.tool_loading import index_message
    tools=[runtime.services.get_tool(n) for n in ('image.edit','image.style_transfer')]
    index=index_message(tools,[])['content']
    # A not-yet-loaded editor must still be discoverable from the compact index.
    assert 'Edit image content, actions, objects or local details' in index
    assert 'Change visual style, not image content or subject actions' in index
    contexts=runtime.app_capability_router.agent_contexts(tools,'local','local')
    import json
    projected=json.dumps(contexts)
    assert 'A request to preserve the current style is not a new style-transfer request' in projected
    assert 'use image.edit for content, actions, objects or local changes' in projected
