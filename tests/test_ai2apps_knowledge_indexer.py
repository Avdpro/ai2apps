from __future__ import annotations

import pytest

from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.knowledge import KnowledgeScope, KnowledgeStore
from ai2apps.knowledge.backends import BackendHealth
from ai2apps.knowledge.indexer import KnowledgeVectorIndexer
from ai2apps.storage import PlatformDatabase


class _Embedding:
    model_id = "fixture/embedding"
    dimension = 2

    def embed(self, texts):
        return tuple((float(len(text)), 1.0) for text in texts)


class _Vector:
    generation = "fixture_v1"

    def __init__(self):
        self.records = {}
        self.deleted = []

    def upsert(self, records):
        self.records.update((record.chunk_id, record) for record in records)

    def delete_items(self, item_ids):
        self.deleted.extend(item_ids)
        selected = set(item_ids)
        self.records = {
            key: record
            for key, record in self.records.items()
            if record.item_id not in selected
        }

    def search(self, request):
        return ()

    def reset(self):
        self.records = {}
        self.deleted = []

    def count(self):
        return len(self.records)

    def health(self):
        return BackendHealth("ready", "fixture", self.generation)


class _FailingEmbedding(_Embedding):
    def embed(self, texts):
        raise RuntimeError("fixture embedding unavailable")


def _principal() -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id="user-1",
        installation_id="installation-1",
        organization_id="local",
        billing_account_id="local",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


def test_change_log_is_chunked_indexed_and_incremental(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.initialize()
    principal = _principal()
    item = store.create_text_item(
        principal,
        scope=KnowledgeScope.PRIVATE,
        title="A long article",
        text=("semantic paragraph。" * 500),
    )
    vector = _Vector()
    indexer = KnowledgeVectorIndexer(store, vector, _Embedding())

    first = indexer.sync()
    second = indexer.sync()

    assert first.changed_items == 1
    assert first.indexed_chunks > 1
    assert second.changed_items == 0
    assert {record.item_id for record in vector.records.values()} == {item.id}
    assert all(
        record.installation_id == principal.installation_id
        for record in vector.records.values()
    )


def test_deleted_items_are_removed_from_disposable_vector_index(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.db")
    store.initialize()
    principal = _principal()
    item = store.create_text_item(
        principal,
        title="Temporary",
        text="This item will be removed.",
    )
    vector = _Vector()
    indexer = KnowledgeVectorIndexer(store, vector, _Embedding())
    indexer.sync()

    store.delete_item(principal, item.id, expected_revision=item.revision)
    result = indexer.sync()

    assert result.deleted_items == 1
    assert item.id in vector.deleted
    assert not vector.records


def test_bucket_membership_changes_reindex_vector_metadata(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.db")
    database.initialize()
    store = KnowledgeStore(database)
    principal = _principal()
    buckets = store.ensure_system_buckets(principal)
    inbox = next(bucket for bucket in buckets if bucket.system_key == "inbox")
    documents = next(bucket for bucket in buckets if bucket.system_key == "documents")
    item = store.create_text_item(
        principal,
        title="Movable note",
        text="Bucket metadata must stay current.",
        bucket_id=inbox.id,
    )
    vector = _Vector()
    indexer = KnowledgeVectorIndexer(store, vector, _Embedding())
    indexer.sync()

    store.add_item_to_bucket(principal, documents.id, item.id)
    added = indexer.sync()
    bucket_ids = next(iter(vector.records.values())).bucket_ids
    assert added.changed_items == 1
    assert bucket_ids == (inbox.id, documents.id)

    store.remove_item_from_bucket(principal, inbox.id, item.id)
    removed = indexer.sync()
    bucket_ids = next(iter(vector.records.values())).bucket_ids
    assert removed.changed_items == 1
    assert bucket_ids == (documents.id,)


def test_platform_index_cursor_survives_indexer_restart(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.create_text_item(
        _principal(),
        title="Durable cursor",
        text="The vector watermark survives a Runtime restart.",
    )
    vector = _Vector()

    first = KnowledgeVectorIndexer(
        store, vector, _Embedding(), profile_id="fixture/hybrid"
    )
    result = first.sync()
    restarted = KnowledgeVectorIndexer(
        store, vector, _Embedding(), profile_id="fixture/hybrid"
    )

    assert result.changed_items == 1
    assert restarted.sync().changed_items == 0
    status = restarted.status()
    assert status.status == "ready"
    assert status.sequence == status.target_sequence == result.sequence
    assert status.processed_changes == 1


def test_rebuild_drops_vectors_and_replays_authoritative_chunks(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.db")
    database.initialize()
    store = KnowledgeStore(database)
    item = store.create_text_item(
        _principal(),
        title="Rebuildable",
        text="Authoritative chunks survive a vector index rebuild.",
    )
    vector = _Vector()
    indexer = KnowledgeVectorIndexer(
        store, vector, _Embedding(), profile_id="fixture/rebuild"
    )
    indexer.sync()

    indexer.reset()
    reset_status = indexer.status()
    assert reset_status.sequence == 0
    assert reset_status.target_sequence > 0
    assert not vector.records

    rebuilt = indexer.sync()
    assert rebuilt.changed_items == 1
    assert {record.item_id for record in vector.records.values()} == {item.id}
    assert indexer.status().status == "ready"


def test_failed_platform_index_can_retry_from_durable_watermark(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.db")
    database.initialize()
    store = KnowledgeStore(database)
    store.create_text_item(
        _principal(),
        title="Retryable index",
        text="A failed embedding batch must not advance the watermark.",
    )
    vector = _Vector()
    failed = KnowledgeVectorIndexer(
        store, vector, _FailingEmbedding(), profile_id="fixture/retry"
    )

    with pytest.raises(RuntimeError, match="fixture embedding unavailable"):
        failed.sync()
    failed_status = failed.status()
    assert failed_status.status == "error"
    assert failed_status.sequence == 0
    assert failed_status.last_error == "fixture embedding unavailable"

    retry = KnowledgeVectorIndexer(
        store, vector, _Embedding(), profile_id="fixture/retry"
    )
    result = retry.sync()
    assert result.changed_items == 1
    assert retry.status().status == "ready"
