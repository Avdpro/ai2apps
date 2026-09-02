"""Durable, content-free audit state for Model Worker operator actions."""

from __future__ import annotations

import json
from typing import Any

from ai2apps.core import EntityIdKind, new_entity_id, utc_now_text
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


class WorkerOperationIdempotencyConflictError(RuntimeError):
    """One action-scoped key was replayed with a different Generation."""


class WorkerManagementRepository:
    def __init__(self, database: PlatformDatabase, events: EventStore) -> None:
        self.database = database
        self.events = events

    @staticmethod
    def _operation(row) -> dict[str, Any]:
        return {
            "operationId": row["id"],
            "serviceKey": row["service_key"],
            "action": row["action"],
            "status": row["status"],
            "expectedGeneration": row["expected_generation"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "completedAt": row["completed_at"],
            "result": None if row["result_json"] is None else json.loads(row["result_json"]),
            "error": None if row["error_json"] is None else json.loads(row["error_json"]),
        }

    def pinned_workers(self) -> tuple[str, ...]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT service_key FROM worker_preferences WHERE pinned=1 ORDER BY service_key"
            ).fetchall()
        return tuple(row[0] for row in rows)

    def set_pinned(self, service_key: str, pinned: bool) -> None:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO worker_preferences(service_key,pinned,updated_at)
                   VALUES(?,?,?) ON CONFLICT(service_key) DO UPDATE SET
                   pinned=excluded.pinned,updated_at=excluded.updated_at""",
                (service_key, int(pinned), now),
            )
            self.events.append_in_transaction(
                connection,
                event_type="worker.preference.changed",
                subject_id=service_key,
                payload={"pinned": pinned},
            )

    def begin(
        self,
        service_key: str,
        action: str,
        *,
        expected_generation: int | None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    """SELECT * FROM worker_operations
                       WHERE service_key=? AND action=? AND idempotency_key=?""",
                    (service_key, action, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing["expected_generation"] != expected_generation:
                        raise WorkerOperationIdempotencyConflictError(
                            "Idempotency key was already used with another Generation"
                        )
                    value = self._operation(existing)
                    value["_reused"] = True
                    return value
            operation_id = new_entity_id(EntityIdKind.WORKER_OPERATION)
            connection.execute(
                """INSERT INTO worker_operations(
                   id,service_key,action,status,expected_generation,idempotency_key,
                   created_at,updated_at) VALUES(?,?,?,'pending',?,?,?,?)""",
                (
                    operation_id,
                    service_key,
                    action,
                    expected_generation,
                    idempotency_key,
                    now,
                    now,
                ),
            )
            self.events.append_in_transaction(
                connection,
                event_type="worker.operation.created",
                subject_id=service_key,
                payload={
                    "operation_id": operation_id,
                    "action": action,
                    "expected_generation": expected_generation,
                },
            )
            row = connection.execute(
                "SELECT * FROM worker_operations WHERE id=?", (operation_id,)
            ).fetchone()
        value = self._operation(row)
        value["_reused"] = False
        return value

    def apply_pin(
        self,
        service_key: str,
        pinned: bool,
        *,
        expected_generation: int | None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Atomically persist a Pin preference, completed operation, and audit."""

        action = "pin" if pinned else "unpin"
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            if idempotency_key is not None:
                existing = connection.execute(
                    """SELECT * FROM worker_operations WHERE
                       service_key=? AND action=? AND idempotency_key=?""",
                    (service_key, action, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing["expected_generation"] != expected_generation:
                        raise WorkerOperationIdempotencyConflictError(
                            "Idempotency key was already used with another Generation"
                        )
                    value = self._operation(existing)
                    value["_reused"] = True
                    return value
            operation_id = new_entity_id(EntityIdKind.WORKER_OPERATION)
            result = {"pinned": pinned}
            connection.execute(
                """INSERT INTO worker_operations(
                   id,service_key,action,status,expected_generation,idempotency_key,
                   result_json,created_at,updated_at,completed_at)
                   VALUES(?,?,?,'completed',?,?,?,?,?,?)""",
                (
                    operation_id,
                    service_key,
                    action,
                    expected_generation,
                    idempotency_key,
                    _json(result),
                    now,
                    now,
                    now,
                ),
            )
            connection.execute(
                """INSERT INTO worker_preferences(service_key,pinned,updated_at)
                   VALUES(?,?,?) ON CONFLICT(service_key) DO UPDATE SET
                   pinned=excluded.pinned,updated_at=excluded.updated_at""",
                (service_key, int(pinned), now),
            )
            self.events.append_in_transaction(
                connection,
                event_type="worker.preference.changed",
                subject_id=service_key,
                payload={"operation_id": operation_id, "pinned": pinned},
            )
            self.events.append_in_transaction(
                connection,
                event_type="worker.operation.updated",
                subject_id=service_key,
                payload={
                    "operation_id": operation_id,
                    "action": action,
                    "status": "completed",
                    "error_code": None,
                },
            )
            row = connection.execute(
                "SELECT * FROM worker_operations WHERE id=?", (operation_id,)
            ).fetchone()
        value = self._operation(row)
        value["_reused"] = False
        return value

    def replay(
        self,
        service_key: str,
        action: str,
        *,
        expected_generation: int | None,
        idempotency_key: str | None,
    ) -> dict[str, Any] | None:
        if idempotency_key is None:
            return None
        with self.database.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM worker_operations WHERE
                   service_key=? AND action=? AND idempotency_key=?""",
                (service_key, action, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        if row["expected_generation"] != expected_generation:
            raise WorkerOperationIdempotencyConflictError(
                "Idempotency key was already used with another Generation"
            )
        return self._operation(row)

    def update(
        self,
        operation_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now_text()
        completed_at = (
            now
            if status in {"completed", "failed", "interrupted", "cancelled"}
            else None
        )
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE worker_operations SET status=?,result_json=?,error_json=?,
                   updated_at=?,completed_at=? WHERE id=?""",
                (
                    status,
                    None if result is None else _json(result),
                    None if error is None else _json(error),
                    now,
                    completed_at,
                    operation_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM worker_operations WHERE id=?", (operation_id,)
            ).fetchone()
            if row is None:
                raise KeyError(operation_id)
            self.events.append_in_transaction(
                connection,
                event_type="worker.operation.updated",
                subject_id=row["service_key"],
                payload={
                    "operation_id": operation_id,
                    "action": row["action"],
                    "status": status,
                    "error_code": None if error is None else error.get("code"),
                },
            )
        return self._operation(row)

    def cancel(self, operation_id: str) -> dict[str, Any] | None:
        current = self.get(operation_id)
        if current is None:
            return None
        if current["status"] not in {"pending", "running"}:
            return current
        return self.update(
            operation_id,
            "cancelled",
            error={
                "code": "operator_cancelled",
                "message": "Worker operation was cancelled by an administrator",
            },
        )

    def get(self, operation_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM worker_operations WHERE id=?", (operation_id,)
            ).fetchone()
        return None if row is None else self._operation(row)

    def list(
        self, *, service_key: str | None = None, limit: int = 50
    ) -> tuple[dict[str, Any], ...]:
        if not 1 <= limit <= 200:
            raise ValueError("limit must be between 1 and 200")
        with self.database.transaction() as connection:
            if service_key is None:
                rows = connection.execute(
                    "SELECT * FROM worker_operations ORDER BY created_at DESC,id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """SELECT * FROM worker_operations WHERE service_key=?
                       ORDER BY created_at DESC,id DESC LIMIT ?""",
                    (service_key, limit),
                ).fetchall()
        return tuple(self._operation(row) for row in rows)

    def recover_interrupted(self) -> int:
        now = utc_now_text()
        error = _json({"code": "runtime_restarted", "message": "Host restarted during operation"})
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                "SELECT id,service_key,action FROM worker_operations WHERE status IN ('pending','running')"
            ).fetchall()
            connection.execute(
                """UPDATE worker_operations SET status='interrupted',error_json=?,
                   updated_at=?,completed_at=? WHERE status IN ('pending','running')""",
                (error, now, now),
            )
            for row in rows:
                self.events.append_in_transaction(
                    connection,
                    event_type="worker.operation.updated",
                    subject_id=row["service_key"],
                    payload={
                        "operation_id": row["id"],
                        "action": row["action"],
                        "status": "interrupted",
                        "error_code": "runtime_restarted",
                    },
                )
        return len(rows)
