"""Strict Local projection of Cloud Peer Sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Mapping
from urllib.parse import urlparse
from uuid import UUID

from ai2apps.core import parse_utc

from .identity import PEER_KEY_SUITE, PeerProtocol, b64url_decode

PeerSessionStatus = Literal["pending", "active", "closed", "expired", "revoked"]
PeerTransport = Literal["direct_quic", "relay_https"]


def _uuid(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID")
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError(f"{field} must be canonical")
    return value


@dataclass(frozen=True, slots=True)
class PeerEndpoint:
    user_id: str
    device_id: str
    installation_id: str
    access_epoch: int
    key_id: str
    key_epoch: int
    identity_signing_public_key: str
    static_dh_public_key: str
    relay_origin: str | None = None

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "PeerEndpoint":
        if value.get("suite") != PEER_KEY_SUITE:
            raise ValueError("Peer endpoint key suite is invalid")
        access_epoch = value.get("accessEpoch")
        key_epoch = value.get("keyEpoch")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in (access_epoch, key_epoch)):
            raise ValueError("Peer endpoint epoch is invalid")
        identity_key = value.get("identitySigningPublicKey")
        static_key = value.get("staticDhPublicKey")
        b64url_decode(identity_key, size=32)
        b64url_decode(static_key, size=32)
        relay_origin = value.get("relayOrigin")
        if relay_origin is not None:
            parsed = urlparse(relay_origin)
            if (
                not isinstance(relay_origin, str)
                or parsed.scheme != "https"
                or parsed.hostname is None
                or not parsed.hostname.startswith("device-")
                or parsed.username
                or parsed.password
                or parsed.port is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Peer relay origin is invalid")
        return cls(
            user_id=_uuid(value.get("userId"), "userId"),
            device_id=_uuid(value.get("deviceId"), "deviceId"),
            installation_id=_uuid(value.get("installationId"), "installationId"),
            access_epoch=access_epoch,
            key_id=_uuid(value.get("keyId"), "keyId"),
            key_epoch=key_epoch,
            identity_signing_public_key=identity_key,
            static_dh_public_key=static_key,
            relay_origin=None if relay_origin is None else relay_origin.rstrip("/"),
        )


@dataclass(frozen=True, slots=True)
class PeerTransportPolicy:
    allowed_transports: tuple[PeerTransport, ...]
    max_bytes: int
    max_streams: int
    policy_version: int
    fallback_policy: Literal["offline_system_message", "rematch_or_fail"]

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "PeerTransportPolicy":
        transports = value.get("allowedTransports")
        if (
            not isinstance(transports, list)
            or not transports
            or len(transports) != len(set(transports))
            or any(item not in {"direct_quic", "relay_https"} for item in transports)
        ):
            raise ValueError("Peer transport policy is invalid")
        max_bytes_text = value.get("maxBytes")
        if not isinstance(max_bytes_text, str) or not max_bytes_text.isdigit() or max_bytes_text.startswith("0"):
            raise ValueError("Peer maxBytes is invalid")
        max_streams = value.get("maxStreams")
        policy_version = value.get("policyVersion")
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in (max_streams, policy_version)):
            raise ValueError("Peer transport limit is invalid")
        fallback = value.get("fallbackPolicy")
        if fallback not in {"offline_system_message", "rematch_or_fail"}:
            raise ValueError("Peer fallback policy is invalid")
        return cls(tuple(transports), int(max_bytes_text), max_streams, policy_version, fallback)


@dataclass(frozen=True, slots=True)
class PeerSession:
    session_id: str
    protocol: PeerProtocol
    purpose_type: str
    purpose_id: str
    status: PeerSessionStatus
    expires_at: datetime
    transport_policy: PeerTransportPolicy
    self_endpoint: PeerEndpoint
    peer_endpoint: PeerEndpoint
    grant: str | None = None

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "PeerSession":
        protocol = PeerProtocol(value.get("protocol"))
        purpose_type = value.get("purposeType")
        purpose_id = value.get("purposeId")
        status = value.get("status")
        if purpose_type != protocol.purpose_type or not isinstance(purpose_id, str) or not purpose_id:
            raise ValueError("Peer Session purpose is invalid")
        if status not in {"pending", "active", "closed", "expired", "revoked"}:
            raise ValueError("Peer Session status is invalid")
        grant = value.get("grant")
        if grant is not None and (not isinstance(grant, str) or not 1 <= len(grant) <= 8192):
            raise ValueError("Peer Session grant is invalid")
        return cls(
            session_id=_uuid(value.get("sessionId"), "sessionId"),
            protocol=protocol,
            purpose_type=purpose_type,
            purpose_id=purpose_id,
            status=status,
            expires_at=parse_utc(value.get("expiresAt")),
            transport_policy=PeerTransportPolicy.parse(value.get("transportPolicy", {})),
            self_endpoint=PeerEndpoint.parse(value.get("self", {})),
            peer_endpoint=PeerEndpoint.parse(value.get("peer", {})),
            grant=grant,
        )
