from __future__ import annotations

from dataclasses import dataclass

from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.knowledge import HybridKnowledgeRetriever, KnowledgeStore
from ai2apps.knowledge.backends.lancedb import LanceDBVectorBackend
from ai2apps.knowledge.backends.protocol import (
    VectorBackendUnavailableError,
    VectorRecord,
    VectorSearchCandidate,
    VectorSearchRequest,
)


def _principal(user: str) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user,
        installation_id="installation-a",
        organization_id="organization-a",
        billing_account_id="billing-a",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )


@dataclass
class _Embedding:
    model_id: str = "test/hash-v1"
    dimension: int = 2

    def embed(self, texts):
        return tuple((0.25, 0.75) for _ in texts)


class _VectorBackend:
    generation = "test-generation"

    def __init__(self, candidates=(), error: Exception | None = None):
        self.candidates = tuple(candidates)
        self.error = error
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.candidates


def test_hybrid_retrieval_adds_semantic_only_hits_and_rechecks_sqlite_acl(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    bob = _principal("bob")
    lexical = store.create_text_item(
        alice,
        title="Watermelon notes",
        text="Watermelon irrigation schedule.",
    )
    semantic = store.create_text_item(
        alice,
        title="Orchard operations",
        text="Apple trees need seasonal pruning.",
    )
    hidden = store.create_text_item(
        bob,
        title="Bob private orchard",
        text="This private orchard must not leak.",
    )
    backend = _VectorBackend(
        (
            VectorSearchCandidate("hidden", hidden.id, hidden.text, 0.01),
            VectorSearchCandidate("semantic", semantic.id, semantic.text, 0.05),
        )
    )
    retriever = HybridKnowledgeRetriever(store, backend, _Embedding())

    hits, diagnostics = retriever.search(alice, "watermelon", limit=10)

    assert {hit.item.id for hit in hits} == {lexical.id, semantic.id}
    assert hidden.id not in {hit.item.id for hit in hits}
    assert diagnostics.mode == "hybrid"
    assert diagnostics.lexical_candidates == 1
    assert diagnostics.semantic_candidates == 1
    assert backend.requests[0].actor_user_id == "alice"


def test_hybrid_retrieval_preserves_relevant_text_after_first_thousand_characters(
    tmp_path,
):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    item = store.create_text_item(
        alice,
        title="Watchmaking article",
        text="A long imported web article.",
    )
    relevant = "tremblage creates thousands of tiny irregular granulations"
    candidate_text = ("navigation filler " * 75) + relevant
    backend = _VectorBackend(
        (VectorSearchCandidate("watchmaking:10", item.id, candidate_text, 0.01),)
    )
    retriever = HybridKnowledgeRetriever(store, backend, _Embedding())

    hits, _diagnostics = retriever.search(alice, "irregular gold dial texture")

    assert len(candidate_text) > 1000
    assert len(hits) == 1
    assert relevant in hits[0].excerpt


def test_hybrid_retrieval_prefers_article_prose_over_same_item_navigation(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    item = store.create_text_item(
        alice,
        title="Watchmaking article",
        text="A long imported web article.",
    )
    navigation = "\n".join(
        ["F.P.Journe", "A. Lange & Söhne"]
        + [f"Watch Brand {index}" for index in range(200)]
    )
    prose = (
        "The dial uses hand tremblage. The engraver continuously oscillates "
        "a graver across the gold surface. This creates irregular granulations."
    )
    backend = _VectorBackend(
        (
            VectorSearchCandidate("watchmaking:menu", item.id, navigation, 0.01),
            VectorSearchCandidate("watchmaking:article", item.id, prose, 0.02),
        )
    )
    retriever = HybridKnowledgeRetriever(store, backend, _Embedding())

    hits, diagnostics = retriever.search(alice, "irregular gold dial texture")

    assert len(hits) == 1
    assert hits[0].excerpt == prose
    assert diagnostics.semantic_candidates == 2


def test_hybrid_retrieval_falls_back_to_fts_when_vector_runtime_is_unavailable(
    tmp_path,
):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    store.initialize()
    alice = _principal("alice")
    item = store.create_text_item(
        alice,
        title="Fallback handbook",
        text="Watermelon fallback remains searchable.",
    )
    backend = _VectorBackend(error=VectorBackendUnavailableError("runtime missing"))
    retriever = HybridKnowledgeRetriever(store, backend, _Embedding())

    hits, diagnostics = retriever.search(alice, "watermelon")

    assert [hit.item.id for hit in hits] == [item.id]
    assert diagnostics.mode == "fts5"
    assert diagnostics.semantic_error == "runtime missing"


class _ArrowRows:
    def __init__(self, rows):
        self.rows = rows

    def to_pylist(self):
        return self.rows


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.where_call = None

    def where(self, predicate, *, prefilter):
        self.where_call = (predicate, prefilter)
        return self

    def select(self, _columns):
        return self

    def limit(self, _limit):
        return self

    def to_arrow(self):
        return _ArrowRows(self.rows)


class _Merge:
    def __init__(self, table):
        self.table = table

    def when_matched_update_all(self):
        return self

    def when_not_matched_insert_all(self):
        return self

    def execute(self, rows):
        self.table.merged = rows


class _Table:
    def __init__(self):
        self.merged = None
        self.deleted = None
        self.query = None

    def merge_insert(self, key):
        assert key == "chunk_id"
        return _Merge(self)

    def delete(self, predicate):
        self.deleted = predicate

    def search(self, _vector, *, vector_column_name):
        assert vector_column_name == "vector"
        self.query = _Query(
            [
                {
                    "chunk_id": "chunk-1",
                    "item_id": "item-1",
                    "text": "semantic text",
                    "_distance": 0.125,
                }
            ]
        )
        return self.query

    def count_rows(self):
        return 1


class _Connection:
    def __init__(self):
        self.table = _Table()
        self.created = None

    def table_names(self):
        return ["knowledge_active"]

    def open_table(self, name):
        assert name == "knowledge_active"
        return self.table

    def create_table(self, name, *, data):
        self.created = (name, data)


def test_lancedb_adapter_upserts_and_uses_acl_prefilter(tmp_path):
    connection = _Connection()
    backend = LanceDBVectorBackend(
        tmp_path,
        generation="active",
        dimension=2,
        connection=connection,
    )
    backend.upsert(
        (
            VectorRecord(
                chunk_id="chunk-1",
                item_id="item-1",
                installation_id="installation-a",
                owner_user_id="o'connor",
                visibility="private",
                bucket_ids=("bucket-a",),
                text="semantic text",
                vector=(0.25, 0.75),
            ),
        )
    )
    hits = backend.search(
        VectorSearchRequest(
            vector=(0.25, 0.75),
            installation_id="installation-a",
            actor_user_id="o'connor",
            bucket_ids=("bucket-a",),
            limit=5,
        )
    )

    assert connection.table.merged[0]["chunk_id"] == "chunk-1"
    predicate, prefilter = connection.table.query.where_call
    assert prefilter is True
    assert "installation_id = 'installation-a'" in predicate
    assert "owner_user_id = 'o''connor'" in predicate
    assert "array_has_any(bucket_ids, ['bucket-a'])" in predicate
    assert hits[0].item_id == "item-1"
    assert backend.health().status == "ready"
