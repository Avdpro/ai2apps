"""Contracts for installable Agent/App packages and device-local Patch stacks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class UnitKind(StrEnum):
    AGENT = "agent"
    APP = "app"


class InteractivePackageStatus(StrEnum):
    INSTALLED = "installed"
    ACTIVE = "active"
    RETAINED = "retained"
    CONFLICTED = "conflicted"
    UNINSTALLED = "uninstalled"


class PatchStatus(StrEnum):
    CLEAN = "clean"
    REBASED = "rebased"
    NEEDS_REVIEW = "needs-review"
    CONFLICTED = "conflicted"
    DISABLED = "disabled"
    SUPERSEDED = "superseded"
    FAILED_TESTS = "failed-tests"


class RebasePolicy(StrEnum):
    STRICT = "strict"
    PRESERVE_LOCAL = "preserve-local"
    AI_ASSISTED = "ai-assisted"
    DROP_IF_SATISFIED = "drop-if-satisfied"


class ExtensionError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None) -> None:
        self.code = code
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class BundleFile:
    path: str
    content_hash: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class InspectedBundle:
    kind: UnitKind | str
    key: str
    version: str
    digest: str
    manifest: dict[str, Any]
    files: tuple[BundleFile, ...]
    sbom: dict[str, Any]
    signature: dict[str, Any]
    attestation: dict[str, Any]
    archive_path: Path


@dataclass(frozen=True, slots=True)
class InteractivePackageRecord:
    id: str
    kind: UnitKind
    unit_key: str
    version: str
    digest: str
    publisher_key: str
    archive_path: str
    store_path: str
    manifest: dict[str, Any]
    file_index: tuple[dict[str, Any], ...]
    sbom: dict[str, Any]
    verification: dict[str, Any]
    status: InteractivePackageStatus
    installed_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


@dataclass(frozen=True, slots=True)
class LocalPatchRecord:
    id: str
    target_kind: UnitKind
    target_key: str
    version: str
    digest: str
    base_digest: str
    intent: str
    rebase_policy: RebasePolicy
    operations: tuple[dict[str, Any], ...]
    resources: dict[str, Any]
    tests: tuple[dict[str, Any], ...]
    audit: dict[str, Any]
    signature: dict[str, Any]
    stack_order: int
    status: PatchStatus
    conflict: dict[str, Any] | None
    archive_path: str
    store_path: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class EffectiveDefinitionRecord:
    id: str
    kind: UnitKind
    unit_key: str
    upstream_digest: str
    patch_set_digest: str
    effective_digest: str
    effective_version: str
    manifest: dict[str, Any]
    resources: dict[str, Any]
    audit: dict[str, Any]
    status: str
    revision: int
    created_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None
