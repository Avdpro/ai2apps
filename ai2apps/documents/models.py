"""Durable attachment and parsed-document records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class DocumentStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AttachmentRecord:
    id: str
    session_id: str
    blob_id: str
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    metadata: dict[str, Any]
    error: dict[str, Any] | None
    created_at: str


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    id: str
    ordinal: int
    kind: str
    text: str
    page: int | None = None
    section: str | None = None
    sheet: str | None = None
    slide: int | None = None
    cell_range: str | None = None
    metadata: dict[str, Any] | None = None
