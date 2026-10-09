from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request

from ai2apps.studio.capability_broker import StudioCapabilityBroker
from ai2apps.web.public_boundary import PublicDeviceBoundary


@pytest.mark.asyncio
async def test_translation_uses_local_boundary_and_preserves_authentication():
    app = FastAPI()
    app.add_middleware(PublicDeviceBoundary, manager_provider=lambda: None)
    seen = []

    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        assert request.cookies.get('ai2apps_local_session_test') == 'test-session'
        seen.append(await request.json())
        return {'choices': [{'message': {'content': '翻译成功'}}]}

    broker = StudioCapabilityBroker(SimpleNamespace(
        extension_manager=None,
        model_manager=SimpleNamespace(resolve_default_model=lambda _: 'cloud/openai/test-model'),
    ))
    request = SimpleNamespace(app=app, headers={'cookie': 'ai2apps_local_session_test=test-session'})
    result = await broker._translation_completion(
        'Hello', system='Translate', principal=None, mounted=None, request=request,
    )
    assert result == '翻译成功'
    assert seen[0]['model'] == 'cloud/openai/test-model'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://ai2apps.internal') as client:
        response = await client.post('/v1/chat/completions')
    assert response.status_code == 403
