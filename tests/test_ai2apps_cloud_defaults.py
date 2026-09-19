import asyncio
import time
from types import SimpleNamespace

import httpx
import pytest

from ai2apps.cloud_defaults import CACHE_SECONDS, refresh_cloud_defaults, validate_policy
from ai2apps.model_manager import ModelManagerStore
from ai2apps.secrets import MemorySecretBackend


def policy(model="deepseek/deepseek-v4-flash", revision="1"):
    return {
        "schema": "ai2apps.ai-defaults/v1",
        "revision": revision,
        "apiDefault": {"modelId": model, "displayName": "DeepSeek V4 Flash"} if model else None,
    }


@pytest.fixture
def store(tmp_path):
    return ModelManagerStore(tmp_path, secret_backend=MemorySecretBackend())


def test_inheritance_tracks_cloud_without_pinning_or_overwriting_user(store):
    store.put_default_models({"work_complex": "my-local-model"})
    explicit_bytes = store.defaults_path.read_bytes()
    store.put_cloud_default_policy(policy(), fetched_at=time.time())
    assert store.resolve_default_model("work_simple") == "cloud/ai2apps/deepseek/deepseek-v4-flash"
    assert store.resolve_default_model("work_standard") == "cloud/ai2apps/deepseek/deepseek-v4-flash"
    assert store.resolve_default_model("work_complex") == "my-local-model"
    assert store.resolve_default_model("image_generation") is None
    store.put_cloud_default_policy(policy("provider/replacement", "2"), fetched_at=time.time())
    assert store.resolve_default_model("work_standard") == "cloud/ai2apps/provider/replacement"
    assert store.defaults_path.read_bytes() == explicit_bytes
    store.put_default_models({})
    assert store.resolve_default_model("work_complex") == "cloud/ai2apps/provider/replacement"


def test_cache_restart_expiry_origin_and_revocation(store):
    store.put_cloud_default_policy(policy(), fetched_at=time.time())
    restarted = ModelManagerStore(store.base_path, secret_backend=MemorySecretBackend())
    assert restarted.resolve_default_model("work_standard")
    restarted.cloud_defaults_origin = "https://another.example"
    assert restarted.resolve_default_model("work_standard") is None
    store.put_cloud_default_policy(policy(), fetched_at=time.time() - CACHE_SECONDS - 1)
    assert store.resolve_default_model("work_standard", "fallback") == "fallback"
    store.put_cloud_default_policy(policy(None), fetched_at=time.time())
    assert store.resolve_default_model("work_standard") is None
    store.cloud_defaults_path.write_text("not json")
    assert store.resolve_default_model("work_standard") is None


@pytest.mark.parametrize("payload", [{}, policy("cloud/openai/model"), policy("../model"), policy(revision="")])
def test_malformed_policy_rejected(payload):
    with pytest.raises(ValueError):
        validate_policy(payload)


@pytest.mark.asyncio
async def test_refresh_old_server_invalid_payload_and_network_failure_preserve_cache(store):
    store.put_cloud_default_policy(policy(), fetched_at=time.time())
    before = store.cloud_defaults_path.read_bytes()
    for status, body in [(404, {}), (200, {}), (503, {})]:
        response = httpx.Response(status, json=body)
        async def request(method, path):
            assert (method, path) == ("GET", "/v1/ai/defaults")
            return response
        assert not await refresh_cloud_defaults(store, SimpleNamespace(request=request))
        assert response.is_closed
        assert store.cloud_defaults_path.read_bytes() == before
    async def unavailable(*args):
        raise httpx.ConnectError("offline")
    assert not await refresh_cloud_defaults(store, SimpleNamespace(request=unavailable))
    assert store.cloud_defaults_path.read_bytes() == before


@pytest.mark.asyncio
async def test_refresh_success_and_cancellation(store):
    async def request(*args):
        return httpx.Response(200, json=policy())
    assert await refresh_cloud_defaults(store, SimpleNamespace(request=request))
    assert store.resolve_default_model("work_standard").startswith("cloud/ai2apps/")
    async def cancelled(*args):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await refresh_cloud_defaults(store, SimpleNamespace(request=cancelled))


@pytest.mark.asyncio
async def test_explicit_cloud_default_keeps_points_route_with_personal_key(monkeypatch, tmp_path):
    from ai2apps import cloud_gateway
    managed_id = "cloud/ai2apps/deepseek/deepseek-v4-flash"
    request = SimpleNamespace(model=managed_id)
    store = SimpleNamespace(
        resolve_cloud_model=lambda model: None,
        list_cloud=lambda: [{"id": "deepseek", "configured": True}],
    )
    async def proxy(request, client, **kwargs):
        assert request.model == managed_id
        return "points-route"
    monkeypatch.setattr(cloud_gateway, "_proxy_ai2apps_chat_completion", proxy)
    result = await cloud_gateway.proxy_cloud_chat_completion(
        request, base_path=tmp_path, model_manager=store,
    )
    assert result == "points-route"
    assert request.model == managed_id


def test_local_policy_endpoint_exposes_inheritance_without_pinning(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.cloud import create_cloud_router
    from ai2apps.identity import RequestPrincipal
    store.put_cloud_default_policy(policy(), fetched_at=time.time())
    runtime = SimpleNamespace(model_manager=store)
    app = FastAPI()
    app.include_router(create_cloud_router(lambda: runtime, RequestPrincipal.legacy_local))
    with TestClient(app) as client:
        response = client.get("/cloud/ai/defaults")
    assert response.status_code == 200
    assert response.json()["policy"] == policy()
    assert store.default_models()["work_standard"] == ""
