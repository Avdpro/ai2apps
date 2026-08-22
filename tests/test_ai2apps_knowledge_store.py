from __future__ import annotations

from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.knowledge import (
    KnowledgeConflictError,
    KnowledgeNotFoundError,
    KnowledgeScope,
    KnowledgeStore,
)


def _principal(user: str, *, installation: str = "installation-a", role=MemberRole.MEMBER):
    return RequestPrincipal(
        actor_user_id=user,
        installation_id=installation,
        organization_id="org-a",
        billing_account_id="billing-a",
        role=role,
        membership_epoch=1,
    )


def test_store_is_explicit_and_creates_invariant_builtin_spaces(tmp_path):
    path = tmp_path / "knowledge.sqlite3"
    store = KnowledgeStore(path)
    assert not path.exists()

    store.initialize()
    private, shared = store.ensure_builtin_spaces(_principal("alice"))
    private_again, shared_again = store.ensure_builtin_spaces(_principal("alice"))
    bob_private, bob_shared = store.ensure_builtin_spaces(_principal("bob"))

    assert private.id == private_again.id
    assert private.shareability == "never"
    assert private.owner_user_id == "alice"
    assert shared.id == shared_again.id == bob_shared.id
    assert shared.shareability == "local_only"
    assert bob_private.id != private.id


def test_private_items_and_tags_do_not_leak_but_shared_items_are_visible(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    bob = _principal("bob")
    private = store.create_text_item(
        alice,
        title="Watermelon article",
        text="A field guide to choosing a sweet watermelon.",
        source_url="https://example.com/watermelon",
        user_tags=("Fruit",),
    )
    shared = store.create_text_item(
        alice,
        scope=KnowledgeScope.INSTALLATION,
        title="Shared watermelon notes",
        text="The shared kitchen bought a watermelon today.",
        user_tags=("Groceries",),
    )

    assert {hit.item.id for hit in store.search(alice, "watermelon")} == {
        private.id,
        shared.id,
    }
    bob_hits = store.search(bob, "watermelon")
    assert [hit.item.id for hit in bob_hits] == [shared.id]
    assert [tag.display_name for tag in bob_hits[0].tags] == ["Groceries"]
    assert bob_hits[0].tags[0].owner_user_id == "alice"
    assert ("source.kind", "upload") in bob_hits[0].source_facets
    try:
        store.get_item(bob, private.id)
    except KnowledgeNotFoundError:
        pass
    else:
        raise AssertionError("private knowledge leaked by direct ID")


def test_cross_installation_search_and_direct_id_are_hidden(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice", installation="installation-a")
    outsider = _principal("alice", installation="installation-b")
    item = store.create_text_item(
        alice,
        scope=KnowledgeScope.INSTALLATION,
        title="Local handbook",
        text="Watermelon storage instructions.",
    )

    assert store.search(outsider, "watermelon") == ()
    try:
        store.get_item(outsider, item.id)
    except KnowledgeNotFoundError:
        pass
    else:
        raise AssertionError("cross-installation item leaked by direct ID")


def test_search_filters_literal_fts_syntax_scope_kind_and_tag(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    note = store.create_text_item(
        alice,
        title="Quoted syntax",
        text='The literal token OR and the word watermelon are searchable.',
        user_tags=("Food Notes",),
    )
    store.create_text_item(
        alice,
        kind="chat",
        title="Chat",
        text="Watermelon was mentioned in this chat.",
    )

    assert [hit.item.id for hit in store.search(alice, "watermelon", kind="note")] == [note.id]
    assert [hit.item.id for hit in store.search(alice, "watermelon", tags=("food notes",))] == [note.id]
    assert store.search(alice, 'missing"token') == ()


def test_delete_requires_owner_and_matching_revision_and_removes_search_result(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    bob = _principal("bob")
    item = store.create_text_item(
        alice,
        scope=KnowledgeScope.INSTALLATION,
        title="Temporary note",
        text="Delete this watermelon note later.",
    )

    try:
        store.delete_item(bob, item.id, expected_revision=1)
    except KnowledgeNotFoundError:
        pass
    else:
        raise AssertionError("non-owner deleted shared knowledge")
    try:
        store.delete_item(alice, item.id, expected_revision=2)
    except KnowledgeConflictError:
        pass
    else:
        raise AssertionError("stale revision was accepted")

    store.delete_item(alice, item.id, expected_revision=1)
    assert store.search(alice, "watermelon") == ()
    assert store.search(bob, "watermelon") == ()
