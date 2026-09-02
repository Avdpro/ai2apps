from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from test_ai2apps_messager_identity import MemorySecrets

from ai2apps.messager.noise_v2 import (
    MessagerV2NoiseError,
    V2InitiatorExchange,
    V2ResponderExchange,
)
from ai2apps.peer.identity import PeerDeviceKeyManager, PeerProtocol, b64url_encode
from ai2apps.peer.session import PeerEndpoint, PeerSession, PeerTransportPolicy


def _endpoint(keys, user_id: str) -> PeerEndpoint:
    return PeerEndpoint(
        user_id=user_id, device_id=keys.device_id, installation_id=str(uuid4()),
        access_epoch=2, key_id=str(uuid4()), key_epoch=3,
        identity_signing_public_key=keys.identity_public,
        static_dh_public_key=keys.static_dh_public,
    )


def _session(self_endpoint, peer_endpoint, session_id: str, purpose_id: str) -> PeerSession:
    return PeerSession(
        session_id=session_id, protocol=PeerProtocol.MESSAGER_V2,
        purpose_type="conversation", purpose_id=purpose_id, status="active",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        transport_policy=PeerTransportPolicy(
            ("relay_https",), 16_777_216, 4, 1, "offline_system_message"
        ),
        self_endpoint=self_endpoint, peer_endpoint=peer_endpoint,
    )


def test_v2_noise_round_trip_binds_both_request_grants_and_one_connection() -> None:
    manager = PeerDeviceKeyManager(MemorySecrets())
    initiator_keys = manager.get_or_create(str(uuid4()), PeerProtocol.MESSAGER_V2)
    responder_keys = manager.get_or_create(str(uuid4()), PeerProtocol.MESSAGER_V2)
    initiator_endpoint = _endpoint(initiator_keys, str(uuid4()))
    responder_endpoint = _endpoint(responder_keys, str(uuid4()))
    session_id, purpose_id = str(uuid4()), "conversation:test"
    initiator_session = _session(initiator_endpoint, responder_endpoint, session_id, purpose_id)
    responder_session = _session(responder_endpoint, initiator_endpoint, session_id, purpose_id)
    handshake_id, handshake_jti, connection_id = str(uuid4()), str(uuid4()), b64url_encode(b"c" * 32)

    initiator, first = V2InitiatorExchange.begin(
        keys=initiator_keys, session=initiator_session, handshake_id=handshake_id,
        handshake_grant_jti=handshake_jti,
    )
    responder, second = V2ResponderExchange.accept(
        keys=responder_keys, session=responder_session, handshake_id=handshake_id,
        handshake_grant_jti=handshake_jti, connection_id=connection_id, request=first,
    )
    assert initiator.finish(second) == connection_id
    message_jti, message_id = str(uuid4()), str(uuid4())
    ciphertext = initiator.encrypt_text(
        message_grant_jti=message_jti, client_message_id=message_id,
        sender_user_id=initiator_endpoint.user_id,
        recipient_user_id=responder_endpoint.user_id, body="v2 private hello",
    )
    clear = responder.decrypt_text(ciphertext, message_grant_jti=message_jti)
    assert clear["body"] == "v2 private hello"
    ack = responder.encrypt_ack(
        message_grant_jti=message_jti, client_message_id=message_id,
        received_at="2026-08-31T00:00:00Z", status="received",
    )
    assert initiator.decrypt_ack(
        ack, message_grant_jti=message_jti, client_message_id=message_id
    )["status"] == "received"


def test_v2_noise_rejects_message_grant_substitution() -> None:
    manager = PeerDeviceKeyManager(MemorySecrets())
    left = manager.get_or_create(str(uuid4()), PeerProtocol.MESSAGER_V2)
    right = manager.get_or_create(str(uuid4()), PeerProtocol.MESSAGER_V2)
    left_endpoint, right_endpoint = _endpoint(left, str(uuid4())), _endpoint(right, str(uuid4()))
    session_id, purpose_id = str(uuid4()), "conversation:test"
    left_session = _session(left_endpoint, right_endpoint, session_id, purpose_id)
    right_session = _session(right_endpoint, left_endpoint, session_id, purpose_id)
    handshake_id, handshake_jti = str(uuid4()), str(uuid4())
    initiator, first = V2InitiatorExchange.begin(
        keys=left, session=left_session, handshake_id=handshake_id, handshake_grant_jti=handshake_jti
    )
    responder, second = V2ResponderExchange.accept(
        keys=right, session=right_session, handshake_id=handshake_id,
        handshake_grant_jti=handshake_jti, connection_id=b64url_encode(b"d" * 32), request=first,
    )
    initiator.finish(second)
    ciphertext = initiator.encrypt_text(
        message_grant_jti=str(uuid4()), client_message_id=str(uuid4()),
        sender_user_id=left_endpoint.user_id, recipient_user_id=right_endpoint.user_id, body="secret",
    )
    with pytest.raises(MessagerV2NoiseError, match="binding"):
        responder.decrypt_text(ciphertext, message_grant_jti=str(uuid4()))
