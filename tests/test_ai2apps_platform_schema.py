# SPDX-License-Identifier: Apache-2.0
"""Relational contract tests for AI2Apps platform schema v2."""

from __future__ import annotations

import json
import sqlite3

import pytest

from ai2apps.core import EntityIdKind, new_entity_id, utc_now_text
from ai2apps.storage import PlatformDatabase


@pytest.fixture
def connection(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    connection = database.connect()
    try:
        yield connection
    finally:
        connection.close()


def _insert_definition(
    connection: sqlite3.Connection,
    *,
    package_id: str = "example.app",
    mode: str = "multiple",
    scope: str | None = None,
) -> str:
    definition_id = new_entity_id(EntityIdKind.APP_DEFINITION)
    now = utc_now_text()
    connection.execute(
        """
        INSERT INTO app_definitions(
            id, package_id, package_version, display_name, instance_mode,
            singleton_scope, source, manifest_json, created_at, updated_at
        ) VALUES (?, ?, '1.0.0', 'Example', ?, ?, 'local', '{}', ?, ?)
        """,
        (definition_id, package_id, mode, scope, now, now),
    )
    return definition_id


def _insert_instance(
    connection: sqlite3.Connection,
    definition_id: str,
    *,
    singleton_key: str | None = None,
) -> str:
    instance_id = new_entity_id(EntityIdKind.APP_INSTANCE)
    now = utc_now_text()
    connection.execute(
        """
        INSERT INTO app_instances(
            id, app_definition_id, singleton_key, status, created_at, updated_at
        ) VALUES (?, ?, ?, 'active', ?, ?)
        """,
        (instance_id, definition_id, singleton_key, now, now),
    )
    return instance_id


def _insert_session(
    connection: sqlite3.Connection,
    instance_id: str,
    *,
    is_home: int = 0,
) -> str:
    session_id = new_entity_id(EntityIdKind.SESSION)
    now = utc_now_text()
    connection.execute(
        """
        INSERT INTO sessions(
            id, app_instance_id, title, is_home, created_at, updated_at
        ) VALUES (?, ?, 'Thread', ?, ?, ?)
        """,
        (session_id, instance_id, is_home, now, now),
    )
    return session_id


def _insert_message(
    connection: sqlite3.Connection,
    session_id: str,
    *,
    sequence: int = 1,
    idempotency_key: str | None = None,
) -> str:
    message_id = new_entity_id(EntityIdKind.MESSAGE)
    now = utc_now_text()
    connection.execute(
        """
        INSERT INTO messages(
            id, session_id, sequence, role, idempotency_key,
            created_at, updated_at
        ) VALUES (?, ?, ?, 'user', ?, ?, ?)
        """,
        (message_id, session_id, sequence, idempotency_key, now, now),
    )
    return message_id


def test_valid_app_session_message_part_graph_is_durable(connection):
    definition_id = _insert_definition(connection)
    instance_id = _insert_instance(connection, definition_id)
    session_id = _insert_session(connection, instance_id, is_home=1)
    message_id = _insert_message(connection, session_id)
    part_id = new_entity_id(EntityIdKind.MESSAGE_PART)
    connection.execute(
        """
        INSERT INTO message_parts(id, message_id, position, kind, content_json, created_at)
        VALUES (?, ?, 0, 'text', ?, ?)
        """,
        (part_id, message_id, json.dumps({"text": "hello"}), utc_now_text()),
    )

    row = connection.execute(
        """
        SELECT d.package_id, i.id, s.id, m.id, p.content_json
        FROM app_definitions d
        JOIN app_instances i ON i.app_definition_id = d.id
        JOIN sessions s ON s.app_instance_id = i.id
        JOIN messages m ON m.session_id = s.id
        JOIN message_parts p ON p.message_id = m.id
        """
    ).fetchone()
    assert row[0:4] == ("example.app", instance_id, session_id, message_id)
    assert json.loads(row[4]) == {"text": "hello"}


def test_definition_instance_policy_and_singleton_keys_are_enforced(connection):
    now = utc_now_text()
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO app_definitions(
                id, package_id, package_version, display_name, instance_mode,
                singleton_scope, source, created_at, updated_at
            ) VALUES (?, 'bad.multiple', '1', 'Bad', 'multiple', 'system',
                      'local', ?, ?)
            """,
            (new_entity_id(EntityIdKind.APP_DEFINITION), now, now),
        )

    definition_id = _insert_definition(
        connection,
        package_id="singleton.app",
        mode="singleton",
        scope="system",
    )
    with pytest.raises(sqlite3.IntegrityError, match="violates definition policy"):
        _insert_instance(connection, definition_id)
    _insert_instance(connection, definition_id, singleton_key="singleton.app:system")
    with pytest.raises(sqlite3.IntegrityError):
        _insert_instance(
            connection,
            definition_id,
            singleton_key="singleton.app:system",
        )

    multiple_definition_id = _insert_definition(
        connection,
        package_id="another.multiple",
    )
    with pytest.raises(sqlite3.IntegrityError, match="violates definition policy"):
        _insert_instance(
            connection,
            multiple_definition_id,
            singleton_key="not-allowed",
        )
    multiple_instance_id = _insert_instance(connection, multiple_definition_id)
    with pytest.raises(sqlite3.IntegrityError, match="cannot change instance policy"):
        connection.execute(
            """
            UPDATE app_definitions
            SET instance_mode = 'singleton', singleton_scope = 'system'
            WHERE id = ?
            """,
            (multiple_definition_id,),
        )
    assert multiple_instance_id


def test_only_one_home_session_exists_per_app_instance(connection):
    instance_id = _insert_instance(connection, _insert_definition(connection))
    _insert_session(connection, instance_id, is_home=1)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_session(connection, instance_id, is_home=1)

    assert _insert_session(connection, instance_id, is_home=0)


def test_message_order_and_idempotency_are_scoped_to_session(connection):
    instance_id = _insert_instance(connection, _insert_definition(connection))
    first_session = _insert_session(connection, instance_id)
    second_session = _insert_session(connection, instance_id)
    _insert_message(connection, first_session, sequence=1, idempotency_key="request-1")

    with pytest.raises(sqlite3.IntegrityError):
        _insert_message(connection, first_session, sequence=1)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_message(connection, first_session, sequence=2, idempotency_key="request-1")

    _insert_message(connection, second_session, sequence=1, idempotency_key="request-1")


def test_foreign_keys_json_and_id_shapes_reject_invalid_records(connection):
    now = utc_now_text()
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO sessions(id, app_instance_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                new_entity_id(EntityIdKind.SESSION),
                new_entity_id(EntityIdKind.APP_INSTANCE),
                now,
                now,
            ),
        )

    definition_id = _insert_definition(connection)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            UPDATE app_definitions SET manifest_json = 'not-json' WHERE id = ?
            """,
            (definition_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE app_definitions SET id = 'app_bad' WHERE id = ?",
            (definition_id,),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE app_definitions SET id = ? WHERE id = ?",
            ("app_" + "g" * 32, definition_id),
        )


def test_events_are_ordered_scoped_and_append_only(connection):
    first_instance = _insert_instance(connection, _insert_definition(connection))
    second_definition = _insert_definition(connection, package_id="second.app")
    second_instance = _insert_instance(connection, second_definition)
    first_session = _insert_session(connection, first_instance)
    now = utc_now_text()

    first_event_id = new_entity_id(EntityIdKind.EVENT)
    connection.execute(
        """
        INSERT INTO events(
            id, type, occurred_at, app_instance_id, session_id,
            subject_id, payload_json
        ) VALUES (?, 'session.created', ?, ?, ?, ?, '{}')
        """,
        (first_event_id, now, first_instance, first_session, first_session),
    )
    second_event_id = new_entity_id(EntityIdKind.EVENT)
    connection.execute(
        """
        INSERT INTO events(id, type, occurred_at, subject_id, payload_json)
        VALUES (?, 'platform.ready', ?, 'platform', '{}')
        """,
        (second_event_id, now),
    )

    sequences = connection.execute(
        "SELECT sequence FROM events ORDER BY sequence"
    ).fetchall()
    assert sequences == [(1,), (2,)]

    with pytest.raises(sqlite3.IntegrityError, match="scope does not own"):
        connection.execute(
            """
            INSERT INTO events(
                id, type, occurred_at, app_instance_id, session_id,
                subject_id, payload_json
            ) VALUES (?, 'bad.scope', ?, ?, ?, ?, '{}')
            """,
            (
                new_entity_id(EntityIdKind.EVENT),
                now,
                second_instance,
                first_session,
                first_session,
            ),
        )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO events(id, type, occurred_at, session_id, subject_id)
            VALUES (?, 'bad.scope', ?, ?, ?)
            """,
            (new_entity_id(EntityIdKind.EVENT), now, first_session, first_session),
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE events SET type = 'changed' WHERE id = ?",
            (first_event_id,),
        )
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute("DELETE FROM events WHERE id = ?", (first_event_id,))
