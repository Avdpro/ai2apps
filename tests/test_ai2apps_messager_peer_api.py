from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.messager_peer import create_messager_peer_ingress_router
from ai2apps.messager.peer_service import MessagerPeerError


class StubPeer:
    async def accept_handshake(self, payload):
        return {"sessionId": "session", "noiseMessage": payload["noiseMessage"]}

    async def accept_message(self, payload):
        if payload.get("sessionId") == "replayed":
            raise MessagerPeerError(
                "MESSAGER_SESSION_INVALID", "expired", status_code=401
            )
        return {"ciphertext": payload["ciphertext"]}


class StubPeerV2:
    async def accept_handshake(self, grant, payload):
        assert grant == "fresh-grant"
        return payload | {"connectionId": "A" * 43}

    async def accept_message(self, grant, payload):
        assert grant == "fresh-grant"
        return payload


def test_public_peer_ingress_has_narrow_contract_and_no_store_errors() -> None:
    runtime = SimpleNamespace(messager_peer=StubPeer(), messager_peer_v2=StubPeerV2())
    app = FastAPI()
    app.include_router(create_messager_peer_ingress_router(lambda: runtime))
    client = TestClient(app)

    handshake = client.post(
        "/v1/messager/peer/v1/handshakes",
        json={"noiseMessage": "abc"},
    )
    assert handshake.status_code == 201
    assert handshake.json() == {"sessionId": "session", "noiseMessage": "abc"}

    rejected = client.post(
        "/v1/messager/peer/v1/messages",
        json={"sessionId": "replayed", "ciphertext": "secret"},
    )
    assert rejected.status_code == 401
    assert rejected.headers["cache-control"] == "no-store"
    assert rejected.json()["error"]["code"] == "MESSAGER_SESSION_INVALID"

    oversized = client.post(
        "/v1/messager/peer/v1/messages",
        content=b"{" + b"x" * 32_768 + b"}",
        headers={"Content-Type": "application/json"},
    )
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "MESSAGER_REQUEST_TOO_LARGE"

    missing_grant = client.post("/v1/messager/peer/v2/handshakes", json={})
    assert missing_grant.status_code == 401
    assert missing_grant.json()["error"]["code"] == "PEER_GRANT_REQUIRED"

    v2 = client.post(
        "/v1/messager/peer/v2/handshakes",
        headers={"Authorization": "Bearer fresh-grant"},
        json={"version": 2, "sessionId": "s", "handshakeId": "h", "noiseMessage": "n"},
    )
    assert v2.status_code == 201
    assert v2.json()["connectionId"] == "A" * 43
