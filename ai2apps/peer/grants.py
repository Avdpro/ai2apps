"""Strict EdDSA validation for short-lived Cloud Peer Session Grants."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .identity import PeerProtocol, b64url_decode
from .session import PeerSession

_UUID_CLAIMS = {
    "sub", "jti", "session_id", "holder_user_id", "holder_device_id",
    "initiator_user_id", "initiator_device_id", "initiator_installation_id",
    "initiator_key_id", "recipient_user_id", "recipient_device_id",
    "recipient_installation_id", "recipient_key_id",
}
_INTEGER_CLAIMS = {
    "iat", "nbf", "exp", "initiator_access_epoch", "initiator_key_epoch",
    "recipient_access_epoch", "recipient_key_epoch", "max_streams", "policy_version",
}
_REQUIRED_CLAIMS = _UUID_CLAIMS | _INTEGER_CLAIMS | {
    "iss", "aud", "protocol", "protocol_version", "purpose_id", "purpose_type",
    "allowed_transports", "max_bytes",
}


class PeerGrantError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class VerifiedPeerGrant:
    header: dict[str, Any]
    claims: dict[str, Any]
    compact: str


def _decode_object(segment: str, name: str) -> dict[str, Any]:
    try:
        value = json.loads(b64url_decode(segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PeerGrantError(f"JWT {name} is invalid") from error
    if not isinstance(value, dict):
        raise PeerGrantError(f"JWT {name} must be an object")
    return value


def _uuid(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise PeerGrantError(f"{name} must be a UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise PeerGrantError(f"{name} must be a UUID") from error
    if str(parsed) != value:
        raise PeerGrantError(f"{name} must be canonical")
    return value


def verify_peer_grant(
    compact: str,
    jwks: Mapping[str, Any],
    *,
    session: PeerSession,
    holder_user_id: str,
    holder_device_id: str,
    now: int | None = None,
) -> VerifiedPeerGrant:
    parts = compact.split(".") if isinstance(compact, str) else []
    if len(parts) != 3 or not all(parts):
        raise PeerGrantError("JWT compact serialization is invalid")
    header = _decode_object(parts[0], "header")
    claims = _decode_object(parts[1], "claims")
    if set(header) != {"alg", "kid", "typ"} or header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
        raise PeerGrantError("JWT protected header is invalid")
    keys = jwks.get("keys") if isinstance(jwks, Mapping) else None
    matches = [item for item in keys or [] if isinstance(item, dict) and item.get("kid") == header.get("kid")]
    if len(matches) != 1:
        raise PeerGrantError("JWT signing key is unknown")
    jwk = matches[0]
    if set(jwk) - {"kty", "crv", "x", "alg", "kid", "use"} or any(
        jwk.get(name) != value
        for name, value in {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig"}.items()
    ):
        raise PeerGrantError("JWT signing JWK is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(b64url_decode(jwk.get("x"), size=32)).verify(
            b64url_decode(parts[2], size=64), f"{parts[0]}.{parts[1]}".encode("ascii")
        )
    except (ValueError, InvalidSignature) as error:
        raise PeerGrantError("JWT signature is invalid") from error
    if set(claims) != _REQUIRED_CLAIMS:
        raise PeerGrantError("JWT claims set is invalid")
    for name in _UUID_CLAIMS:
        _uuid(claims[name], name)
    for name in _INTEGER_CLAIMS:
        value = claims[name]
        if isinstance(value, bool) or not isinstance(value, int):
            raise PeerGrantError(f"{name} must be an integer")
        if name not in {"iat", "nbf", "exp"} and value < 1:
            raise PeerGrantError(f"{name} must be positive")
    if claims["iss"] != "ai2apps-cloud" or claims["aud"] != session.protocol.audience:
        raise PeerGrantError("JWT issuer or audience is invalid")
    if claims["protocol"] != session.protocol.value or claims["protocol_version"] != 1:
        raise PeerGrantError("JWT protocol binding is invalid")
    if claims["sub"] != claims["holder_user_id"]:
        raise PeerGrantError("JWT subject binding is invalid")
    expected_top = {
        "session_id": session.session_id,
        "purpose_type": session.purpose_type,
        "purpose_id": session.purpose_id,
        "holder_user_id": holder_user_id,
        "holder_device_id": holder_device_id,
        "allowed_transports": list(session.transport_policy.allowed_transports),
        "max_bytes": str(session.transport_policy.max_bytes),
        "max_streams": session.transport_policy.max_streams,
        "policy_version": session.transport_policy.policy_version,
    }
    if any(claims.get(name) != value for name, value in expected_top.items()):
        raise PeerGrantError("JWT Session or holder binding is invalid")
    if claims["initiator_device_id"] == session.self_endpoint.device_id:
        endpoints = (("initiator", session.self_endpoint), ("recipient", session.peer_endpoint))
    elif claims["recipient_device_id"] == session.self_endpoint.device_id:
        endpoints = (("initiator", session.peer_endpoint), ("recipient", session.self_endpoint))
    else:
        raise PeerGrantError("JWT holder endpoint is not part of the Session")
    for prefix, endpoint in endpoints:
        expected = {
            f"{prefix}_user_id": endpoint.user_id,
            f"{prefix}_device_id": endpoint.device_id,
            f"{prefix}_installation_id": endpoint.installation_id,
            f"{prefix}_access_epoch": endpoint.access_epoch,
            f"{prefix}_key_id": endpoint.key_id,
            f"{prefix}_key_epoch": endpoint.key_epoch,
        }
        if any(claims.get(name) != value for name, value in expected.items()):
            raise PeerGrantError(f"JWT {prefix} endpoint binding is invalid")
    transports = claims["allowed_transports"]
    if not isinstance(transports, list) or any(item not in {"direct_quic", "relay_https"} for item in transports):
        raise PeerGrantError("JWT allowed_transports is invalid")
    max_bytes = claims["max_bytes"]
    if not isinstance(max_bytes, str) or not max_bytes.isdigit() or max_bytes.startswith("0"):
        raise PeerGrantError("JWT max_bytes is invalid")
    current = int(time.time()) if now is None else now
    if claims["exp"] - claims["iat"] != 90 or claims["nbf"] != claims["iat"] - 5:
        raise PeerGrantError("JWT lifetime is invalid")
    if claims["iat"] > current + 30 or current < claims["nbf"] - 30 or current > claims["exp"] + 30:
        raise PeerGrantError("JWT is outside its validity window")
    return VerifiedPeerGrant(header=header, claims=claims, compact=compact)
