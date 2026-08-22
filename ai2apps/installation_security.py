"""Durable security identity for one Local AI2Apps data root."""

from __future__ import annotations

import fcntl
import hashlib
import os
import platform
import secrets
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.storage.database import PlatformDatabase


class LocalInstanceAlreadyRunningError(RuntimeError):
    """The canonical data root is already owned by another live Host."""


class LocalSecurityIdentityClaimError(RuntimeError):
    """A copied security identity is already bound to another data root."""


def claim_local_security_identity(
    security_instance_id: str,
    platform_root,
) -> None:
    """Atomically bind an identity to one root outside the copyable data tree."""

    resolved_root = platform_root.resolve()
    configured = os.environ.get("AI2APPS_SECURITY_CLAIM_DIR")
    if configured:
        claims_root = Path(configured).expanduser().resolve()
    elif _is_temporary_root(resolved_root):
        claims_root = Path(tempfile.gettempdir()) / (
            f"ai2apps-security-claims-{os.getuid()}"
        )
    elif platform.system() == "Darwin":
        claims_root = (
            Path.home()
            / "Library"
            / "Application Support"
            / "AI2Apps"
            / "SecurityClaims"
        )
    else:
        claims_root = (
            Path.home()
            / ".local"
            / "state"
            / "ai2apps"
            / "security-claims"
        )
    claims_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    claim_name = hashlib.sha256(security_instance_id.encode("ascii")).hexdigest()
    root_digest = hashlib.sha256(str(resolved_root).encode("utf-8")).hexdigest()
    claim_path = claims_root / claim_name
    try:
        descriptor = os.open(
            claim_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError:
        try:
            existing = claim_path.read_text(encoding="ascii").strip()
        except OSError as error:
            raise LocalSecurityIdentityClaimError(
                "Local security identity claim cannot be verified"
            ) from error
        if existing != root_digest:
            raise LocalSecurityIdentityClaimError(
                "Local security identity is already claimed by another data root"
            ) from None
        return
    try:
        os.write(descriptor, (root_digest + "\n").encode("ascii"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _is_temporary_root(resolved_root: Path) -> bool:
    """Recognize macOS' /var -> /private/var resolved temp-directory alias."""

    candidates = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    for temporary_root in candidates:
        try:
            resolved_root.relative_to(temporary_root)
        except ValueError:
            continue
        return True
    return False


class LocalInstanceLease:
    """Hold a non-blocking process lease for one canonical Platform root."""

    def __init__(self, descriptor: int, path) -> None:
        self._descriptor = descriptor
        self.path = path

    @classmethod
    def acquire(cls, platform_root) -> LocalInstanceLease:
        platform_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = (platform_root / "instance.lock").resolve()
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            os.close(descriptor)
            raise LocalInstanceAlreadyRunningError(
                f"AI2Apps data root is already active: {platform_root.parent}"
            ) from exc
        os.ftruncate(descriptor, 0)
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        os.fsync(descriptor)
        return cls(descriptor, lock_path)

    def release(self) -> None:
        if self._descriptor < 0:
            return
        try:
            fcntl.flock(self._descriptor, fcntl.LOCK_UN)
        finally:
            os.close(self._descriptor)
            self._descriptor = -1

    def __del__(self) -> None:
        with suppress(Exception):
            self.release()
        # Interpreter shutdown can clear fcntl/os module globals before
        # finalizers run. The kernel still closes the descriptor when the
        # process exits, so finalization must never emit a spurious error.


@dataclass(frozen=True, slots=True)
class LocalSecurityIdentity:
    """Immutable namespace identity created before optional Cloud enrollment."""

    security_instance_id: str
    created_at: datetime

    @property
    def short_id(self) -> str:
        return self.security_instance_id.removeprefix("local_")[:16]


class LocalSecurityIdentityRepository:
    """Create or load exactly one security identity for a Platform database."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    def get_or_create(self) -> LocalSecurityIdentity:
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT security_instance_id,created_at "
                "FROM local_security_identity WHERE singleton_id=1"
            ).fetchone()
            if row is None:
                security_instance_id = "local_" + secrets.token_hex(16)
                created_at = utc_now_text()
                connection.execute(
                    """
                    INSERT INTO local_security_identity(
                        singleton_id,security_instance_id,created_at
                    ) VALUES (1,?,?)
                    """,
                    (security_instance_id, created_at),
                )
                row = connection.execute(
                    "SELECT security_instance_id,created_at "
                    "FROM local_security_identity WHERE singleton_id=1"
                ).fetchone()
                assert row is not None
            return LocalSecurityIdentity(
                security_instance_id=str(row["security_instance_id"]),
                created_at=parse_utc(str(row["created_at"])),
            )

    def get(self) -> LocalSecurityIdentity | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT security_instance_id,created_at "
                "FROM local_security_identity WHERE singleton_id=1"
            ).fetchone()
        if row is None:
            return None
        return LocalSecurityIdentity(
            security_instance_id=str(row["security_instance_id"]),
            created_at=parse_utc(str(row["created_at"])),
        )
