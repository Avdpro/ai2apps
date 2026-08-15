"""Trusted Service package, dependency, audit, and operation contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from ai2apps.services import ServiceDependency, ServiceRuntimeMode


class PackageError(RuntimeError):
    def __init__(
        self, code: str, message: str, *, details: dict[str, Any] | None = None
    ):
        self.code = code
        self.details = details or {}
        super().__init__(message)


class TrustStatus(StrEnum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    REVOKED = "revoked"


class PackageStatus(StrEnum):
    INSTALLED = "installed"
    ACTIVE = "active"
    RETAINED = "retained"
    REJECTED = "rejected"
    UNINSTALLED = "uninstalled"


class AuditDecision(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    REJECT = "reject"


class AuditRisk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class OperationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True, slots=True)
class PackageFile:
    path: str
    content_hash: str
    size_bytes: int
    media_type: str | None = None


@dataclass(frozen=True, slots=True)
class ServicePackageManifest:
    service_key: str
    name: str
    version: str
    publisher_key: str
    runtime_mode: ServiceRuntimeMode
    protocol: str
    entrypoint: str | None
    command: tuple[str, ...]
    endpoint: str | None
    contract: str | None
    capabilities: tuple[str, ...]
    dependencies: tuple[ServiceDependency, ...]
    permissions: dict[str, Any]
    compatibility: dict[str, Any]
    health: dict[str, Any]
    restart: dict[str, Any]
    tools: tuple[dict[str, Any], ...]
    models: tuple[dict[str, Any], ...]
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class InspectedServicePackage:
    archive_path: Path
    digest: str
    manifest: ServicePackageManifest
    files: tuple[PackageFile, ...]
    sbom: dict[str, Any]
    publisher_attestation: dict[str, Any]
    signature: dict[str, Any]
    bundled_attestations: tuple[dict[str, Any], ...]
    total_size_bytes: int


@dataclass(frozen=True, slots=True)
class PublisherRecord:
    id: str
    publisher_key: str
    display_name: str
    key_id: str
    algorithm: str
    public_key: str
    trust_status: TrustStatus
    source: str
    metadata: dict[str, Any]
    revision: int
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class InstalledPackageRecord:
    id: str
    service_key: str
    package_version: str
    package_digest: str
    publisher_key: str
    runtime_mode: ServiceRuntimeMode
    protocol: str
    entrypoint: str | None
    archive_path: str
    store_path: str
    manifest: dict[str, Any]
    permissions: dict[str, Any]
    compatibility: dict[str, Any]
    sbom: dict[str, Any]
    verification: dict[str, Any]
    status: PackageStatus
    installed_at: datetime
    activated_at: datetime | None
    retired_at: datetime | None


@dataclass(frozen=True, slots=True)
class AttestationRecord:
    id: str
    package_digest: str
    kind: str
    issuer: str
    decision: AuditDecision
    risk: AuditRisk
    model: str | None
    policy_version: str | None
    evidence: dict[str, Any]
    signature: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class DependencyLock:
    service_key: str
    package_digest: str
    dependency_key: str
    dependency_version: str
    dependency_digest: str
    optional: bool


@dataclass(frozen=True, slots=True)
class InstallPlan:
    root_digest: str
    packages: tuple[InspectedServicePackage, ...]
    locks: tuple[DependencyLock, ...]
    replacing: dict[str, str]


@dataclass(frozen=True, slots=True)
class CompatibilityContext:
    os_name: str
    architecture: str
    python_version: str
    accelerator: str | None = None
    features: frozenset[str] = frozenset()
