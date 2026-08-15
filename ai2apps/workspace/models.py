"""Workspace, opaque ResourceHandle, and immutable Artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class ResourceKind(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    ARTIFACT = "artifact"


class LocatorKind(StrEnum):
    WORKSPACE = "workspace"
    ARTIFACT = "artifact"
    EXTERNAL = "external"


@dataclass(frozen=True, slots=True)
class SandboxRecord:
    id: str
    session_id: str
    quota_bytes: int
    used_bytes: int
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ResourceHandleRecord:
    id: str
    session_id: str
    artifact_id: str | None
    kind: ResourceKind
    display_name: str
    locator_kind: LocatorKind
    locator: str
    capabilities: tuple[str, ...]
    media_type: str | None
    size_bytes: int | None
    content_hash: str | None
    source: str
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def uri(self) -> str:
        return f"resource://{self.id}"


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    id: str
    session_id: str
    run_id: str | None
    name: str
    media_type: str
    content_hash: str
    size_bytes: int
    storage_key: str
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @property
    def uri(self) -> str:
        return f"artifact://{self.id}"


class WorkspaceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)
