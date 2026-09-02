"""LanceDB spike adapter.

This module is deliberately lazy-loaded. Production use belongs in an isolated
``.ai2service`` Worker; the AI2Apps Host must not import LanceDB at startup.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .protocol import (
    BackendHealth,
    VectorBackendError,
    VectorBackendUnavailableError,
    VectorRecord,
    VectorSearchCandidate,
    VectorSearchRequest,
)

_SAFE_GENERATION = re.compile(r"[^a-zA-Z0-9_]")


def _sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


class LanceDBVectorBackend:
    """Synchronous LanceDB implementation used by the isolated spike Worker."""

    def __init__(
        self,
        root: str | Path,
        *,
        generation: str,
        dimension: int,
        connection: Any | None = None,
    ) -> None:
        if dimension < 1:
            raise ValueError("dimension must be positive")
        normalized = _SAFE_GENERATION.sub("_", generation).strip("_")
        if not normalized:
            raise ValueError("generation must contain a letter or number")
        self.root = Path(root)
        self._generation = generation
        self.dimension = dimension
        self.table_name = f"knowledge_{normalized}"
        self._connection = connection

    @property
    def generation(self) -> str:
        return self._generation

    def _db(self):
        if self._connection is not None:
            return self._connection
        try:
            import lancedb
        except ImportError as error:
            raise VectorBackendUnavailableError(
                "LanceDB is not installed in the Knowledge vector Runtime"
            ) from error
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            self._connection = lancedb.connect(str(self.root))
        except Exception as error:
            raise VectorBackendUnavailableError(
                f"cannot open LanceDB: {error}"
            ) from error
        return self._connection

    def _table_names(self) -> tuple[str, ...]:
        names = self._db().table_names()
        if hasattr(names, "tables"):
            names = names.tables
        return tuple(str(name) for name in names)

    def _table(self):
        if self.table_name not in self._table_names():
            return None
        return self._db().open_table(self.table_name)

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        rows = []
        for record in records:
            if len(record.vector) != self.dimension:
                raise VectorBackendError(
                    f"vector dimension {len(record.vector)} does not match {self.dimension}"
                )
            rows.append(
                {
                    "chunk_id": record.chunk_id,
                    "item_id": record.item_id,
                    "installation_id": record.installation_id,
                    "owner_user_id": record.owner_user_id,
                    "visibility": record.visibility,
                    "bucket_ids": list(record.bucket_ids),
                    "text": record.text,
                    "vector": list(record.vector),
                }
            )
        try:
            table = self._table()
            if table is None:
                self._db().create_table(self.table_name, data=rows)
                return
            (
                table.merge_insert("chunk_id")
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(rows)
            )
        except VectorBackendError:
            raise
        except Exception as error:
            raise VectorBackendError(f"LanceDB upsert failed: {error}") from error

    def delete_items(self, item_ids: Sequence[str]) -> None:
        selected = tuple(dict.fromkeys(item_ids))
        if not selected:
            return
        table = self._table()
        if table is None:
            return
        values = ",".join(_sql_string(item_id) for item_id in selected)
        try:
            table.delete(f"item_id IN ({values})")
        except Exception as error:
            raise VectorBackendError(f"LanceDB delete failed: {error}") from error

    @staticmethod
    def _acl_filter(request: VectorSearchRequest) -> str:
        installation = _sql_string(request.installation_id)
        actor = _sql_string(request.actor_user_id)
        clauses = [
            f"installation_id = {installation}",
            "(visibility = 'installation' OR "
            f"(visibility = 'private' AND owner_user_id = {actor}))",
        ]
        if request.bucket_ids:
            buckets = ",".join(_sql_string(value) for value in request.bucket_ids)
            clauses.append(f"array_has_any(bucket_ids, [{buckets}])")
        return " AND ".join(clauses)

    def search(self, request: VectorSearchRequest) -> tuple[VectorSearchCandidate, ...]:
        if len(request.vector) != self.dimension:
            raise VectorBackendError("query vector dimension mismatch")
        if not 1 <= request.limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        table = self._table()
        if table is None:
            return ()
        try:
            rows = (
                table.search(list(request.vector), vector_column_name="vector")
                .where(self._acl_filter(request), prefilter=True)
                .select(["chunk_id", "item_id", "text"])
                .limit(request.limit)
                .to_arrow()
                .to_pylist()
            )
        except Exception as error:
            raise VectorBackendError(f"LanceDB search failed: {error}") from error
        return tuple(
            VectorSearchCandidate(
                chunk_id=str(row["chunk_id"]),
                item_id=str(row["item_id"]),
                text=str(row["text"]),
                distance=float(row["_distance"]),
            )
            for row in rows
        )

    def count(self) -> int:
        table = self._table()
        return 0 if table is None else int(table.count_rows())

    def health(self) -> BackendHealth:
        try:
            self._db()
            count = self.count()
        except VectorBackendError as error:
            return BackendHealth(
                status="unavailable",
                backend="lancedb",
                generation=self.generation,
                detail=str(error),
            )
        return BackendHealth(
            status="ready",
            backend="lancedb",
            generation=self.generation,
            detail=f"{count} chunks",
        )
