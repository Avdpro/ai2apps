"""Transactional trusted Service installation, activation, rollback, and removal."""

from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import shutil
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ai2apps.config import PlatformPaths
from ai2apps.core import ResourceNotFoundError
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ServiceStatus,
)

from .archive import ServicePackageArchive
from .models import (
    AuditDecision,
    AuditRisk,
    CompatibilityContext,
    InspectedServicePackage,
    InstalledPackageRecord,
    InstallPlan,
    PackageError,
    PackageStatus,
    TrustStatus,
)
from .repository import PackageRepository
from .resolver import ServiceDependencyResolver
from .runtime import PackageRuntimeBinder
from .supervisor import ManagedServiceSupervisor
from .trust import PackageTrustVerifier


class ServicePackageManager:
    def __init__(
        self,
        paths: PlatformPaths,
        packages: PackageRepository,
        services: ServiceRepository,
        registry: ServiceRegistry,
        *,
        compatibility: CompatibilityContext | None = None,
    ) -> None:
        self.paths = paths
        self.packages = packages
        self.services = services
        self.registry = registry
        self.trust = PackageTrustVerifier(packages)
        self.resolver = ServiceDependencyResolver(packages)
        self.supervisor = ManagedServiceSupervisor(
            packages, services, paths.packages_path
        )
        self.runtime = PackageRuntimeBinder(services, registry, self.supervisor)
        self.compatibility = compatibility or CompatibilityContext(
            os_name=platform.system().lower(),
            architecture=platform.machine().lower(),
            python_version=".".join(map(str, sys.version_info[:3])),
        )
        self._install_lock = asyncio.Lock()

    def inspect(self, archive_path: str | Path) -> InspectedServicePackage:
        package = ServicePackageArchive.inspect(archive_path)
        self._select_variant(package)
        return package

    def plan(
        self,
        archive_path: str | Path,
        dependency_archives: tuple[str | Path, ...] = (),
    ) -> InstallPlan:
        root = self.inspect(archive_path)
        candidates = tuple(self.inspect(path) for path in dependency_archives)
        plan = self.resolver.resolve(root, candidates)
        for package in plan.packages:
            for installed in self.packages.installed(package.manifest.service_key):
                if (
                    installed.package_version == package.manifest.version
                    and installed.package_digest != package.digest
                ):
                    raise PackageError(
                        "version_digest_conflict",
                        "The same Service version is already installed with a different digest",
                    )
        return plan

    def _check_active_dependents(
        self,
        plan: InstallPlan,
    ) -> None:
        """Reject an upgrade that would violate an unchanged active dependent."""
        planned_keys = {item.manifest.service_key for item in plan.packages}
        for candidate in plan.packages:
            version = Version(candidate.manifest.version)
            for dependent_key in self.packages.dependents(
                candidate.manifest.service_key
            ):
                if dependent_key in planned_keys:
                    continue
                dependent = self.packages.active(dependent_key)
                if dependent is None:
                    continue
                for requirement in dependent.manifest.get("requires", {}).get(
                    "services", []
                ):
                    if requirement.get("id") != candidate.manifest.service_key:
                        continue
                    raw_spec = str(requirement.get("version", "*"))
                    spec = SpecifierSet("" if raw_spec == "*" else raw_spec)
                    if version not in spec:
                        raise PackageError(
                            "dependent_version_conflict",
                            "Upgrade would break an active dependent Service",
                            details={
                                "service_key": candidate.manifest.service_key,
                                "version": candidate.manifest.version,
                                "dependent": dependent_key,
                                "required_version": raw_spec,
                            },
                        )

    def _active_start_order(self) -> tuple[InstalledPackageRecord, ...]:
        """Return active packages in deterministic dependency-first order."""
        active = {
            item.service_key: item
            for item in self.packages.installed()
            if item.status is PackageStatus.ACTIVE
        }
        dependencies: dict[str, set[str]] = {key: set() for key in active}
        for key, package in active.items():
            for lock in self.packages.locks(package.package_digest):
                if lock.dependency_key in active:
                    dependencies[key].add(lock.dependency_key)
        ordered: list[InstalledPackageRecord] = []
        remaining = dict(dependencies)
        while remaining:
            ready = sorted(key for key, required in remaining.items() if not required)
            if not ready:
                raise PackageError(
                    "dependency_cycle",
                    "Active Service dependency locks contain a cycle",
                    details={"services": sorted(remaining)},
                )
            for key in ready:
                ordered.append(active[key])
                remaining.pop(key)
            for required in remaining.values():
                required.difference_update(ready)
        return tuple(ordered)

    async def audit(
        self,
        archive_path: str | Path,
        *,
        allow_untrusted: bool = False,
    ) -> dict:
        package = self.inspect(archive_path)
        signature = self.trust.verify_signature(
            package, allow_untrusted=allow_untrusted
        )
        audit = await self.trust.audit(package)
        return {
            "service_key": package.manifest.service_key,
            "version": package.manifest.version,
            "digest": package.digest,
            "signature": signature,
            "audit": audit,
        }

    def _check_requirements(
        self, value: dict, package: InspectedServicePackage
    ) -> None:
        context = self.compatibility
        os_names = value.get("os", [])
        aliases = {"darwin": "macos", "macos": "darwin"}
        if isinstance(os_names, str):
            os_names = [os_names]
        accepted_os = {str(item).lower() for item in os_names}
        if (
            accepted_os
            and context.os_name not in accepted_os
            and aliases.get(context.os_name) not in accepted_os
        ):
            raise PackageError(
                "platform_incompatible",
                f"Package does not support OS {context.os_name}",
            )
        architectures = value.get("architectures", value.get("architecture", []))
        if isinstance(architectures, str):
            architectures = [architectures]
        if architectures and context.architecture not in {
            str(item).lower() for item in architectures
        }:
            raise PackageError(
                "platform_incompatible",
                f"Package does not support architecture {context.architecture}",
            )
        python_spec = value.get("python") or package.manifest.raw.get(
            "requires", {}
        ).get("python")
        if python_spec and Version(context.python_version) not in SpecifierSet(
            str(python_spec)
        ):
            raise PackageError(
                "platform_incompatible",
                f"Package does not support Python {context.python_version}",
            )
        accelerators = value.get("accelerators", [])
        if isinstance(accelerators, str):
            accelerators = [accelerators]
        if accelerators and context.accelerator not in accelerators:
            raise PackageError(
                "accelerator_incompatible", "No compatible accelerator variant"
            )
        required_features = set(value.get("features", []))
        missing = required_features - context.features
        if missing:
            raise PackageError(
                "platform_feature_missing",
                "Package requires unavailable platform features",
                details={"missing": sorted(missing)},
            )

    def _select_variant(self, package: InspectedServicePackage) -> str | None:
        variants = package.manifest.raw.get("variants", [])
        if not variants:
            self._check_requirements(package.manifest.compatibility, package)
            return None
        if not isinstance(variants, list) or not all(
            isinstance(item, dict) and isinstance(item.get("id"), str)
            for item in variants
        ):
            raise PackageError("invalid_variants", "Package variants are invalid")
        failures = []
        ordered = sorted(
            variants,
            key=lambda item: (-int(item.get("priority", 0)), item["id"]),
        )
        indexed = {item.path for item in package.files}
        for variant in ordered:
            requirements = {
                **package.manifest.compatibility,
                **variant.get("compatibility", {}),
            }
            try:
                self._check_requirements(requirements, package)
                declared_files = set(variant.get("files", []))
                if not declared_files.issubset(indexed):
                    raise PackageError(
                        "variant_file_missing",
                        f"Variant {variant['id']} references an unindexed file",
                    )
                return variant["id"]
            except PackageError as error:
                failures.append({"variant": variant["id"], "code": error.code})
        raise PackageError(
            "platform_incompatible",
            "No signed package variant is compatible with this device",
            details={"variants": failures},
        )

    async def _verify(
        self,
        package: InspectedServicePackage,
        *,
        allow_untrusted: bool,
        approve_audit_review: bool,
    ) -> tuple[dict, dict]:
        signature = self.trust.verify_signature(
            package, allow_untrusted=allow_untrusted
        )
        signature["selected_variant"] = self._select_variant(package)
        if (
            package.manifest.runtime_mode is ServiceRuntimeMode.IN_PROCESS
            and signature["trust"] != TrustStatus.TRUSTED.value
        ):
            raise PackageError(
                "embedded_requires_trusted_publisher",
                "Embedded Services require a trusted publisher",
            )
        audit = await self.trust.audit(package)
        if audit["decision"] == AuditDecision.REVIEW.value and not approve_audit_review:
            raise PackageError(
                "audit_review_required",
                "Package audit requires explicit installation approval",
                details=audit,
            )
        return signature, audit

    @staticmethod
    def _make_immutable(root: Path) -> None:
        for item in sorted(root.rglob("*"), reverse=True):
            if item.is_file():
                item.chmod(0o444)
            elif item.is_dir():
                item.chmod(0o555)
        root.chmod(0o555)

    @staticmethod
    def _remove_tree(root: Path) -> None:
        if not root.exists():
            return
        for item in root.rglob("*"):
            with suppress(OSError):
                item.chmod(0o755 if item.is_dir() else 0o644)
        with suppress(OSError):
            root.chmod(0o755)
        shutil.rmtree(root, ignore_errors=True)

    def _store(self, package: InspectedServicePackage) -> tuple[Path, bool]:
        digest = package.digest.removeprefix("sha256:")
        final = (
            self.paths.packages_path
            / "services"
            / package.manifest.service_key
            / package.manifest.version
            / digest
        )
        if final.is_dir():
            return final, False
        staging_parent = self.paths.packages_path / ".staging"
        staging_parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="service-", dir=staging_parent))
        payload = staging / "payload"
        try:
            ServicePackageArchive.extract(package, payload)
            shutil.copy2(package.archive_path, payload / "package.ai2service")
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(payload, final)
            self._make_immutable(final)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return final, True

    def _declare(self, package: InstalledPackageRecord) -> None:
        from ai2apps.model_providers import validate_package_models

        manifest = package.manifest
        try:
            existing_service = self.services.get_service(package.service_key)
        except ResourceNotFoundError:
            existing_service = None
        if existing_service is not None and existing_service.source != "installed":
            raise PackageError(
                "reserved_service_id",
                f"Installed Package cannot replace built-in Service {package.service_key}",
            )
        package_models = validate_package_models(
            package.service_key,
            manifest.get("models", []),
            runtime_mode=package.runtime_mode.value,
            protocol=package.protocol,
        )
        service = self.services.ensure_service(
            service_key=package.service_key,
            package_id=package.service_key,
            package_version=package.package_version,
            display_name=str(manifest["name"]),
            runtime_mode=package.runtime_mode,
            source="installed",
            capabilities=tuple(manifest.get("capabilities", [])),
            config={
                "protocol": package.protocol,
                "health": manifest.get("health", {}),
                "package_store": package.store_path,
                "models": list(package_models),
            },
            package_digest=package.package_digest,
            permissions=package.permissions,
            dependencies=tuple(self._manifest_dependencies(manifest)),
        )
        endpoint = (
            manifest["runtime"].get("endpoint")
            if package.runtime_mode is ServiceRuntimeMode.EXTERNAL
            else None
        )
        self.services.ensure_instance(
            service_id=service.id,
            provider_key=f"package:{package.service_key}",
            status=ServiceInstanceStatus.INSTALLED,
            endpoint=endpoint,
            health={"status": "installed", "verified": True},
        )
        self.runtime.register(package)

    @staticmethod
    def _manifest_dependencies(manifest: dict):
        from ai2apps.services import ServiceDependency

        for item in manifest.get("requires", {}).get("services", []):
            yield ServiceDependency(
                item["id"],
                str(item.get("version", "*")),
                bool(item.get("optional", False)),
            )

    async def _activate(self, package: InstalledPackageRecord) -> None:
        self._validate_installed(package)
        self.packages.activate(package.service_key, package.package_digest)
        package = self.packages.get_by_digest(package.package_digest)
        self._declare(package)
        await self.runtime.start(package)

    def _validate_installed(self, package: InstalledPackageRecord) -> None:
        root = Path(package.store_path).resolve(strict=True)
        archive = root / "package.ai2service"
        cloud_contract = (
            package.verification.get("signature", {}).get("trust")
            == "ai2apps-cloud-registry-v1"
        )
        if cloud_contract:
            from .contract_v1 import inspect_package as inspect_contract_package

            inspected_contract = inspect_contract_package(archive)
            if f"sha256:{inspected_contract.sha256}" != package.package_digest:
                raise PackageError(
                    "installed_package_tampered",
                    "Stored package digest no longer matches the installed record",
                )
        else:
            inspected = ServicePackageArchive.inspect(archive)
            if inspected.digest != package.package_digest:
                raise PackageError(
                    "installed_package_tampered",
                    "Stored package digest no longer matches the installed record",
                )
            allow_untrusted = (
                package.verification.get("signature", {}).get("trust")
                == "untrusted"
            )
            self.trust.verify_signature(inspected, allow_untrusted=allow_untrusted)
        expected = {
            item["path"]: item for item in self.packages.files(package.package_digest)
        }
        actual_paths = {
            item.relative_to(root).as_posix()
            for item in root.rglob("*")
            if item.is_file()
            and item.relative_to(root).as_posix() != "package.ai2service"
            and (
                not cloud_contract
                or item.relative_to(root).as_posix() != "ai2apps.json"
            )
            and item.relative_to(root).as_posix() != "META/files.json"
            and not item.relative_to(root)
            .as_posix()
            .startswith(("attestations/", "signatures/"))
        }
        if actual_paths != set(expected):
            raise PackageError(
                "installed_package_tampered",
                "Stored package file set changed after verification",
            )
        for relative, metadata in expected.items():
            path = root.joinpath(*relative.split("/"))
            content = path.read_bytes()
            digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            if (
                len(content) != metadata["size_bytes"]
                or digest != metadata["content_hash"]
            ):
                raise PackageError(
                    "installed_package_tampered",
                    f"Stored package file changed: {relative}",
                )

    async def install(
        self,
        archive_path: str | Path,
        *,
        dependency_archives: tuple[str | Path, ...] = (),
        allow_untrusted: bool = False,
        approve_audit_review: bool = False,
    ) -> InstalledPackageRecord:
        async with self._install_lock:
            return await self._install_impl(
                archive_path,
                dependency_archives=dependency_archives,
                allow_untrusted=allow_untrusted,
                approve_audit_review=approve_audit_review,
            )

    async def install_verified_package(
        self,
        package: InspectedServicePackage,
        verification: dict,
        *,
        approve_audit_review: bool = False,
    ) -> InstalledPackageRecord:
        """Install a Service authenticated by Cloud v1 detached metadata."""

        async with self._install_lock:
            self._select_variant(package)
            for installed in self.packages.installed(package.manifest.service_key):
                if (
                    installed.package_version == package.manifest.version
                    and installed.package_digest != package.digest
                ):
                    raise PackageError(
                        "version_digest_conflict",
                        "The same Service version is installed with another digest",
                    )
            unresolved = [
                dependency.service_key
                for dependency in package.manifest.dependencies
                if not dependency.optional
                and self.packages.active(dependency.service_key) is None
            ]
            if unresolved:
                raise PackageError(
                    "dependency_unresolved",
                    "Required Service dependencies are not installed",
                    details={"dependencies": unresolved},
                )
            audit = await self.trust.audit(package)
            if (
                audit["decision"] == AuditDecision.REVIEW.value
                and not approve_audit_review
            ):
                raise PackageError(
                    "audit_review_required",
                    "Package audit requires explicit installation approval",
                    details=audit,
                )
            prior = self.packages.active(package.manifest.service_key)
            operation_id = self.packages.begin_operation(
                package.manifest.service_key,
                "upgrade" if prior else "install",
                from_digest=None if prior is None else prior.package_digest,
                to_digest=package.digest,
                plan={"contract": "ai2apps.package-release.v1"},
            )
            stored = None
            try:
                store, created = self._store(package)
                if created:
                    stored = store
                record = self.packages.record_install(
                    package,
                    store_path=str(store),
                    verification={"signature": verification, "audit": audit},
                )
                self.packages.add_attestation(
                    package_digest=package.digest,
                    kind="local-ai" if audit.get("model") else "static-policy",
                    issuer=audit["issuer"],
                    decision=AuditDecision(audit["decision"]),
                    risk=AuditRisk(audit["risk"]),
                    model=audit.get("model"),
                    policy_version=audit.get("policy_version"),
                    evidence=audit.get("evidence", {}),
                )
                if prior and prior.package_digest != record.package_digest:
                    await self.runtime.stop(prior)
                await self._activate(record)
                self.packages.settle_operation(operation_id, "completed")
                return self.packages.get_by_digest(package.digest)
            except BaseException as error:
                if prior is not None:
                    with suppress(Exception):
                        await self._activate(prior)
                if stored is not None:
                    with suppress(Exception):
                        self.packages.set_package_status(
                            package.digest, PackageStatus.UNINSTALLED
                        )
                    self._remove_tree(stored)
                self.packages.settle_operation(
                    operation_id,
                    "rolled_back",
                    {
                        "code": getattr(error, "code", "install_failed"),
                        "message": str(error),
                    },
                )
                raise

    async def _install_impl(
        self,
        archive_path: str | Path,
        *,
        dependency_archives: tuple[str | Path, ...] = (),
        allow_untrusted: bool = False,
        approve_audit_review: bool = False,
    ) -> InstalledPackageRecord:
        plan = self.plan(archive_path, dependency_archives)
        self._check_active_dependents(plan)
        root = next(item for item in plan.packages if item.digest == plan.root_digest)
        active_root = self.packages.active(root.manifest.service_key)
        operation = "upgrade" if active_root is not None else "install"
        operation_id = self.packages.begin_operation(
            root.manifest.service_key,
            operation,
            from_digest=None if active_root is None else active_root.package_digest,
            to_digest=root.digest,
            plan={
                "packages": [
                    {
                        "service_key": item.manifest.service_key,
                        "version": item.manifest.version,
                        "digest": item.digest,
                    }
                    for item in plan.packages
                ],
                "locks": [asdict(lock) for lock in plan.locks],
            },
        )
        stored_new: list[tuple[InspectedServicePackage, Path]] = []
        installed_records: dict[str, InstalledPackageRecord] = {}
        previous = {
            item.manifest.service_key: self.packages.active(item.manifest.service_key)
            for item in plan.packages
        }
        activated: list[InstalledPackageRecord] = []
        try:
            verification: dict[str, tuple[dict, dict]] = {}
            for item in plan.packages:
                verification[item.digest] = await self._verify(
                    item,
                    allow_untrusted=allow_untrusted,
                    approve_audit_review=approve_audit_review,
                )
            for item in plan.packages:
                store, created = self._store(item)
                if created:
                    stored_new.append((item, store))
                signature, audit = verification[item.digest]
                record = self.packages.record_install(
                    item,
                    store_path=str(store),
                    verification={"signature": signature, "audit": audit},
                )
                installed_records[item.digest] = record
                self.packages.add_attestation(
                    package_digest=item.digest,
                    kind="local-ai" if audit.get("model") else "static-policy",
                    issuer=audit["issuer"],
                    decision=AuditDecision(audit["decision"]),
                    risk=AuditRisk(audit["risk"]),
                    model=audit.get("model"),
                    policy_version=audit.get("policy_version"),
                    evidence=audit.get("evidence", {}),
                )
            for item in plan.packages:
                relevant = tuple(
                    lock for lock in plan.locks if lock.package_digest == item.digest
                )
                self.packages.store_locks(
                    item.manifest.service_key, item.digest, relevant
                )
            for item in plan.packages:
                record = installed_records[item.digest]
                current = previous[item.manifest.service_key]
                if (
                    current is not None
                    and current.package_digest == record.package_digest
                ):
                    continue
                if current is not None:
                    await self.runtime.stop(current)
                activated.append(record)
                await self._activate(record)
            self.packages.settle_operation(operation_id, "completed")
            return self.packages.get_by_digest(root.digest)
        except BaseException as error:
            for record in reversed(activated):
                with suppress(Exception):
                    await self.runtime.stop(record)
                prior = previous.get(record.service_key)
                if prior is not None:
                    with suppress(Exception):
                        await self._activate(prior)
                else:
                    with suppress(Exception):
                        self.services.remove_service(record.service_key)
                self.packages.set_package_status(
                    record.package_digest, PackageStatus.INSTALLED
                )
            for item, store in stored_new:
                with suppress(Exception):
                    self.packages.set_package_status(
                        item.digest, PackageStatus.UNINSTALLED
                    )
                self._remove_tree(store)
            self.packages.settle_operation(
                operation_id,
                "rolled_back",
                {
                    "code": getattr(error, "code", "install_failed"),
                    "message": str(error),
                },
            )
            raise

    def restore_registry(self) -> None:
        for package in self._active_start_order():
            self._declare(package)

    async def startup(self) -> None:
        await asyncio.to_thread(self.supervisor.recover_orphans)
        for package in self._active_start_order():
            service = self.services.get_service(package.service_key)
            if service.status is ServiceStatus.ENABLED:
                self._validate_installed(package)
                await self.runtime.start(package)

    async def shutdown(self) -> None:
        for package in reversed(self._active_start_order()):
            with suppress(Exception):
                await self.runtime.stop(package)
        await self.runtime.shutdown()

    async def enable(self, service_key: str, expected_revision: int):
        package = self.packages.active(service_key)
        if package is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        self._validate_installed(package)
        operation_id = self.packages.begin_operation(
            service_key,
            "enable",
            from_digest=package.package_digest,
            to_digest=package.package_digest,
            plan={},
        )
        try:
            result = await self.registry.set_enabled(
                service_key, expected_revision=expected_revision, enabled=True
            )
            self.packages.settle_operation(operation_id, "completed")
            return result
        except BaseException as error:
            self.packages.settle_operation(
                operation_id, "failed", {"code": "enable_failed", "message": str(error)}
            )
            raise

    async def disable(self, service_key: str, expected_revision: int):
        dependents = self.packages.dependents(service_key)
        if dependents:
            raise PackageError(
                "service_has_dependents",
                "Required dependents prevent disabling this Service",
                details={"dependents": list(dependents)},
            )
        package = self.packages.active(service_key)
        operation_id = self.packages.begin_operation(
            service_key,
            "disable",
            from_digest=None if package is None else package.package_digest,
            to_digest=None if package is None else package.package_digest,
            plan={},
        )
        try:
            result = await self.registry.set_enabled(
                service_key, expected_revision=expected_revision, enabled=False
            )
            self.packages.settle_operation(operation_id, "completed")
            return result
        except BaseException as error:
            self.packages.settle_operation(
                operation_id,
                "failed",
                {"code": "disable_failed", "message": str(error)},
            )
            raise

    async def restart(self, service_key: str) -> None:
        package = self.packages.active(service_key)
        if package is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        self._validate_installed(package)
        operation_id = self.packages.begin_operation(
            service_key,
            "restart",
            from_digest=package.package_digest,
            to_digest=package.package_digest,
            plan={},
        )
        try:
            await self.registry.restart(service_key)
            self.packages.settle_operation(operation_id, "completed")
        except BaseException as error:
            self.packages.settle_operation(
                operation_id,
                "failed",
                {"code": "restart_failed", "message": str(error)},
            )
            raise

    async def start(self, service_key: str) -> None:
        package = self.packages.active(service_key)
        if package is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        service = self.services.get_service(service_key)
        if service.status is ServiceStatus.DISABLED:
            raise PackageError(
                "service_disabled", "Enable the Service before starting it"
            )
        self._validate_installed(package)
        operation_id = self.packages.begin_operation(
            service_key,
            "start",
            from_digest=package.package_digest,
            to_digest=package.package_digest,
            plan={},
        )
        try:
            await self.runtime.start(package)
            self.packages.settle_operation(operation_id, "completed")
        except BaseException as error:
            self.packages.settle_operation(
                operation_id, "failed", {"code": "start_failed", "message": str(error)}
            )
            raise

    async def stop(self, service_key: str) -> None:
        dependents = self.packages.dependents(service_key)
        if dependents:
            raise PackageError(
                "service_has_dependents",
                "Required dependents prevent stopping this Service",
                details={"dependents": list(dependents)},
            )
        package = self.packages.active(service_key)
        if package is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        operation_id = self.packages.begin_operation(
            service_key,
            "stop",
            from_digest=package.package_digest,
            to_digest=package.package_digest,
            plan={},
        )
        try:
            await self.runtime.stop(package)
            service = self.services.get_service(service_key)
            instance = self.services.get_instance_for_service(service.id)
            self.services.set_instance_status(
                instance.id,
                ServiceInstanceStatus.STOPPED,
                health={"status": "stopped"},
            )
            self.packages.settle_operation(operation_id, "completed")
        except BaseException as error:
            self.packages.settle_operation(
                operation_id, "failed", {"code": "stop_failed", "message": str(error)}
            )
            raise

    async def rollback(self, service_key: str) -> InstalledPackageRecord:
        active = self.packages.active(service_key)
        if active is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        retained = [
            item
            for item in self.packages.installed(service_key)
            if item.status is PackageStatus.RETAINED
        ]
        if not retained:
            raise PackageError("rollback_unavailable", "No retained package version")
        target = retained[0]
        operation_id = self.packages.begin_operation(
            service_key,
            "rollback",
            from_digest=active.package_digest,
            to_digest=target.package_digest,
            plan={"from": active.package_digest, "to": target.package_digest},
        )
        try:
            await self.runtime.stop(active)
            await self._activate(target)
            self.packages.settle_operation(operation_id, "completed")
            return self.packages.get_by_digest(target.package_digest)
        except BaseException as error:
            with suppress(Exception):
                await self._activate(active)
            self.packages.settle_operation(
                operation_id,
                "rolled_back",
                {
                    "code": getattr(error, "code", "rollback_failed"),
                    "message": str(error),
                },
            )
            raise

    async def uninstall(self, service_key: str) -> None:
        dependents = self.packages.dependents(service_key)
        if dependents:
            raise PackageError(
                "service_has_dependents",
                "Required dependents prevent uninstalling this Service",
                details={"dependents": list(dependents)},
            )
        active = self.packages.active(service_key)
        if active is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        operation_id = self.packages.begin_operation(
            service_key,
            "uninstall",
            from_digest=active.package_digest,
            to_digest=None,
            plan={
                "versions": [
                    item.package_digest for item in self.packages.installed(service_key)
                ]
            },
        )
        await self.runtime.stop(active)
        self.services.remove_service(service_key)
        for item in self.packages.installed(service_key):
            self.packages.set_package_status(
                item.package_digest, PackageStatus.UNINSTALLED
            )
            self._remove_tree(Path(item.store_path))
        self.packages.settle_operation(operation_id, "completed")
