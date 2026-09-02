"""Durable ACPF Provisioning Session storage."""

from __future__ import annotations

import json
import uuid
from typing import Any

from ai2apps.core import utc_now_text
from ai2apps.storage.database import PlatformDatabase

ACTIVE_STATUSES = frozenset(
    {
        "planning",
        "awaiting_confirmation",
        "installing_runtime",
        "awaiting_restart",
        "installing_provider",
        "downloading_checkpoint",
        "activating",
        "verifying",
    }
)
TERMINAL_STATUSES = frozenset({"ready", "failed", "cancelled", "unsupported"})


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


class ProvisioningSessionRepository:
    def __init__(self, database: PlatformDatabase) -> None:
        self.database = database

    @staticmethod
    def _record(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "actorId": row["actor_id"],
            "installationId": row["installation_id"],
            "appInstanceId": row["app_instance_id"],
            "appId": row["app_id"],
            "capability": row["capability"],
            "actionId": row["action_id"],
            "status": row["status"],
            "profileId": row["profile_id"],
            "requestFingerprint": row["request_fingerprint"],
            "plan": json.loads(row["plan_json"]),
            "intent": json.loads(row["intent_json"]),
            "operations": json.loads(row["operations_json"]),
            "progress": json.loads(row["progress_json"]),
            "error": None
            if row["error_json"] is None
            else json.loads(row["error_json"]),
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "completedAt": row["completed_at"],
        }

    def get(self, session_id: str) -> dict[str, Any] | None:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM provisioning_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return None if row is None else self._record(row)

    def find_active(
        self,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        app_id: str,
        capability: str,
        action_id: str,
        request_fingerprint: str,
    ) -> dict[str, Any] | None:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        with self.database.transaction() as connection:
            row = connection.execute(
                f"""SELECT * FROM provisioning_sessions
                    WHERE actor_id = ? AND installation_id = ?
                      AND app_instance_id = ? AND app_id = ?
                      AND capability = ? AND action_id = ?
                      AND request_fingerprint = ?
                      AND status IN ({placeholders})
                    ORDER BY updated_at DESC LIMIT 1""",
                (
                    actor_id,
                    installation_id,
                    app_instance_id,
                    app_id,
                    capability,
                    action_id,
                    request_fingerprint,
                    *sorted(ACTIVE_STATUSES),
                ),
            ).fetchone()
        return None if row is None else self._record(row)

    def create(
        self,
        *,
        actor_id: str,
        installation_id: str,
        app_instance_id: str,
        app_id: str,
        capability: str,
        action_id: str,
        status: str,
        profile_id: str | None,
        request_fingerprint: str,
        plan: dict[str, Any],
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self.find_active(
            actor_id=actor_id,
            installation_id=installation_id,
            app_instance_id=app_instance_id,
            app_id=app_id,
            capability=capability,
            action_id=action_id,
            request_fingerprint=request_fingerprint,
        )
        if existing is not None:
            return existing
        session_id = "prv_" + uuid.uuid4().hex
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """INSERT INTO provisioning_sessions(
                    id,actor_id,installation_id,app_instance_id,app_id,capability,
                    action_id,status,profile_id,request_fingerprint,plan_json,
                    intent_json,operations_json,progress_json,error_json,created_at,
                    updated_at,completed_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    session_id,
                    actor_id,
                    installation_id,
                    app_instance_id,
                    app_id,
                    capability,
                    action_id,
                    status,
                    profile_id,
                    request_fingerprint,
                    _json(plan),
                    _json(intent),
                    "[]",
                    _json({"phase": status, "percent": 0}),
                    None,
                    now,
                    now,
                ),
            )
        record = self.get(session_id)
        assert record is not None
        return record

    def update(
        self,
        session_id: str,
        *,
        status: str | None = None,
        plan: dict[str, Any] | None = None,
        intent: dict[str, Any] | None = None,
        operations: list[dict[str, Any]] | None = None,
        progress: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
        clear_error: bool = False,
    ) -> dict[str, Any]:
        current = self.get(session_id)
        if current is None:
            raise KeyError(session_id)
        next_status = status or current["status"]
        now = utc_now_text()
        completed = now if next_status in TERMINAL_STATUSES else current["completedAt"]
        next_error = (
            None if clear_error else (error if error is not None else current["error"])
        )
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE provisioning_sessions SET status=?,plan_json=?,intent_json=?,
                    operations_json=?,progress_json=?,error_json=?,updated_at=?,
                    completed_at=? WHERE id=?""",
                (
                    next_status,
                    _json(plan if plan is not None else current["plan"]),
                    _json(intent if intent is not None else current["intent"]),
                    _json(
                        operations if operations is not None else current["operations"]
                    ),
                    _json(progress if progress is not None else current["progress"]),
                    None if next_error is None else _json(next_error),
                    now,
                    completed,
                    session_id,
                ),
            )
        record = self.get(session_id)
        assert record is not None
        return record

    def list_active(self, *, actor_id: str | None = None) -> tuple[dict[str, Any], ...]:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        query = f"SELECT * FROM provisioning_sessions WHERE status IN ({placeholders})"
        params: list[Any] = list(sorted(ACTIVE_STATUSES))
        if actor_id is not None:
            query += " AND actor_id = ?"
            params.append(actor_id)
        query += " ORDER BY updated_at DESC"
        with self.database.transaction() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._record(row) for row in rows)

    def list_returnable(
        self, *, actor_id: str | None = None
    ) -> tuple[dict[str, Any], ...]:
        """List active or just-finished sessions whose return intent is unconsumed."""

        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        query = f"""SELECT * FROM provisioning_sessions
            WHERE (
                status IN ({placeholders})
                OR (
                    status = 'ready'
                    AND json_extract(intent_json, '$.returnTo') IS NOT NULL
                    AND json_extract(intent_json, '$.returnAcknowledgedAt') IS NULL
                )
            )"""
        params: list[Any] = list(sorted(ACTIVE_STATUSES))
        if actor_id is not None:
            query += " AND actor_id = ?"
            params.append(actor_id)
        query += " ORDER BY updated_at DESC"
        with self.database.transaction() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return tuple(self._record(row) for row in rows)

    def acknowledge_return(self, session_id: str) -> dict[str, Any]:
        current = self.get(session_id)
        if current is None:
            raise KeyError(session_id)
        intent = dict(current["intent"])
        if intent.get("returnAcknowledgedAt"):
            return current
        intent["returnAcknowledgedAt"] = utc_now_text()
        return self.update(session_id, intent=intent)
