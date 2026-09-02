"""Versioned retrieval profiles independent from authoritative Knowledge data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum


class RetrievalMode(StrEnum):
    FTS5 = "fts5"
    HYBRID = "hybrid"


@dataclass(frozen=True, slots=True)
class RetrievalProfile:
    id: str
    revision: int
    mode: RetrievalMode
    lexical_backend: str = "sqlite-fts5"
    vector_backend: str | None = None
    embedding_model_id: str | None = None
    embedding_dimension: int | None = None
    fusion: str | None = None
    rrf_constant: int = 60
    lexical_weight: float = 1.0
    semantic_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.id or self.revision < 1:
            raise ValueError("retrieval profile identity is invalid")
        if self.rrf_constant < 1:
            raise ValueError("rrf_constant must be positive")
        if self.lexical_weight < 0 or self.semantic_weight < 0:
            raise ValueError("retrieval weights must not be negative")
        if self.mode is RetrievalMode.HYBRID and (
            not self.vector_backend
            or not self.embedding_model_id
            or not self.embedding_dimension
            or self.fusion != "rrf"
        ):
            raise ValueError("hybrid profiles require vector, embedding and RRF fields")

    @classmethod
    def fts5(cls) -> RetrievalProfile:
        return cls(id="ai2apps.knowledge.fts5/v1", revision=1, mode=RetrievalMode.FTS5)

    @classmethod
    def hybrid(
        cls,
        *,
        vector_backend: str,
        embedding_model_id: str,
        embedding_dimension: int,
        revision: int = 1,
    ) -> RetrievalProfile:
        return cls(
            id=(
                "ai2apps.knowledge.hybrid/"
                f"{vector_backend}/{embedding_model_id}/{embedding_dimension}/v{revision}"
            ),
            revision=revision,
            mode=RetrievalMode.HYBRID,
            vector_backend=vector_backend,
            embedding_model_id=embedding_model_id,
            embedding_dimension=embedding_dimension,
            fusion="rrf",
        )

    def descriptor(self) -> dict:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        return payload
