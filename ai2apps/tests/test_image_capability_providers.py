import base64
import io
from dataclasses import replace
import pytest
from PIL import Image
from ai2apps.chat import ChatRepository
from ai2apps.services import ToolCallContext
from ai2apps.services.capability_routing import ProviderUnavailable
from test_app_interactions import runtime

@pytest.mark.asyncio
async def test_real_studio_job_fallback_preference_edit_and_ownership(runtime,monkeypatch):
    calls=[]
    image=io.BytesIO();Image.new('RGB',(16,16),'red').save(image,format='PNG')
    async def cloud(body,**kwargs):
        calls.append((body,kwargs))
        return {'image':{'dataUrl':'data:image/png;base64,'+base64.b64encode(image.getvalue()).decode(),'format':'png'}}
    monkeypatch.setattr('ai2apps.cloud_gateway.request_cloud_image',cloud)
    from ai2apps.images.parameters import from_options
    async def catalog(*args):return [from_options('cloud/ai2apps/openai/gpt-image-2','GPT Image',{})],[]
    monkeypatch.setattr('ai2apps.images.parameters.models',catalog)
    monkeypatch.setattr(runtime,'cloud_ai_authorization_headers',lambda principal:{'X-Test-Actor':principal.actor_user_id})
    router=runtime.app_capability_router
    original=router.providers['ai2apps.images.generate']
    async def unavailable(*args):raise ProviderUnavailable('test preflight outage; no request sent')
    assert router.providers['ai2apps.imagine.text-to-image'].priority>original.priority
    router.providers[original.id]=replace(original,priority=200,handler=unavailable)
    session=ChatRepository(runtime.database,runtime.events).create_thread(title='Image adapter test')[0].session.id
    ctx=ToolCallContext(caller_id='agent:test',session_id=session,actor_user_id='local',installation_id='local',invocation_id='test-inv-1')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        result=await router.invoke('image.generate',{'prompt':'red mug'},ctx)
        assert result['provider']=='ai2apps.imagine.text-to-image'
        assert [x['status'] for x in result['provider_attempts']]==['unavailable','succeeded']
        assert calls[0][1]['cloud_headers']=={'X-Test-Actor':'local'}
        assert result['studio_run_id']
        artifact=runtime.workspace.get_artifact(session,result['artifact']['id'])
        assert runtime.workspace.artifact_path(artifact).read_bytes()==image.getvalue()
        # Restore first provider: last success still selects Mini-App.
        router.providers[original.id]=original
        second=await router.invoke('image.generate',{'prompt':'green mug'},replace(ctx,invocation_id='test-inv-2'))
        assert second['provider_attempts']==[{'provider':'ai2apps.imagine.text-to-image','status':'succeeded'}]
        edited=await router.invoke('image.edit',{'prompt':'make blue','artifact_id':artifact.id},replace(ctx,invocation_id='test-inv-3'))
        assert edited['mini_app_id']=='ai2apps.imagine.image-edit'
        assert calls[-1][1]['edit'] is True
        assert calls[-1][0]['imageDataUrls'][0].endswith(base64.b64encode(image.getvalue()).decode())
        other=ChatRepository(runtime.database,runtime.events).create_thread(title='other')[0].session.id
        with pytest.raises(Exception):
            await router.invoke('image.edit',{'prompt':'blue','artifact_id':artifact.id},replace(ctx,session_id=other,invocation_id='test-inv-4'))
        assert len(calls)==3
    finally:await runtime.stop_background_tasks()


def test_mini_app_catalog_declares_registered_capabilities():
    from ai2apps.api.imagine_studio import MINI_APP_BY_ID
    from ai2apps.images.capabilities import MINI_APP_CAPABILITIES
    for mini_id, capability in MINI_APP_CAPABILITIES.items():
        assert MINI_APP_BY_ID[mini_id]['agentCapabilities'] == [capability]


def test_generated_image_context_preserves_artifact_reference_not_local_url():
    from ai2apps.agents.general import _model_safe_artifact_message
    message = {"role": "assistant", "content": [{"type": "image_url", "image_url": {
        "url": "/v1/platform/sessions/ses_test/artifacts/art_test/download", "artifact_id": "art_test"}}]}
    converted = _model_safe_artifact_message(message)
    assert converted["content"][0]["type"] == "text"
    assert "art_test" in converted["content"][0]["text"]
    assert message["content"][0]["type"] == "image_url"
    user_image = {**message, "role": "user"}
    assert _model_safe_artifact_message(user_image) is user_image


def test_system_capability_inventory(runtime):
    from types import SimpleNamespace
    from ai2apps.services.capability_catalog import capability_catalog
    data=capability_catalog(runtime,SimpleNamespace(actor_user_id='local',installation_id='local'))
    assert any(t['name']=='image.generate' and 'image.generate' in t['capabilities'] for t in data['tools'])
    assert any(p['mini_app_id']=='ai2apps.imagine.text-to-image' for p in data['providers'])
    assert all('input_schema' in t and 'service_status' in t for t in data['tools'])
