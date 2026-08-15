# SPDX-License-Identifier: Apache-2.0
"""REST contract tests for generic Sessions, Messages, and Event snapshots."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.config import PlatformConfig
from ai2apps.core import AppInstanceMode
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.storage.repositories import AppRepository


def _client(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.database is not None
    assert runtime.events is not None
    apps = AppRepository(runtime.database, runtime.events)
    definition = apps.create_definition(
        package_id="host.app",
        package_version="1.0.0",
        display_name="Host App",
        instance_mode=AppInstanceMode.MULTIPLE,
    )
    instance = apps.create_instance(app_definition_id=definition.id)
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))
    return TestClient(app), runtime, instance.id


def test_mini_and_in_app_chats_are_generic_unlisted_temporary_sessions(tmp_path):
    client, _, instance_id = _client(tmp_path)

    mini = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"kind": "mini_chat", "title": "Quick help"},
    )
    in_app = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"kind": "in_app_chat", "title": "Document helper"},
    )
    thread = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"kind": "chat_thread", "title": "Real thread"},
    )
    invalid_thread = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={
            "kind": "chat_thread",
            "visibility": "unlisted",
            "retention": "temporary",
        },
    )

    assert mini.status_code == 201
    assert mini.json()["kind"] == "mini_chat"
    assert mini.json()["visibility"] == "unlisted"
    assert mini.json()["retention"] == "temporary"
    assert mini.json()["expires_at"] is not None
    assert in_app.json()["kind"] == "in_app_chat"
    assert thread.json()["kind"] == "chat_thread"
    assert thread.json()["visibility"] == "listed"
    assert thread.json()["retention"] == "durable"
    assert invalid_thread.status_code == 409
    assert invalid_thread.json()["error"]["code"] == "resource_conflict"

    thread_list = client.get(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        params={"kind": "chat_thread", "visibility": "listed"},
    )
    assert [item["id"] for item in thread_list.json()["items"]] == [
        thread.json()["id"]
    ]

    chat_app_threads = client.get("/v1/platform/chat/threads")
    assert chat_app_threads.status_code == 200
    chat_app_thread_ids = {item["id"] for item in chat_app_threads.json()["items"]}
    assert mini.json()["id"] not in chat_app_thread_ids
    assert in_app.json()["id"] not in chat_app_thread_ids


def test_durable_session_expiry_is_rejected_by_api_contract(tmp_path):
    client, _, instance_id = _client(tmp_path)

    response = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"expires_at": "2025-01-01T00:00:00Z"},
    )

    assert response.status_code == 422


def test_session_crud_revision_conflict_and_logical_delete(tmp_path):
    client, _, instance_id = _client(tmp_path)
    created = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"title": "Before"},
    ).json()

    updated = client.patch(
        f"/v1/platform/app-instances/{instance_id}/sessions/{created['id']}",
        json={"expected_revision": 1, "title": "After"},
    )
    stale = client.patch(
        f"/v1/platform/app-instances/{instance_id}/sessions/{created['id']}",
        json={"expected_revision": 1, "title": "Stale"},
    )
    deleted = client.delete(
        f"/v1/platform/app-instances/{instance_id}/sessions/{created['id']}",
        params={"expected_revision": 2},
    )

    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"
    assert deleted.json()["status"] == "deleted"
    listed = client.get(
        f"/v1/platform/app-instances/{instance_id}/sessions"
    ).json()["items"]
    assert listed == []


def test_message_api_idempotency_parts_and_event_snapshot(tmp_path):
    client, _, instance_id = _client(tmp_path)
    session = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={"kind": "in_app_chat"},
    ).json()
    payload = {
        "role": "user",
        "parts": [{"kind": "text", "content": {"text": "hello"}}],
    }

    first = client.post(
        f"/v1/platform/sessions/{session['id']}/messages",
        json=payload,
        headers={"Idempotency-Key": "request-1"},
    )
    replay = client.post(
        f"/v1/platform/sessions/{session['id']}/messages",
        json=payload,
        headers={"Idempotency-Key": "request-1"},
    )
    conflict = client.post(
        f"/v1/platform/sessions/{session['id']}/messages",
        json={
            "role": "user",
            "parts": [{"kind": "text", "content": {"text": "different"}}],
        },
        headers={"Idempotency-Key": "request-1"},
    )

    assert first.status_code == 201
    assert first.json()["created"] is True
    assert replay.status_code == 200
    assert replay.json()["created"] is False
    assert replay.json()["id"] == first.json()["id"]
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    messages = client.get(
        f"/v1/platform/sessions/{session['id']}/messages"
    ).json()["items"]
    assert len(messages) == 1
    assert messages[0]["parts"][0]["content"] == {"text": "hello"}
    events = client.get(
        f"/v1/platform/sessions/{session['id']}/events"
    ).json()["items"]
    assert [event["type"] for event in events] == [
        "session.created",
        "message.created",
    ]


def test_message_header_body_idempotency_mismatch_is_stable_error(tmp_path):
    client, _, instance_id = _client(tmp_path)
    session = client.post(
        f"/v1/platform/app-instances/{instance_id}/sessions",
        json={},
    ).json()
    response = client.post(
        f"/v1/platform/sessions/{session['id']}/messages",
        json={
            "role": "user",
            "idempotency_key": "body-key",
            "parts": [{"kind": "text", "content": {"text": "hello"}}],
        },
        headers={"Idempotency-Key": "header-key"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "idempotency_key_mismatch"


def test_invalid_sse_cursor_returns_platform_error(tmp_path):
    client, _, _ = _client(tmp_path)
    response = client.get(
        "/v1/platform/events",
        headers={"Last-Event-ID": "not-an-integer"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_event_cursor"


def test_resource_and_event_routes_are_published_in_openapi(tmp_path):
    client, _, _ = _client(tmp_path)
    paths = client.app.openapi()["paths"]

    assert "/v1/platform/app-instances/{app_instance_id}/sessions" in paths
    assert "/v1/platform/sessions/{session_id}/messages" in paths
    assert "/v1/platform/sessions/{session_id}/events" in paths
    assert "/v1/platform/events" in paths
