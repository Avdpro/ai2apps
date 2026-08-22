"""Metadata persistence, Tool scoping, injection, and redaction for secrets."""

from __future__ import annotations

import fnmatch
import json
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    new_entity_id,
    parse_utc,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import PlatformDatabase

from .backends import SecretBackend
from .models import SecretInjection, SecretRecord


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _text_contains_secret(value: str, secret: str) -> bool:
    return value == secret or (len(secret) >= 8 and secret in value)


def _metadata_contains_value(value: Any, secret: str) -> bool:
    if isinstance(value, str):
        return _text_contains_secret(value, secret)
    if isinstance(value, dict):
        return any(
            _metadata_contains_value(key, secret)
            or _metadata_contains_value(item, secret)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_metadata_contains_value(item, secret) for item in value)
    return False


class SecretRepository:
    def __init__(
        self, database: PlatformDatabase, events: EventStore, backend: SecretBackend
    ) -> None:
        self.database = database
        self.events = events
        self.backend = backend

    @staticmethod
    def _record(row) -> SecretRecord:
        return SecretRecord(
            id=row["id"], name=row["name"], purpose=row["purpose"],
            allowed_tools=tuple(json.loads(row["allowed_tools_json"])),
            status=row["status"], metadata=json.loads(row["metadata_json"]),
            created_at=parse_utc(row["created_at"]),
            updated_at=parse_utc(row["updated_at"]),
            deleted_at=None if row["deleted_at"] is None else parse_utc(row["deleted_at"]),
        )

    def create(
        self, *, name: str, value: str, purpose: str = "",
        allowed_tools: tuple[str, ...] = (), metadata: dict[str, Any] | None = None,
    ) -> SecretRecord:
        if not name.strip() or not value:
            raise ValueError("Secret name and value cannot be empty")
        if _text_contains_secret(name, value) or _text_contains_secret(
            purpose, value
        ) or _metadata_contains_value(
            metadata or {}, value
        ):
            raise ValueError("Secret value cannot appear in metadata")
        secret_id = new_entity_id(EntityIdKind.SECRET)
        backend_key = secret_id
        now = utc_now_text()
        self.backend.store(backend_key, value)
        try:
            with self.database.transaction(write=True) as connection:
                connection.execute(
                    """INSERT INTO secret_records(
                       id, name, backend_key, purpose, allowed_tools_json,
                       metadata_json, created_at, updated_at
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (secret_id, name.strip(), backend_key, purpose.strip(),
                     _json(sorted(set(allowed_tools))), _json(metadata or {}), now, now),
                )
                self.events.append_in_transaction(
                    connection, event_type="secret.created", subject_id=secret_id,
                    payload={"name": name.strip(), "allowed_tools": sorted(set(allowed_tools))},
                )
                row = connection.execute(
                    "SELECT * FROM secret_records WHERE id = ?", (secret_id,)
                ).fetchone()
        except Exception:
            self.backend.delete(backend_key)
            raise
        assert row is not None
        return self._record(row)

    def list(self, *, include_deleted: bool = False) -> tuple[SecretRecord, ...]:
        where = "" if include_deleted else "WHERE status = 'active'"
        with self.database.transaction() as connection:
            rows = connection.execute(
                f"SELECT * FROM secret_records {where} ORDER BY name"
            ).fetchall()
        return tuple(self._record(row) for row in rows)

    def get(self, secret_id: str) -> SecretRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE id = ?", (secret_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("secret", secret_id)
        return self._record(row)

    def replace(self, secret_id: str, value: str) -> SecretRecord:
        if not value:
            raise ValueError("Secret value cannot be empty")
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE id = ? AND status = 'active'",
                (secret_id,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("secret", secret_id)
        if (
            _text_contains_secret(str(row["name"]), value)
            or _text_contains_secret(str(row["purpose"]), value)
            or _metadata_contains_value(json.loads(row["metadata_json"]), value)
        ):
            raise ValueError("Secret value cannot appear in metadata")
        self.backend.store(row["backend_key"], value)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                "UPDATE secret_records SET updated_at = ? WHERE id = ?", (now, secret_id)
            )
            self.events.append_in_transaction(
                connection, event_type="secret.replaced", subject_id=secret_id,
                payload={"name": row["name"]},
            )
        return self.get(secret_id)

    def last_use(self, secret_id: str) -> tuple[Any, str | None]:
        """Return audited usage metadata without resolving the secret value."""

        event = self.events.latest_for_subject(
            secret_id, event_type="secret.injected"
        )
        if event is None:
            return None, None
        return event.occurred_at, str(event.payload.get("tool_name") or "") or None

    def delete(self, secret_id: str) -> SecretRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE id = ?", (secret_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("secret", secret_id)
        if row["status"] == "deleted":
            return self._record(row)
        self.backend.delete(row["backend_key"])
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            connection.execute(
                """UPDATE secret_records SET status = 'deleted', deleted_at = ?,
                   updated_at = ? WHERE id = ?""", (now, now, secret_id)
            )
            self.events.append_in_transaction(
                connection, event_type="secret.deleted", subject_id=secret_id,
                payload={"name": row["name"]},
            )
        return self.get(secret_id)

    def _resolve(self, secret_id: str, tool_name: str) -> str:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM secret_records WHERE id = ? AND status = 'active'",
                (secret_id,),
            ).fetchone()
            consumer = connection.execute(
                """
                SELECT s.source,s.execution_mode
                FROM tool_descriptors t
                JOIN service_descriptors s ON s.id=t.service_id
                WHERE t.qualified_name=?
                """,
                (tool_name,),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("secret", secret_id)
        if (
            consumer is not None
            and consumer["source"] == "installed"
            and consumer["execution_mode"] == "external"
        ):
            self.events.append(
                event_type="secret.injection_denied",
                subject_id=secret_id,
                payload={"tool_name": tool_name, "reason": "external_service"},
            )
            raise ResourceConflictError(
                "Installed external Services cannot receive Secret values; "
                "use a managed Service or a Host-brokered provider operation"
            )
        allowed = tuple(json.loads(row["allowed_tools_json"]))
        if not allowed or not any(fnmatch.fnmatchcase(tool_name, item) for item in allowed):
            self.events.append(
                event_type="secret.injection_denied",
                subject_id=secret_id,
                payload={"tool_name": tool_name, "reason": "tool_scope"},
            )
            raise ResourceConflictError(f"Secret {secret_id} is not allowed for {tool_name}")
        value = self.backend.load(row["backend_key"])
        # Record successful disclosure without ever placing the value in
        # SQLite. Denied attempts remain visible through the Tool invocation
        # failure audit, while this event answers which Secret was disclosed.
        self.events.append(
            event_type="secret.injected",
            subject_id=secret_id,
            payload={"tool_name": tool_name},
        )
        return value

    def inject_arguments(self, arguments: dict[str, Any], tool_name: str) -> SecretInjection:
        values: list[str] = []
        ids: list[str] = []

        def inject(value: Any) -> Any:
            if isinstance(value, str) and value.startswith("secret://sec_"):
                secret_id = value.removeprefix("secret://")
                resolved = self._resolve(secret_id, tool_name)
                values.append(resolved)
                ids.append(secret_id)
                return resolved
            if isinstance(value, dict):
                return {key: inject(item) for key, item in value.items()}
            if isinstance(value, list):
                return [inject(item) for item in value]
            return value

        return SecretInjection(inject(arguments), tuple(values), tuple(ids))

    @staticmethod
    def redact(value: Any, sensitive_values: tuple[str, ...] = ()) -> Any:
        if isinstance(value, dict):
            return {key: SecretRepository.redact(item, sensitive_values) for key, item in value.items()}
        if isinstance(value, list):
            return [SecretRepository.redact(item, sensitive_values) for item in value]
        if isinstance(value, str):
            result = value
            for secret in sensitive_values:
                if secret:
                    result = result.replace(secret, "[secret]")
            return result
        return value
