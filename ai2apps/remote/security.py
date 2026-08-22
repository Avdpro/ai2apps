"""Ed25519 Cloud token verification and bounded local mobile sessions."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from ai2apps.core import utc_now

from .models import RemoteMobileSession

REMOTE_TOKEN_ISSUER = "ai2apps-cloud"
REMOTE_TOKEN_AUDIENCE = "ai2apps-remote-mobile-v1"
INSTALLATION_MEMBER_TOKEN_AUDIENCE = "ai2apps-installation-member-v1"
FEDERATION_RELAY_TOKEN_AUDIENCE = "ai2apps-federation-relay-v1"
MOBILE_SESSION_LIFETIME = timedelta(minutes=15)
ACCESS_CHECK_WINDOW = timedelta(seconds=60)


class RemoteTokenError(ValueError):
    pass


def verify_federation_relay_token(
    token: str, jwks: dict[str, Any], *, installation_id: str,
    export_id: str, request_id: str, ancestor_node_ids: tuple[str, ...],
) -> dict[str, Any]:
    """Verify one short-lived Cloud assertion at the upstream connector."""

    parts = token.split(".")
    if len(parts) != 3:
        raise RemoteTokenError("Federation relay assertion must be a compact JWT")
    try:
        header = json.loads(_decode(parts[0]))
        claims = json.loads(_decode(parts[1]))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RemoteTokenError("Federation relay assertion JSON is invalid") from error
    if header.get("alg") != "EdDSA" or not isinstance(header.get("kid"), str):
        raise RemoteTokenError("Federation relay assertion algorithm is not allowed")
    key = next((item for item in jwks.get("keys", []) if item.get("kid") == header["kid"]), None)
    if not key or any(key.get(name) != expected for name, expected in {
        "kty": "OKP", "crv": "Ed25519", "use": "sig", "alg": "EdDSA",
    }.items()):
        raise RemoteTokenError("Federation relay signing key is unavailable")
    try:
        Ed25519PublicKey.from_public_bytes(_decode(key["x"])).verify(
            _decode(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii")
        )
    except (KeyError, ValueError, InvalidSignature) as error:
        raise RemoteTokenError("Federation relay signature is invalid") from error
    required = (
        "iss", "aud", "sub", "jti", "iat", "nbf", "exp", "request_id",
        "node_link_id", "upstream_installation_id", "downstream_installation_id",
        "export_id", "grant_epoch", "link_epoch", "ancestor_node_ids",
    )
    if any(name not in claims for name in required):
        raise RemoteTokenError("Federation relay assertion is missing required claims")
    now = int(utc_now().timestamp())
    try:
        issued_at, not_before, expires_at = int(claims["iat"]), int(claims["nbf"]), int(claims["exp"])
        grant_epoch, link_epoch = int(claims["grant_epoch"]), int(claims["link_epoch"])
    except (TypeError, ValueError) as error:
        raise RemoteTokenError("Federation relay assertion contains invalid epochs") from error
    claim_path = claims["ancestor_node_ids"]
    if (
        claims["iss"] != REMOTE_TOKEN_ISSUER
        or claims["aud"] != FEDERATION_RELAY_TOKEN_AUDIENCE
        or claims["upstream_installation_id"] != installation_id
        or claims["export_id"] != export_id
        or claims["request_id"] != request_id
        or not isinstance(claim_path, list)
        or tuple(claim_path) != ancestor_node_ids
        or not claim_path or claim_path[-1] != installation_id
        or len(set(claim_path)) != len(claim_path)
        or len(claim_path) != 2
        or grant_epoch < 1 or link_epoch < 1
        or expires_at - issued_at > 120 or expires_at <= issued_at
        or issued_at > now + 30 or not_before > now + 30 or expires_at <= now - 30
    ):
        raise RemoteTokenError("Federation relay assertion binding is invalid")
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise RemoteTokenError("Federation relay actor is invalid")
    return claims


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value.encode("ascii") + b"=" * (-len(value) % 4))
    except (ValueError, UnicodeError) as error:
        raise RemoteTokenError("Remote token contains invalid base64url") from error


def verify_remote_token(
    token: str,
    jwks: dict[str, Any],
    *,
    device_id: str,
    access_epoch: int,
) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        raise RemoteTokenError("Remote token must be a compact JWT")
    try:
        header = json.loads(_decode(parts[0]))
        claims = json.loads(_decode(parts[1]))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RemoteTokenError("Remote token JSON is invalid") from error
    if header.get("alg") != "EdDSA" or not isinstance(header.get("kid"), str):
        raise RemoteTokenError("Remote token algorithm is not allowed")
    key = next((item for item in jwks.get("keys", []) if item.get("kid") == header["kid"]), None)
    if not key or any(key.get(name) != expected for name, expected in {
        "kty": "OKP", "crv": "Ed25519", "use": "sig", "alg": "EdDSA",
    }.items()):
        raise RemoteTokenError("Remote token signing key is unavailable")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_decode(key["x"]))
        public_key.verify(_decode(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii"))
    except (KeyError, ValueError, InvalidSignature) as error:
        raise RemoteTokenError("Remote token signature is invalid") from error
    now = int(utc_now().timestamp())
    required = ("iss", "aud", "sub", "device_id", "access_epoch", "iat", "exp", "jti")
    if any(name not in claims for name in required):
        raise RemoteTokenError("Remote token is missing required claims")
    if claims["iss"] != REMOTE_TOKEN_ISSUER or claims["aud"] != REMOTE_TOKEN_AUDIENCE:
        raise RemoteTokenError("Remote token issuer or audience is invalid")
    if claims["device_id"] != device_id or int(claims["access_epoch"]) != access_epoch:
        raise RemoteTokenError("Remote token is bound to a different device epoch")
    if not isinstance(claims["sub"], str) or not claims["sub"] or not isinstance(claims["jti"], str):
        raise RemoteTokenError("Remote token identity claims are invalid")
    if int(claims["exp"]) <= now or int(claims["iat"]) > now + 30:
        raise RemoteTokenError("Remote token is expired or not yet valid")
    return claims


def verify_installation_member_token(
    token: str,
    jwks: dict[str, Any],
    *,
    installation_id: str,
    device_id: str,
    organization_id: str,
    access_epoch: int,
) -> dict[str, Any]:
    """Verify a short-lived Cloud member assertion for one installation."""

    parts = token.split(".")
    if len(parts) != 3:
        raise RemoteTokenError("Member assertion must be a compact JWT")
    try:
        header = json.loads(_decode(parts[0]))
        claims = json.loads(_decode(parts[1]))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise RemoteTokenError("Member assertion JSON is invalid") from error
    if header.get("alg") != "EdDSA" or not isinstance(header.get("kid"), str):
        raise RemoteTokenError("Member assertion algorithm is not allowed")
    key = next(
        (item for item in jwks.get("keys", []) if item.get("kid") == header["kid"]),
        None,
    )
    if not key or any(
        key.get(name) != expected
        for name, expected in {
            "kty": "OKP",
            "crv": "Ed25519",
            "use": "sig",
            "alg": "EdDSA",
        }.items()
    ):
        raise RemoteTokenError("Member assertion signing key is unavailable")
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_decode(key["x"]))
        public_key.verify(
            _decode(parts[2]), f"{parts[0]}.{parts[1]}".encode("ascii")
        )
    except (KeyError, ValueError, InvalidSignature) as error:
        raise RemoteTokenError("Member assertion signature is invalid") from error

    required = (
        "iss", "aud", "sub", "jti", "iat", "nbf", "exp",
        "installation_id", "cloud_device_id", "organization_id",
        "organization_type", "role", "membership_epoch", "access_epoch",
    )
    if any(name not in claims for name in required):
        raise RemoteTokenError("Member assertion is missing required claims")
    if (
        claims["iss"] != REMOTE_TOKEN_ISSUER
        or claims["aud"] != INSTALLATION_MEMBER_TOKEN_AUDIENCE
    ):
        raise RemoteTokenError("Member assertion issuer or audience is invalid")
    if (
        claims["installation_id"] != installation_id
        or claims["cloud_device_id"] != device_id
        or claims["organization_id"] != organization_id
        or int(claims["access_epoch"]) != access_epoch
    ):
        raise RemoteTokenError("Member assertion is bound to another installation")
    if not isinstance(claims["sub"], str) or not claims["sub"]:
        raise RemoteTokenError("Member assertion subject is invalid")
    if not isinstance(claims["jti"], str) or not claims["jti"]:
        raise RemoteTokenError("Member assertion identifier is invalid")
    try:
        issued_at = int(claims["iat"])
        not_before = int(claims["nbf"])
        expires_at = int(claims["exp"])
        membership_epoch = int(claims["membership_epoch"])
    except (TypeError, ValueError) as error:
        raise RemoteTokenError("Member assertion time or epoch is invalid") from error
    now = int(utc_now().timestamp())
    if (
        membership_epoch < 1
        or expires_at - issued_at > 300
        or expires_at <= issued_at
        or issued_at > now + 30
        or not_before > now + 30
        or expires_at <= now - 30
    ):
        raise RemoteTokenError("Member assertion is expired or not yet valid")
    return claims


class RemoteSessionStore:
    """In-memory, restart-invalidated sessions keyed by a SHA-256 cookie digest."""

    def __init__(self) -> None:
        self._sessions: dict[str, RemoteMobileSession] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def create(
        self,
        *,
        device_id: str,
        owner_user_id: str,
        access_epoch: int,
        local_session_token: str | None = None,
        client_scope: str = "desktop",
    ) -> tuple[str, RemoteMobileSession]:
        now = utc_now()
        token = secrets.token_urlsafe(32)
        digest = self._digest(token)
        session = RemoteMobileSession(
            token_digest=digest, device_id=device_id, owner_user_id=owner_user_id,
            access_epoch=access_epoch, created_at=now,
            expires_at=now + MOBILE_SESSION_LIFETIME, last_access_check_at=now,
            local_session_token=local_session_token,
            client_scope=client_scope,
        )
        self._sessions[digest] = session
        return token, session

    def get(self, token: str | None) -> RemoteMobileSession | None:
        if not token:
            return None
        session = self._sessions.get(self._digest(token))
        if session is not None and session.expires_at <= utc_now():
            self._sessions.pop(session.token_digest, None)
            return None
        return session

    def checked(self, session: RemoteMobileSession) -> RemoteMobileSession:
        updated = RemoteMobileSession(
            token_digest=session.token_digest, device_id=session.device_id,
            owner_user_id=session.owner_user_id, access_epoch=session.access_epoch,
            created_at=session.created_at, expires_at=session.expires_at,
            last_access_check_at=utc_now(),
            local_session_token=session.local_session_token,
            client_scope=session.client_scope,
        )
        self._sessions[session.token_digest] = updated
        return updated

    def revoke_device(self, device_id: str) -> None:
        for digest, session in tuple(self._sessions.items()):
            if session.device_id == device_id:
                self._sessions.pop(digest, None)

    def clear(self) -> None:
        self._sessions.clear()
