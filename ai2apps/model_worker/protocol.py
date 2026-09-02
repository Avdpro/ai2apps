# SPDX-License-Identifier: Apache-2.0
"""Public v1 contracts implemented by a Model Package adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class ModelWorkerError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "model_worker_error",
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ModelWorkerCheckpoint:
    """A checkpoint selected and resolved by the trusted Host."""

    model_id: str
    upstream_id: str
    provider: str
    repo_id: str
    revision: str
    path: Path | None
    preparation: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ModelWorkerContext:
    service_id: str
    package_root: Path
    data_root: Path
    models: tuple[Mapping[str, Any], ...]
    checkpoints: tuple[ModelWorkerCheckpoint, ...] = ()
    huggingface_cache_root: Path | None = None

    def checkpoint_for(self, model_id: str) -> ModelWorkerCheckpoint | None:
        return next(
            (
                checkpoint
                for checkpoint in self.checkpoints
                if model_id in {checkpoint.model_id, checkpoint.upstream_id}
            ),
            None,
        )


@dataclass(frozen=True, slots=True)
class ModelWorkerPart:
    """A request-scoped file materialized by the trusted Worker transport.

    The path is valid only for the duration of the invocation (including a
    streaming response) and must never be persisted or returned to clients.
    """

    name: str
    path: Path
    media_type: str
    filename: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ModelWorkerRequest:
    operation: str
    payload: Mapping[str, Any]
    request_id: str
    parts: Mapping[str, ModelWorkerPart] | None = None
    output_root: Path | None = None
    progress: Callable[[Mapping[str, Any]], Awaitable[None] | None] | None = None

    def part(self, name: str) -> ModelWorkerPart:
        part = (self.parts or {}).get(name)
        if part is None:
            raise ModelWorkerError(
                f"Required request part is missing: {name}",
                code="invalid_request_part",
                status_code=400,
            )
        return part


@dataclass(frozen=True, slots=True)
class ModelWorkerResponse:
    content: bytes
    media_type: str = "application/octet-stream"
    status_code: int = 200
    headers: Mapping[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ModelWorkerArtifact:
    """A response file created under this request's controlled output root."""

    path: Path
    media_type: str
    filename: str
    metadata: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ModelWorkerStream:
    chunks: AsyncIterator[bytes]
    media_type: str = "text/event-stream"
    status_code: int = 200
    headers: Mapping[str, str] | None = None


@runtime_checkable
class ModelWorkerAdapter(Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def invoke(
        self, request: ModelWorkerRequest
    ) -> Mapping[str, Any] | ModelWorkerResponse | ModelWorkerArtifact | ModelWorkerStream: ...
