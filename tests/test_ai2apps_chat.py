# SPDX-License-Identifier: Apache-2.0
"""Singleton Chat App, collection, and compatibility contract tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.router import create_ai2apps_router
from ai2apps.chat import ChatRepository, LegacyChatMessageInput
from ai2apps.config import BUILTIN_CHAT_PACKAGE_ID, PlatformConfig
from ai2apps.core import (
    AppInstanceStatus,
    MessageRole,
    ResourceConflictError,
    RevisionConflictError,
    SessionStatus,
)
from ai2apps.events import EventStore
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import MessageRepository, SessionRepository


@pytest.fixture
def chat_runtime(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.database is not None
    assert runtime.events is not None
    return runtime, ChatRepository(runtime.database, runtime.events)


def test_builtin_chat_bootstrap_is_idempotent_and_concurrent(chat_runtime):
    runtime, repository = chat_runtime

    with ThreadPoolExecutor(max_workers=5) as executor:
        records = list(executor.map(lambda _: repository.ensure_builtin(), range(10)))

    assert len({record.definition.id for record in records}) == 1
    assert len({record.instance.id for record in records}) == 1
    assert records[0].definition.package_id == BUILTIN_CHAT_PACKAGE_ID
    with runtime.database.transaction() as connection:
        assert connection.execute(
            """
            SELECT COUNT(*) FROM app_instances i
            JOIN app_definitions d ON d.id = i.app_definition_id
            WHERE d.package_id = ?
            """,
            (BUILTIN_CHAT_PACKAGE_ID,),
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM chat_collections").fetchone()[
            0
        ] == 1


def test_ten_threads_share_one_instance_and_keep_messages_isolated(chat_runtime):
    runtime, repository = chat_runtime
    threads = [repository.create_thread(title=f"Thread {number}")[0] for number in range(10)]
    messages = MessageRepository(runtime.database, runtime.events)
    messages.append(
        session_id=threads[0].session.id,
        role=MessageRole.USER,
        parts=(MessagePartInput(kind="text", content={"text": "first"}),),
    )
    messages.append(
        session_id=threads[1].session.id,
        role=MessageRole.USER,
        parts=(MessagePartInput(kind="text", content={"text": "second"}),),
    )

    assert len({thread.session.app_instance_id for thread in threads}) == 1
    assert threads[0].session.is_home is True
    assert sum(thread.session.is_home for thread in threads) == 1
    assert messages.list_for_session(threads[0].session.id)[0].parts[0].content == {
        "text": "first"
    }
    assert messages.list_for_session(threads[1].session.id)[0].parts[0].content == {
        "text": "second"
    }


def test_archive_selected_home_reassigns_without_closing_chat(chat_runtime):
    _, repository = chat_runtime
    first, _ = repository.create_thread(title="First")
    second, _ = repository.create_thread(title="Second")
    collection = repository.get_collection()
    repository.set_home_thread(
        second.session.id,
        expected_revision=second.session.revision,
    )

    archived = repository.update_thread(
        second.session.id,
        expected_revision=2,
        status=SessionStatus.ARCHIVED,
    )
    current = repository.get_collection()
    builtin = repository.ensure_builtin()

    assert archived.session.status is SessionStatus.ARCHIVED
    assert current.selected_session_id == first.session.id
    assert repository.get_thread(first.session.id).session.is_home is True
    assert builtin.instance.status is AppInstanceStatus.ACTIVE
    assert collection.app_instance_id == builtin.instance.id


def test_rename_pin_select_and_delete_use_independent_revisions(chat_runtime):
    _, repository = chat_runtime
    first, _ = repository.create_thread(title="First")
    second, _ = repository.create_thread(title="Second")
    collection = repository.get_collection()
    updated = repository.update_thread(
        first.session.id,
        expected_revision=1,
        title="Renamed",
        pinned=True,
    )
    selected = repository.select_thread(
        first.session.id,
        expected_revision=collection.revision,
    )

    with pytest.raises(RevisionConflictError):
        repository.select_thread(
            second.session.id,
            expected_revision=collection.revision,
        )
    deleted = repository.update_thread(
        first.session.id,
        expected_revision=updated.session.revision,
        status=SessionStatus.DELETED,
    )

    assert updated.session.title == "Renamed"
    assert updated.pinned is True
    assert selected.selected_session_id == first.session.id
    assert deleted.session.status is SessionStatus.DELETED
    assert repository.get_collection().selected_session_id == second.session.id


def test_generic_session_api_cannot_bypass_selected_home_reassignment(chat_runtime):
    runtime, repository = chat_runtime
    thread, _ = repository.create_thread(title="Protected")

    with pytest.raises(ResourceConflictError, match="reassigned first"):
        SessionRepository(runtime.database, runtime.events).update(
            thread.session.id,
            expected_revision=1,
            status=SessionStatus.ARCHIVED,
        )

    assert repository.get_thread(thread.session.id).session.status is SessionStatus.ACTIVE


def test_legacy_thread_mapping_is_idempotent(chat_runtime):
    runtime, repository = chat_runtime

    first, created = repository.create_thread(
        title="Imported",
        legacy_thread_id="legacy-thread-42",
        metadata={"model": "legacy-model"},
        legacy_messages=(
            LegacyChatMessageInput(
                role=MessageRole.USER,
                content="hello",
                metadata={},
            ),
            LegacyChatMessageInput(
                role=MessageRole.ASSISTANT,
                content=[{"type": "text", "text": "hi"}],
                metadata={"finish_reason": "stop"},
            ),
        ),
    )
    replay, replay_created = repository.create_thread(
        title="Ignored on idempotent replay",
        legacy_thread_id="legacy-thread-42",
    )

    assert created is True
    assert replay_created is False
    assert replay.session.id == first.session.id
    assert len(repository.list_threads()) == 1
    imported_messages = MessageRepository(
        runtime.database, runtime.events
    ).list_for_session(first.session.id)
    assert imported_messages[0].parts[0].content == {"text": "hello"}
    assert imported_messages[1].parts[0].content == {
        "content": [{"type": "text", "text": "hi"}]
    }


def test_chat_content_snapshot_round_trips_and_rejects_stale_writer(chat_runtime):
    _, repository = chat_runtime
    thread, _ = repository.create_thread(title="Snapshot")
    content = repository.replace_content(
        thread.session.id,
        expected_revision=1,
        metadata={"model": "test-model", "systemPrompt": "Be concise"},
        messages=(
            LegacyChatMessageInput(
                role=MessageRole.USER,
                content=[{"type": "text", "text": "hello"}],
                metadata={"id": "client-message-1"},
            ),
        ),
    )

    assert content.thread.session.revision == 2
    assert content.metadata["model"] == "test-model"
    assert content.messages[0].content == [{"type": "text", "text": "hello"}]
    assert content.messages[0].metadata == {"id": "client-message-1"}
    with pytest.raises(RevisionConflictError):
        repository.replace_content(
            thread.session.id,
            expected_revision=1,
            metadata={},
            messages=(),
        )


class _FailingEventStore(EventStore):
    def append_in_transaction(self, *args, **kwargs):
        raise RuntimeError("simulated Chat migration event failure")


def test_legacy_import_rolls_back_session_and_mapping(chat_runtime):
    runtime, repository = chat_runtime
    builtin = repository.ensure_builtin()
    failing = ChatRepository(runtime.database, _FailingEventStore(runtime.database))

    with pytest.raises(RuntimeError, match="migration event failure"):
        failing.create_thread(title="Rollback", legacy_thread_id="legacy-broken")

    with runtime.database.transaction() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM chat_thread_entries WHERE legacy_thread_id = ?",
            ("legacy-broken",),
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT COUNT(*) FROM sessions
            WHERE app_instance_id = ? AND title = 'Rollback'
            """,
            (builtin.instance.id,),
        ).fetchone()[0] == 0


def test_chat_aliases_allow_two_clients_to_display_different_threads(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))
    first_client = TestClient(app)
    second_client = TestClient(app)
    first = first_client.post(
        "/v1/platform/chat/threads", json={"title": "First"}
    ).json()
    second = second_client.post(
        "/v1/platform/chat/threads", json={"title": "Second"}
    ).json()

    first_view = first_client.get(
        f"/v1/platform/chat/threads/{first['id']}"
    ).json()
    second_view = second_client.get(
        f"/v1/platform/chat/threads/{second['id']}"
    ).json()
    chat = first_client.get("/v1/platform/chat").json()

    assert first_view["title"] == "First"
    assert second_view["title"] == "Second"
    assert first_view["app_instance_id"] == second_view["app_instance_id"]
    assert chat["selected_thread_id"] == second["id"]


def test_chat_content_api_round_trips_ui_snapshot_and_conflict(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime))
    client = TestClient(app)
    thread = client.post(
        "/v1/platform/chat/threads", json={"title": "Before"}
    ).json()
    payload = {
        "expected_revision": thread["revision"],
        "title": "After",
        "session_metadata": {"model": "test-model"},
        "messages": [
            {
                "role": "user",
                "content": "hello",
                "metadata": {"id": "ui-message-1"},
            }
        ],
    }

    replaced = client.put(
        f"/v1/platform/chat/threads/{thread['id']}/content", json=payload
    )
    stale = client.put(
        f"/v1/platform/chat/threads/{thread['id']}/content", json=payload
    )
    loaded = client.get(
        f"/v1/platform/chat/threads/{thread['id']}/content"
    )

    assert replaced.status_code == 200
    assert replaced.json()["thread"]["title"] == "After"
    assert replaced.json()["thread"]["revision"] == 2
    assert loaded.json()["messages"][0] == {
        "role": "user",
        "content": "hello",
        "metadata": {"id": "ui-message-1"},
    }
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "revision_conflict"
