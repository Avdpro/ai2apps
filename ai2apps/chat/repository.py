"""Transactional backend for the built-in singleton Chat App."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from ai2apps.config import (
    BUILTIN_CHAT_PACKAGE_ID,
    BUILTIN_CHAT_PACKAGE_VERSION,
    BUILTIN_CHAT_SINGLETON_KEY,
)
from ai2apps.core import (
    EntityIdKind,
    MessageRole,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
    SessionStatus,
    new_entity_id,
    utc_now_text,
)
from ai2apps.events import EventStore
from ai2apps.storage import (
    BuiltinChatRecord,
    ChatCollectionRecord,
    ChatThreadRecord,
    PlatformDatabase,
)
from ai2apps.storage.records import (
    app_definition_from_row,
    app_instance_from_row,
    canonical_json,
    chat_collection_from_row,
    chat_thread_from_joined_row,
)

_THREAD_SELECT = """
    SELECT s.*,
           e.pinned AS chat_pinned,
           e.sort_order AS chat_sort_order,
           e.legacy_thread_id AS chat_legacy_thread_id,
           e.created_at AS chat_created_at,
           e.updated_at AS chat_updated_at
    FROM chat_thread_entries e
    JOIN sessions s ON s.id = e.session_id
"""


@dataclass(frozen=True, slots=True)
class LegacyChatMessageInput:
    """Browser-owned oMLX message accepted by the backend migration seam."""

    role: MessageRole
    content: Any
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ChatContentRecord:
    thread: ChatThreadRecord
    metadata: dict[str, Any]
    messages: tuple[LegacyChatMessageInput, ...]


class ChatRepository:
    """Keep Chat collection state separate from generic Session content."""

    def __init__(self, database: PlatformDatabase, events: EventStore | None = None):
        self.database = database
        self.events = events or EventStore(database)

    def ensure_builtin(self, *, trace_id: str | None = None) -> BuiltinChatRecord:
        """Idempotently seed and resolve the local-user singleton Chat App."""

        with self.database.transaction() as connection:
            definition = connection.execute(
                """
                SELECT * FROM app_definitions
                WHERE package_id = ? AND package_version = ?
                """,
                (BUILTIN_CHAT_PACKAGE_ID, BUILTIN_CHAT_PACKAGE_VERSION),
            ).fetchone()
            instance = connection.execute(
                "SELECT * FROM app_instances WHERE singleton_key = ?",
                (BUILTIN_CHAT_SINGLETON_KEY,),
            ).fetchone()
            collection = (
                None
                if instance is None
                else connection.execute(
                    "SELECT * FROM chat_collections WHERE app_instance_id = ?",
                    (instance["id"],),
                ).fetchone()
            )
        if definition is not None and (
            definition["instance_mode"] != "singleton"
            or definition["singleton_scope"] != "user"
            or definition["source"] != "builtin"
        ):
            raise ResourceConflictError(
                "Built-in Chat definition has incompatible policy"
            )
        if (
            definition is not None
            and instance is not None
            and instance["app_definition_id"] != definition["id"]
        ):
            raise ResourceConflictError(
                "Built-in Chat singleton key belongs to another definition"
            )
        if definition is not None and instance is not None and collection is not None:
            return BuiltinChatRecord(
                definition=app_definition_from_row(definition),
                instance=app_instance_from_row(instance),
                collection=chat_collection_from_row(collection),
            )

        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                definition = connection.execute(
                    """
                    SELECT * FROM app_definitions
                    WHERE package_id = ? AND package_version = ?
                    """,
                    (BUILTIN_CHAT_PACKAGE_ID, BUILTIN_CHAT_PACKAGE_VERSION),
                ).fetchone()
                if definition is None:
                    definition_id = new_entity_id(EntityIdKind.APP_DEFINITION)
                    connection.execute(
                        """
                        INSERT INTO app_definitions(
                            id, package_id, package_version, display_name,
                            instance_mode, singleton_scope, source, status,
                            manifest_json, created_at, updated_at
                        ) VALUES (?, ?, ?, 'Chat', 'singleton', 'user',
                                  'builtin', 'enabled', ?, ?, ?)
                        """,
                        (
                            definition_id,
                            BUILTIN_CHAT_PACKAGE_ID,
                            BUILTIN_CHAT_PACKAGE_VERSION,
                            canonical_json(
                                {
                                    "entry": "chat",
                                    "instance_mode": "singleton",
                                    "session_kind": "chat_thread",
                                }
                            ),
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="app.definition.created",
                        subject_id=definition_id,
                        trace_id=trace_id,
                        payload={
                            "package_id": BUILTIN_CHAT_PACKAGE_ID,
                            "package_version": BUILTIN_CHAT_PACKAGE_VERSION,
                        },
                    )
                    definition = connection.execute(
                        "SELECT * FROM app_definitions WHERE id = ?",
                        (definition_id,),
                    ).fetchone()
                    assert definition is not None
                if (
                    definition["instance_mode"] != "singleton"
                    or definition["singleton_scope"] != "user"
                    or definition["source"] != "builtin"
                ):
                    raise ResourceConflictError(
                        "Built-in Chat definition has incompatible policy"
                    )

                instance = connection.execute(
                    "SELECT * FROM app_instances WHERE singleton_key = ?",
                    (BUILTIN_CHAT_SINGLETON_KEY,),
                ).fetchone()
                if instance is None:
                    instance_id = new_entity_id(EntityIdKind.APP_INSTANCE)
                    connection.execute(
                        """
                        INSERT INTO app_instances(
                            id, app_definition_id, singleton_key, status,
                            state_json, created_at, updated_at
                        ) VALUES (?, ?, ?, 'active', '{}', ?, ?)
                        """,
                        (
                            instance_id,
                            definition["id"],
                            BUILTIN_CHAT_SINGLETON_KEY,
                            now,
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="app.instance.created",
                        subject_id=instance_id,
                        app_instance_id=instance_id,
                        trace_id=trace_id,
                        payload={"app_definition_id": definition["id"]},
                    )
                    instance = connection.execute(
                        "SELECT * FROM app_instances WHERE id = ?", (instance_id,)
                    ).fetchone()
                    assert instance is not None
                elif instance["app_definition_id"] != definition["id"]:
                    raise ResourceConflictError(
                        "Built-in Chat singleton key belongs to another definition"
                    )

                connection.execute(
                    """
                    INSERT OR IGNORE INTO chat_collections(
                        app_instance_id, created_at, updated_at
                    ) VALUES (?, ?, ?)
                    """,
                    (instance["id"], now, now),
                )
                collection = connection.execute(
                    "SELECT * FROM chat_collections WHERE app_instance_id = ?",
                    (instance["id"],),
                ).fetchone()
                assert collection is not None
                return BuiltinChatRecord(
                    definition=app_definition_from_row(definition),
                    instance=app_instance_from_row(instance),
                    collection=chat_collection_from_row(collection),
                )
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_collection(self) -> ChatCollectionRecord:
        builtin = self.ensure_builtin()
        return builtin.collection

    def _thread_row(self, connection, session_id: str):
        return connection.execute(
            _THREAD_SELECT + " WHERE e.session_id = ?",
            (session_id,),
        ).fetchone()

    def get_thread(self, session_id: str) -> ChatThreadRecord:
        builtin = self.ensure_builtin()
        with self.database.transaction() as connection:
            row = connection.execute(
                _THREAD_SELECT
                + " WHERE e.session_id = ? AND e.app_instance_id = ?",
                (session_id, builtin.instance.id),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("chat_thread", session_id)
        return chat_thread_from_joined_row(row)

    def list_threads(
        self,
        *,
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 100,
    ) -> tuple[ChatThreadRecord, ...]:
        if not 1 <= limit <= 1_000:
            raise ValueError("limit must be between 1 and 1000")
        builtin = self.ensure_builtin()
        statuses = ["active"]
        if include_archived:
            statuses.append("archived")
        if include_deleted:
            statuses.append("deleted")
        placeholders = ",".join("?" for _ in statuses)
        with self.database.transaction() as connection:
            rows = connection.execute(
                _THREAD_SELECT
                + f""" WHERE e.app_instance_id = ?
                         AND s.status IN ({placeholders})
                       ORDER BY e.pinned DESC, e.sort_order DESC LIMIT ?""",
                (builtin.instance.id, *statuses, limit),
            ).fetchall()
        return tuple(chat_thread_from_joined_row(row) for row in rows)

    def create_thread(
        self,
        *,
        title: str = "",
        pinned: bool = False,
        legacy_thread_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        legacy_messages: tuple[LegacyChatMessageInput, ...] = (),
        trace_id: str | None = None,
    ) -> tuple[ChatThreadRecord, bool]:
        builtin = self.ensure_builtin(trace_id=trace_id)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                if legacy_thread_id is not None:
                    existing = connection.execute(
                        _THREAD_SELECT + " WHERE e.legacy_thread_id = ?",
                        (legacy_thread_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["app_instance_id"] != builtin.instance.id:
                            raise ResourceConflictError(
                                "Legacy thread belongs to another Chat collection"
                            )
                        return chat_thread_from_joined_row(existing), False
                has_home = connection.execute(
                    """
                    SELECT 1 FROM sessions
                    WHERE app_instance_id = ? AND is_home = 1 AND status = 'active'
                    """,
                    (builtin.instance.id,),
                ).fetchone()
                order = int(
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(sort_order), 0) + 1
                        FROM chat_thread_entries WHERE app_instance_id = ?
                        """,
                        (builtin.instance.id,),
                    ).fetchone()[0]
                )
                session_id = new_entity_id(EntityIdKind.SESSION)
                connection.execute(
                    """
                    INSERT INTO sessions(
                        id, app_instance_id, title, is_home, session_kind,
                        visibility, retention, metadata_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'chat_thread', 'listed', 'durable',
                              ?, ?, ?)
                    """,
                    (
                        session_id,
                        builtin.instance.id,
                        title,
                        int(has_home is None),
                        canonical_json(metadata or {}),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO chat_thread_entries(
                        session_id, app_instance_id, pinned, sort_order,
                        legacy_thread_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        builtin.instance.id,
                        int(pinned),
                        order,
                        legacy_thread_id,
                        now,
                        now,
                    ),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="session.created",
                    subject_id=session_id,
                    app_instance_id=builtin.instance.id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "is_home": has_home is None,
                        "retention": "durable",
                        "session_kind": "chat_thread",
                        "title": title,
                        "visibility": "listed",
                    },
                )
                for sequence, message in enumerate(legacy_messages, start=1):
                    message_id = new_entity_id(EntityIdKind.MESSAGE)
                    part_id = new_entity_id(EntityIdKind.MESSAGE_PART)
                    connection.execute(
                        """
                        INSERT INTO messages(
                            id, session_id, sequence, role, status,
                            metadata_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                        """,
                        (
                            message_id,
                            session_id,
                            sequence,
                            message.role.value,
                            canonical_json(message.metadata),
                            now,
                            now,
                        ),
                    )
                    if isinstance(message.content, str):
                        part_kind = "text"
                        part_content = {"text": message.content}
                    else:
                        part_kind = "openai_content"
                        part_content = {"content": message.content}
                    connection.execute(
                        """
                        INSERT INTO message_parts(
                            id, message_id, position, kind, content_json, created_at
                        ) VALUES (?, ?, 0, ?, ?, ?)
                        """,
                        (
                            part_id,
                            message_id,
                            part_kind,
                            canonical_json(part_content),
                            now,
                        ),
                    )
                    self.events.append_in_transaction(
                        connection,
                        event_type="message.created",
                        subject_id=message_id,
                        app_instance_id=builtin.instance.id,
                        session_id=session_id,
                        trace_id=trace_id,
                        payload={
                            "legacy_import": True,
                            "role": message.role.value,
                            "sequence": sequence,
                        },
                    )
                connection.execute(
                    """
                    UPDATE chat_collections
                    SET selected_session_id = ?, revision = revision + 1,
                        updated_at = ?
                    WHERE app_instance_id = ?
                    """,
                    (session_id, now, builtin.instance.id),
                )
                self.events.append_in_transaction(
                    connection,
                    event_type="chat.thread.created",
                    subject_id=session_id,
                    app_instance_id=builtin.instance.id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={"legacy_thread_id": legacy_thread_id, "pinned": pinned},
                )
                row = self._thread_row(connection, session_id)
                assert row is not None
                return chat_thread_from_joined_row(row), True
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def select_thread(
        self,
        session_id: str,
        *,
        expected_revision: int,
        trace_id: str | None = None,
    ) -> ChatCollectionRecord:
        builtin = self.ensure_builtin(trace_id=trace_id)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                thread = self._thread_row(connection, session_id)
                if (
                    thread is None
                    or thread["app_instance_id"] != builtin.instance.id
                ):
                    raise ResourceNotFoundError("chat_thread", session_id)
                if thread["status"] != "active":
                    raise ResourceConflictError("Only active Chat threads can be selected")
                cursor = connection.execute(
                    """
                    UPDATE chat_collections
                    SET selected_session_id = ?, revision = revision + 1,
                        updated_at = ?
                    WHERE app_instance_id = ? AND revision = ?
                    """,
                    (session_id, now, builtin.instance.id, expected_revision),
                )
                if cursor.rowcount == 0:
                    current = connection.execute(
                        "SELECT revision FROM chat_collections WHERE app_instance_id = ?",
                        (builtin.instance.id,),
                    ).fetchone()
                    assert current is not None
                    raise RevisionConflictError(
                        builtin.instance.id,
                        expected_revision,
                        int(current["revision"]),
                    )
                self.events.append_in_transaction(
                    connection,
                    event_type="chat.thread.selected",
                    subject_id=session_id,
                    app_instance_id=builtin.instance.id,
                    session_id=session_id,
                    trace_id=trace_id,
                )
                row = connection.execute(
                    "SELECT * FROM chat_collections WHERE app_instance_id = ?",
                    (builtin.instance.id,),
                ).fetchone()
                assert row is not None
                return chat_collection_from_row(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def set_home_thread(
        self,
        session_id: str,
        *,
        expected_revision: int,
        trace_id: str | None = None,
    ) -> ChatThreadRecord:
        builtin = self.ensure_builtin(trace_id=trace_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            target = self._thread_row(connection, session_id)
            if target is None or target["app_instance_id"] != builtin.instance.id:
                raise ResourceNotFoundError("chat_thread", session_id)
            if target["status"] != "active":
                raise ResourceConflictError("Home Chat thread must be active")
            if int(target["revision"]) != expected_revision:
                raise RevisionConflictError(
                    session_id, expected_revision, int(target["revision"])
                )
            old_home = connection.execute(
                """
                SELECT id FROM sessions
                WHERE app_instance_id = ? AND is_home = 1 AND id != ?
                """,
                (builtin.instance.id, session_id),
            ).fetchone()
            if old_home is not None:
                connection.execute(
                    """
                    UPDATE sessions SET is_home = 0, revision = revision + 1,
                                        updated_at = ? WHERE id = ?
                    """,
                    (now, old_home["id"]),
                )
            if not bool(target["is_home"]):
                connection.execute(
                    """
                    UPDATE sessions SET is_home = 1, revision = revision + 1,
                                        updated_at = ? WHERE id = ?
                    """,
                    (now, session_id),
                )
            self.events.append_in_transaction(
                connection,
                event_type="chat.thread.home_changed",
                subject_id=session_id,
                app_instance_id=builtin.instance.id,
                session_id=session_id,
                trace_id=trace_id,
                payload={
                    "previous_session_id": (
                        None if old_home is None else old_home["id"]
                    )
                },
            )
            row = self._thread_row(connection, session_id)
            assert row is not None
            return chat_thread_from_joined_row(row)

    def update_thread(
        self,
        session_id: str,
        *,
        expected_revision: int,
        title: str | None = None,
        pinned: bool | None = None,
        status: SessionStatus | None = None,
        trace_id: str | None = None,
    ) -> ChatThreadRecord:
        if title is None and pinned is None and status is None:
            raise ValueError("At least one Chat thread field must change")
        builtin = self.ensure_builtin(trace_id=trace_id)
        now = utc_now_text()
        try:
            with self.database.transaction(write=True) as connection:
                current = self._thread_row(connection, session_id)
                if (
                    current is None
                    or current["app_instance_id"] != builtin.instance.id
                ):
                    raise ResourceNotFoundError("chat_thread", session_id)
                if int(current["revision"]) != expected_revision:
                    raise RevisionConflictError(
                        session_id, expected_revision, int(current["revision"])
                    )
                fallback_id: str | None = None
                leaving_active = status in {
                    SessionStatus.ARCHIVED,
                    SessionStatus.DELETED,
                }
                collection = connection.execute(
                    "SELECT * FROM chat_collections WHERE app_instance_id = ?",
                    (builtin.instance.id,),
                ).fetchone()
                assert collection is not None
                if leaving_active:
                    fallback = connection.execute(
                        """
                        SELECT s.id FROM chat_thread_entries e
                        JOIN sessions s ON s.id = e.session_id
                        WHERE e.app_instance_id = ? AND s.status = 'active'
                          AND s.id != ?
                        ORDER BY e.pinned DESC, e.sort_order DESC LIMIT 1
                        """,
                        (builtin.instance.id, session_id),
                    ).fetchone()
                    fallback_id = None if fallback is None else fallback["id"]
                    if collection["selected_session_id"] == session_id:
                        connection.execute(
                            """
                            UPDATE chat_collections
                            SET selected_session_id = ?, revision = revision + 1,
                                updated_at = ? WHERE app_instance_id = ?
                            """,
                            (fallback_id, now, builtin.instance.id),
                        )
                    if bool(current["is_home"]):
                        connection.execute(
                            "UPDATE sessions SET is_home = 0 WHERE id = ?",
                            (session_id,),
                        )
                        if fallback_id is not None:
                            connection.execute(
                                """
                                UPDATE sessions
                                SET is_home = 1, revision = revision + 1,
                                    updated_at = ? WHERE id = ?
                                """,
                                (now, fallback_id),
                            )

                session_changes: dict[str, object] = {"updated_at": now}
                if title is not None:
                    session_changes["title"] = title
                if status is not None:
                    session_changes["status"] = status.value
                    if status is SessionStatus.ARCHIVED:
                        session_changes["archived_at"] = now
                        session_changes["deleted_at"] = None
                    elif status is SessionStatus.DELETED:
                        session_changes["deleted_at"] = now
                    elif status is SessionStatus.ACTIVE:
                        session_changes["archived_at"] = None
                        session_changes["deleted_at"] = None
                assignments = [f"{column} = ?" for column in session_changes]
                assignments.append("revision = revision + 1")
                connection.execute(
                    f"UPDATE sessions SET {', '.join(assignments)} WHERE id = ?",
                    (*session_changes.values(), session_id),
                )
                if pinned is not None:
                    connection.execute(
                        """
                        UPDATE chat_thread_entries
                        SET pinned = ?, updated_at = ? WHERE session_id = ?
                        """,
                        (int(pinned), now, session_id),
                    )
                event_type = (
                    "chat.thread.archived"
                    if status is SessionStatus.ARCHIVED
                    else "chat.thread.deleted"
                    if status is SessionStatus.DELETED
                    else "chat.thread.updated"
                )
                self.events.append_in_transaction(
                    connection,
                    event_type=event_type,
                    subject_id=session_id,
                    app_instance_id=builtin.instance.id,
                    session_id=session_id,
                    trace_id=trace_id,
                    payload={
                        "fallback_session_id": fallback_id,
                        "pinned": pinned,
                        "title_changed": title is not None,
                    },
                )
                row = self._thread_row(connection, session_id)
                assert row is not None
                return chat_thread_from_joined_row(row)
        except sqlite3.IntegrityError as exc:
            raise ResourceConflictError(str(exc)) from exc

    def get_content(self, session_id: str) -> ChatContentRecord:
        thread = self.get_thread(session_id)
        with self.database.transaction() as connection:
            rows = connection.execute(
                """
                SELECT m.role, m.metadata_json, p.kind, p.content_json
                FROM messages m
                JOIN message_parts p ON p.message_id = m.id
                WHERE m.session_id = ? AND p.position = 0
                ORDER BY m.sequence
                """,
                (session_id,),
            ).fetchall()
        messages: list[LegacyChatMessageInput] = []
        for row in rows:
            content_data = json.loads(row["content_json"])
            content = (
                content_data.get("text", "")
                if row["kind"] == "text"
                else content_data.get("content")
            )
            messages.append(
                LegacyChatMessageInput(
                    role=MessageRole(row["role"]),
                    content=content,
                    metadata=json.loads(row["metadata_json"]),
                )
            )
        return ChatContentRecord(
            thread=thread,
            metadata=thread.session.metadata,
            messages=tuple(messages),
        )

    def replace_content(
        self,
        session_id: str,
        *,
        expected_revision: int,
        title: str | None = None,
        metadata: dict[str, Any],
        messages: tuple[LegacyChatMessageInput, ...],
        trace_id: str | None = None,
    ) -> ChatContentRecord:
        """Atomically replace one UI snapshot using generic Message resources."""

        builtin = self.ensure_builtin(trace_id=trace_id)
        now = utc_now_text()
        with self.database.transaction(write=True) as connection:
            current = self._thread_row(connection, session_id)
            if current is None or current["app_instance_id"] != builtin.instance.id:
                raise ResourceNotFoundError("chat_thread", session_id)
            if int(current["revision"]) != expected_revision:
                raise RevisionConflictError(
                    session_id, expected_revision, int(current["revision"])
                )
            connection.execute(
                """
                DELETE FROM message_parts WHERE message_id IN (
                    SELECT id FROM messages WHERE session_id = ?
                )
                """,
                (session_id,),
            )
            connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            for sequence, message in enumerate(messages, start=1):
                message_id = new_entity_id(EntityIdKind.MESSAGE)
                part_id = new_entity_id(EntityIdKind.MESSAGE_PART)
                connection.execute(
                    """
                    INSERT INTO messages(
                        id, session_id, sequence, role, status, metadata_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                    """,
                    (
                        message_id,
                        session_id,
                        sequence,
                        message.role.value,
                        canonical_json(message.metadata),
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO message_parts(
                        id, message_id, position, kind, content_json, created_at
                    ) VALUES (?, ?, 0, 'chat_ui_content', ?, ?)
                    """,
                    (
                        part_id,
                        message_id,
                        canonical_json({"content": message.content}),
                        now,
                    ),
                )
            connection.execute(
                """
                UPDATE sessions
                SET title = COALESCE(?, title), metadata_json = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (title, canonical_json(metadata), now, session_id),
            )
            self.events.append_in_transaction(
                connection,
                event_type="chat.thread.content_replaced",
                subject_id=session_id,
                app_instance_id=builtin.instance.id,
                session_id=session_id,
                trace_id=trace_id,
                payload={"message_count": len(messages)},
            )
        return self.get_content(session_id)
