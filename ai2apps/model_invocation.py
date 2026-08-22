"""Trusted identity and cache ownership for model invocations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    RequestPrincipal,
)
from ai2apps.storage.database import PlatformDatabase


@dataclass(frozen=True, slots=True)
class ModelInvocationContext:
    """Server-derived actor, payer, and device-local model cache boundary."""

    actor_user_id: str
    installation_id: str
    organization_id: str
    billing_account_id: str
    membership_epoch: int
    session_id: str
    authentication_type: str
    app_instance_id: str | None = None

    @classmethod
    def from_principal(
        cls,
        principal: RequestPrincipal,
        *,
        session_id: str,
        app_instance_id: str | None = None,
    ) -> ModelInvocationContext:
        return cls(
            actor_user_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            organization_id=principal.organization_id,
            billing_account_id=principal.billing_account_id,
            membership_epoch=principal.membership_epoch,
            session_id=session_id,
            authentication_type=principal.authentication_type,
            app_instance_id=app_instance_id,
        )

    @classmethod
    def for_session(
        cls,
        database: PlatformDatabase,
        session_id: str,
    ) -> ModelInvocationContext:
        """Resolve identity from Session ownership, never from model payload."""

        with database.transaction() as connection:
            row = connection.execute(
                """
                SELECT i.owner_user_id, i.id AS app_instance_id
                FROM sessions s
                JOIN app_instances i ON i.id=s.app_instance_id
                WHERE s.id=? AND s.status='active'
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Active Session not found: {session_id}")
        owner_user_id = row["owner_user_id"]
        if owner_user_id is not None:
            try:
                principal = IdentityRepository(database).principal_for(owner_user_id)
            except IdentityBindingError as error:
                raise ValueError(
                    "Session owner is not an active installation member"
                ) from error
        else:
            principal = RequestPrincipal.legacy_local()
        return cls.from_principal(
            principal,
            session_id=session_id,
            app_instance_id=row["app_instance_id"],
        )

    @property
    def cache_namespace(self) -> str:
        """Opaque, stable namespace unique to actor + installation + Session."""

        material = "\0".join(
            (
                "ai2apps-model-cache-v1",
                self.installation_id,
                self.actor_user_id,
                str(self.membership_epoch),
                self.session_id,
            )
        ).encode("utf-8")
        return "a2c-" + hashlib.sha256(material).hexdigest()[:40]

    def audit_payload(self) -> dict[str, str | int]:
        return {
            "actor_user_id": self.actor_user_id,
            "installation_id": self.installation_id,
            "organization_id": self.organization_id,
            "billing_account_id": self.billing_account_id,
            "membership_epoch": self.membership_epoch,
            "authentication_type": self.authentication_type,
            "cache_namespace": self.cache_namespace,
        }
