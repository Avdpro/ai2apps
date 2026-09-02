"""Frozen Noise IK codec for one Messager Peer v2 logical message."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from noise.connection import Keypair, NoiseConnection
from noise.exceptions import NoiseHandshakeError, NoiseInvalidMessage

from ai2apps.peer.identity import PeerDeviceKeys, b64url_decode
from ai2apps.peer.session import PeerSession

NOISE_PROTOCOL = b"Noise_IK_25519_ChaChaPoly_SHA256"
PROLOGUE_DOMAIN = b"ai2apps-messager-peer-v2\0"
MAX_TEXT_BYTES = 16_384


class MessagerV2NoiseError(ValueError):
    pass


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _object(value: bytes, fields: set[str]) -> dict[str, Any]:
    try:
        result = json.loads(value.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MessagerV2NoiseError("Encrypted Messager v2 payload is invalid") from error
    if not isinstance(result, dict) or set(result) != fields:
        raise MessagerV2NoiseError("Encrypted Messager v2 payload fields are invalid")
    return result


def _uuid(value: Any, field: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, TypeError, AttributeError) as error:
        raise MessagerV2NoiseError(f"{field} is invalid") from error
    if str(parsed) != value:
        raise MessagerV2NoiseError(f"{field} is not canonical")
    return value


def _prologue(session: PeerSession, handshake_id: str, grant_jti: str) -> bytes:
    _uuid(handshake_id, "Handshake ID")
    _uuid(grant_jti, "Grant JTI")
    # Endpoint direction is frozen by the Cloud Session, not by the local holder view.
    if session.self_endpoint.user_id < session.peer_endpoint.user_id:
        first, second = session.self_endpoint, session.peer_endpoint
    else:
        first, second = session.peer_endpoint, session.self_endpoint
    return PROLOGUE_DOMAIN + _canonical_json({
        "handshakeGrantJti": grant_jti,
        "handshakeId": handshake_id,
        "initiatorAccessEpoch": first.access_epoch,
        "initiatorKeyEpoch": first.key_epoch,
        "policyVersion": session.transport_policy.policy_version,
        "purposeId": session.purpose_id,
        "recipientAccessEpoch": second.access_epoch,
        "recipientKeyEpoch": second.key_epoch,
        "sessionId": session.session_id,
    })


def _connection(*, initiator: bool, keys: PeerDeviceKeys, session: PeerSession,
                handshake_id: str, grant_jti: str) -> NoiseConnection:
    noise = NoiseConnection.from_name(NOISE_PROTOCOL)
    noise.set_as_initiator() if initiator else noise.set_as_responder()
    noise.set_prologue(_prologue(session, handshake_id, grant_jti))
    noise.set_keypair_from_private_bytes(Keypair.STATIC, keys.static_dh_private.private_bytes_raw())
    return noise


@dataclass(slots=True)
class V2InitiatorExchange:
    noise: NoiseConnection
    session_id: str
    handshake_id: str
    handshake_grant_jti: str
    connection_id: str | None = None

    @classmethod
    def begin(cls, *, keys: PeerDeviceKeys, session: PeerSession, handshake_id: str,
              handshake_grant_jti: str) -> tuple[V2InitiatorExchange, bytes]:
        noise = _connection(initiator=True, keys=keys, session=session,
                            handshake_id=handshake_id, grant_jti=handshake_grant_jti)
        try:
            noise.set_keypair_from_public_bytes(
                Keypair.REMOTE_STATIC, b64url_decode(session.peer_endpoint.static_dh_public_key, size=32)
            )
            noise.start_handshake()
            first = bytes(noise.write_message(_canonical_json({
                "handshakeGrantJti": handshake_grant_jti,
                "handshakeId": handshake_id,
                "sessionId": session.session_id,
                "version": 2,
            })))
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerV2NoiseError("Messager v2 initiator handshake failed") from error
        return cls(noise, session.session_id, handshake_id, handshake_grant_jti), first

    def finish(self, response: bytes) -> str:
        try:
            payload = _object(bytes(self.noise.read_message(response)), {
                "connectionId", "handshakeGrantJti", "handshakeId", "sessionId", "version"
            })
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerV2NoiseError("Messager v2 responder handshake failed") from error
        expected = {"handshakeGrantJti": self.handshake_grant_jti,
                    "handshakeId": self.handshake_id, "sessionId": self.session_id, "version": 2}
        if any(payload.get(name) != value for name, value in expected.items()):
            raise MessagerV2NoiseError("Messager v2 responder binding is invalid")
        connection_id = payload.get("connectionId")
        if not isinstance(connection_id, str) or len(connection_id) != 43:
            raise MessagerV2NoiseError("Messager v2 connection ID is invalid")
        b64url_decode(connection_id, size=32)
        self.connection_id = connection_id
        return connection_id

    def encrypt_text(self, *, message_grant_jti: str, client_message_id: str,
                     sender_user_id: str, recipient_user_id: str, body: str) -> bytes:
        if self.connection_id is None:
            raise MessagerV2NoiseError("Messager v2 handshake is incomplete")
        for value, field in ((message_grant_jti, "Grant JTI"), (client_message_id, "Client message ID"),
                             (sender_user_id, "Sender user ID"), (recipient_user_id, "Recipient user ID")):
            _uuid(value, field)
        if not isinstance(body, str) or not body or len(body) > 4000 or len(body.encode()) > MAX_TEXT_BYTES:
            raise MessagerV2NoiseError("Messager v2 text size is invalid")
        return self.noise.encrypt(_canonical_json({
            "body": body, "clientMessageId": client_message_id,
            "connectionId": self.connection_id, "messageGrantJti": message_grant_jti,
            "recipientUserId": recipient_user_id, "senderUserId": sender_user_id,
            "sequence": "0", "sessionId": self.session_id, "type": "text", "version": 2,
        }))

    def decrypt_ack(self, ciphertext: bytes, *, message_grant_jti: str,
                    client_message_id: str) -> dict[str, Any]:
        try:
            payload = _object(self.noise.decrypt(ciphertext), {
                "clientMessageId", "connectionId", "messageGrantJti", "receivedAt",
                "sequence", "sessionId", "status", "version",
            })
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerV2NoiseError("Messager v2 acknowledgement authentication failed") from error
        expected = {"clientMessageId": client_message_id, "connectionId": self.connection_id,
                    "messageGrantJti": message_grant_jti, "sequence": "0",
                    "sessionId": self.session_id, "version": 2}
        if any(payload.get(name) != value for name, value in expected.items()) or payload.get("status") not in {"received", "duplicate"}:
            raise MessagerV2NoiseError("Messager v2 acknowledgement binding is invalid")
        return payload


@dataclass(slots=True)
class V2ResponderExchange:
    noise: NoiseConnection
    session_id: str
    connection_id: str

    @classmethod
    def accept(cls, *, keys: PeerDeviceKeys, session: PeerSession, handshake_id: str,
               handshake_grant_jti: str, connection_id: str, request: bytes) -> tuple[V2ResponderExchange, bytes]:
        noise = _connection(initiator=False, keys=keys, session=session,
                            handshake_id=handshake_id, grant_jti=handshake_grant_jti)
        try:
            noise.start_handshake()
            payload = _object(bytes(noise.read_message(request)), {
                "handshakeGrantJti", "handshakeId", "sessionId", "version"
            })
            learned = bytes(noise.noise_protocol.handshake_state.rs.public_bytes)
            if learned != b64url_decode(session.peer_endpoint.static_dh_public_key, size=32):
                raise MessagerV2NoiseError("Messager v2 initiator static key binding is invalid")
            expected = {"handshakeGrantJti": handshake_grant_jti, "handshakeId": handshake_id,
                        "sessionId": session.session_id, "version": 2}
            if payload != expected:
                raise MessagerV2NoiseError("Messager v2 initiator binding is invalid")
            response = bytes(noise.write_message(_canonical_json(expected | {"connectionId": connection_id})))
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            if isinstance(error, MessagerV2NoiseError):
                raise
            raise MessagerV2NoiseError("Messager v2 responder handshake failed") from error
        return cls(noise, session.session_id, connection_id), response

    def decrypt_text(self, ciphertext: bytes, *, message_grant_jti: str) -> dict[str, Any]:
        try:
            payload = _object(self.noise.decrypt(ciphertext), {
                "body", "clientMessageId", "connectionId", "messageGrantJti",
                "recipientUserId", "senderUserId", "sequence", "sessionId", "type", "version",
            })
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerV2NoiseError("Messager v2 message authentication failed") from error
        expected = {"connectionId": self.connection_id, "messageGrantJti": message_grant_jti,
                    "sequence": "0", "sessionId": self.session_id, "type": "text", "version": 2}
        if any(payload.get(name) != value for name, value in expected.items()):
            raise MessagerV2NoiseError("Messager v2 message binding is invalid")
        for name in ("clientMessageId", "senderUserId", "recipientUserId"):
            _uuid(payload.get(name), name)
        body = payload.get("body")
        if not isinstance(body, str) or not body or len(body) > 4000 or len(body.encode()) > MAX_TEXT_BYTES:
            raise MessagerV2NoiseError("Messager v2 text size is invalid")
        return payload

    def encrypt_ack(self, *, message_grant_jti: str, client_message_id: str,
                    received_at: str, status: str) -> bytes:
        if status not in {"received", "duplicate"}:
            raise MessagerV2NoiseError("Messager v2 acknowledgement status is invalid")
        return self.noise.encrypt(_canonical_json({
            "clientMessageId": client_message_id, "connectionId": self.connection_id,
            "messageGrantJti": message_grant_jti, "receivedAt": received_at,
            "sequence": "0", "sessionId": self.session_id, "status": status, "version": 2,
        }))
