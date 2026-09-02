"""Noise IK primitives for one authenticated Local Messager exchange."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from noise.connection import Keypair, NoiseConnection
from noise.exceptions import NoiseHandshakeError, NoiseInvalidMessage

from .identity import MessagerDeviceKeys, b64url_decode

NOISE_PROTOCOL = b"Noise_IK_25519_ChaChaPoly_SHA256"
PROLOGUE_DOMAIN = b"ai2apps-messager-peer-v1\0"
MAX_TEXT_BYTES = 16_384


class MessagerNoiseError(ValueError):
    """A Noise handshake or encrypted application frame was invalid."""


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _decode_object(value: bytes, *, expected_keys: set[str]) -> dict[str, Any]:
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MessagerNoiseError("Encrypted Messager payload is invalid") from error
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        raise MessagerNoiseError("Encrypted Messager payload fields are invalid")
    return payload


def _prologue(handshake_id: str) -> bytes:
    try:
        parsed = UUID(handshake_id)
    except ValueError as error:
        raise MessagerNoiseError("Handshake ID is invalid") from error
    if str(parsed) != handshake_id:
        raise MessagerNoiseError("Handshake ID is not canonical")
    return PROLOGUE_DOMAIN + parsed.bytes


def _uuid_text(value: str, name: str) -> str:
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as error:
        raise MessagerNoiseError(f"{name} is invalid") from error
    if str(parsed) != value:
        raise MessagerNoiseError(f"{name} is not canonical")
    return value


def _connection(*, initiator: bool, keys: MessagerDeviceKeys, handshake_id: str) -> NoiseConnection:
    noise = NoiseConnection.from_name(NOISE_PROTOCOL)
    noise.set_as_initiator() if initiator else noise.set_as_responder()
    noise.set_prologue(_prologue(handshake_id))
    noise.set_keypair_from_private_bytes(
        Keypair.STATIC,
        keys.static_dh_private.private_bytes_raw(),
    )
    return noise


@dataclass(slots=True)
class InitiatorExchange:
    noise: NoiseConnection
    handshake_id: str
    assertion_jti: str

    @classmethod
    def begin(
        cls,
        *,
        keys: MessagerDeviceKeys,
        peer_static_public: str,
        handshake_id: str,
        assertion_jti: str,
    ) -> tuple[InitiatorExchange, bytes]:
        noise = _connection(initiator=True, keys=keys, handshake_id=handshake_id)
        try:
            noise.set_keypair_from_public_bytes(
                Keypair.REMOTE_STATIC,
                b64url_decode(peer_static_public, size=32),
            )
            noise.start_handshake()
            message = bytes(
                noise.write_message(
                    _canonical_json(
                        {
                            "handshakeId": handshake_id,
                            "jti": assertion_jti,
                            "version": 1,
                        }
                    )
                )
            )
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerNoiseError("Noise IK initiator handshake failed") from error
        return cls(noise, handshake_id, assertion_jti), message

    def finish(self, response: bytes) -> bytes:
        try:
            payload = _decode_object(
                bytes(self.noise.read_message(response)),
                expected_keys={"handshakeId", "jti", "version"},
            )
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerNoiseError("Noise IK responder handshake failed") from error
        if payload != {
            "handshakeId": self.handshake_id,
            "jti": self.assertion_jti,
            "version": 1,
        }:
            raise MessagerNoiseError("Noise IK responder binding is invalid")
        return self.noise.get_handshake_hash()

    def encrypt_text(
        self, *, client_message_id: str, sender_user_id: str, recipient_user_id: str, body: str
    ) -> bytes:
        encoded = body.encode("utf-8")
        if not body or len(body) > 4000 or len(encoded) > MAX_TEXT_BYTES:
            raise MessagerNoiseError("Messager text size is invalid")
        _uuid_text(client_message_id, "Client message ID")
        _uuid_text(sender_user_id, "Sender user ID")
        _uuid_text(recipient_user_id, "Recipient user ID")
        frame = _canonical_json(
            {
                "body": body,
                "clientMessageId": client_message_id,
                "recipientUserId": recipient_user_id,
                "senderUserId": sender_user_id,
                "type": "text",
                "version": 1,
            }
        )
        try:
            return self.noise.encrypt(frame)
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerNoiseError("Noise encryption failed") from error

    def decrypt_ack(self, ciphertext: bytes) -> dict[str, Any]:
        try:
            cleartext = self.noise.decrypt(ciphertext)
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerNoiseError("Noise acknowledgement authentication failed") from error
        return _decode_object(
            cleartext,
            expected_keys={"clientMessageId", "receivedAt", "status", "version"},
        )


@dataclass(slots=True)
class ResponderExchange:
    noise: NoiseConnection
    handshake_id: str
    assertion_jti: str

    @classmethod
    def accept(
        cls,
        *,
        keys: MessagerDeviceKeys,
        asserted_initiator_static_public: str,
        handshake_id: str,
        assertion_jti: str,
        request: bytes,
    ) -> tuple[ResponderExchange, bytes]:
        noise = _connection(initiator=False, keys=keys, handshake_id=handshake_id)
        try:
            noise.start_handshake()
            payload = _decode_object(
                bytes(noise.read_message(request)),
                expected_keys={"handshakeId", "jti", "version"},
            )
            learned_static = bytes(noise.noise_protocol.handshake_state.rs.public_bytes)
            asserted_static = b64url_decode(asserted_initiator_static_public, size=32)
            if learned_static != asserted_static:
                raise MessagerNoiseError("Noise initiator static key binding is invalid")
            expected = {
                "handshakeId": handshake_id,
                "jti": assertion_jti,
                "version": 1,
            }
            if payload != expected:
                raise MessagerNoiseError("Noise initiator assertion binding is invalid")
            response = bytes(noise.write_message(_canonical_json(expected)))
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            if isinstance(error, MessagerNoiseError):
                raise
            raise MessagerNoiseError("Noise IK responder handshake failed") from error
        return cls(noise, handshake_id, assertion_jti), response

    def decrypt_text(self, ciphertext: bytes) -> dict[str, Any]:
        try:
            cleartext = self.noise.decrypt(ciphertext)
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise MessagerNoiseError("Noise message authentication failed") from error
        payload = _decode_object(
            cleartext,
            expected_keys={
                "body", "clientMessageId", "recipientUserId", "senderUserId",
                "type", "version",
            },
        )
        if payload["type"] != "text" or payload["version"] != 1:
            raise MessagerNoiseError("Noise message type is invalid")
        _uuid_text(payload["clientMessageId"], "Client message ID")
        _uuid_text(payload["senderUserId"], "Sender user ID")
        _uuid_text(payload["recipientUserId"], "Recipient user ID")
        if not isinstance(payload["body"], str) or not payload["body"] or len(payload["body"]) > 4000 or len(payload["body"].encode("utf-8")) > MAX_TEXT_BYTES:
            raise MessagerNoiseError("Noise message text size is invalid")
        return payload

    def encrypt_ack(
        self, *, client_message_id: str, received_at: str, status: str = "received"
    ) -> bytes:
        if status not in {"received", "duplicate"}:
            raise MessagerNoiseError("Acknowledgement status is invalid")
        return self.noise.encrypt(
            _canonical_json(
                {
                    "clientMessageId": client_message_id,
                    "receivedAt": received_at,
                    "status": status,
                    "version": 1,
                }
            )
        )


def handshake_fingerprint(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
