"""Short-lived authenticated Host Broker request envelopes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True, slots=True)
class BrokerEnvelope:
    token: str
    nonce: str
    expires_at: datetime
    token_digest: str


class BrokerAuthority:
    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or secrets.token_bytes(32)

    def issue(
        self,
        *,
        request_id: str,
        session_id: str,
        run_id: str | None,
        operation: str,
        ttl_seconds: int = 30,
    ) -> BrokerEnvelope:
        nonce = secrets.token_hex(16)
        expires = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        payload = {
            "request_id": request_id,
            "session_id": session_id,
            "run_id": run_id,
            "operation": operation,
            "nonce": nonce,
            "expires_at": expires.isoformat(),
        }
        encoded = (
            base64.urlsafe_b64encode(
                json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
            )
            .decode()
            .rstrip("=")
        )
        signature = hmac.new(self._secret, encoded.encode(), hashlib.sha256).hexdigest()
        token = f"{encoded}.{signature}"
        return BrokerEnvelope(
            token,
            nonce,
            expires,
            f"sha256:{hashlib.sha256(token.encode()).hexdigest()}",
        )

    def verify(
        self, token: str, *, session_id: str, run_id: str | None, operation: str
    ) -> dict:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(
                self._secret, encoded.encode(), hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("signature")
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded))
            expires = datetime.fromisoformat(payload["expires_at"])
        except Exception as exc:
            raise PermissionError("Invalid Host Broker authorization") from exc
        if datetime.now(UTC) >= expires:
            raise PermissionError("Expired Host Broker authorization")
        if (
            payload.get("session_id") != session_id
            or payload.get("run_id") != run_id
            or payload.get("operation") != operation
        ):
            raise PermissionError("Host Broker scope mismatch")
        return payload
