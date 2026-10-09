"""Local-only identity and sessions for an explicitly unregistered desktop."""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import tempfile
import time
from pathlib import Path

from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    MemberRole,
    RequestPrincipal,
    validate_identity,
)


class OfflineAccess:
    """Persist mode and session digests in an instance-owned local file.

    No Cloud installation/member projection is created. Activation is limited
    to unbound installations; callers must authenticate the native Shell.
    """

    def __init__(self, database, instance_id: str):
        validate_identity(instance_id, "instance_id")
        self.identities = IdentityRepository(database)
        self.instance_id = instance_id
        self.path = database.path.parent / f"offline-access-{instance_id}.json"
        try:
            raw = self.path.read_text()
        except FileNotFoundError:
            raw = None
        try:
            self.state = json.loads(raw) if raw is not None else None
        except (ValueError, TypeError) as error:
            raise IdentityBindingError("Invalid offline mode state") from error
        if raw is not None and (
            not isinstance(self.state, dict)
            or self.state.get("version") != 1
            or not isinstance(self.state.get("sessions"), dict)
            or any(
                not isinstance(expiry, (int, float)) or not math.isfinite(expiry)
                for expiry in self.state["sessions"].values()
            )
        ):
            raise IdentityBindingError("Invalid offline mode state")
        if self.state is not None and self.identities.get_installation() is not None:
            raise IdentityBindingError("Offline mode cannot use a Cloud-bound installation")

    def _save(self, state: dict) -> None:
        descriptor, name = tempfile.mkstemp(prefix=".offline-", dir=self.path.parent)
        try:
            with os.fdopen(descriptor, "w") as stream:
                json.dump(state, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            self.state = state
        finally:
            Path(name).unlink(missing_ok=True)

    @property
    def enabled(self) -> bool:
        return self.state is not None

    def principal(self) -> RequestPrincipal:
        if not self.enabled:
            raise IdentityBindingError("Offline mode is not enabled")
        return RequestPrincipal(
            actor_user_id=f"offline.{self.instance_id}",
            installation_id=self.instance_id,
            organization_id=f"offline.{self.instance_id}",
            billing_account_id=f"offline.{self.instance_id}",
            role=MemberRole.CORE,
            membership_epoch=1,
            authentication_type="offline_session",
        )

    def activate(self) -> tuple[str, RequestPrincipal]:
        if self.identities.get_installation() is not None:
            raise IdentityBindingError("Use an unbound installation for offline mode")
        token = secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode()).hexdigest()
        sessions = dict((self.state or {}).get("sessions", {}))
        now = time.time()
        sessions = {key: expiry for key, expiry in sessions.items() if expiry > now}
        if len(sessions) >= 16:
            sessions.pop(min(sessions, key=sessions.get))
        sessions[digest] = now + 180 * 86400
        self._save({"version": 1, "sessions": sessions})
        return token, self.principal()

    def authorize(self, token: str | None) -> RequestPrincipal | None:
        if not self.enabled or not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        if self.state["sessions"].get(digest, 0) <= time.time():
            return None
        return self.principal()

    def revoke(self, token: str | None) -> None:
        if self.enabled and token:
            digest = hashlib.sha256(token.encode()).hexdigest()
            sessions = dict(self.state["sessions"])
            sessions.pop(digest, None)
            self._save({"version": 1, "sessions": sessions})
