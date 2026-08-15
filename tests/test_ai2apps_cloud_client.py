import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.cloud_client import (
    AI2AppsCloudClient,
    CloudSessionStore,
    resolve_cloud_base_url,
)
from ai2apps.secrets import MemorySecretBackend


def _local_client(handler):
    backend = MemorySecretBackend()
    cloud = AI2AppsCloudClient(
        base_url="https://coder.ai2apps.test",
        session_store=CloudSessionStore(backend, "https://coder.ai2apps.test"),
        transport=httpx.MockTransport(handler),
    )
    runtime = SimpleNamespace(cloud=cloud)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))
    return TestClient(app), backend, cloud


def test_cloud_origin_validation_rejects_credentials_and_paths():
    assert resolve_cloud_base_url("https://coder.ai2apps.com/") == (
        "https://coder.ai2apps.com"
    )
    with pytest.raises(ValueError):
        resolve_cloud_base_url("https://user:secret@example.com")
    with pytest.raises(ValueError):
        resolve_cloud_base_url("https://example.com/api")
    with pytest.raises(ValueError):
        resolve_cloud_base_url("http://example.com")
    assert resolve_cloud_base_url("http://127.0.0.1:8787") == (
        "http://127.0.0.1:8787"
    )


def test_login_cookie_stays_in_native_client_and_is_restored_for_auth_me():
    captured = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/auth/login":
            captured["login"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"user": {"id": "user-1"}},
                headers={
                    "set-cookie": (
                        "ai2apps_session=session-secret; Path=/; HttpOnly; "
                        "Secure; SameSite=Strict"
                    )
                },
            )
        captured["cookie"] = request.headers.get("cookie")
        return httpx.Response(200, json={"user": {"id": "user-1"}})

    client, backend, cloud = _local_client(handler)
    login = client.post(
        "/v1/platform/cloud/auth/login",
        json={"email": "me@example.com", "password": "long-password"},
    )
    me = client.get("/v1/platform/cloud/auth/me")

    assert login.status_code == 200
    assert "set-cookie" not in login.headers
    assert captured["login"] == {
        "email": "me@example.com",
        "password": "long-password",
    }
    assert captured["cookie"] == "ai2apps_session=session-secret"
    assert backend.values[cloud.session_store.key] == "session-secret"
    assert me.json()["user"]["id"] == "user-1"


def test_logout_clears_persisted_cloud_session():
    def handler(request: httpx.Request):
        return httpx.Response(204)

    client, backend, cloud = _local_client(handler)
    backend.store(cloud.session_store.key, "old-session")

    response = client.post("/v1/platform/cloud/auth/logout")

    assert response.status_code == 204
    assert cloud.session_store.key not in backend.values


def test_admin_reauthentication_is_forwarded_without_persisting_password():
    captured = {}

    def handler(request: httpx.Request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "verifiedAt": "2026-08-14T05:30:00Z",
                "expiresAt": "2026-08-14T05:45:00Z",
            },
        )

    client, backend, _ = _local_client(handler)
    response = client.post(
        "/v1/platform/cloud/admin/reauth",
        json={"password": "long-password"},
    )

    assert response.status_code == 200
    assert captured == {
        "path": "/v1/admin/reauth",
        "body": {"password": "long-password"},
    }
    assert not any("long-password" in value for value in backend.values.values())


def test_points_remain_decimal_strings_and_ai_sse_is_forwarded():
    captured = {}

    def handler(request: httpx.Request):
        if request.url.path == "/v1/points":
            return httpx.Response(
                200,
                json={"promotional": "300", "paid": "500", "total": "800"},
            )
        captured["idempotency"] = request.headers["idempotency-key"]
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=(
                b"event: response.created\ndata: {\"requestId\":\"req-1\"}\n\n"
                b"event: output_text.delta\ndata: {\"delta\":\"hello\"}\n\n"
                b"event: response.completed\ndata: {\"charged\":\"1\"}\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    client, _, _ = _local_client(handler)
    points = client.get("/v1/platform/cloud/points")
    streamed = client.post(
        "/v1/platform/cloud/ai/responses",
        headers={"Idempotency-Key": "request-123"},
        json={
            "model": "openai/gpt-test",
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hi"}],
                }
            ],
            "stream": True,
        },
    )

    assert points.json() == {"promotional": "300", "paid": "500", "total": "800"}
    assert captured["idempotency"] == "request-123"
    assert captured["body"]["model"] == "openai/gpt-test"
    assert streamed.headers["content-type"].startswith("text/event-stream")
    assert "response.completed" in streamed.text


def test_image_generation_and_edit_are_forwarded_without_protocol_rewriting():
    captured = []

    def handler(request: httpx.Request):
        captured.append(
            {
                "path": request.url.path,
                "idempotency": request.headers["idempotency-key"],
                "body": json.loads(request.content),
            }
        )
        return httpx.Response(
            200,
            json={
                "requestId": f"req-{len(captured)}",
                "image": {
                    "dataUrl": "data:image/png;base64,aW1hZ2U=",
                    "size": "1024x1024",
                    "quality": "auto",
                    "format": "png",
                },
                "charged": "3",
                "balance": "797",
            },
        )

    client, _, _ = _local_client(handler)
    generated = client.post(
        "/v1/platform/cloud/ai/images/generations",
        headers={"Idempotency-Key": "image-generate-1"},
        json={
            "model": "openai/gpt-image-2",
            "prompt": "A paper boat",
            "size": "1024x1024",
            "quality": "auto",
            "outputFormat": "png",
            "n": 1,
        },
    )
    edited = client.post(
        "/v1/platform/cloud/ai/images/edits",
        headers={"Idempotency-Key": "image-edit-1"},
        json={
            "model": "openai/gpt-image-2",
            "prompt": "Make it blue",
            "imageDataUrls": ["data:image/png;base64,aW5wdXQ="],
        },
    )

    assert generated.status_code == edited.status_code == 200
    assert generated.json()["image"]["dataUrl"].startswith("data:image/png;base64,")
    assert [item["path"] for item in captured] == [
        "/v1/ai/images/generations",
        "/v1/ai/images/edits",
    ]
    assert captured[0]["idempotency"] == "image-generate-1"
    assert captured[1]["idempotency"] == "image-edit-1"
    assert captured[1]["body"]["imageDataUrls"] == [
        "data:image/png;base64,aW5wdXQ="
    ]


def test_cloud_transport_failure_has_stable_redacted_error():
    def handler(request: httpx.Request):
        raise httpx.ConnectError("secret internal address", request=request)

    client, _, _ = _local_client(handler)
    response = client.get("/v1/platform/cloud/auth/me")

    assert response.status_code == 502
    assert response.json()["error"] == {
        "code": "cloud_unavailable",
        "message": "AI2Apps Cloud is unavailable.",
        "retryable": True,
        "details": {},
    }
