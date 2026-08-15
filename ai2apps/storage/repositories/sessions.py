"""ConversationSession persistence with optimistic revisions."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Any

from ai2apps.config import DEFAULT_TEMPORARY_SESSION_TTL_SECONDS
from ai2apps.core import (
    EntityIdKind,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
    SessionKind,
    SessionRetention,
    SessionStatus,
    SessionVisibility,
    format_utc,
    new_entity_id,
    parse_utc,
    utc_now,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage.database import PlatformDatabase
from ai2apps.storage.models import SessionRecord
from ai2apps.storage.records import canonical_json, session_from_row


class SessionRepository:
    def __init__(
        self,
        database: PlatformDatabase,
        event_store: EventStore | None = None,
    ) -> None:
        self.database = database
        self.events = event_store or EventStore(database)

    def create(
        self,
        *,
        app_instance_id: str,
        title: str = "",
        is_home: bool = False,
        session_kind: SessionKind = SessionKind.APP,
        visibility: SessionVisibility = SessionVisibility.LISTED,
        retention: SessionRetention = SessionRetention.DURABLE,
        expires_at: str | None = None,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> SessionRecord:
        session_id = new_entity_id(EntityIdKind.SESSION)
        now_value = utc_now()
        now = format_utc(now_value)
        if retention is SessionRetention.TEMPORARY and expires_at is None:
            expires_at = format_utc(
                now_value + timedelta(seconds=DEFAULT_TEMPORARY_SESSION_TTL_SECONDS)
            )
        elif retention is SessionRetention.DURABLE and expires_at is not None:
            raise ValueError("Durable Sessions cannot have expires_at")
        if expires_at is not None:
            parse_utc(expires_at)
        try:
            with self.database.transaction(write=True) as connection:
                owner = connection.execute(
                    "SELECT id FROM app_instances WHERE id = ?", (app_instance_id,)
                ).fetchone()
                if owner is None:
                    raise ResourceNotFoundError("app_instance", app_instance_id)
                connection.execute(
                    """
                    INSERT INTO sessions(
                        id, app_instance_id, title, is_home, session_kind,
                        visibility, retention, expires_at, metadata_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        app_instance_id,
                        title,
                        int(is_home),
                        session_kind.value,
                        visibility.value,
                        retention.value,
                        expires_at,
                        canonical_json(metadata or {}),
                        now,
                        now,
                    ),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="session.created",
                    subject_id=session_id,
                    app_instance_id=app_instance_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "is_home": is_home,
                        "retention": retention.value,
                        "session_kind": session_kind.value,
                        "title": title,
                        "visibility": visibility.value,
                    },
                )
                row = connection.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                assert row is not None
                return session_from_row(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get(
        self,
        session_id: str,
        *,
        app_instance_id: str | None = None,
    ) -> SessionRecord:
        query = "SELECT * FROM sessions WHERE id = ?"
        params: tuple[Any, ...] = (session_id,)
        if app_instance_id is not None:
            query += " AND app_instance_id = ?"
            params += (app_instance_id,)
        with self.database.transaction() as connection:
            row = connection.execute(query, params).fetchone()
        if row is None:
            raise ResourceNotFoundError("session", session_id)
        return session_from_row(row)

    def list_for_instance(
        self,
        app_instance_id: str,
        *,
        include_deleted: bool = False,
        session_kind: SessionKind | None = None,
        visibility: SessionVisibility | None = None,
        limit: int = 100,
    ) -> tuple[SessionRecord, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        query = "SELECT * FROM sessions WHERE app_instance_id = ?"
        params: list[Any] = [app_instance_id]
        if not include_deleted:
            query += " AND status != 'deleted'"
        if session_kind is not None:
            query += " AND session_kind = ?"
            params.append(session_kind.value)
        if visibility is not None:
            query += " AND visibility = ?"
            params.append(visibility.value)
        query += " ORDER BY is_home DESC, updated_at DESC, id LIMIT ?"
        params.append(limit)
        with self.database.transaction() as connection:
            owner = connection.execute(
                "SELECT id FROM app_instances WHERE id = ?", (app_instance_id,)
            ).fetchone()
            if owner is None:
                raise ResourceNotFoundError("app_instance", app_instance_id)
            rows = connection.execute(query, params).fetchall()
        return tuple(session_from_row(row) for row in rows)

    def update(
        self,
        session_id: str,
        *,
        expected_revision: int,
        app_instance_id: str | None = None,
        title: str | None = None,
        status: SessionStatus | None = None,
        is_home: bool | None = None,
        metadata: dict[str, Any] | None = None,
        visibility: SessionVisibility | None = None,
        retention: SessionRetention | None = None,
        trace_id: str | None = None,
    ) -> SessionRecord:
        changes: dict[str, Any] = {}
        if title is not None:
            changes["title"] = title
        if status is not None:
            changes["status"] = status.value
        if is_home is not None:
            changes["is_home"] = int(is_home)
        if metadata is not None:
            changes["metadata_json"] = canonical_json(metadata)
        if visibility is not None:
            changes["visibility"] = visibility.value
        if retention is not None:
            changes["retention"] = retention.value
        if not changes:
            raise ValueError("At least one Session field must change")

        now_value = utc_now()
        now = format_utc(now_value)
        if retention is SessionRetention.TEMPORARY:
            changes["expires_at"] = format_utc(
                now_value + timedelta(seconds=DEFAULT_TEMPORARY_SESSION_TTL_SECONDS)
            )
        elif retention is SessionRetention.DURABLE:
            changes["expires_at"] = None
        if status is SessionStatus.ARCHIVED:
            changes["archived_at"] = now
            changes["deleted_at"] = None
        elif status is SessionStatus.DELETED:
            changes["deleted_at"] = now
        elif status is SessionStatus.ACTIVE:
            changes["archived_at"] = None
            changes["deleted_at"] = None
        changes["updated_at"] = now

        assignments = [f"{column} = ?" for column in changes]
        assignments.append("revision = revision + 1")
        params = list(changes.values())
        where = "id = ? AND revision = ?"
        params.extend((session_id, expected_revision))
        if app_instance_id is not None:
            where += " AND app_instance_id = ?"
            params.append(app_instance_id)

        try:
            with self.database.transaction(write=True) as connection:
                cursor = connection.execute(
                    f"UPDATE sessions SET {', '.join(assignments)} WHERE {where}",
                    params,
                )
                if cursor.rowcount == 0:
                    current = connection.execute(
                        "SELECT revision, app_instance_id FROM sessions WHERE id = ?",
                        (session_id,),
                    ).fetchone()
                    if current is None or (
                        app_instance_id is not None
                        and current["app_instance_id"] != app_instance_id
                    ):
                        raise ResourceNotFoundError("session", session_id)
                    raise RevisionConflictError(
                        session_id,
                        expected_revision,
                        int(current["revision"]),
                    )
                row = connection.execute(
                    "SELECT * FROM sessions WHERE id = ?", (session_id,)
                ).fetchone()
                assert row is not None
                updated = session_from_row(row)
                event_type = (
                    "session.archived"
                    if status is SessionStatus.ARCHIVED
                    else "session.deleted"
                    if status is SessionStatus.DELETED
                    else "session.updated"
                )
                self.events.append_in_transaction(
                    connection,
                    event_type=event_type,
                    subject_id=session_id,
                    app_instance_id=updated.app_instance_id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "changed_fields": sorted(changes),
                        "revision": updated.revision,
                    },
                )
                return updated
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def expire_temporary(
        self,
        *,
        now: str | None = None,
        limit: int = 100,
    ) -> tuple[SessionRecord, ...]:
        """Soft-delete one bounded batch of expired temporary Sessions."""

        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        cutoff = now or utc_now_text()
        parse_utc(cutoff)
        expired: list[SessionRecord] = []
        with self.database.transaction(write=True) as connection:
            rows = connection.execute(
                """
                SELECT id FROM sessions
                WHERE retention = 'temporary'
                  AND status != 'deleted'
                  AND expires_at <= ?
                ORDER BY expires_at, id
                LIMIT ?
                """,
                (cutoff, limit),
            ).fetchall()
            for candidate in rows:
                connection.execute(
                    """
                    UPDATE sessions
                    SET status = 'deleted', deleted_at = ?, updated_at = ?,
                        revision = revision + 1
                    WHERE id = ? AND status != 'deleted'
                    """,
                    (cutoff, cutoff, candidate["id"]),
                )
                row = connection.execute(
                    "SELECT * FROM sessions WHERE id = ?", (candidate["id"],)
                ).fetchone()
                assert row is not None
                record = session_from_row(row)
                expired.append(record)
                self.events.append_in_transaction(
                    connection,
                    event_type="session.expired",
                    subject_id=record.id,
                    app_instance_id=record.app_instance_id,
                    session_id=record.id,
                    payload={"expires_at": format_utc(record.expires_at)},
                )
        return tuple(expired)
