from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest
from fastapi import HTTPException

from ai2apps.cloud_gateway import _check_ai2apps_tool_limit, _proxy_ai2apps_chat_completion
from ai2apps.agents.runtime import _model_error_retryable
from ai2apps.peer.broker import PeerBrokerClient, PeerBrokerError
from ai2apps.peer.identity import PeerProtocol


@pytest.mark.asyncio
@pytest.mark.parametrize("status,payload", [
    (200, {"version": 1, "brokerEnabled": False, "protocols": {"messager-v2": False}, "refreshAfterSeconds": 300}),
    (404, {}), (200, {"version": 1, "brokerEnabled": True, "protocols": {"messager-v2": False}}),
])
async def test_peer_discovery_skips_keys_and_caches_unknown_or_disabled(status, payload):
    calls = []
    async def request(method, path, **kwargs):
        calls.append(path)
        return httpx.Response(status, json=payload)
    keys = Mock()
    client = PeerBrokerClient(cloud=SimpleNamespace(request=request), keys=keys,
                              device_id="test", device_headers=Mock())
    for _ in range(2):
        with pytest.raises(PeerBrokerError) as error:
            await client.ensure_registered(None, PeerProtocol.MESSAGER_V2)
        assert not error.value.retryable
    assert calls == ["/v1/peer/capabilities"]
    keys.get_or_create.assert_not_called()
    client.device_headers.assert_not_called()


@pytest.mark.asyncio
async def test_peer_refresh_can_enable_specific_protocol():
    payload = {"version": 1, "brokerEnabled": False, "protocols": {"messager-v2": False}}
    async def request(*args, **kwargs):
        return httpx.Response(200, json=payload)
    client = PeerBrokerClient(cloud=SimpleNamespace(request=request), keys=Mock(),
                              device_id="test", device_headers=Mock())
    with pytest.raises(PeerBrokerError):
        await client.require_protocol(PeerProtocol.MESSAGER_V2)
    payload.update(brokerEnabled=True, protocols={"messager-v2": True})
    client._capabilities_expires_at = 0
    await client.require_protocol(PeerProtocol.MESSAGER_V2)
    with pytest.raises(PeerBrokerError):
        await client.require_protocol(PeerProtocol.MODEL_SHARE_V1)


@pytest.mark.asyncio
@pytest.mark.parametrize("limit,count,rejected", [(32, 33, True), (128, 128, False), (128, 129, True), (0, 1, True)])
async def test_catalog_limits_are_model_specific_and_never_truncate(limit, count, rejected):
    async def request(method, path, **kwargs):
        assert kwargs["headers"] == {"X-Test": "member"}
        return httpx.Response(200, json={"items": [{"id": "chosen", "capabilities": {
            "toolOptions": {"maxTools": limit, "protocol": "openai-responses"}}}]})
    tools = [{"name": f"tool{i}"} for i in range(count)]
    body = {"model": "chosen", "tools": tools}
    if rejected:
        with pytest.raises(HTTPException) as error:
            await _check_ai2apps_tool_limit(SimpleNamespace(request=request), body, {"X-Test": "member"})
        assert error.value.detail["details"]["actual"] == count
        assert not _model_error_retryable(error.value)
    else:
        await _check_ai2apps_tool_limit(SimpleNamespace(request=request), body, {"X-Test": "member"})
    assert len(body["tools"]) == count


@pytest.mark.asyncio
async def test_old_catalog_does_not_guess_limit():
    async def request(*args, **kwargs):
        return httpx.Response(200, json={"items": [{"id": "chosen"}]})
    await _check_ai2apps_tool_limit(SimpleNamespace(request=request), {"model": "chosen", "tools": [{}] * 129})


def test_provider_retry_policy():
    assert not _model_error_retryable(HTTPException(400, {"retryable": False}))
    assert not _model_error_retryable(HTTPException(401, "Unauthorized"))
    assert _model_error_retryable(HTTPException(429, "Busy"))
    assert _model_error_retryable(TimeoutError())


@pytest.mark.asyncio
async def test_gateway_over_limit_never_submits_to_provider():
    calls = []
    async def request(method, path, **kwargs):
        calls.append((method, path))
        return httpx.Response(200, json={"items": [{"id": "chosen", "capabilities": {
            "toolOptions": {"maxTools": 32}}}]})
    request_body = SimpleNamespace(model="cloud/ai2apps/chosen", messages=[],
        max_tokens=10, stream=False, temperature=None,
        tools=[SimpleNamespace(function={"name": f"tool{i}"}) for i in range(33)])
    with pytest.raises(HTTPException) as error:
        await _proxy_ai2apps_chat_completion(request_body, SimpleNamespace(request=request))
    assert error.value.detail["param"] == "tools"
    assert calls == [("GET", "/v1/ai/models")]


@pytest.mark.asyncio
async def test_gateway_preserves_upstream_limit_diagnostics():
    detail = {"code": "INVALID_AI_TOOLS", "message": "too many", "retryable": False,
              "param": "tools", "details": {"limit": 32, "actual": 33}}
    async def request(method, path, **kwargs):
        return httpx.Response(400, json={"error": detail})
    request_body = SimpleNamespace(model="cloud/ai2apps/chosen", messages=[],
        max_tokens=10, stream=False, temperature=None, tools=None)
    with pytest.raises(HTTPException) as error:
        await _proxy_ai2apps_chat_completion(request_body, SimpleNamespace(request=request))
    assert error.value.detail == detail
