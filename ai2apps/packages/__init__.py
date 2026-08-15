"""Trusted, dependency-aware AI2Apps Service packages."""

from .archive import ServicePackageArchive, canonical_json, package_digest
from .manager import ServicePackageManager
from .models import (
    AttestationRecord,
    AuditDecision,
    AuditRisk,
    CompatibilityContext,
    DependencyLock,
    InspectedServicePackage,
    InstalledPackageRecord,
    InstallPlan,
    PackageError,
    PackageFile,
    PackageStatus,
    PublisherRecord,
    ServicePackageManifest,
    TrustStatus,
)
from .repository import PackageRepository
from .resolver import ServiceDependencyResolver
from .trust import PackageTrustVerifier

__all__ = [
    "AttestationRecord",
    "AuditDecision",
    "AuditRisk",
    "CompatibilityContext",
    "DependencyLock",
    "InstalledPackageRecord",
    "InspectedServicePackage",
    "InstallPlan",
    "PackageError",
    "PackageFile",
    "PackageRepository",
    "PackageStatus",
    "PackageTrustVerifier",
    "PublisherRecord",
    "ServiceDependencyResolver",
    "ServicePackageArchive",
    "ServicePackageManager",
    "ServicePackageManifest",
    "TrustStatus",
    "canonical_json",
    "package_digest",
]
