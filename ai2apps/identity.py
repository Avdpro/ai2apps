"""Installation-owned user identity contracts for the local AI2Apps runtime."""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from ai2apps.config import BUILTIN_CHAT_SINGLETON_KEY
from ai2apps.core import parse_utc, utc_now, utc_now_text
from ai2apps.storage.database import PlatformDatabase

_IDENTITY = re.compile(r"^[A-Za-z0-9._~-]{1,200}$")
# Compatibility-only name used by releases before Local sessions were scoped
# to one Installation. New cookies must use local_session_cookie_name().
LOCAL_SESSION_COOKIE = "ai2apps_local_session"
LOCAL_SESSION_COOKIE_PREFIX = LOCAL_SESSION_COOKIE
LOCAL_SESSION_IDLE_TIMEOUT = timedelta(days=30)
LOCAL_SESSION_LIFETIME = timedelta(days=180)
LOCAL_SESSION_RENEWAL_WINDOW = timedelta(days=7)


class OrganizationType(StrEnum):
    HOUSEHOLD = "household"
    BUSINESS = "business"


class MemberRole(StrEnum):
    CORE = "core"
    OWNER = "owner"
    ADMIN = "admin"
    DEVELOPER = "developer"
    MEMBER = "member"
    CHILD = "child"
    GUEST = "guest"


class IdentityBindingError(RuntimeError):
    """The local installation or membership conflicts with durable identity."""


def validate_identity(value: str, label: str) -> str:
    """Validate Cloud/device identifiers before using them in durable keys."""

    if not _IDENTITY.fullmatch(value):
        raise ValueError(
            f"{label} must contain 1 to 200 URL-safe identity characters"
        )
    return value


def local_session_cookie_name(installation_id: str) -> str:
    """Return a stable, cookie-safe name scoped to one Local Installation.

    HTTP cookies are not scoped by TCP port. Hashing the durable Installation
    identity gives every Local instance a distinct cookie name without placing
    an arbitrary Cloud identifier in an HTTP header name.
    """

    validate_identity(installation_id, "installation_id")
    suffix = hashlib.sha256(installation_id.encode("ascii")).hexdigest()[:16]
    return f"{LOCAL_SESSION_COOKIE_PREFIX}_{suffix}"


@dataclass(frozen=True, slots=True)
class RequestPrincipal:
    """Authoritative actor and billing context attached by trusted auth code."""

    actor_user_id: str
    installation_id: str
    organization_id: str
    billing_account_id: str
    role: MemberRole
    membership_epoch: int
    authentication_type: str = "cloud_session"
    client_scope: str = "desktop"

    def __post_init__(self) -> None:
        validate_identity(self.actor_user_id, "actor_user_id")
        validate_identity(self.installation_id, "installation_id")
        validate_identity(self.organization_id, "organization_id")
        validate_identity(self.billing_account_id, "billing_account_id")
        validate_identity(self.client_scope, "client_scope")
        if self.membership_epoch < 1:
            raise ValueError("membership_epoch must be positive")

    @property
    def is_core(self) -> bool:
        return self.role in {MemberRole.CORE, MemberRole.OWNER}

    @classmethod
    def legacy_local(cls) -> RequestPrincipal:
        """Compatibility principal for the existing installation API key."""

        return cls(
            actor_user_id="local",
            installation_id="local",
            organization_id="local",
            billing_account_id="local",
            role=MemberRole.CORE,
            membership_epoch=1,
            authentication_type="legacy_api_key",
        )


@dataclass(frozen=True, slots=True)
class InstallationIdentity:
    id: str
    cloud_device_id: str
    organization_id: str
    organization_type: OrganizationType
    core_user_id: str
    billing_account_id: str
    access_epoch: int
    local_session_epoch: int
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class InstallationMembership:
    installation_id: str
    cloud_user_id: str
    role: MemberRole
    status: str
    membership_epoch: int
    account_session_epoch: int
    last_verified_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LocalLoginSession:
    token_digest: str
    installation_id: str
    actor_user_id: str
    role_snapshot: MemberRole
    membership_epoch: int
    access_epoch: int
    local_session_epoch: int
    account_session_epoch: int
    client_scope: str
    created_at: datetime
    expires_at: datetime
    last_access_check_at: datetime


class IdentityRepository:
    """Persist one installation binding and its Cloud-authoritative members."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _installation(row: sqlite3.Row) -> InstallationIdentity:
        return InstallationIdentity(
            id=row["id"],
            cloud_device_id=row["cloud_device_id"],
            organization_id=row["organization_id"],
            organization_type=OrganizationType(row["organization_type"]),
            core_user_id=row["core_user_id"],
            billing_account_id=row["billing_account_id"],
            access_epoch=int(row["access_epoch"]),
            local_session_epoch=int(row["local_session_epoch"]),
            status=row["status"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _membership(row: sqlite3.Row) -> InstallationMembership:
        return InstallationMembership(
            installation_id=row["installation_id"],
            cloud_user_id=row["cloud_user_id"],
            role=MemberRole(row["role"]),
            status=row["status"],
            membership_epoch=int(row["membership_epoch"]),
            account_session_epoch=int(row["account_session_epoch"]),
            last_verified_at=parse_utc(row["last_verified_at"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    @staticmethod
    def _local_session(row: sqlite3.Row) -> LocalLoginSession:
        return LocalLoginSession(
            token_digest=row["token_digest"],
            installation_id=row["installation_id"],
            actor_user_id=row["actor_user_id"],
            role_snapshot=MemberRole(row["role_snapshot"]),
            membership_epoch=int(row["membership_epoch"]),
            access_epoch=int(row["access_epoch"]),
            local_session_epoch=int(row["local_session_epoch"]),
            account_session_epoch=int(row["account_session_epoch"]),
            client_scope=row["client_scope"],
            created_at=parse_utc(row["created_at"]),
            expires_at=parse_utc(row["expires_at"]),
            last_access_check_at=parse_utc(row["last_access_check_at"]),
        )

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()

    def get_installation(self) -> InstallationIdentity | None:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM installations ORDER BY created_at LIMIT 2"
            ).fetchall()
        if len(rows) > 1:
            raise IdentityBindingError(
                "Local database contains more than one installation binding"
            )
        return None if not rows else self._installation(rows[0])

    def bind_installation(
        self,
        *,
        installation_id: str,
        cloud_device_id: str,
        organization_id: str,
        organization_type: OrganizationType,
        core_user_id: str,
        billing_account_id: str,
        access_epoch: int,
        local_session_epoch: int | None = None,
        core_membership_epoch: int | None = None,
        core_account_session_epoch: int | None = None,
        core_role: MemberRole = MemberRole.CORE,
    ) -> InstallationIdentity:
        """Bind once, allowing only an idempotent refresh of the same authority."""

        for value, label in (
            (installation_id, "installation_id"),
            (cloud_device_id, "cloud_device_id"),
            (organization_id, "organization_id"),
            (core_user_id, "core_user_id"),
            (billing_account_id, "billing_account_id"),
        ):
            validate_identity(value, label)
        if access_epoch < 1:
            raise ValueError("access_epoch must be positive")
        if local_session_epoch is not None and local_session_epoch < 1:
            raise ValueError("local_session_epoch must be positive")
        if core_membership_epoch is None:
            core_membership_epoch = access_epoch
        if core_membership_epoch < 1:
            raise ValueError("core_membership_epoch must be positive")
        if (
            core_account_session_epoch is not None
            and core_account_session_epoch < 1
        ):
            raise ValueError("core_account_session_epoch must be positive")
        if core_role not in {MemberRole.CORE, MemberRole.OWNER}:
            raise ValueError("core_role must be core or owner")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM installations ORDER BY created_at LIMIT 1"
            ).fetchone()
            access_changed = False
            if existing is not None:
                authority = (
                    existing["id"],
                    existing["cloud_device_id"],
                    existing["organization_id"],
                    existing["organization_type"],
                    existing["core_user_id"],
                    existing["billing_account_id"],
                )
                proposed = (
                    installation_id,
                    cloud_device_id,
                    organization_id,
                    organization_type.value,
                    core_user_id,
                    billing_account_id,
                )
                if authority != proposed:
                    raise IdentityBindingError(
                        "Installation is already bound to another Cloud authority"
                    )
                if access_epoch < int(existing["access_epoch"]):
                    raise IdentityBindingError("Installation access epoch regressed")
                if local_session_epoch is None:
                    local_session_epoch = int(existing["local_session_epoch"])
                if local_session_epoch < int(existing["local_session_epoch"]):
                    raise IdentityBindingError("Local Session epoch regressed")
                access_changed = access_epoch != int(existing["access_epoch"])
                local_session_changed = local_session_epoch != int(
                    existing["local_session_epoch"]
                )
                connection.execute(
                    """
                    UPDATE installations
                    SET access_epoch=?,local_session_epoch=?,status='active',
                        updated_at=? WHERE id=?
                    """,
                    (access_epoch, local_session_epoch, now, installation_id),
                )
            else:
                local_session_epoch = local_session_epoch or 1
                local_session_changed = False
                connection.execute(
                    """
                    INSERT INTO installations(
                        id,cloud_device_id,organization_id,organization_type,
                        core_user_id,billing_account_id,access_epoch,
                        local_session_epoch,status,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,'active',?,?)
                    """,
                    (
                        installation_id,
                        cloud_device_id,
                        organization_id,
                        organization_type.value,
                        core_user_id,
                        billing_account_id,
                        access_epoch,
                        local_session_epoch,
                        now,
                        now,
                    ),
                )
            existing_core = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (installation_id, core_user_id),
            ).fetchone()
            if core_account_session_epoch is None:
                core_account_session_epoch = (
                    1
                    if existing_core is None
                    else int(existing_core["account_session_epoch"])
                )
            if (
                existing_core is not None
                and core_account_session_epoch
                < int(existing_core["account_session_epoch"])
            ):
                raise IdentityBindingError("Core account Session epoch regressed")
            if (
                existing_core is not None
                and core_membership_epoch
                < int(existing_core["membership_epoch"])
            ):
                raise IdentityBindingError("Core membership epoch regressed")
            core_authorization_changed = (
                existing_core is not None
                and (
                    existing_core["role"] != core_role.value
                    or existing_core["status"] != "active"
                    or int(existing_core["membership_epoch"])
                    != core_membership_epoch
                    or int(existing_core["account_session_epoch"])
                    != core_account_session_epoch
                )
            )
            connection.execute(
                """
                INSERT INTO installation_memberships(
                    installation_id,cloud_user_id,role,status,membership_epoch,
                    account_session_epoch,
                    last_verified_at,created_at,updated_at
                ) VALUES (?,?,?,'active',?,?,?,?,?)
                ON CONFLICT(installation_id,cloud_user_id) DO UPDATE SET
                    role=excluded.role,status='active',
                    membership_epoch=MAX(
                        installation_memberships.membership_epoch,
                        excluded.membership_epoch
                    ),
                    account_session_epoch=MAX(
                        installation_memberships.account_session_epoch,
                        excluded.account_session_epoch
                    ),
                    last_verified_at=excluded.last_verified_at,
                    updated_at=excluded.updated_at
                """,
                (
                    installation_id,
                    core_user_id,
                    core_role.value,
                    core_membership_epoch,
                    core_account_session_epoch,
                    now,
                    now,
                    now,
                ),
            )
            if access_changed or local_session_changed:
                connection.execute(
                    "DELETE FROM local_login_sessions WHERE installation_id=?",
                    (installation_id,),
                )
            elif core_authorization_changed:
                connection.execute(
                    """
                    DELETE FROM local_login_sessions
                    WHERE installation_id=? AND actor_user_id=?
                    """,
                    (installation_id, core_user_id),
                )
            row = connection.execute(
                "SELECT * FROM installations WHERE id=?", (installation_id,)
            ).fetchone()
            assert row is not None
            return self._installation(row)

    def upsert_membership(
        self,
        *,
        cloud_user_id: str,
        role: MemberRole,
        status: str,
        membership_epoch: int,
        account_session_epoch: int | None = None,
    ) -> InstallationMembership:
        """Apply a Cloud-authoritative membership snapshot monotonically."""

        validate_identity(cloud_user_id, "cloud_user_id")
        if status not in {"active", "suspended", "revoked"}:
            raise ValueError("membership status is invalid")
        if membership_epoch < 1:
            raise ValueError("membership_epoch must be positive")
        if account_session_epoch is not None and account_session_epoch < 1:
            raise ValueError("account_session_epoch must be positive")
        installation = self.get_installation()
        if installation is None:
            raise IdentityBindingError("Installation is not bound")
        if cloud_user_id == installation.core_user_id and role not in {
            MemberRole.CORE,
            MemberRole.OWNER,
        }:
            raise IdentityBindingError("Core account role cannot be downgraded locally")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            existing = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (installation.id, cloud_user_id),
            ).fetchone()
            if existing is not None and membership_epoch < int(
                existing["membership_epoch"]
            ):
                raise IdentityBindingError("Membership epoch regressed")
            if account_session_epoch is None:
                account_session_epoch = (
                    1
                    if existing is None
                    else int(existing["account_session_epoch"])
                )
            if (
                existing is not None
                and account_session_epoch < int(existing["account_session_epoch"])
            ):
                raise IdentityBindingError("Account Session epoch regressed")
            connection.execute(
                """
                INSERT INTO installation_memberships(
                    installation_id,cloud_user_id,role,status,membership_epoch,
                    account_session_epoch,
                    last_verified_at,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(installation_id,cloud_user_id) DO UPDATE SET
                    role=excluded.role,status=excluded.status,
                    membership_epoch=excluded.membership_epoch,
                    account_session_epoch=excluded.account_session_epoch,
                    last_verified_at=excluded.last_verified_at,
                    updated_at=excluded.updated_at
                """,
                (
                    installation.id,
                    cloud_user_id,
                    role.value,
                    status,
                    membership_epoch,
                    account_session_epoch,
                    now,
                    now,
                    now,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (installation.id, cloud_user_id),
            ).fetchone()
            assert row is not None
            return self._membership(row)

    def apply_access_projection(
        self,
        *,
        installation_id: str,
        cloud_device_id: str,
        organization_id: str,
        device_status: str,
        access_epoch: int,
        local_session_epoch: int | None = None,
        memberships: Sequence[dict[str, Any]],
    ) -> InstallationIdentity:
        """Atomically apply one complete Cloud authorization projection."""

        for value, label in (
            (installation_id, "installation_id"),
            (cloud_device_id, "cloud_device_id"),
            (organization_id, "organization_id"),
        ):
            validate_identity(value, label)
        if device_status not in {"active", "suspended", "revoked"}:
            raise ValueError("device status is invalid")
        if access_epoch < 1:
            raise ValueError("access_epoch must be positive")
        if local_session_epoch is not None and local_session_epoch < 1:
            raise ValueError("local_session_epoch must be positive")

        normalized: list[tuple[str, MemberRole, str, int, int | None]] = []
        seen: set[str] = set()
        for item in memberships:
            try:
                user_id = validate_identity(str(item["user_id"]), "cloud_user_id")
                role = MemberRole(str(item["role"]))
                status = str(item["status"])
                membership_epoch = int(item["membership_epoch"])
                raw_account_epoch = item.get("account_session_epoch")
                account_session_epoch = (
                    None if raw_account_epoch is None else int(raw_account_epoch)
                )
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("membership projection is invalid") from error
            if user_id in seen:
                raise ValueError("membership projection contains duplicate users")
            if status not in {"active", "suspended", "revoked"}:
                raise ValueError("membership status is invalid")
            if membership_epoch < 1:
                raise ValueError("membership_epoch must be positive")
            if account_session_epoch is not None and account_session_epoch < 1:
                raise ValueError("account_session_epoch must be positive")
            seen.add(user_id)
            normalized.append(
                (user_id, role, status, membership_epoch, account_session_epoch)
            )

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            installation = connection.execute(
                "SELECT * FROM installations WHERE id=?", (installation_id,)
            ).fetchone()
            if installation is None:
                raise IdentityBindingError("Installation is not bound")
            if (
                installation["cloud_device_id"] != cloud_device_id
                or installation["organization_id"] != organization_id
            ):
                raise IdentityBindingError(
                    "Cloud access projection changed installation authority"
                )
            prior_access_epoch = int(installation["access_epoch"])
            prior_local_session_epoch = int(installation["local_session_epoch"])
            if access_epoch < prior_access_epoch:
                raise IdentityBindingError("Installation access epoch regressed")
            if local_session_epoch is None:
                local_session_epoch = prior_local_session_epoch
            if local_session_epoch < prior_local_session_epoch:
                raise IdentityBindingError("Local Session epoch regressed")

            core_user_id = str(installation["core_user_id"])
            core = next((item for item in normalized if item[0] == core_user_id), None)
            if core is None or core[1] not in {MemberRole.CORE, MemberRole.OWNER}:
                raise IdentityBindingError(
                    "Cloud access projection omitted the core account"
                )
            if device_status == "active" and core[2] != "active":
                raise IdentityBindingError(
                    "Active installation projection has an inactive core account"
                )

            existing_rows = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=?
                """,
                (installation_id,),
            ).fetchall()
            existing = {str(row["cloud_user_id"]): row for row in existing_rows}
            for user_id, _role, _status, membership_epoch, account_epoch in normalized:
                row = existing.get(user_id)
                if row is not None and membership_epoch < int(row["membership_epoch"]):
                    raise IdentityBindingError("Membership epoch regressed")
                if (
                    row is not None
                    and account_epoch is not None
                    and account_epoch < int(row["account_session_epoch"])
                ):
                    raise IdentityBindingError("Account Session epoch regressed")

            connection.execute(
                """
                UPDATE installations
                SET status=?,access_epoch=?,local_session_epoch=?,updated_at=?
                WHERE id=?
                """,
                (
                    device_status,
                    access_epoch,
                    local_session_epoch,
                    now,
                    installation_id,
                ),
            )
            for user_id, role, status, membership_epoch, account_epoch in normalized:
                row = existing.get(user_id)
                resolved_account_epoch = (
                    account_epoch
                    if account_epoch is not None
                    else 1 if row is None else int(row["account_session_epoch"])
                )
                authorization_changed = (
                    row is None
                    or row["role"] != role.value
                    or row["status"] != status
                    or int(row["membership_epoch"]) != membership_epoch
                    or int(row["account_session_epoch"])
                    != resolved_account_epoch
                )
                connection.execute(
                    """
                    INSERT INTO installation_memberships(
                        installation_id,cloud_user_id,role,status,membership_epoch,
                        account_session_epoch,
                        last_verified_at,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(installation_id,cloud_user_id) DO UPDATE SET
                        role=excluded.role,status=excluded.status,
                        membership_epoch=excluded.membership_epoch,
                        account_session_epoch=excluded.account_session_epoch,
                        last_verified_at=excluded.last_verified_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        installation_id,
                        user_id,
                        role.value,
                        status,
                        membership_epoch,
                        resolved_account_epoch,
                        now,
                        now,
                        now,
                    ),
                )
                if authorization_changed or status != "active":
                    connection.execute(
                        """
                        DELETE FROM local_login_sessions
                        WHERE installation_id=? AND actor_user_id=?
                        """,
                        (installation_id, user_id),
                    )

            missing_user_ids = set(existing) - seen
            for user_id in missing_user_ids:
                connection.execute(
                    """
                    UPDATE installation_memberships
                    SET status='revoked',last_verified_at=?,updated_at=?
                    WHERE installation_id=? AND cloud_user_id=?
                    """,
                    (now, now, installation_id, user_id),
                )
                connection.execute(
                    """
                    DELETE FROM local_login_sessions
                    WHERE installation_id=? AND actor_user_id=?
                    """,
                    (installation_id, user_id),
                )

            if (
                access_epoch != prior_access_epoch
                or local_session_epoch != prior_local_session_epoch
                or device_status != "active"
            ):
                connection.execute(
                    "DELETE FROM local_login_sessions WHERE installation_id=?",
                    (installation_id,),
                )
            row = connection.execute(
                "SELECT * FROM installations WHERE id=?", (installation_id,)
            ).fetchone()
            assert row is not None
            return self._installation(row)

    def touch_access_projection(self, installation_id: str) -> None:
        """Record a successful ETag revalidation without changing authority."""

        validate_identity(installation_id, "installation_id")
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE installation_memberships SET last_verified_at=?
                WHERE installation_id=?
                """,
                (now, installation_id),
            )

    def deactivate_installation(self, status: str) -> None:
        """Fail closed after a definitive Cloud device suspension or revocation."""

        if status not in {"suspended", "revoked"}:
            raise ValueError("installation status must be suspended or revoked")
        installation = self.get_installation()
        if installation is None:
            return
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE installations SET status=?,updated_at=? WHERE id=?",
                (status, now, installation.id),
            )
            connection.execute(
                "DELETE FROM local_login_sessions WHERE installation_id=?",
                (installation.id,),
            )

    def principal_for(self, cloud_user_id: str) -> RequestPrincipal:
        """Resolve only an active member of the active bound installation."""

        validate_identity(cloud_user_id, "cloud_user_id")
        installation = self.get_installation()
        if installation is None or installation.status != "active":
            raise IdentityBindingError("Installation is not active")
        with self.database.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (installation.id, cloud_user_id),
            ).fetchone()
        if row is None or row["status"] != "active":
            raise IdentityBindingError("User is not an active installation member")
        membership = self._membership(row)
        return RequestPrincipal(
            actor_user_id=membership.cloud_user_id,
            installation_id=installation.id,
            organization_id=installation.organization_id,
            billing_account_id=installation.billing_account_id,
            role=membership.role,
            membership_epoch=membership.membership_epoch,
        )

    def create_local_session(
        self,
        cloud_user_id: str,
        *,
        lifetime: timedelta = LOCAL_SESSION_LIFETIME,
        client_scope: str = "desktop",
    ) -> tuple[str, LocalLoginSession]:
        """Create an opaque local cookie for a currently active Cloud member."""

        if lifetime <= timedelta(0) or lifetime > timedelta(days=365):
            raise ValueError("Local session lifetime must be within 365 days")
        validate_identity(client_scope, "client_scope")
        principal = self.principal_for(cloud_user_id)
        installation = self.get_installation()
        if installation is None:
            raise IdentityBindingError("Installation is not bound")
        with self.database.transaction() as connection:
            membership_row = connection.execute(
                """
                SELECT * FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (installation.id, cloud_user_id),
            ).fetchone()
        if membership_row is None:
            raise IdentityBindingError("User is not an installation member")
        membership = self._membership(membership_row)
        token = secrets.token_urlsafe(32)
        digest = self._token_digest(token)
        now_dt = utc_now()
        now = now_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        expires_at = now_dt + lifetime
        expires = expires_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                INSERT INTO local_login_sessions(
                    token_digest,installation_id,actor_user_id,role_snapshot,
                    membership_epoch,access_epoch,local_session_epoch,
                    account_session_epoch,client_scope,created_at,expires_at,
                    last_access_check_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    digest,
                    principal.installation_id,
                    principal.actor_user_id,
                    principal.role.value,
                    principal.membership_epoch,
                    installation.access_epoch,
                    installation.local_session_epoch,
                    membership.account_session_epoch,
                    client_scope,
                    now,
                    expires,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM local_login_sessions WHERE token_digest=?",
                (digest,),
            ).fetchone()
            assert row is not None
            return token, self._local_session(row)

    def authorize_local_session(self, token: str | None) -> RequestPrincipal | None:
        """Resolve a cookie only while its installation and membership remain valid."""

        if not token:
            return None
        try:
            digest = self._token_digest(token)
        except UnicodeEncodeError:
            return None
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_login_sessions WHERE token_digest=?",
                (digest,),
            ).fetchone()
        if row is None:
            return None
        session = self._local_session(row)
        now_dt = utc_now()
        if (
            session.expires_at <= now_dt
            or session.last_access_check_at + LOCAL_SESSION_IDLE_TIMEOUT <= now_dt
        ):
            self.revoke_local_session(token)
            return None
        try:
            principal = self.principal_for(session.actor_user_id)
        except IdentityBindingError:
            return None
        if (
            principal.installation_id != session.installation_id
            or principal.membership_epoch != session.membership_epoch
            or principal.role != session.role_snapshot
        ):
            return None
        installation = self.get_installation()
        with self.database.transaction() as connection:
            membership_row = connection.execute(
                """
                SELECT account_session_epoch FROM installation_memberships
                WHERE installation_id=? AND cloud_user_id=?
                """,
                (session.installation_id, session.actor_user_id),
            ).fetchone()
        if (
            installation is None
            or membership_row is None
            or installation.access_epoch != session.access_epoch
            or installation.local_session_epoch != session.local_session_epoch
            or int(membership_row["account_session_epoch"])
            != session.account_session_epoch
        ):
            self.revoke_local_session(token)
            return None
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE local_login_sessions SET last_access_check_at=?
                WHERE token_digest=?
                """,
                (now, digest),
            )
        return replace(principal, client_scope=session.client_scope)

    def refresh_local_session(
        self,
        token: str | None,
        *,
        renewal_window: timedelta = LOCAL_SESSION_RENEWAL_WINDOW,
    ) -> tuple[str, RequestPrincipal, bool] | None:
        """Rotate an active desktop session when its absolute expiry is near."""

        if renewal_window < timedelta(0) or renewal_window > LOCAL_SESSION_LIFETIME:
            raise ValueError("Local session renewal window is invalid")
        principal = self.authorize_local_session(token)
        if principal is None or token is None:
            return None
        try:
            digest = self._token_digest(token)
        except UnicodeEncodeError:
            return None
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM local_login_sessions WHERE token_digest=?",
                (digest,),
            ).fetchone()
        if row is None:
            return None
        session = self._local_session(row)
        if session.expires_at > utc_now() + renewal_window:
            return token, principal, False
        new_token, _ = self.create_local_session(
            session.actor_user_id,
            lifetime=LOCAL_SESSION_LIFETIME,
            client_scope=session.client_scope,
        )
        self.revoke_local_session(token)
        return new_token, principal, True

    def revoke_local_session(self, token: str | None) -> None:
        if not token:
            return
        try:
            digest = self._token_digest(token)
        except UnicodeEncodeError:
            return
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "DELETE FROM local_login_sessions WHERE token_digest=?",
                (digest,),
            )


def user_singleton_key(
    package_id: str,
    actor_user_id: str,
    client_scope: str = "desktop",
) -> str:
    """Return one stable user singleton key without conflating installations."""

    validate_identity(package_id, "package_id")
    validate_identity(actor_user_id, "actor_user_id")
    validate_identity(client_scope, "client_scope")
    if package_id == "ai2apps.general-chat" and actor_user_id == "local":
        return BUILTIN_CHAT_SINGLETON_KEY
    base = f"{package_id}:user:{actor_user_id}"
    if client_scope == "desktop":
        return base
    return f"{base}:client:{client_scope}"
