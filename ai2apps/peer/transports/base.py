"""Transport-neutral streaming contracts used by application protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol


class PeerTransportError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, result_unknown: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.result_unknown = result_unknown


@dataclass(frozen=True, slots=True)
class PeerTransportStream:
    status_code: int
    headers: Mapping[str, str]
    body: AsyncIterator[bytes]


@dataclass(frozen=True, slots=True)
class PeerTransportResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class PeerStreamingTransport(Protocol):
    async def post_stream(
        self, *, path: str, grant: str, payload: bytes, max_response_bytes: int
    ) -> PeerTransportStream: ...


class PeerRequestTransport(Protocol):
    async def post(
        self, *, path: str, grant: str, payload: bytes, max_response_bytes: int
    ) -> PeerTransportResponse: ...
