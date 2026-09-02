import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ai2apps.peer.grants import PeerGrantError, verify_peer_grant
from ai2apps.peer.identity import (
    PEER_KEY_SUITE,
    PeerDeviceKeyManager,
    PeerDeviceKeys,
    PeerProtocol,
    b64url_encode,
)
from ai2apps.peer.session import PeerEndpoint, PeerSession, PeerTransportPolicy
from ai2apps.peer.transports.relay_https import RelayHttpsTransport


def _raw_public(key):
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _endpoint():
    return PeerEndpoint(
        user_id=str(uuid4()), device_id=str(uuid4()), installation_id=str(uuid4()),
        access_epoch=3, key_id=str(uuid4()), key_epoch=2,
        identity_signing_public_key=b64url_encode(_raw_public(Ed25519PrivateKey.generate())),
        static_dh_public_key=b64url_encode(_raw_public(X25519PrivateKey.generate())),
    )


def _compact(private_key, kid, claims):
    encode = lambda value: base64.urlsafe_b64encode(
        json.dumps(value, separators=(",", ":")).encode()
    ).rstrip(b"=").decode()
    header = encode({"alg": "EdDSA", "kid": kid, "typ": "JWT"})
    payload = encode(claims)
    signature = b64url_encode(private_key.sign(f"{header}.{payload}".encode("ascii")))
    return f"{header}.{payload}.{signature}"


def test_peer_registration_transcript_is_protocol_scoped():
    device_id = str(uuid4())
    keys = PeerDeviceKeys(device_id, PeerProtocol.MODEL_SHARE_V1, Ed25519PrivateKey.generate(), X25519PrivateKey.generate())
    challenge = {
        "challengeId": str(uuid4()), "challenge": "challenge-value",
        "deviceId": device_id, "protocol": "model-share-v1", "accessEpoch": 7,
    }
    expected = "\n".join((
        "ai2apps-peer-device-key-registration-v1", challenge["challengeId"],
        challenge["challenge"], device_id, "model-share-v1", "7", PEER_KEY_SUITE,
        keys.identity_public, keys.static_dh_public, "",
    )).encode()
    assert PeerDeviceKeyManager.registration_transcript(challenge, keys) == expected


def test_peer_grant_is_bound_to_every_session_authority_field():
    signing = Ed25519PrivateKey.generate()
    kid = str(uuid4())
    self_endpoint, peer_endpoint = _endpoint(), _endpoint()
    now = int(datetime.now(UTC).timestamp())
    session = PeerSession(
        session_id=str(uuid4()), protocol=PeerProtocol.MODEL_SHARE_V1,
        purpose_type="compute_contract", purpose_id=str(uuid4()), status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        transport_policy=PeerTransportPolicy(("relay_https",), 1024, 1, 4, "rematch_or_fail"),
        self_endpoint=self_endpoint, peer_endpoint=peer_endpoint,
    )
    claims = {
        "iss": "ai2apps-cloud", "aud": session.protocol.audience,
        "sub": self_endpoint.user_id, "jti": str(uuid4()), "iat": now,
        "nbf": now - 5, "exp": now + 90, "session_id": session.session_id,
        "protocol": session.protocol.value, "protocol_version": 1,
        "purpose_id": session.purpose_id, "purpose_type": session.purpose_type,
        "holder_user_id": self_endpoint.user_id, "holder_device_id": self_endpoint.device_id,
        "initiator_user_id": self_endpoint.user_id, "initiator_device_id": self_endpoint.device_id,
        "initiator_installation_id": self_endpoint.installation_id,
        "initiator_access_epoch": self_endpoint.access_epoch, "initiator_key_id": self_endpoint.key_id,
        "initiator_key_epoch": self_endpoint.key_epoch, "recipient_user_id": peer_endpoint.user_id,
        "recipient_device_id": peer_endpoint.device_id, "recipient_installation_id": peer_endpoint.installation_id,
        "recipient_access_epoch": peer_endpoint.access_epoch, "recipient_key_id": peer_endpoint.key_id,
        "recipient_key_epoch": peer_endpoint.key_epoch, "allowed_transports": ["relay_https"],
        "max_bytes": "1024", "max_streams": 1, "policy_version": 4,
    }
    jwks = {"keys": [{
        "kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig", "kid": kid,
        "x": b64url_encode(_raw_public(signing)),
    }]}
    compact = _compact(signing, kid, claims)
    assert verify_peer_grant(
        compact, jwks, session=session,
        holder_user_id=self_endpoint.user_id, holder_device_id=self_endpoint.device_id, now=now,
    ).claims["jti"] == claims["jti"]
    claims["purpose_id"] = str(uuid4())
    with pytest.raises(PeerGrantError):
        verify_peer_grant(
            _compact(signing, kid, claims), jwks, session=session,
            holder_user_id=self_endpoint.user_id, holder_device_id=self_endpoint.device_id, now=now,
        )


def test_peer_session_accepts_cloud_authorized_relay_origin():
    self_endpoint, peer_endpoint = _endpoint(), _endpoint()
    payload = {
        "sessionId": str(uuid4()), "protocol": "model-share-v1",
        "purposeType": "compute_contract", "purposeId": str(uuid4()),
        "status": "active", "expiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "transportPolicy": {"allowedTransports": ["relay_https"], "maxBytes": "1024",
                            "maxStreams": 1, "policyVersion": 1, "fallbackPolicy": "rematch_or_fail"},
        "self": {"userId": self_endpoint.user_id, "deviceId": self_endpoint.device_id,
                 "installationId": self_endpoint.installation_id, "accessEpoch": self_endpoint.access_epoch,
                 "keyId": self_endpoint.key_id, "keyEpoch": self_endpoint.key_epoch, "suite": PEER_KEY_SUITE,
                 "identitySigningPublicKey": self_endpoint.identity_signing_public_key,
                 "staticDhPublicKey": self_endpoint.static_dh_public_key},
        "peer": {"userId": peer_endpoint.user_id, "deviceId": peer_endpoint.device_id,
                 "installationId": peer_endpoint.installation_id, "accessEpoch": peer_endpoint.access_epoch,
                 "keyId": peer_endpoint.key_id, "keyEpoch": peer_endpoint.key_epoch, "suite": PEER_KEY_SUITE,
                 "identitySigningPublicKey": peer_endpoint.identity_signing_public_key,
                 "staticDhPublicKey": peer_endpoint.static_dh_public_key,
                 "relayOrigin": "https://device-0123456789abcdef0123456789abcdef.ai2apps.com"},
    }
    session = PeerSession.parse(payload)
    assert session.peer_endpoint.relay_origin == payload["peer"]["relayOrigin"]


@pytest.mark.asyncio
async def test_relay_transport_allows_only_versioned_messager_paths():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer grant"
        return httpx.Response(200, json={"accepted": True})

    transport = RelayHttpsTransport(
        "https://device-0123456789abcdef0123456789abcdef.ai2apps.com",
        transport=httpx.MockTransport(handler),
    )
    response = await transport.post(
        path="/v1/messager/peer/v2/messages", grant="grant", payload=b"{}", max_response_bytes=1024,
    )
    assert json.loads(response.body) == {"accepted": True}

    with pytest.raises(Exception):
        await transport.post(path="/v1/remote/devices", grant="grant", payload=b"{}", max_response_bytes=1024)
