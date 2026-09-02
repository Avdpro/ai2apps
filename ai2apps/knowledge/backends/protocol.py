"""Backend-neutral contracts for rebuildable semantic Knowledge indices."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


class VectorBackendError(RuntimeError):
    """A derived vector index operation failed."""


class VectorBackendUnavailableError(VectorBackendError):
    """The optional semantic backend is not installed or ready."""


@dataclass(frozen=True, slots=True)
class BackendHealth:
    status: str
    backend: str
    generation: str
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One rebuildable chunk row sent to an isolated vector backend."""

    chunk_id: str
    item_id: str
    installation_id: str
    owner_user_id: str
    visibility: str
    bucket_ids: tuple[str, ...]
    text: str
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class VectorSearchRequest:
    vector: tuple[float, ...]
    installation_id: str
    actor_user_id: str
    bucket_ids: tuple[str, ...] = ()
    limit: int = 20


@dataclass(frozen=True, slots=True)
class VectorSearchCandidate:
    chunk_id: str
    item_id: str
    text: str
    distance: float


class VectorIndexBackend(Protocol):
    """Protocol implemented by an isolated, disposable vector index."""

    @property
    def generation(self) -> str: ...

    def upsert(self, records: Sequence[VectorRecord]) -> None: ...

    def delete_items(self, item_ids: Sequence[str]) -> None: ...

    def reset(self) -> None: ...

    def search(
        self, request: VectorSearchRequest
    ) -> tuple[VectorSearchCandidate, ...]: ...

    def count(self) -> int: ...

    def health(self) -> BackendHealth: ...


class EmbeddingProvider(Protocol):
    """Embedding stays independent from the vector database implementation."""

    @property
    def model_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: Sequence[str]) -> tuple[tuple[float, ...], ...]: ...
