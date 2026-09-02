# SPDX-License-Identifier: Apache-2.0
"""Local-first Messager persistence and principal-isolation tests."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.messager import create_messager_router
from ai2apps.events import EventStore
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.messager import MessagerIdempotencyConflictError, MessagerRepository
from ai2apps.storage import PlatformDatabase


def _principal(user_id: str) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.CORE,
        membership_epoch=1,
    )


def _repository(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database)
    return database, events, MessagerRepository(database, events)


def test_cloud_incoming_is_idempotent_and_audit_excludes_body(tmp_path):
    _, events, repository = _repository(tmp_path)
    private_body = "a private incoming message"
    item = {
        "id": "cloud-message-1",
        "kind": "user.offline_message",
        "senderUserId": "friend-1",
        "body": private_body,
        "createdAt": "2026-08-23T00:00:00Z",
    }

    first = repository.ingest_cloud_message("owner-1", item)
    repeated = repository.ingest_cloud_message("owner-1", item)

    assert first is not None
    assert repeated is not None
    assert repeated["id"] == first["id"]
    assert repository.list_messages("owner-1", "friend-1") == [first]
    recorded = events.list_after(subject_id=first["id"], limit=10)
    assert [event.type for event in recorded] == ["messager.message.received"]
    assert private_body not in json.dumps(recorded[0].payload)


def test_cloud_incoming_image_only_message_keeps_private_metadata(tmp_path):
    _, _, repository = _repository(tmp_path)
    attachment_id = "323e4567-e89b-42d3-a456-426614174000"

    item = repository.ingest_cloud_message(
        "owner-1",
        {
            "id": "cloud-message-image",
            "kind": "user.offline_message",
            "senderUserId": "friend-1",
            "body": None,
            "createdAt": "2026-08-23T00:00:00Z",
            "attachment": {
                "id": attachment_id,
                "mediaType": "image/webp",
                "byteSize": 123,
                "width": 10,
                "height": 20,
                "contentPath": (
                    f"/v1/system-message-attachments/{attachment_id}/content"
                ),
            },
        },
    )

    assert item is not None
    assert item["body"] == ""
    assert item["attachment_id"] == attachment_id
    assert item["attachment_media_type"] == "image/webp"


def test_outgoing_client_message_id_is_idempotent(tmp_path):
    _, _, repository = _repository(tmp_path)
    kwargs = {
        "owner_user_id": "owner-1",
        "peer_user_id": "friend-1",
        "client_message_id": "123e4567-e89b-42d3-a456-426614174000",
        "body": "hello",
        "remote_message_id": "cloud-message-2",
        "created_at": "2026-08-23T00:00:01Z",
    }

    first = repository.record_cloud_outgoing(**kwargs)
    repeated = repository.record_cloud_outgoing(**kwargs)

    assert repeated["id"] == first["id"]
    assert repository.list_messages("owner-1", "friend-1") == [first]


def test_outgoing_client_message_id_rejects_different_logical_message(tmp_path):
    _, _, repository = _repository(tmp_path)
    client_message_id = "123e4567-e89b-42d3-a456-426614174000"
    repository.record_cloud_outgoing(
        owner_user_id="owner-1",
        peer_user_id="friend-1",
        client_message_id=client_message_id,
        body="hello",
        remote_message_id="cloud-message-2",
    )

    with pytest.raises(MessagerIdempotencyConflictError):
        repository.validate_cloud_outgoing(
            owner_user_id="owner-1",
            peer_user_id="friend-2",
            client_message_id=client_message_id,
            body="hello",
        )


def test_local_history_is_isolated_by_authenticated_principal(tmp_path):
    database, events, repository = _repository(tmp_path)
    repository.record_cloud_outgoing(
        owner_user_id="owner-1",
        peer_user_id="friend-1",
        client_message_id="123e4567-e89b-42d3-a456-426614174000",
        body="owner one only",
        remote_message_id="cloud-message-1",
    )
    repository.record_cloud_outgoing(
        owner_user_id="owner-2",
        peer_user_id="friend-1",
        client_message_id="223e4567-e89b-42d3-a456-426614174000",
        body="owner two only",
        remote_message_id="cloud-message-2",
    )

    current = {"principal": _principal("owner-1")}
    runtime = SimpleNamespace(database=database, events=events)
    app = FastAPI()
    app.include_router(
        create_messager_router(
            lambda: runtime,
            principal_provider=lambda: current["principal"],
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    first = client.get("/v1/platform/messager/conversations/friend-1/messages")
    assert first.status_code == 200
    assert [item["body"] for item in first.json()["items"]] == ["owner one only"]

    current["principal"] = _principal("owner-2")
    second = client.get("/v1/platform/messager/conversations/friend-1/messages")
    assert second.status_code == 200
    assert [item["body"] for item in second.json()["items"]] == ["owner two only"]

    conversations = client.get("/v1/platform/messager/conversations")
    assert conversations.status_code == 200
    assert [item["lastBody"] for item in conversations.json()["items"]] == [
        "owner two only"
    ]


def test_local_peer_replay_and_message_deduplication(tmp_path):
    _, events, repository = _repository(tmp_path)
    kwargs = {
        "assertion_jti": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "handshake_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "initiator_user_id": "owner-1",
        "initiator_device_id": "device-1",
        "expires_at": 2_000_000_000,
    }
    assert repository.accept_peer_handshake(**kwargs) is True
    assert repository.accept_peer_handshake(**kwargs) is False

    first, created = repository.record_local_incoming(
        owner_user_id="owner-2",
        peer_user_id="owner-1",
        remote_message_id="123e4567-e89b-42d3-a456-426614174000",
        body="secret local text",
    )
    repeated, created_again = repository.record_local_incoming(
        owner_user_id="owner-2",
        peer_user_id="owner-1",
        remote_message_id="123e4567-e89b-42d3-a456-426614174000",
        body="secret local text",
    )
    assert created is True
    assert created_again is False
    assert repeated["id"] == first["id"]
    audit = events.list_after(subject_id=first["id"], limit=10)
    assert "secret local text" not in json.dumps(audit[0].payload)


def test_device_key_rotation_requires_system_manage_and_hides_key_material():
    class StubPeer:
        async def rotate_device_key(self, principal):
            assert principal.actor_user_id == "owner-1"
            return {
                "deviceId": "device-1",
                "keyId": "msgk-new",
                "status": "active",
                "identitySigningPublicKey": "must-not-leak",
                "staticDhPublicKey": "must-not-leak",
            }

    current = {"principal": _principal("owner-1")}
    runtime = SimpleNamespace(messager_peer=StubPeer())
    app = FastAPI()
    app.include_router(
        create_messager_router(
            lambda: runtime,
            principal_provider=lambda: current["principal"],
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    rotated = client.post("/v1/platform/messager/device-key/rotate")
    assert rotated.status_code == 200
    assert rotated.headers["cache-control"] == "no-store"
    assert rotated.json() == {
        "deviceId": "device-1",
        "keyId": "msgk-new",
        "status": "active",
    }

    current["principal"] = RequestPrincipal(
        actor_user_id="member-1",
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )
    denied = client.post("/v1/platform/messager/device-key/rotate")
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "app_access_denied"
