"""Incremental, rebuildable Knowledge vector indexing."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from ai2apps.core import utc_now_text

from .backends.protocol import EmbeddingProvider, VectorIndexBackend, VectorRecord
from .store import KnowledgeStore

CHUNK_CHARACTERS = 1800
CHUNK_OVERLAP = 200
MAX_CHUNKS_PER_ITEM = 512
EMBEDDING_BATCH = 32
VECTOR_BATCH = 256


@dataclass(frozen=True, slots=True)
class IndexSyncResult:
    sequence: int
    changed_items: int
    indexed_chunks: int
    deleted_items: int


@dataclass(frozen=True, slots=True)
class IndexStatus:
    profile_id: str
    generation: str
    sequence: int
    target_sequence: int
    status: str
    processed_changes: int
    indexed_chunks: int
    last_error: str | None
    started_at: str | None
    completed_at: str | None
    updated_at: str | None


def _chunks(title: str, text: str) -> tuple[str, ...]:
    content = (title.strip() + "\n\n" + text.strip()).strip()
    if not content:
        return ()
    result = []
    start = 0
    while start < len(content) and len(result) < MAX_CHUNKS_PER_ITEM:
        end = min(len(content), start + CHUNK_CHARACTERS)
        if end < len(content):
            boundary = max(
                content.rfind("\n", start + CHUNK_CHARACTERS // 2, end),
                content.rfind("。", start + CHUNK_CHARACTERS // 2, end),
                content.rfind(". ", start + CHUNK_CHARACTERS // 2, end),
            )
            if boundary > start:
                end = boundary + 1
        result.append(content[start:end])
        if end >= len(content):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return tuple(result)


class KnowledgeVectorIndexer:
    """Replay the authoritative change log into a disposable vector index."""

    def __init__(
        self,
        store: KnowledgeStore,
        vector_backend: VectorIndexBackend,
        embedding_provider: EmbeddingProvider,
        *,
        profile_id: str | None = None,
    ) -> None:
        self.store = store
        self.vector_backend = vector_backend
        self.embedding_provider = embedding_provider
        self.profile_id = profile_id or (
            f"{embedding_provider.model_id}/{vector_backend.generation}"
        )
        self.generation = vector_backend.generation
        self._sequence = 0
        self._lock = threading.Lock()

    def _has_durable_state(self, connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='knowledge_index_states'"
            ).fetchone()
            is not None
        )

    def _prepare_state(self, connection) -> tuple[int, int, bool]:
        target = int(
            connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) FROM knowledge_change_log"
            ).fetchone()[0]
        )
        durable = self._has_durable_state(connection)
        if not durable:
            return self._sequence, target, False
        now = utc_now_text()
        row = connection.execute(
            "SELECT generation, sequence FROM knowledge_index_states WHERE profile_id=?",
            (self.profile_id,),
        ).fetchone()
        sequence = (
            int(row["sequence"])
            if row is not None and str(row["generation"]) == self.generation
            else 0
        )
        connection.execute(
            """
            INSERT INTO knowledge_index_states(
                profile_id, generation, sequence, target_sequence, status,
                processed_changes, indexed_chunks, last_error, started_at, updated_at
            ) VALUES (?, ?, ?, ?, 'indexing', 0, 0, NULL, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET
                generation=excluded.generation,
                sequence=CASE
                    WHEN knowledge_index_states.generation=excluded.generation
                    THEN knowledge_index_states.sequence ELSE 0 END,
                processed_changes=CASE
                    WHEN knowledge_index_states.generation=excluded.generation
                    THEN knowledge_index_states.processed_changes ELSE 0 END,
                indexed_chunks=CASE
                    WHEN knowledge_index_states.generation=excluded.generation
                    THEN knowledge_index_states.indexed_chunks ELSE 0 END,
                target_sequence=excluded.target_sequence,
                status='indexing', last_error=NULL,
                started_at=excluded.updated_at, updated_at=excluded.updated_at
            """,
            (self.profile_id, self.generation, sequence, target, now, now),
        )
        return sequence, target, True

    def _finish_state(
        self,
        *,
        sequence: int | None = None,
        target: int | None = None,
        changed: int = 0,
        indexed: int = 0,
        error: Exception | None = None,
    ) -> None:
        with self.store.transaction(write=True) as connection:
            if not self._has_durable_state(connection):
                return
            now = utc_now_text()
            if error is not None:
                connection.execute(
                    """
                    UPDATE knowledge_index_states
                    SET status='error', last_error=?, completed_at=?, updated_at=?
                    WHERE profile_id=?
                    """,
                    (str(error)[:1000], now, now, self.profile_id),
                )
                return
            assert sequence is not None and target is not None
            status = "ready" if sequence >= target else "idle"
            connection.execute(
                """
                UPDATE knowledge_index_states
                SET sequence=?, target_sequence=?, status=?,
                    processed_changes=processed_changes+?,
                    indexed_chunks=indexed_chunks+?, last_error=NULL,
                    completed_at=?, updated_at=?
                WHERE profile_id=?
                """,
                (
                    sequence,
                    target,
                    status,
                    changed,
                    indexed,
                    now,
                    now,
                    self.profile_id,
                ),
            )

    def status(self) -> IndexStatus:
        with self.store.transaction() as connection:
            target = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) FROM knowledge_change_log"
                ).fetchone()[0]
            )
            if self._has_durable_state(connection):
                row = connection.execute(
                    "SELECT * FROM knowledge_index_states WHERE profile_id=?",
                    (self.profile_id,),
                ).fetchone()
                if row is not None:
                    return IndexStatus(
                        profile_id=self.profile_id,
                        generation=str(row["generation"]),
                        sequence=int(row["sequence"]),
                        target_sequence=max(target, int(row["target_sequence"])),
                        status=str(row["status"]),
                        processed_changes=int(row["processed_changes"]),
                        indexed_chunks=int(row["indexed_chunks"]),
                        last_error=row["last_error"],
                        started_at=row["started_at"],
                        completed_at=row["completed_at"],
                        updated_at=row["updated_at"],
                    )
        return IndexStatus(
            self.profile_id,
            self.generation,
            self._sequence,
            target,
            "ready" if self._sequence >= target else "idle",
            0,
            0,
            None,
            None,
            None,
            None,
        )

    def reset(self) -> None:
        """Drop the derived generation and rewind its durable watermark."""

        with self._lock:
            self.vector_backend.reset()
            self._sequence = 0
            with self.store.transaction(write=True) as connection:
                if not self._has_durable_state(connection):
                    return
                target = int(
                    connection.execute(
                        "SELECT COALESCE(MAX(sequence), 0) FROM knowledge_change_log"
                    ).fetchone()[0]
                )
                now = utc_now_text()
                connection.execute(
                    """
                    INSERT INTO knowledge_index_states(
                        profile_id,generation,sequence,target_sequence,status,
                        processed_changes,indexed_chunks,last_error,updated_at
                    ) VALUES(?,?,0,?,'idle',0,0,NULL,?)
                    ON CONFLICT(profile_id) DO UPDATE SET
                        generation=excluded.generation, sequence=0,
                        target_sequence=excluded.target_sequence, status='idle',
                        processed_changes=0, indexed_chunks=0, last_error=NULL,
                        started_at=NULL, completed_at=NULL, updated_at=excluded.updated_at
                    """,
                    (self.profile_id, self.generation, target, now),
                )

    def sync(self, *, max_changes: int = 200) -> IndexSyncResult:
        if not 1 <= max_changes <= 10_000:
            raise ValueError("max_changes must be between 1 and 10000")
        with self._lock:
            try:
                return self._sync(max_changes=max_changes)
            except Exception as error:
                self._finish_state(error=error)
                raise

    def _sync(self, *, max_changes: int) -> IndexSyncResult:
        with self.store.transaction(write=True) as connection:
            sequence_before, target, durable = self._prepare_state(connection)
            rows = connection.execute(
                """
                SELECT sequence, operation, item_id
                FROM knowledge_change_log
                WHERE sequence > ? ORDER BY sequence LIMIT ?
                """,
                (sequence_before, max_changes),
            ).fetchall()
            if not rows:
                self._sequence = sequence_before
                if durable:
                    now = utc_now_text()
                    connection.execute(
                        """
                        UPDATE knowledge_index_states
                        SET sequence=?, target_sequence=?, status='ready',
                            last_error=NULL, completed_at=?, updated_at=?
                        WHERE profile_id=?
                        """,
                        (sequence_before, target, now, now, self.profile_id),
                    )
                return IndexSyncResult(sequence_before, 0, 0, 0)
            sequence = int(rows[-1]["sequence"])
            latest = {str(row["item_id"]): str(row["operation"]) for row in rows}
            item_ids = tuple(latest)
            placeholders = ",".join("?" for _ in item_ids)
            active_rows = connection.execute(
                f"""
                SELECT i.id, i.installation_id, i.owner_user_id, i.visibility,
                       i.title, r.text
                FROM knowledge_items i
                JOIN knowledge_representations r
                  ON r.item_id=i.id AND r.ordinal=0
                WHERE i.id IN ({placeholders})
                  AND i.status='ready' AND i.deleted_at IS NULL
                """,
                item_ids,
            ).fetchall()
            chunk_rows = connection.execute(
                f"""
                SELECT item_id, ordinal, text
                FROM knowledge_chunks
                WHERE item_id IN ({placeholders})
                ORDER BY item_id, ordinal
                """,
                item_ids,
            ).fetchall()
            has_buckets = connection.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name='knowledge_bucket_items'"
            ).fetchone()
            bucket_rows = (
                connection.execute(
                    f"""
                    SELECT item_id, bucket_id FROM knowledge_bucket_items
                    WHERE item_id IN ({placeholders})
                    ORDER BY item_id, position
                    """,
                    item_ids,
                ).fetchall()
                if has_buckets is not None
                else ()
            )

        buckets: dict[str, list[str]] = {}
        for row in bucket_rows:
            buckets.setdefault(str(row["item_id"]), []).append(str(row["bucket_id"]))
        active_ids = {str(row["id"]) for row in active_rows}
        deleted = tuple(item_id for item_id in item_ids if item_id not in active_ids)
        self.vector_backend.delete_items(deleted)

        chunks_by_item: dict[str, list[tuple[int, str]]] = {}
        for chunk in chunk_rows:
            chunks_by_item.setdefault(str(chunk["item_id"]), []).append(
                (int(chunk["ordinal"]), str(chunk["text"]))
            )
        pending: list[tuple[object, int, str]] = []
        for row in active_rows:
            item_id = str(row["id"])
            source_chunks = chunks_by_item.get(item_id) or [(0, str(row["text"]))]
            for source_ordinal, source_text in source_chunks:
                for sub_ordinal, text in enumerate(
                    _chunks(str(row["title"]), source_text)
                ):
                    ordinal = source_ordinal * MAX_CHUNKS_PER_ITEM + sub_ordinal
                    pending.append((row, ordinal, text))

        records: list[VectorRecord] = []
        indexed = 0
        for offset in range(0, len(pending), EMBEDDING_BATCH):
            batch = pending[offset : offset + EMBEDDING_BATCH]
            vectors = self.embedding_provider.embed(tuple(value[2] for value in batch))
            if len(vectors) != len(batch):
                raise RuntimeError(
                    "Embedding Provider returned an incomplete index batch"
                )
            for (row, ordinal, text), vector in zip(batch, vectors, strict=True):
                item_id = str(row["id"])
                records.append(
                    VectorRecord(
                        chunk_id=f"{item_id}:{ordinal}",
                        item_id=item_id,
                        installation_id=str(row["installation_id"]),
                        owner_user_id=str(row["owner_user_id"]),
                        visibility=str(row["visibility"]),
                        bucket_ids=tuple(buckets.get(item_id, ())),
                        text=text,
                        vector=vector,
                    )
                )
                if len(records) >= VECTOR_BATCH:
                    self.vector_backend.upsert(records)
                    indexed += len(records)
                    records.clear()
        if records:
            self.vector_backend.upsert(records)
            indexed += len(records)
        self._sequence = sequence
        if durable:
            self._finish_state(
                sequence=sequence,
                target=target,
                changed=len(item_ids),
                indexed=indexed,
            )
        return IndexSyncResult(sequence, len(item_ids), indexed, len(deleted))
