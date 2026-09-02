"""Frozen record and Noise codec for AI2Apps Peer Direct QUIC v1."""

from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import Any
from uuid import UUID

import rfc8785
from cryptography.exceptions import InvalidTag
from noise.connection import Keypair, NoiseConnection
from noise.exceptions import NoiseHandshakeError, NoiseInvalidMessage

from .identity import PeerDeviceKeys, b64url_decode
from .session import PeerSession

ALPN = "ai2apps-peer-direct-v1"
NOISE_PROTOCOL = b"Noise_IK_25519_ChaChaPoly_SHA256"
PROLOGUE_DOMAIN = b"ai2apps-peer-direct-v1\0"
MAGIC = b"A2PQ"
VERSION = 1
HEADER_SIZE = 12
MAX_RECORD_PAYLOAD = 1_048_576


class DirectRecordType(IntEnum):
    CLIENT_HELLO = 0x01
    SERVER_HELLO = 0x02
    REQUEST_HEAD = 0x10
    REQUEST_BODY = 0x11
    REQUEST_END = 0x12
    RESPONSE_HEAD = 0x20
    RESPONSE_BODY = 0x21
    RESPONSE_END = 0x22
    ERROR = 0x7F


class PeerDirectError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class DirectRecord:
    record_type: DirectRecordType
    header: bytes
    payload: bytes


def canonical_json(value: Mapping[str, Any]) -> bytes:
    try:
        return rfc8785.dumps(dict(value))
    except (TypeError, ValueError) as error:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct JSON is not canonicalizable.") from error


def decode_object(value: bytes, expected_fields: set[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct JSON is invalid.") from error
    if not isinstance(parsed, dict) or set(parsed) != expected_fields or canonical_json(parsed) != value:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct JSON fields or canonical encoding are invalid.")
    return parsed


def record_header(record_type: DirectRecordType, payload_length: int) -> bytes:
    if isinstance(payload_length, bool) or not 0 <= payload_length <= MAX_RECORD_PAYLOAD:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record length is invalid.")
    return struct.pack("!4sBBHI", MAGIC, VERSION, int(record_type), 0, payload_length)


def plain_record(record_type: DirectRecordType, payload: bytes) -> bytes:
    return record_header(record_type, len(payload)) + payload


def parse_record(value: bytes) -> DirectRecord:
    if len(value) < HEADER_SIZE:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record is truncated.")
    header = value[:HEADER_SIZE]
    magic, version, raw_type, flags, size = struct.unpack("!4sBBHI", header)
    if magic != MAGIC or version != VERSION or flags != 0:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record header is invalid.")
    try:
        record_type = DirectRecordType(raw_type)
    except ValueError as error:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record type is invalid.") from error
    if size > MAX_RECORD_PAYLOAD or len(value) != HEADER_SIZE + size:
        raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record length does not match its payload.")
    return DirectRecord(record_type, header, value[HEADER_SIZE:])


def _uuid(value: Any, name: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError, AttributeError) as error:
        raise PeerDirectError("DIRECT_GRANT_REJECTED", f"{name} is invalid.") from error
    if str(parsed) != value:
        raise PeerDirectError("DIRECT_GRANT_REJECTED", f"{name} is not canonical.")
    return value


def binding_from_claims(session: PeerSession, claims: Mapping[str, Any]) -> dict[str, Any]:
    expected = {
        "session_id": session.session_id,
        "protocol": session.protocol.value,
        "purpose_id": session.purpose_id,
        "policy_version": session.transport_policy.policy_version,
    }
    if any(claims.get(name) != value for name, value in expected.items()):
        raise PeerDirectError("DIRECT_GRANT_REJECTED", "Direct Grant does not match the Session.")
    if "direct_quic" not in claims.get("allowed_transports", ()):
        raise PeerDirectError("DIRECT_GRANT_REJECTED", "Direct QUIC is not allowed by the Grant.")
    return {
        "grantJti": _uuid(claims.get("jti"), "Grant JTI"),
        "holderDeviceId": _uuid(claims.get("holder_device_id"), "Holder Device ID"),
        "initiatorAccessEpoch": claims.get("initiator_access_epoch"),
        "initiatorKeyEpoch": claims.get("initiator_key_epoch"),
        "policyVersion": claims.get("policy_version"),
        "protocol": claims.get("protocol"),
        "purposeId": claims.get("purpose_id"),
        "recipientAccessEpoch": claims.get("recipient_access_epoch"),
        "recipientKeyEpoch": claims.get("recipient_key_epoch"),
        "sessionId": claims.get("session_id"),
    }


def prologue(session: PeerSession, claims: Mapping[str, Any]) -> bytes:
    return PROLOGUE_DOMAIN + canonical_json(binding_from_claims(session, claims))


def _noise(*, initiator: bool, keys: PeerDeviceKeys, session: PeerSession,
           claims: Mapping[str, Any]) -> NoiseConnection:
    noise = NoiseConnection.from_name(NOISE_PROTOCOL)
    noise.set_as_initiator() if initiator else noise.set_as_responder()
    noise.set_prologue(prologue(session, claims))
    noise.set_keypair_from_private_bytes(Keypair.STATIC, keys.static_dh_private.private_bytes_raw())
    return noise


def _hello_binding(session: PeerSession, claims: Mapping[str, Any]) -> dict[str, Any]:
    return binding_from_claims(session, claims) | {"protocolVersion": 1}


@dataclass(slots=True)
class DirectNoiseState:
    noise: NoiseConnection

    def encrypt_record(self, record_type: DirectRecordType, plaintext: bytes) -> bytes:
        if record_type in {DirectRecordType.CLIENT_HELLO, DirectRecordType.SERVER_HELLO}:
            raise PeerDirectError("DIRECT_FRAME_REJECTED", "Hello Records are not Transport Messages.")
        header = record_header(record_type, len(plaintext) + 16)
        try:
            ciphertext = self.noise.noise_protocol.cipher_state_encrypt.encrypt_with_ad(header, plaintext)
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct Record encryption failed.") from error
        return header + bytes(ciphertext)

    def decrypt_record(self, value: bytes, expected_type: DirectRecordType) -> bytes:
        record = parse_record(value)
        if record.record_type is not expected_type:
            raise PeerDirectError("DIRECT_FRAME_REJECTED", "Direct Record order is invalid.")
        try:
            return bytes(self.noise.noise_protocol.cipher_state_decrypt.decrypt_with_ad(record.header, record.payload))
        except (InvalidTag, NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct Record authentication failed.") from error


@dataclass(slots=True)
class DirectInitiatorHandshake:
    noise: NoiseConnection
    session: PeerSession
    claims: Mapping[str, Any]

    @classmethod
    def begin(cls, *, keys: PeerDeviceKeys, session: PeerSession,
              claims: Mapping[str, Any]) -> tuple[DirectInitiatorHandshake, bytes]:
        noise = _noise(initiator=True, keys=keys, session=session, claims=claims)
        try:
            noise.set_keypair_from_public_bytes(
                Keypair.REMOTE_STATIC,
                b64url_decode(session.peer_endpoint.static_dh_public_key, size=32),
            )
            noise.start_handshake()
            message = bytes(noise.write_message(canonical_json(_hello_binding(session, claims))))
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct initiator handshake failed.") from error
        return cls(noise, session, claims), message

    def finish(self, message: bytes, connection_id: str) -> DirectNoiseState:
        try:
            payload = bytes(self.noise.read_message(message))
        except (NoiseHandshakeError, NoiseInvalidMessage) as error:
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct responder handshake failed.") from error
        expected = _hello_binding(self.session, self.claims) | {"connectionId": connection_id}
        if decode_object(payload, set(expected)) != expected:
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct responder binding is invalid.")
        b64url_decode(connection_id, size=32)
        return DirectNoiseState(self.noise)


@dataclass(slots=True)
class DirectResponderHandshake:
    noise: NoiseConnection

    @classmethod
    def accept(cls, *, keys: PeerDeviceKeys, session: PeerSession, claims: Mapping[str, Any],
               message: bytes, connection_id: str) -> tuple[DirectNoiseState, bytes]:
        noise = _noise(initiator=False, keys=keys, session=session, claims=claims)
        expected = _hello_binding(session, claims)
        try:
            noise.start_handshake()
            payload = bytes(noise.read_message(message))
            learned = bytes(noise.noise_protocol.handshake_state.rs.public_bytes)
            if learned != b64url_decode(session.peer_endpoint.static_dh_public_key, size=32):
                raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct initiator Static Key is invalid.")
            if decode_object(payload, set(expected)) != expected:
                raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct initiator binding is invalid.")
            response = bytes(noise.write_message(canonical_json(expected | {"connectionId": connection_id})))
            b64url_decode(connection_id, size=32)
        except (ValueError, NoiseHandshakeError, NoiseInvalidMessage) as error:
            if isinstance(error, PeerDirectError):
                raise
            raise PeerDirectError("DIRECT_NOISE_REJECTED", "Direct responder handshake failed.") from error
        return DirectNoiseState(noise), response
