# SPDX-License-Identifier: Apache-2.0
"""Transactional Repository and Event Store tests for Milestone 1B."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from ai2apps.core import (
    AppInstanceMode,
    AppInstanceStatus,
    IdempotencyConflictError,
    MessageRole,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
    SessionRetention,
    SessionStatus,
    SingletonScope,
)
from ai2apps.events import EventStore
from ai2apps.storage import MessagePartInput, PlatformDatabase
from ai2apps.storage.repositories import (
    AppRepository,
    MessageRepository,
    SessionRepository,
)


@pytest.fixture
def platform(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database)
    return database, events, AppRepository(database, events)


def _create_instance(apps: AppRepository, *, package_id: str = "example.app"):
    definition = apps.create_definition(
        package_id=package_id,
        package_version="1.0.0",
        display_name="Example",
        instance_mode=AppInstanceMode.MULTIPLE,
        manifest={"entry": "main"},
    )
    return definition, apps.create_instance(app_definition_id=definition.id)


def test_app_and_session_repositories_return_typed_records_and_events(platform):
    database, events, apps = platform
    definition, instance = _create_instance(apps)
    sessions = SessionRepository(database, events)
    session = sessions.create(
        app_instance_id=instance.id,
        title="Home",
        is_home=True,
        metadata={"source": "test"},
        trace_id="trace-create",
    )

    assert definition.manifest == {"entry": "main"}
    assert instance.app_definition_id == definition.id
    assert session.app_instance_id == instance.id
    assert session.is_home is True
    assert session.revision == 1
    assert session.metadata == {"source": "test"}
    assert sessions.get(session.id) == session

    replay = events.list_after()
    assert [event.type for event in replay] == [
        "app.definition.created",
        "app.instance.created",
        "session.created",
    ]
    assert [event.sequence for event in replay] == [1, 2, 3]
    assert replay[-1].trace_id == "trace-create"


def test_singleton_conflicts_are_typed_and_atomic(platform):
    database, events, apps = platform
    definition = apps.create_definition(
        package_id="singleton.app",
        package_version="1.0.0",
        display_name="Singleton",
        instance_mode=AppInstanceMode.SINGLETON,
        singleton_scope=SingletonScope.SYSTEM,
    )
    first = apps.create_instance(
        app_definition_id=definition.id,
        singleton_key="singleton.app:system",
    )

    with pytest.raises(ResourceConflictError):
        apps.create_instance(
            app_definition_id=definition.id,
            singleton_key="singleton.app:system",
        )

    assert apps.get_instance(first.id) == first
    with database.transaction() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM app_instances"
        ).fetchone()[0] == 1
    assert [event.type for event in events.list_after()] == [
        "app.definition.created",
        "app.instance.created",
    ]


def test_app_instance_state_update_uses_optimistic_revision(platform):
    _, events, apps = platform
    _, instance = _create_instance(apps)

    updated = apps.update_instance(
        instance.id,
        expected_revision=1,
        status=AppInstanceStatus.BACKGROUND,
        state={"counter": 1},
    )

    assert updated.status is AppInstanceStatus.BACKGROUND
    assert updated.state == {"counter": 1}
    assert updated.revision == 2
    assert events.latest_for_subject(instance.id).type == "app.instance.updated"

    with pytest.raises(RevisionConflictError):
        apps.update_instance(
            instance.id,
            expected_revision=1,
            state={"counter": 2},
        )
    assert apps.get_instance(instance.id) == updated


def test_missing_app_definition_and_instance_are_not_conflicts(platform):
    database, events, apps = platform
    missing_definition = "app_" + "0" * 32
    missing_instance = "appi_" + "0" * 32

    with pytest.raises(ResourceNotFoundError):
        apps.create_instance(app_definition_id=missing_definition)
    with pytest.raises(ResourceNotFoundError):
        SessionRepository(database, events).list_for_instance(missing_instance)


def test_session_update_uses_optimistic_revision_and_atomic_event(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    sessions = SessionRepository(database, events)
    session = sessions.create(app_instance_id=instance.id, title="Before")

    updated = sessions.update(
        session.id,
        expected_revision=1,
        title="After",
        metadata={"color": "blue"},
    )

    assert updated.title == "After"
    assert updated.metadata == {"color": "blue"}
    assert updated.revision == 2
    assert events.latest_for_subject(session.id).payload["revision"] == 2

    with pytest.raises(RevisionConflictError) as error:
        sessions.update(session.id, expected_revision=1, title="Stale")
    assert error.value.actual == 2
    assert sessions.get(session.id).title == "After"
    assert [event.type for event in events.list_after()].count("session.updated") == 1


def test_session_and_message_reads_are_owner_scoped(platform):
    database, events, apps = platform
    _, first_instance = _create_instance(apps, package_id="first.app")
    _, second_instance = _create_instance(apps, package_id="second.app")
    sessions = SessionRepository(database, events)
    session = sessions.create(app_instance_id=first_instance.id)
    messages = MessageRepository(database, events)
    message = messages.append(
        session_id=session.id,
        app_instance_id=first_instance.id,
        role=MessageRole.USER,
        parts=(MessagePartInput(kind="text", content={"text": "hello"}),),
    )

    with pytest.raises(ResourceNotFoundError):
        sessions.get(session.id, app_instance_id=second_instance.id)
    with pytest.raises(ResourceNotFoundError):
        messages.list_for_session(
            session.id,
            app_instance_id=second_instance.id,
        )
    with pytest.raises(ResourceNotFoundError):
        messages.get(message.value.message.id, session_id="ses_" + "0" * 32)


def test_message_append_is_idempotent_per_session(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    session = SessionRepository(database, events).create(app_instance_id=instance.id)
    messages = MessageRepository(database, events)
    parts = (
        MessagePartInput(kind="text", content={"text": "hello"}),
        MessagePartInput(kind="json", content={"answer": 42}),
    )

    first = messages.append(
        session_id=session.id,
        role=MessageRole.USER,
        parts=parts,
        idempotency_key="request-1",
        metadata={"client": "test"},
    )
    replay = messages.append(
        session_id=session.id,
        role=MessageRole.USER,
        parts=parts,
        idempotency_key="request-1",
        metadata={"client": "test"},
    )

    assert first.created is True
    assert replay.created is False
    assert replay.value == first.value
    assert replay.event == first.event

    with pytest.raises(IdempotencyConflictError):
        messages.append(
            session_id=session.id,
            role=MessageRole.USER,
            parts=(MessagePartInput(kind="text", content={"text": "different"}),),
            idempotency_key="request-1",
            metadata={"client": "test"},
        )

    assert len(messages.list_for_session(session.id)) == 1
    assert [event.type for event in events.list_after()].count("message.created") == 1


class _FailingEventStore(EventStore):
    def append_in_transaction(self, *args, **kwargs):
        raise RuntimeError("simulated event failure")


def test_event_failure_rolls_back_message_and_parts(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    session = SessionRepository(database, events).create(app_instance_id=instance.id)
    messages = MessageRepository(database, _FailingEventStore(database))

    with pytest.raises(RuntimeError, match="simulated event failure"):
        messages.append(
            session_id=session.id,
            role=MessageRole.USER,
            parts=(MessagePartInput(kind="text", content={"text": "rollback"}),),
        )

    with database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM message_parts").fetchone()[0] == 0
    assert [event.type for event in events.list_after()].count("message.created") == 0


def test_concurrent_message_appends_receive_gapless_session_sequences(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    session = SessionRepository(database, events).create(app_instance_id=instance.id)

    def append_message(number: int):
        return MessageRepository(database, events).append(
            session_id=session.id,
            role=MessageRole.USER,
            parts=(
                MessagePartInput(kind="text", content={"text": str(number)}),
            ),
            idempotency_key=f"request-{number}",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(append_message, range(12)))

    assert all(result.created for result in results)
    stored = MessageRepository(database, events).list_for_session(session.id)
    assert [value.message.sequence for value in stored] == list(range(1, 13))
    assert len({value.message.id for value in stored}) == 12


def test_concurrent_identical_idempotency_key_creates_one_message(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    session = SessionRepository(database, events).create(app_instance_id=instance.id)

    def append_same_message(_: int):
        return MessageRepository(database, events).append(
            session_id=session.id,
            role=MessageRole.USER,
            parts=(MessagePartInput(kind="text", content={"text": "same"}),),
            idempotency_key="same-request",
        )

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(append_same_message, range(12)))

    assert sum(result.created for result in results) == 1
    assert len({result.value.message.id for result in results}) == 1
    assert len(MessageRepository(database, events).list_for_session(session.id)) == 1
    assert [event.type for event in events.list_after()].count("message.created") == 1


def test_archive_restart_and_cursor_replay(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    sessions = SessionRepository(database, events)
    session = sessions.create(app_instance_id=instance.id, title="Persistent")
    MessageRepository(database, events).append(
        session_id=session.id,
        role=MessageRole.ASSISTANT,
        parts=(MessagePartInput(kind="text", content={"text": "saved"}),),
    )
    archived = sessions.update(
        session.id,
        expected_revision=1,
        status=SessionStatus.ARCHIVED,
    )

    restarted_events = EventStore(PlatformDatabase(database.path))
    restarted_sessions = SessionRepository(restarted_events.database, restarted_events)
    restarted_messages = MessageRepository(restarted_events.database, restarted_events)

    assert restarted_sessions.get(session.id) == archived
    assert restarted_messages.list_for_session(session.id)[0].parts[0].content == {
        "text": "saved"
    }
    all_events = restarted_events.list_after()
    tail = restarted_events.list_after(
        after_sequence=all_events[-2].sequence,
        session_id=session.id,
    )
    assert [event.type for event in tail] == ["session.archived"]


def test_temporary_session_expiry_is_bounded_atomic_and_idempotent(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    sessions = SessionRepository(database, events)
    first = sessions.create(
        app_instance_id=instance.id,
        retention=SessionRetention.TEMPORARY,
        expires_at="2025-01-01T00:00:00.000000Z",
    )
    second = sessions.create(
        app_instance_id=instance.id,
        retention=SessionRetention.TEMPORARY,
        expires_at="2025-01-01T00:00:01.000000Z",
    )
    durable = sessions.create(app_instance_id=instance.id)

    batch = sessions.expire_temporary(
        now="2025-01-02T00:00:00.000000Z", limit=1
    )
    remainder = sessions.expire_temporary(now="2025-01-02T00:00:00.000000Z")
    repeated = sessions.expire_temporary(now="2025-01-02T00:00:00.000000Z")

    assert [record.id for record in batch] == [first.id]
    assert [record.id for record in remainder] == [second.id]
    assert repeated == ()
    assert sessions.get(first.id).status is SessionStatus.DELETED
    assert sessions.get(second.id).revision == 2
    assert sessions.get(durable.id).status is SessionStatus.ACTIVE
    assert [event.type for event in events.list_after()].count("session.expired") == 2


def test_temporary_session_gets_default_expiry_and_durable_rejects_one(platform):
    database, events, apps = platform
    _, instance = _create_instance(apps)
    sessions = SessionRepository(database, events)

    temporary = sessions.create(
        app_instance_id=instance.id,
        retention=SessionRetention.TEMPORARY,
    )

    assert temporary.expires_at is not None
    with pytest.raises(ValueError, match="Durable Sessions"):
        sessions.create(
            app_instance_id=instance.id,
            expires_at="2025-01-01T00:00:00.000000Z",
        )
