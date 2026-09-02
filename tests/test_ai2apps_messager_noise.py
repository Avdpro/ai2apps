from __future__ import annotations

import uuid

import pytest
from test_ai2apps_messager_identity import MemorySecrets

from ai2apps.messager import (
    InitiatorExchange,
    MessagerDeviceKeyManager,
    MessagerNoiseError,
    ResponderExchange,
)


def test_noise_ik_round_trip_and_static_binding() -> None:
    manager = MessagerDeviceKeyManager(MemorySecrets())
    initiator_keys = manager.get_or_create("11111111-1111-4111-8111-111111111111")
    responder_keys = manager.get_or_create("22222222-2222-4222-8222-222222222222")
    handshake_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    initiator, first = InitiatorExchange.begin(
        keys=initiator_keys,
        peer_static_public=responder_keys.static_dh_public,
        handshake_id=handshake_id,
        assertion_jti=jti,
    )
    responder, second = ResponderExchange.accept(
        keys=responder_keys,
        asserted_initiator_static_public=initiator_keys.static_dh_public,
        handshake_id=handshake_id,
        assertion_jti=jti,
        request=first,
    )
    assert initiator.finish(second) == responder.noise.get_handshake_hash()
    message_id = str(uuid.uuid4())
    encrypted = initiator.encrypt_text(
        client_message_id=message_id,
        sender_user_id="33333333-3333-4333-8333-333333333333",
        recipient_user_id="44444444-4444-4444-8444-444444444444",
        body="private hello",
    )
    clear = responder.decrypt_text(encrypted)
    assert clear["body"] == "private hello"
    ack = responder.encrypt_ack(
        client_message_id=message_id, received_at="2026-08-23T12:00:00Z"
    )
    assert initiator.decrypt_ack(ack)["status"] == "received"


def test_noise_ik_rejects_asserted_static_key_mismatch() -> None:
    manager = MessagerDeviceKeyManager(MemorySecrets())
    initiator_keys = manager.get_or_create("11111111-1111-4111-8111-111111111111")
    responder_keys = manager.get_or_create("22222222-2222-4222-8222-222222222222")
    attacker_keys = manager.get_or_create("33333333-3333-4333-8333-333333333333")
    handshake_id = str(uuid.uuid4())
    jti = str(uuid.uuid4())
    _, first = InitiatorExchange.begin(
        keys=initiator_keys,
        peer_static_public=responder_keys.static_dh_public,
        handshake_id=handshake_id,
        assertion_jti=jti,
    )
    with pytest.raises(MessagerNoiseError, match="static key binding"):
        ResponderExchange.accept(
            keys=responder_keys,
            asserted_initiator_static_public=attacker_keys.static_dh_public,
            handshake_id=handshake_id,
            assertion_jti=jti,
            request=first,
        )
