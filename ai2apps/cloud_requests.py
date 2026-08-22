"""Local ownership ledger for requests billed through AI2Apps Cloud."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from ai2apps.core import parse_utc, utc_now_text
from ai2apps.identity import RequestPrincipal
from ai2apps.storage.database import PlatformDatabase


class CloudRequestOwnershipError(RuntimeError):
    """An idempotency key or Cloud request belongs to another local actor."""


@dataclass(frozen=True, slots=True)
class CloudAIRequestRecord:
    idempotency_key: str
    cloud_request_id: str | None
    actor_user_id: str
    installation_id: str
    organization_id: str
    billing_account_id: str
    membership_epoch: int
    operation: str
    model: str
    status: str
    created_at: datetime
    updated_at: datetime


class CloudAIRequestRepository:
    """Persist metadata only; prompts, outputs, and credentials never enter it."""

    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _record(row: sqlite3.Row) -> CloudAIRequestRecord:
        return CloudAIRequestRecord(
            idempotency_key=row["idempotency_key"],
            cloud_request_id=row["cloud_request_id"],
            actor_user_id=row["actor_user_id"],
            installation_id=row["installation_id"],
            organization_id=row["organization_id"],
            billing_account_id=row["billing_account_id"],
            membership_epoch=int(row["membership_epoch"]),
            operation=row["operation"],
            model=row["model"],
            status=row["status"],
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
        )

    def begin(
        self,
        principal: RequestPrincipal,
        *,
        idempotency_key: str,
        operation: str,
        model: str,
    ) -> CloudAIRequestRecord:
        """Create or validate an idempotent retry by the same local actor."""

        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            row = connection.execute(
                "SELECT * FROM cloud_ai_requests WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if row is None:
                connection.execute(
                    """
                    INSERT INTO cloud_ai_requests(
                        idempotency_key,cloud_request_id,actor_user_id,
                        installation_id,organization_id,billing_account_id,
                        membership_epoch,operation,model,status,created_at,updated_at
                    ) VALUES (?,NULL,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        idempotency_key,
                        principal.actor_user_id,
                        principal.installation_id,
                        principal.organization_id,
                        principal.billing_account_id,
                        principal.membership_epoch,
                        operation,
                        model[:500],
                        "requested",
                        now,
                        now,
                    ),
                )
                row = connection.execute(
                    "SELECT * FROM cloud_ai_requests WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
            else:
                existing = self._record(row)
                if (
                    existing.actor_user_id != principal.actor_user_id
                    or existing.installation_id != principal.installation_id
                    or existing.operation != operation
                    or existing.model != model[:500]
                ):
                    raise CloudRequestOwnershipError(
                        "Idempotency key is already owned by another model request"
                    )
            assert row is not None
            return self._record(row)

    def bind_cloud_request_id(
        self,
        idempotency_key: str,
        cloud_request_id: str,
        *,
        status: str = "in_progress",
    ) -> CloudAIRequestRecord:
        if not 1 <= len(cloud_request_id) <= 200:
            raise ValueError("cloud_request_id must contain 1 to 200 characters")
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                cursor = connection.execute(
                    """
                    UPDATE cloud_ai_requests
                    SET cloud_request_id=COALESCE(cloud_request_id, ?),
                        status=?, updated_at=?
                    WHERE idempotency_key=?
                      AND (cloud_request_id IS NULL OR cloud_request_id=?)
                    """,
                    (
                        cloud_request_id,
                        status,
                        now,
                        idempotency_key,
                        cloud_request_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise CloudRequestOwnershipError(
                        "Cloud request identity conflicts with its idempotency key"
                    )
                row = connection.execute(
                    "SELECT * FROM cloud_ai_requests WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                assert row is not None
                return self._record(row)
        except sqlite3.IntegrityError as error:
            raise CloudRequestOwnershipError(
                "Cloud request ID is already owned by another local request"
            ) from error

    def set_status(self, idempotency_key: str, status: str) -> None:
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """
                UPDATE cloud_ai_requests SET status=?, updated_at=?
                WHERE idempotency_key=?
                """,
                (status, utc_now_text(), idempotency_key),
            )

    def get_by_cloud_request_id(
        self, cloud_request_id: str
    ) -> CloudAIRequestRecord | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM cloud_ai_requests WHERE cloud_request_id=?",
                (cloud_request_id,),
            ).fetchone()
        return None if row is None else self._record(row)

    def authorize(
        self,
        principal: RequestPrincipal,
        cloud_request_id: str,
        *,
        allow_core_override: bool = True,
    ) -> CloudAIRequestRecord | None:
        record = self.get_by_cloud_request_id(cloud_request_id)
        if record is None:
            return None
        if (allow_core_override and principal.is_core) or (
            record.installation_id == principal.installation_id
            and record.actor_user_id == principal.actor_user_id
        ):
            return record
        return None
