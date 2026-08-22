# SPDX-License-Identifier: Apache-2.0
"""Singleton Chat App, collection, and compatibility contract tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

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
    ResourceNotFoundError,
    RevisionConflictError,
    SessionStatus,
)
from ai2apps.events import EventStore
from ai2apps.identity import MemberRole, RequestPrincipal
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
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
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
    app.include_router(create_ai2apps_router(runtime_provider=lambda: runtime, principal_provider=RequestPrincipal.legacy_local))
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


def _member_principal(user_id: str) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="household-1",
        billing_account_id="billing-core",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


def _core_principal(user_id: str) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="household-1",
        billing_account_id=user_id,
        role=MemberRole.CORE,
        membership_epoch=1,
    )


def test_two_cloud_members_have_distinct_chat_singletons_and_idor_is_hidden(
    tmp_path,
):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    alice = ChatRepository(
        runtime.database,
        runtime.events,
        principal=_member_principal("user-alice"),
    )
    bob = ChatRepository(
        runtime.database,
        runtime.events,
        principal=_member_principal("user-bob"),
    )

    alice_thread, _ = alice.create_thread(title="Alice private")
    bob_thread, _ = bob.create_thread(title="Bob private")

    assert alice.ensure_builtin().instance.id != bob.ensure_builtin().instance.id
    assert alice.ensure_builtin().instance.owner_user_id == "user-alice"
    assert bob.ensure_builtin().instance.owner_user_id == "user-bob"
    assert [item.session.id for item in alice.list_threads()] == [
        alice_thread.session.id
    ]
    assert [item.session.id for item in bob.list_threads()] == [bob_thread.session.id]
    with pytest.raises(ResourceNotFoundError):
        bob.get_thread(alice_thread.session.id)


def test_same_user_desktop_and_mobile_have_distinct_chat_singletons(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    desktop_principal = _core_principal("user-core")
    mobile_principal = replace(
        desktop_principal,
        client_scope="mobile-browser-one",
    )
    desktop = ChatRepository(
        runtime.database,
        runtime.events,
        principal=desktop_principal,
    )
    mobile = ChatRepository(
        runtime.database,
        runtime.events,
        principal=mobile_principal,
    )

    desktop_thread, _ = desktop.create_thread(title="Desktop private")
    mobile_thread, _ = mobile.create_thread(title="Mobile private")

    assert desktop.ensure_builtin().instance.singleton_key == (
        "ai2apps.general-chat:user:user-core"
    )
    assert mobile.ensure_builtin().instance.singleton_key == (
        "ai2apps.general-chat:user:user-core:client:mobile-browser-one"
    )
    assert [item.session.id for item in desktop.list_threads()] == [
        desktop_thread.session.id
    ]
    assert [item.session.id for item in mobile.list_threads()] == [
        mobile_thread.session.id
    ]
    with pytest.raises(ResourceNotFoundError):
        mobile.get_thread(desktop_thread.session.id)
    with pytest.raises(ResourceNotFoundError):
        desktop.get_thread(mobile_thread.session.id)


def test_chat_api_uses_trusted_principal_provider_for_user_isolation(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    alice_principal = _member_principal("user-alice")
    bob_principal = _member_principal("user-bob")

    alice_app = FastAPI()
    alice_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: alice_principal,
        )
    )
    bob_app = FastAPI()
    bob_app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime,
            principal_provider=lambda: bob_principal,
        )
    )
    alice_client = TestClient(alice_app)
    bob_client = TestClient(bob_app)

    alice_thread = alice_client.post(
        "/v1/platform/chat/threads", json={"title": "Alice"}
    ).json()
    bob_thread = bob_client.post(
        "/v1/platform/chat/threads", json={"title": "Bob"}
    ).json()

    assert alice_thread["app_instance_id"] != bob_thread["app_instance_id"]
    assert alice_client.get("/v1/platform/chat/threads").json()["items"] == [
        alice_thread
    ]
    assert bob_client.get("/v1/platform/chat/threads").json()["items"] == [
        bob_thread
    ]
    assert (
        bob_client.get(
            f"/v1/platform/chat/threads/{alice_thread['id']}"
        ).status_code
        == 404
    )


def test_core_principal_claims_legacy_local_chat_without_losing_sessions(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    legacy = ChatRepository(runtime.database, runtime.events)
    legacy_thread, _ = legacy.create_thread(title="Existing local history")
    legacy_instance_id = legacy.ensure_builtin().instance.id

    core = ChatRepository(
        runtime.database,
        runtime.events,
        principal=_core_principal("user-core"),
    )
    claimed = core.ensure_builtin()

    assert claimed.instance.id == legacy_instance_id
    assert claimed.instance.owner_user_id == "user-core"
    assert core.get_thread(legacy_thread.session.id).session.title == (
        "Existing local history"
    )
    assert claimed.instance.singleton_key == "ai2apps.general-chat:user:user-core"


def test_non_core_member_never_claims_legacy_local_chat(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    legacy = ChatRepository(runtime.database, runtime.events)
    legacy_instance = legacy.ensure_builtin().instance

    member = ChatRepository(
        runtime.database,
        runtime.events,
        principal=_member_principal("user-member"),
    ).ensure_builtin()

    assert member.instance.id != legacy_instance.id
    assert member.instance.owner_user_id == "user-member"
    with runtime.database.transaction() as connection:
        still_legacy = connection.execute(
            "SELECT singleton_key,owner_user_id FROM app_instances WHERE id=?",
            (legacy_instance.id,),
        ).fetchone()
    assert tuple(still_legacy) == ("ai2apps.general-chat:user:local", None)
