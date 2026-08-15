"""Transactional append and cursor replay for semantic platform Events."""

from __future__ import annotations

import sqlite3
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    ResourceNotFoundError,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events.bus import EventNotificationBus
from ai2apps.storage.database import PlatformDatabase
from ai2apps.storage.models import EventRecord
from ai2apps.storage.records import canonical_json, event_from_row


class EventStore:
    """Append-only Event Store using the platform database's global cursor."""

    def __init__(
        self,
        database: PlatformDatabase,
        notifications: EventNotificationBus | None = None,
    ) -> None:
        self.database = database
        self.notifications = notifications

    def append_in_transaction(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        subject_id: str,
        payload: dict[str, Any] | None = None,
        app_instance_id: str | None = None,
        session_id: str | None = None,
        trace_id: str | None = None,
        schema_version: int = 1,
        occurred_at: str | None = None,
    ) -> EventRecord:
        """Append using a caller-owned transaction for atomic state plus Event."""

        event_id = new_entity_id(EntityIdKind.EVENT)
        cursor = connection.execute(
            """
            INSERT INTO events(
                id, type, occurred_at, app_instance_id, session_id,
                subject_id, trace_id, schema_version, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                event_type,
                occurred_at or utc_now_text(),
                app_instance_id,
                session_id,
                subject_id,
                trace_id,
                schema_version,
                canonical_json(payload or {}),
            ),
        )
        row = connection.execute(
            "SELECT * FROM events WHERE sequence = ?", (cursor.lastrowid,)
        ).fetchone()
        assert row is not None
        event = event_from_row(row)
        if self.notifications is not None:
            self.database.after_commit(connection, self.notifications.notify)
        return event

    def append(self, **kwargs: Any) -> EventRecord:
        """Append a standalone Event in its own short transaction."""

        with self.database.transaction(write=True) as connection:
            return self.append_in_transaction(connection, **kwargs)

    def get(self, event_id: str) -> EventRecord:
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("event", event_id)
        return event_from_row(row)

    def latest_for_subject(
        self,
        subject_id: str,
        *,
        event_type: str | None = None,
    ) -> EventRecord | None:
        clauses = ["subject_id = ?"]
        params: list[Any] = [subject_id]
        if event_type is not None:
            clauses.append("type = ?")
            params.append(event_type)
        query = (
            "SELECT * FROM events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY sequence DESC LIMIT 1"
        )
        with self.database.transaction() as connection:
            row = connection.execute(query, params).fetchone()
        return None if row is None else event_from_row(row)

    def list_after(
        self,
        after_sequence: int = 0,
        *,
        session_id: str | None = None,
        app_instance_id: str | None = None,
        subject_id: str | None = None,
        limit: int = 100,
    ) -> tuple[EventRecord, ...]:
        """Replay Events strictly after a durable global sequence cursor."""

        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        clauses = ["sequence > ?"]
        params: list[Any] = [after_sequence]
        if session_id is not None:
            clauses.append("session_id = ?")
            params.append(session_id)
        if app_instance_id is not None:
            clauses.append("app_instance_id = ?")
            params.append(app_instance_id)
        if subject_id is not None:
            clauses.append("subject_id = ?")
            params.append(subject_id)
        params.append(limit)
        query = (
            "SELECT * FROM events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY sequence LIMIT ?"
        )
        with self.database.transaction() as connection:
            rows = connection.execute(query, params).fetchall()
        return tuple(event_from_row(row) for row in rows)
