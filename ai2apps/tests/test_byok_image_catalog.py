from types import SimpleNamespace
import asyncio
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.imagine_studio import create_imagine_studio_router
from ai2apps.model_manager import ModelManagerStore
from ai2apps.model_capabilities import cloud_model_capabilities
from ai2apps.secrets import MemorySecretBackend
from ai2apps.cloud_gateway import request_cloud_image


def test_vision_and_image_capabilities_are_distinct():
    for name in ('gpt-6-luna', 'gpt-6-astra', 'gpt-6-sol'):
        assert 'image_recognition' in cloud_model_capabilities({'id': name})
    assert 'image_recognition' in cloud_model_capabilities({'id': 'custom', 'capabilities': ['image_input']})
    for name in ('gpt-image-2.5-sunburst', 'gpt-image-2.5-flare'):
        capabilities = cloud_model_capabilities({'id': name})
        assert 'image_generation' in capabilities
        assert 'image_recognition' not in capabilities


def test_offline_byok_image_catalog_and_direct_request(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path, secret_backend=MemorySecretBackend())
    names = ['gpt-image-2.5-sunburst', 'gpt-image-2.5-flare', 'gpt-6-luna', 'gpt-image-disabled']
    store.put_cloud('openai', {'api_key': 'fixture-secret', 'models': names})
    for name in names[:-1]: store.set_cloud_model_enabled('openai', name, True)
    runtime = SimpleNamespace(model_manager=store, offline_mode=True)
    monkeypatch.setattr('ai2apps.api.imagine_studio.list_package_models', lambda _: [])
    app = FastAPI()
    app.include_router(create_imagine_studio_router(lambda: runtime, lambda: object()))
    response = TestClient(app).get('/imagine-studio/models')
    assert response.status_code == 200
    models = response.json()['data']
    assert {m['id'] for m in models} == {f'cloud/openai/{name}' for name in names[:2]}
    assert all(m['source_type'] == 'byok' and 'image_edit' in m['capabilities'] for m in models)
    assert 'fixture-secret' not in response.text and 'credential' not in response.text
    class BlockCloud:
        async def request(self, *args, **kwargs): raise AssertionError('BYOK reached Cloud')
    calls = []
    def handle(request):
        assert request.url.host == 'api.openai.com'
        assert request.url.path == '/v1/images/generations'
        calls.append(request)
        return httpx.Response(200, json={'data': [{'b64_json': 'aW1hZ2U='}]})
    async def run():
        for model in models:
            result = await request_cloud_image({'model': model['id'], 'prompt': 'test'}, edit=False,
                base_path=tmp_path, model_manager=store, cloud_client=BlockCloud(), transport=httpx.MockTransport(handle))
            assert result['image']['dataUrl'].startswith('data:image/png;base64,')
    asyncio.run(run())
    assert len(calls) == 2
