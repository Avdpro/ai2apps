"""Structured Message persistence with Session-scoped idempotency."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

from ai2apps.core import (
    EntityIdKind,
    IdempotencyConflictError,
    MessageRole,
    MessageStatus,
    ResourceConflictError,
    ResourceNotFoundError,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage.database import PlatformDatabase
from ai2apps.storage.models import (
    AppendMessageResult,
    MessagePartInput,
    MessagePartRecord,
    MessageWithParts,
)
from ai2apps.storage.records import (
    canonical_json,
    event_from_row,
    message_from_row,
    message_part_from_row,
)


class MessageRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        event_store: EventStore | None = None,
    ) -> None:
        self.database = database
        self.events = event_store or EventStore(database)

    @staticmethod
    def _load(
        connection: sqlite3.Connection,
        message_id: str,
    ) -> MessageWithParts | None:
        row = connection.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if row is None:
            return None
        part_rows = connection.execute(
            "SELECT * FROM message_parts WHERE message_id = ? ORDER BY position",
            (message_id,),
        ).fetchall()
        return MessageWithParts(
            message=message_from_row(row),
            parts=tuple(message_part_from_row(part) for part in part_rows),
        )

    @staticmethod
    def _same_request(
        existing: MessageWithParts,
        *,
        role: MessageRole,
        status: MessageStatus,
        metadata: dict[str, Any],
        parts: Sequence[MessagePartInput],
    ) -> bool:
        return (
            existing.message.role is role
            and existing.message.status is status
            and existing.message.metadata == metadata
            and tuple((part.kind, part.content) for part in existing.parts)
            == tuple((part.kind, part.content) for part in parts)
        )

    def append(
        self,
        *,
        session_id: str,
        role: MessageRole,
        parts: Sequence[MessagePartInput],
        status: MessageStatus = MessageStatus.COMPLETED,
        idempotency_key: str | None = None,
        metadata: dict[str, Any] | None = None,
        app_instance_id: str | None = None,
        trace_id: str | None = None,
    ) -> AppendMessageResult:
        if not parts:
            raise ValueError("A Message must contain at least one part")
        if any(not part.kind for part in parts):
            raise ValueError("Message part kind must not be empty")
        metadata_value = metadata or {}

        try:
            with self.database.transaction(write=True) as connection:
                session = connection.execute(
                    "SELECT app_instance_id, status FROM sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
                if session is None or (
                    app_instance_id is not None
                    and session["app_instance_id"] != app_instance_id
                ):
                    raise ResourceNotFoundError("session", session_id)
                if session["status"] == "deleted":
                    raise ResourceConflictError(
                        f"Cannot append a Message to deleted Session {session_id}"
                    )
                owner_id = str(session["app_instance_id"])

                if idempotency_key is not None:
                    existing_row = connection.execute(
                        """
                        SELECT id FROM messages
                        WHERE session_id = ? AND idempotency_key = ?
                        """,
                        (session_id, idempotency_key),
                    ).fetchone()
                    if existing_row is not None:
                        existing = self._load(connection, existing_row["id"])
                        assert existing is not None
                        if not self._same_request(
                            existing,
                            role=role,
                            status=status,
                            metadata=metadata_value,
                            parts=parts,
                        ):
                            raise IdempotencyConflictError(
                                session_id, idempotency_key
                            )
                        event_row = connection.execute(
                            """
                            SELECT * FROM events
                            WHERE subject_id = ? AND type = 'message.created'
                            ORDER BY sequence DESC LIMIT 1
                            """,
                            (existing.message.id,),
                        ).fetchone()
                        return AppendMessageResult(
                            value=existing,
                            event=None if event_row is None else event_from_row(event_row),
                            created=False,
                        )

                message_id = new_entity_id(EntityIdKind.MESSAGE)
                now = utc_now_text()
                next_sequence = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sequence), 0) + 1
                        FROM messages WHERE session_id = ?
                        """,
                        (session_id,),
                    ).fetchone()[0]
                )
                connection.execute(
                    """
                    INSERT INTO messages(
                        id, session_id, sequence, role, status,
                        idempotency_key, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        session_id,
                        next_sequence,
                        role.value,
                        status.value,
                        idempotency_key,
                        canonical_json(metadata_value),
                        now,
                        now,
                    ),
                )
                part_records: list[MessagePartRecord] = []
                for position, part in enumerate(parts):
                    part_id = new_entity_id(EntityIdKind.MESSAGE_PART)
                    connection.execute(
                        """
                        INSERT INTO message_parts(
                            id, message_id, position, kind, content_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            part_id,
                            message_id,
                            position,
                            part.kind,
                            canonical_json(part.content),
                            now,
                        ),
                    )
                    part_row = connection.execute(
                        "SELECT * FROM message_parts WHERE id = ?", (part_id,)
                    ).fetchone()
                    assert part_row is not None
                    part_records.append(message_part_from_row(part_row))

                message_row = connection.execute(
                    "SELECT * FROM messages WHERE id = ?", (message_id,)
                ).fetchone()
                assert message_row is not None
                value = MessageWithParts(
                    message=message_from_row(message_row),
                    parts=tuple(part_records),
                )
                event = self.events.append_in_transaction(
                    connection,
                    event_type="message.created",
                    subject_id=message_id,
                    app_instance_id=owner_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "part_ids": [part.id for part in part_records],
                        "role": role.value,
                        "sequence": next_sequence,
                    },
                )
                return AppendMessageResult(value=value, event=event, created=True)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get(
        self,
        message_id: str,
        *,
        session_id: str | None = None,
    ) -> MessageWithParts:
        with self.database.transaction() as connection:
            value = self._load(connection, message_id)
        if value is None or (
            session_id is not None and value.message.session_id != session_id
        ):
            raise ResourceNotFoundError("message", message_id)
        return value

    def list_for_session(
        self,
        session_id: str,
        *,
        app_instance_id: str | None = None,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> tuple[MessageWithParts, ...]:
        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        with self.database.transaction() as connection:
            session = connection.execute(
                "SELECT app_instance_id FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
            if session is None or (
                app_instance_id is not None
                and session["app_instance_id"] != app_instance_id
            ):
                raise ResourceNotFoundError("session", session_id)
            rows = connection.execute(
                """
                SELECT id FROM messages
                WHERE session_id = ? AND sequence > ?
                ORDER BY sequence LIMIT ?
                """,
                (session_id, after_sequence, limit),
            ).fetchall()
            values = tuple(self._load(connection, row["id"]) for row in rows)
        return tuple(value for value in values if value is not None)
