import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ai2apps.peer.direct_v1 import (
    DirectInitiatorHandshake,
    DirectRecordType,
    DirectResponderHandshake,
    PeerDirectError,
    parse_record,
    plain_record,
    prologue,
    record_header,
)
from ai2apps.peer.identity import PeerDeviceKeys, PeerProtocol, b64url_encode
from ai2apps.peer.session import PeerEndpoint, PeerSession, PeerTransportPolicy
from ai2apps.peer.transports.base import PeerTransportResponse
from ai2apps.peer.transports.direct_quic import (
    DIRECT_IDLE_TIMEOUT_SECONDS,
    DirectAuthorization,
    DirectQuicServer,
    DirectQuicTransport,
    _client_configuration,
    _server_configuration,
)


def endpoint(keys):
    return PeerEndpoint(
        user_id=str(uuid4()), device_id=keys.device_id, installation_id=str(uuid4()),
        access_epoch=2, key_id=str(uuid4()), key_epoch=3,
        identity_signing_public_key=keys.identity_public,
        static_dh_public_key=keys.static_dh_public,
    )


def exchange():
    protocol = PeerProtocol.MESSAGER_V2
    first_keys = PeerDeviceKeys(str(uuid4()), protocol, Ed25519PrivateKey.generate(), X25519PrivateKey.generate())
    second_keys = PeerDeviceKeys(str(uuid4()), protocol, Ed25519PrivateKey.generate(), X25519PrivateKey.generate())
    first, second = endpoint(first_keys), endpoint(second_keys)
    session_id, purpose_id, jti = str(uuid4()), "conversation-1", str(uuid4())
    initiator_session = PeerSession(
        session_id, protocol, "conversation", purpose_id, "active",
        datetime.now(UTC) + timedelta(minutes=5),
        PeerTransportPolicy(("direct_quic", "relay_https"), 1024 * 1024, 4, 1, "offline_system_message"),
        first, second,
    )
    responder_session = PeerSession(
        session_id, protocol, "conversation", purpose_id, "active", initiator_session.expires_at,
        initiator_session.transport_policy, second, first,
    )
    claims = {
        "jti": jti, "holder_device_id": first.device_id, "session_id": session_id,
        "protocol": protocol.value, "purpose_id": purpose_id, "policy_version": 1,
        "initiator_access_epoch": first.access_epoch, "initiator_key_epoch": first.key_epoch,
        "recipient_access_epoch": second.access_epoch, "recipient_key_epoch": second.key_epoch,
        "allowed_transports": ["direct_quic", "relay_https"],
    }
    return first_keys, second_keys, initiator_session, responder_session, claims


def test_record_header_matches_cloud_cross_implementation_fixture():
    assert record_header(DirectRecordType.CLIENT_HELLO, 5).hex() == "413250510101000000000005"
    record = parse_record(plain_record(DirectRecordType.CLIENT_HELLO, b"hello"))
    assert record.record_type is DirectRecordType.CLIENT_HELLO
    assert record.payload == b"hello"
    for value in (
        bytes.fromhex("423250510101000000000005") + b"hello",
        bytes.fromhex("413250510201000000000005") + b"hello",
        bytes.fromhex("413250510101000100000005") + b"hello",
        bytes.fromhex("413250510155000000000005") + b"hello",
    ):
        with pytest.raises(PeerDirectError):
            parse_record(value)


def test_direct_quic_idle_timeout_covers_silent_compute_execution_window():
    assert DIRECT_IDLE_TIMEOUT_SECONDS == 10 * 60
    assert _client_configuration().idle_timeout == DIRECT_IDLE_TIMEOUT_SECONDS
    assert _server_configuration().idle_timeout == DIRECT_IDLE_TIMEOUT_SECONDS


def test_prologue_is_domain_separated_and_jcs_canonical():
    _first, _second, session, _responder, claims = exchange()
    value = prologue(session, claims)
    assert value.startswith(b"ai2apps-peer-direct-v1\0{")
    parsed = json.loads(value.split(b"\0", 1)[1])
    assert list(parsed) == sorted(parsed)
    assert parsed["grantJti"] == claims["jti"]


def test_noise_ik_binds_static_keys_and_authenticates_record_header_as_ad():
    first, second, initiator_session, responder_session, claims = exchange()
    initiator, first_message = DirectInitiatorHandshake.begin(
        keys=first, session=initiator_session, claims=claims,
    )
    connection_id = b64url_encode(b"c" * 32)
    responder, second_message = DirectResponderHandshake.accept(
        keys=second, session=responder_session, claims=claims,
        message=first_message, connection_id=connection_id,
    )
    client = initiator.finish(second_message, connection_id)
    encoded = client.encrypt_record(DirectRecordType.REQUEST_BODY, b"secret")
    assert responder.decrypt_record(encoded, DirectRecordType.REQUEST_BODY) == b"secret"
    tampered = bytearray(encoded)
    tampered[5] = DirectRecordType.REQUEST_END
    with pytest.raises(PeerDirectError, match="authentication"):
        responder.decrypt_record(bytes(tampered), DirectRecordType.REQUEST_END)


def test_noise_rejects_wrong_registered_peer_static_key():
    first, second, initiator_session, responder_session, claims = exchange()
    attacker = PeerDeviceKeys(str(uuid4()), PeerProtocol.MESSAGER_V2,
                              Ed25519PrivateKey.generate(), X25519PrivateKey.generate())
    initiator, first_message = DirectInitiatorHandshake.begin(
        keys=attacker,
        session=PeerSession(
            initiator_session.session_id, initiator_session.protocol, initiator_session.purpose_type,
            initiator_session.purpose_id, initiator_session.status, initiator_session.expires_at,
            initiator_session.transport_policy,
            PeerEndpoint(
                initiator_session.self_endpoint.user_id, attacker.device_id,
                initiator_session.self_endpoint.installation_id, initiator_session.self_endpoint.access_epoch,
                initiator_session.self_endpoint.key_id, initiator_session.self_endpoint.key_epoch,
                attacker.identity_public, attacker.static_dh_public,
            ),
            initiator_session.peer_endpoint,
        ),
        claims=claims,
    )
    with pytest.raises(PeerDirectError, match="Static Key"):
        DirectResponderHandshake.accept(
            keys=second, session=responder_session, claims=claims,
            message=first_message, connection_id=b64url_encode(b"c" * 32),
        )


@pytest.mark.asyncio
async def test_real_quic_v1_stream_uses_frozen_alpn_noise_and_record_codec():
    first, second, initiator_session, responder_session, claims = exchange()

    async def authorize(grant, session_id):
        assert grant == "verified-grant"
        assert session_id == responder_session.session_id
        return DirectAuthorization(responder_session, claims, second, grant)

    async def handler(authorization, path, payload):
        assert authorization.session is responder_session
        assert path == "/v1/messager/peer/v2/messages"
        assert payload == b'{"hello":"direct"}'
        return PeerTransportResponse(200, {"content-type": "application/json"}, b'{"accepted":true}')

    server = DirectQuicServer(authorize=authorize, handler=handler)
    port = await server.start(host="127.0.0.1")
    try:
        transport = DirectQuicTransport(
            address="127.0.0.1", port=port, session=initiator_session,
            keys=first, grant="verified-grant", claims=claims,
        )
        response = await transport.post(
            path="/v1/messager/peer/v2/messages", grant="verified-grant",
            payload=b'{"hello":"direct"}', max_response_bytes=1024,
        )
        assert response.status_code == 200
        assert response.body == b'{"accepted":true}'
    finally:
        await server.close()
