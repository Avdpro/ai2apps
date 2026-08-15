import json
from types import SimpleNamespace

import httpx
import pytest

from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.cloud_gateway import proxy_cloud_chat_completion, request_cloud_image
from ai2apps.model_manager import ModelManagerStore
from ai2apps.secrets import MemorySecretBackend


class Request:
    model = "cloud/openai/gpt-test"
    stream = False

    def model_dump(self, **kwargs):
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": self.stream,
            "temperature": 0.2,
            "top_k": 10,
            "ai2apps_session_id": "session-secret",
        }


@pytest.mark.asyncio
async def test_cloud_gateway_uses_external_model_and_strips_local_fields(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "models": ["gpt-test"],
        },
    )
    store.set_cloud_model_enabled("openai", "gpt-test", True)
    captured = {}

    def handler(request: httpx.Request):
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": "response", "choices": []},
            headers={"content-type": "application/json"},
        )

    response = await proxy_cloud_chat_completion(
        Request(), base_path=tmp_path, transport=httpx.MockTransport(handler)
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["authorization"] == "Bearer sk-secret"
    assert captured["body"]["model"] == "gpt-test"
    assert "top_k" not in captured["body"]
    assert "ai2apps_session_id" not in captured["body"]
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_cloud_gateway_retries_modern_openai_token_parameter(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "models": ["gpt-5-test"],
        },
    )
    store.set_cloud_model_enabled("openai", "gpt-5-test", True)
    bodies = []

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": (
                            "Unsupported parameter: 'max_tokens' is not supported "
                            "with this model. Use 'max_completion_tokens' instead."
                        )
                    }
                },
            )
        return httpx.Response(200, json={"id": "response", "choices": []})

    class ModernRequest(Request):
        model = "cloud/openai/gpt-5-test"

        def model_dump(self, **kwargs):
            return {
                **super().model_dump(**kwargs),
                "model": self.model,
                "max_tokens": 4096,
            }

    response = await proxy_cloud_chat_completion(
        ModernRequest(), base_path=tmp_path, transport=httpx.MockTransport(handler)
    )
    cached_response = await proxy_cloud_chat_completion(
        ModernRequest(), base_path=tmp_path, transport=httpx.MockTransport(handler)
    )

    assert response.status_code == 200
    assert cached_response.status_code == 200
    assert len(bodies) == 3
    assert bodies[0]["max_tokens"] == 4096
    assert bodies[0]["temperature"] == 0.2
    assert "max_tokens" not in bodies[1]
    assert bodies[1]["max_completion_tokens"] == 4096
    assert "temperature" not in bodies[1]
    assert bodies[2] == bodies[1]


@pytest.mark.asyncio
async def test_cloud_gateway_streams_after_modern_token_parameter_retry(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-secret",
            "models": ["gpt-5-stream-test"],
        },
    )
    store.set_cloud_model_enabled("openai", "gpt-5-stream-test", True)
    attempts = 0

    def handler(request: httpx.Request):
        nonlocal attempts
        attempts += 1
        body = json.loads(request.content)
        if attempts == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": (
                            "Unsupported parameter: 'max_tokens' is not supported "
                            "with this model. Use 'max_completion_tokens' instead."
                        )
                    }
                },
            )
        assert body["stream"] is True
        assert body["max_completion_tokens"] == 128
        return httpx.Response(
            200,
            content=b'data: {"choices":[{"delta":{"content":"OK"}}]}\n\ndata: [DONE]\n\n',
            headers={"content-type": "text/event-stream"},
        )

    class ModernStreamRequest(Request):
        model = "cloud/openai/gpt-5-stream-test"
        stream = True

        def model_dump(self, **kwargs):
            return {
                **super().model_dump(**kwargs),
                "model": self.model,
                "stream": True,
                "max_tokens": 128,
            }

    response = await proxy_cloud_chat_completion(
        ModernStreamRequest(),
        base_path=tmp_path,
        transport=httpx.MockTransport(handler),
    )
    content = b"".join([chunk async for chunk in response.body_iterator])

    assert attempts == 2
    assert b'"content":"OK"' in content
    assert content.endswith(b"data: [DONE]\n\n")


@pytest.mark.asyncio
async def test_cloud_gateway_rejects_unselected_model_without_network(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai", {"api_key": "sk-secret", "models": ["gpt-test"]}
    )

    with pytest.raises(Exception) as exc_info:
        await proxy_cloud_chat_completion(Request(), base_path=tmp_path)

    assert getattr(exc_info.value, "status_code", None) == 404


@pytest.mark.asyncio
async def test_cloud_gateway_streams_provider_sse(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {"api_key": "sk-secret", "models": ["gpt-test"]},
    )
    store.set_cloud_model_enabled("openai", "gpt-test", True)

    def handler(request: httpx.Request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            content=b"data: {\"choices\":[]}\n\ndata: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    request = Request()
    request.stream = True
    response = await proxy_cloud_chat_completion(
        request, base_path=tmp_path, transport=httpx.MockTransport(handler)
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert b"data: [DONE]" in body


def _ai2apps_request(*, stream=False):
    return SimpleNamespace(
        model="cloud/ai2apps/openai/gpt-test",
        stream=stream,
        max_tokens=128,
        temperature=0.2,
        tools=None,
        messages=[SimpleNamespace(role="user", content="hello", tool_calls=None, tool_call_id=None)],
    )


def _ai2apps_client(handler):
    return AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(MemorySecretBackend(), "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_ai2apps_account_model_uses_managed_cloud_gateway(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        captured["idempotency"] = request.headers["idempotency-key"]
        return httpx.Response(
            200,
            json={
                "requestId": "req-1",
                "stopReason": "stop",
                "usage": {"inputTokens": 2, "outputTokens": 3},
                "output": [{"type": "output_text", "text": "hello back"}],
            },
        )

    cloud = _ai2apps_client(handler)
    response = await proxy_cloud_chat_completion(
        _ai2apps_request(), base_path=tmp_path, cloud_client=cloud
    )
    payload = json.loads(response.body)

    assert captured["path"] == "/v1/ai/responses"
    assert captured["body"]["model"] == "openai/gpt-test"
    assert captured["body"]["input"][0]["content"] == [
        {"type": "input_text", "text": "hello"}
    ]
    assert captured["idempotency"].startswith("local-chat-")
    assert payload["choices"][0]["message"]["content"] == "hello back"
    assert payload["usage"]["total_tokens"] == 5
    await cloud.close()


@pytest.mark.asyncio
async def test_ai2apps_account_model_forwards_stable_client_idempotency_key(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["idempotency"] = request.headers["idempotency-key"]
        return httpx.Response(
            200,
            json={
                "requestId": "req-stable",
                "stopReason": "stop",
                "usage": {"inputTokens": 1, "outputTokens": 1},
                "charged": "2",
                "balance": "998",
                "output": [{"type": "output_text", "text": "stable"}],
            },
        )

    request = _ai2apps_request()
    request.ai2apps_idempotency_key = "stable-chat-request-123"
    cloud = _ai2apps_client(handler)
    response = await proxy_cloud_chat_completion(
        request, base_path=tmp_path, cloud_client=cloud
    )
    payload = json.loads(response.body)

    assert captured["idempotency"] == "stable-chat-request-123"
    assert payload["ai2apps_cloud"]["requestId"] == "req-stable"
    assert payload["ai2apps_cloud"]["charged"] == "2"
    assert payload["ai2apps_cloud"]["balance"] == "998"
    await cloud.close()


@pytest.mark.asyncio
async def test_ai2apps_account_is_transparent_fallback_without_local_key(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["model"] = json.loads(request.content)["model"]
        return httpx.Response(
            200,
            json={
                "requestId": "req-fallback",
                "stopReason": "stop",
                "usage": {"inputTokens": 1, "outputTokens": 1},
                "output": [{"type": "output_text", "text": "fallback"}],
            },
        )

    request = _ai2apps_request()
    request.model = "cloud/openai/gpt-test"
    cloud = _ai2apps_client(handler)
    response = await proxy_cloud_chat_completion(
        request, base_path=tmp_path, cloud_client=cloud
    )

    assert captured["model"] == "openai/gpt-test"
    assert json.loads(response.body)["choices"][0]["message"]["content"] == "fallback"
    await cloud.close()


@pytest.mark.asyncio
async def test_ai2apps_account_model_converts_cloud_sse_to_openai_chunks(tmp_path):
    def handler(request: httpx.Request):
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            content=(
                b'event: response.created\ndata: {"requestId":"req-stream"}\n\n'
                b'event: output_text.delta\ndata: {"delta":"hello"}\n\n'
                b'event: response.completed\ndata: {"requestId":"req-stream","stopReason":"stop","usage":{"inputTokens":1,"outputTokens":1},"charged":"3","released":"7","balance":"997","pricingVersion":"price-2"}\n\n'
            ),
            headers={"content-type": "text/event-stream"},
        )

    cloud = _ai2apps_client(handler)
    response = await proxy_cloud_chat_completion(
        _ai2apps_request(stream=True), base_path=tmp_path, cloud_client=cloud
    )
    body = b"".join([chunk async for chunk in response.body_iterator])

    assert b'"content":"hello"' in body
    assert b'"id":"req-stream"' in body
    assert b'"total_tokens":2' in body
    assert b'"ai2apps_cloud":{"phase":"created"' in body
    assert b'"phase":"completed"' in body
    assert b'"charged":"3"' in body
    assert b'"balance":"997"' in body
    assert body.endswith(b"data: [DONE]\n\n")
    await cloud.close()


@pytest.mark.asyncio
async def test_ai2apps_account_image_uses_managed_image_api(tmp_path):
    captured = {}

    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        captured["idempotency"] = request.headers["idempotency-key"]
        return httpx.Response(
            200,
            json={
                "requestId": "req-image",
                "image": {
                    "dataUrl": "data:image/png;base64,aW1hZ2U=",
                    "size": "1024x1024",
                    "quality": "auto",
                    "format": "png",
                },
            },
        )

    cloud = _ai2apps_client(handler)
    result = await request_cloud_image(
        {
            "model": "cloud/ai2apps/openai/gpt-image-2",
            "prompt": "draw a lighthouse",
            "size": "1024x1024",
            "outputFormat": "png",
            "idempotencyKey": "image-request-1",
        },
        edit=False,
        base_path=tmp_path,
        cloud_client=cloud,
    )

    assert captured["path"] == "/v1/ai/images/generations"
    assert captured["body"]["model"] == "openai/gpt-image-2"
    assert captured["body"]["prompt"] == "draw a lighthouse"
    assert captured["idempotency"] == "image-request-1"
    assert result["image"]["dataUrl"].startswith("data:image/png;base64,")
    await cloud.close()


@pytest.mark.asyncio
async def test_local_openai_image_model_returns_normalized_data_url(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_cloud(
        "openai",
        {
            "base_url": "https://api.openai.test/v1",
            "api_key": "sk-image",
            "models": ["gpt-image-2"],
        },
    )
    store.set_cloud_model_enabled("openai", "gpt-image-2", True)
    captured = {}

    def handler(request: httpx.Request):
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["authorization"] = request.headers["authorization"]
        return httpx.Response(
            200,
            json={"data": [{"b64_json": "aW1hZ2U="}], "usage": {"total_tokens": 9}},
        )

    result = await request_cloud_image(
        {
            "model": "cloud/openai/gpt-image-2",
            "prompt": "draw a lighthouse",
            "outputFormat": "png",
        },
        edit=False,
        base_path=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert captured["url"] == "https://api.openai.test/v1/images/generations"
    assert captured["authorization"] == "Bearer sk-image"
    assert captured["body"]["model"] == "gpt-image-2"
    assert "response_format" not in captured["body"]
    assert captured["body"]["output_format"] == "png"
    assert result["image"]["dataUrl"] == "data:image/png;base64,aW1hZ2U="
    assert result["provider"] == "local"
