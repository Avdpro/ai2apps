"""Strict EdDSA verification for Cloud-authorized Messager peer handshakes."""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .identity import MESSAGER_SUITE, b64url_decode

_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_ORIGIN_HOST = re.compile(r"^device-[0-9a-f]{32}\.[a-z0-9.-]+$")
_UUID_CLAIMS = {
    "sub", "jti", "handshake_id", "initiator_user_id", "initiator_device_id",
    "initiator_installation_id", "initiator_key_id", "recipient_user_id",
    "recipient_device_id", "recipient_installation_id", "recipient_key_id",
}
_INTEGER_CLAIMS = {
    "iat", "nbf", "exp", "initiator_access_epoch", "initiator_key_epoch",
    "recipient_access_epoch", "recipient_key_epoch",
}
_FINGERPRINT_CLAIMS = {
    "initiator_identity_signing_key_sha256", "initiator_static_dh_key_sha256",
    "recipient_identity_signing_key_sha256", "recipient_static_dh_key_sha256",
    "friendship_pair_key_sha256",
}
_REQUIRED_CLAIMS = _UUID_CLAIMS | _INTEGER_CLAIMS | _FINGERPRINT_CLAIMS | {
    "iss", "aud", "recipient_public_origin"
}


class MessagerAssertionError(ValueError):
    """A peer assertion failed cryptographic or semantic validation."""


@dataclass(frozen=True, slots=True)
class VerifiedPeerAssertion:
    header: dict[str, Any]
    claims: dict[str, Any]
    compact: str


def _canonical_uuid(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise MessagerAssertionError(f"{name} must be a UUID")
    try:
        parsed = UUID(value)
    except ValueError as error:
        raise MessagerAssertionError(f"{name} must be a UUID") from error
    if str(parsed) != value:
        raise MessagerAssertionError(f"{name} must be canonical")
    return value


def _decode_json(segment: str, name: str) -> dict[str, Any]:
    try:
        value = json.loads(b64url_decode(segment).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MessagerAssertionError(f"JWT {name} is invalid") from error
    if not isinstance(value, dict):
        raise MessagerAssertionError(f"JWT {name} must be an object")
    return value


def _validate_origin(value: Any) -> str:
    if not isinstance(value, str):
        raise MessagerAssertionError("recipient_public_origin is invalid")
    parsed = urlparse(value)
    if (
        parsed.scheme != "https" or parsed.username or parsed.password or parsed.port
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
        or parsed.hostname is None or _ORIGIN_HOST.fullmatch(parsed.hostname) is None
    ):
        raise MessagerAssertionError("recipient_public_origin is invalid")
    return value.rstrip("/")


def _endpoint_fingerprint(endpoint: Mapping[str, Any], key: str) -> str:
    raw = b64url_decode(str(endpoint.get(key) or ""), size=32)
    return hashlib.sha256(raw).hexdigest()


def verify_peer_assertion(
    compact: str,
    jwks: Mapping[str, Any],
    *,
    handshake_id: str,
    now: int | None = None,
    self_endpoint: Mapping[str, Any] | None = None,
    peer_endpoint: Mapping[str, Any] | None = None,
    expected_recipient_device_id: str | None = None,
) -> VerifiedPeerAssertion:
    parts = compact.split(".") if isinstance(compact, str) else []
    if len(parts) != 3 or not all(parts):
        raise MessagerAssertionError("JWT compact serialization is invalid")
    header = _decode_json(parts[0], "header")
    claims = _decode_json(parts[1], "claims")
    if set(header) != {"alg", "kid", "typ"} or header.get("alg") != "EdDSA" or header.get("typ") != "JWT":
        raise MessagerAssertionError("JWT protected header is invalid")
    kid = header.get("kid")
    keys = jwks.get("keys") if isinstance(jwks, Mapping) else None
    matches = [key for key in keys or [] if isinstance(key, dict) and key.get("kid") == kid]
    if len(matches) != 1:
        raise MessagerAssertionError("JWT signing key is unknown")
    jwk = matches[0]
    if set(jwk) - {"kty", "crv", "x", "alg", "kid", "use"} or any(
        jwk.get(name) != value
        for name, value in {"kty": "OKP", "crv": "Ed25519", "alg": "EdDSA", "use": "sig"}.items()
    ):
        raise MessagerAssertionError("JWT signing JWK is invalid")
    try:
        Ed25519PublicKey.from_public_bytes(
            b64url_decode(jwk.get("x"), size=32)
        ).verify(b64url_decode(parts[2], size=64), f"{parts[0]}.{parts[1]}".encode("ascii"))
    except (ValueError, InvalidSignature) as error:
        raise MessagerAssertionError("JWT signature is invalid") from error

    if set(claims) != _REQUIRED_CLAIMS:
        raise MessagerAssertionError("JWT claims set is invalid")
    for name in _UUID_CLAIMS:
        _canonical_uuid(claims[name], name)
    for name in _INTEGER_CLAIMS:
        if isinstance(claims[name], bool) or not isinstance(claims[name], int):
            raise MessagerAssertionError(f"{name} must be an integer")
        if name.endswith("epoch") and claims[name] < 1:
            raise MessagerAssertionError(f"{name} must be positive")
    for name in _FINGERPRINT_CLAIMS:
        if not isinstance(claims[name], str) or _FINGERPRINT.fullmatch(claims[name]) is None:
            raise MessagerAssertionError(f"{name} is invalid")
    if claims["iss"] != "ai2apps-cloud" or claims["aud"] != "ai2apps-messager-peer-v1":
        raise MessagerAssertionError("JWT issuer or audience is invalid")
    if claims["sub"] != claims["initiator_user_id"]:
        raise MessagerAssertionError("JWT subject binding is invalid")
    if claims["handshake_id"] != _canonical_uuid(handshake_id, "handshake_id"):
        raise MessagerAssertionError("JWT handshake binding is invalid")
    current = int(time.time()) if now is None else now
    if claims["exp"] - claims["iat"] != 90 or claims["nbf"] != claims["iat"] - 5:
        raise MessagerAssertionError("JWT lifetime is invalid")
    if (
        claims["iat"] > current + 30
        or current < claims["nbf"] - 30
        or current > claims["exp"] + 30
    ):
        raise MessagerAssertionError("JWT is outside its validity window")
    origin = _validate_origin(claims["recipient_public_origin"])
    if expected_recipient_device_id is not None and claims["recipient_device_id"] != expected_recipient_device_id:
        raise MessagerAssertionError("JWT recipient Device binding is invalid")

    bindings = (
        ("initiator", self_endpoint), ("recipient", peer_endpoint)
    )
    for prefix, endpoint in bindings:
        if endpoint is None:
            continue
        expected = {
            "userId": claims[f"{prefix}_user_id"],
            "deviceId": claims[f"{prefix}_device_id"],
            "installationId": claims[f"{prefix}_installation_id"],
            "accessEpoch": claims[f"{prefix}_access_epoch"],
            "keyId": claims[f"{prefix}_key_id"],
            "keyEpoch": claims[f"{prefix}_key_epoch"],
            "suite": MESSAGER_SUITE,
        }
        if any(endpoint.get(name) != value for name, value in expected.items()):
            raise MessagerAssertionError(f"JWT {prefix} endpoint binding is invalid")
        if _endpoint_fingerprint(endpoint, "identitySigningPublicKey") != claims[f"{prefix}_identity_signing_key_sha256"]:
            raise MessagerAssertionError(f"JWT {prefix} identity key binding is invalid")
        if _endpoint_fingerprint(endpoint, "staticDhPublicKey") != claims[f"{prefix}_static_dh_key_sha256"]:
            raise MessagerAssertionError(f"JWT {prefix} static key binding is invalid")
    if peer_endpoint is not None and str(peer_endpoint.get("publicOrigin") or "").rstrip("/") != origin:
        raise MessagerAssertionError("JWT recipient origin binding is invalid")
    return VerifiedPeerAssertion(header=header, claims=claims, compact=compact)
