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
MOBILE_SESSION_LIFETIME = timedelta(minutes=15)
ACCESS_CHECK_WINDOW = timedelta(seconds=60)


class RemoteTokenError(ValueError):
    pass


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


class RemoteSessionStore:
    """In-memory, restart-invalidated sessions keyed by a SHA-256 cookie digest."""

    def __init__(self) -> None:
        self._sessions: dict[str, RemoteMobileSession] = {}

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def create(self, *, device_id: str, owner_user_id: str, access_epoch: int) -> tuple[str, RemoteMobileSession]:
        now = utc_now()
        token = secrets.token_urlsafe(32)
        digest = self._digest(token)
        session = RemoteMobileSession(
            token_digest=digest, device_id=device_id, owner_user_id=owner_user_id,
            access_epoch=access_epoch, created_at=now,
            expires_at=now + MOBILE_SESSION_LIFETIME, last_access_check_at=now,
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
        )
        self._sessions[session.token_digest] = updated
        return updated

    def revoke_device(self, device_id: str) -> None:
        for digest, session in tuple(self._sessions.items()):
            if session.device_id == device_id:
                self._sessions.pop(digest, None)

    def clear(self) -> None:
        self._sessions.clear()
