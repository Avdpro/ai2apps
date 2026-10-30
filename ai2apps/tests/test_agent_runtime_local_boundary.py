"""Exercise the actual server-bound Agent callback without loading MLX engines."""
import ast
import inspect
import json
from pathlib import Path
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request, HTTPException
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse, StreamingResponse

from ai2apps.agents.model_stream import ChatCompletionStreamAccumulator
from ai2apps.web.public_boundary import PublicDeviceBoundary
from ai2apps.identity import RequestPrincipal
from ai2apps.model_invocation import ModelInvocationContext


@pytest.mark.asyncio
@pytest.mark.parametrize('api_key', [None, 'fixture-api-key'])
async def test_server_agent_callback_uses_local_route_and_preserves_auth(api_key, monkeypatch):
    source = Path(__file__).resolve().parents[2] / 'omlx/server.py'
    tree = ast.parse(source.read_text())
    callback = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.AsyncFunctionDef)
                    and node.name == '_invoke_agent_model')
    app = FastAPI()
    app.add_middleware(PublicDeviceBoundary, manager_provider=lambda: None)
    seen = []
    principal = RequestPrincipal.legacy_local()
    context = ModelInvocationContext.from_principal(principal, session_id='owned-session')
    current = [context]
    monkeypatch.setattr(ModelInvocationContext, 'for_session', lambda *a: current[0])
    runtime = SimpleNamespace(database=object())
    namespace = dict(app=app, _server_state=SimpleNamespace(api_key=api_key),
                     ChatCompletionStreamAccumulator=ChatCompletionStreamAccumulator,
                     json=json, time=time, inspect=inspect,
                     _AGENT_MODEL_SCOPE=object(), ModelInvocationContext=ModelInvocationContext,
                     RequestPrincipal=RequestPrincipal, HTTPConnection=HTTPConnection,
                     HTTPException=HTTPException, get_ai2apps_platform_runtime=lambda: runtime)
    auth = next(node for node in ast.walk(tree) if isinstance(node, ast.AsyncFunctionDef)
                and node.name == 'verify_ai2apps_platform_access')
    exec(compile(ast.Module(body=[auth, callback], type_ignores=[]), str(source), 'exec'), namespace)

    @app.post('/v1/chat/completions')
    async def completion(request: Request):
        await namespace['verify_ai2apps_platform_access'](request)
        if api_key and request.headers.get('authorization') != f'Bearer {api_key}':
            return JSONResponse({'detail': 'Invalid API key'}, status_code=401)
        seen.append((request.url.hostname, await request.json()))
        chunk = {'choices': [{'index': 0, 'delta': {'content': 'local success'},
                              'finish_reason': 'stop'}]}
        return StreamingResponse(iter(['data: ' + json.dumps(chunk) + '\n\n',
                                       'data: [DONE]\n\n']),
                                 media_type='text/event-stream')

    result = await namespace['_invoke_agent_model'](
        {'model': 'arbitrary-local-model', 'messages': []},
        model_context=context)
    assert result['choices'][0]['message']['content'] == 'local success'
    assert seen[0][0] == '127.0.0.1'
    assert seen[0][1]['ai2apps_session_id'] == context.cache_namespace
    assert seen[0][1]['ai2apps_kv_policy'] == 'session'
    assert seen[0][1]['stream_options']['include_usage'] is True
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        for host in ('untrusted.example', 'ai2apps.internal'):
            response = await client.post(f'http://{host}/v1/chat/completions',
                                         headers={'Authorization': f'Bearer {api_key}'})
            assert response.status_code == 403
        response = await client.post('http://127.0.0.1/v1/chat/completions',
            headers={'X-Agent-Model-Context': 'owned-session', 'Authorization': f'Bearer {api_key}'},
            json={'ai2apps_session_id': 'owned-session'})
        assert response.status_code == 401
    from dataclasses import replace
    current[0] = replace(context, membership_epoch=context.membership_epoch + 1)
    with pytest.raises(RuntimeError, match='HTTP 401'):
        await namespace['_invoke_agent_model']({'model': 'arbitrary-local-model'}, model_context=context)
    def revoked(*args):
        raise ValueError('Session no longer active')
    monkeypatch.setattr(ModelInvocationContext, 'for_session', revoked)
    with pytest.raises(RuntimeError, match='HTTP 401'):
        await namespace['_invoke_agent_model']({'model': 'arbitrary-local-model'}, model_context=context)
    # Even an authentic internal context has no authority on another endpoint.
    scope = {'type': 'http', 'method': 'POST', 'path': '/v1/platform/secrets',
             'headers': [(b'host', b'127.0.0.1')],
             namespace['_AGENT_MODEL_SCOPE']: context}
    with pytest.raises(HTTPException) as denied:
        await namespace['verify_ai2apps_platform_access'](Request(scope))
    assert denied.value.status_code == 401
    assert len(seen) == 1
