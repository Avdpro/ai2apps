"""Transactional trusted Service installation, activation, rollback, and removal."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import platform
import shutil
import stat
import sys
import tempfile
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

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
from .inference_runtime import (
    InferenceRuntimeInstaller,
    InferenceRuntimeResolver,
    is_native_runtime_manifest,
)
from .models import (
    AuditDecision,
    AuditRisk,
    CompatibilityContext,
    InspectedServicePackage,
    InstalledPackageRecord,
    InstallPlan,
    PackageError,
    PackageStatus,
)
from .repository import PackageRepository
from .resolver import ServiceDependencyResolver
from .runtime import PackageRuntimeBinder
from .supervisor import ManagedServiceSupervisor
from .trust import PackageTrustVerifier

logger = logging.getLogger(__name__)


_RECOVERABLE_DEPENDENCY_START_ERRORS = frozenset(
    {
        "runtime_dependency_inactive",
        "runtime_dependency_unlocked",
        "runtime_dependency_missing",
        "runtime_version_mismatch",
        "runtime_capability_missing",
    }
)


def _detect_local_accelerator() -> str | None:
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Darwin" and machine in {"arm64", "aarch64"}:
        return "metal"
    if system == "Linux" and any(
        path.exists()
        for path in (
            Path("/dev/nvidiactl"),
            Path("/proc/driver/nvidia/version"),
        )
    ):
        return "cuda"
    return None


def _package_checkpoint_repositories(manifest: dict) -> set[str]:
    """Return validated Hugging Face repositories owned by a model Package."""

    repositories: set[str] = set()
    for model in manifest.get("models", []):
        weights = model.get("weights") if isinstance(model, dict) else None
        if not isinstance(weights, dict) or weights.get("provider") != "huggingface":
            continue
        repo_id = weights.get("repo_id")
        if isinstance(repo_id, str) and repo_id.count("/") == 1 and "--" not in repo_id:
            owner, name = repo_id.split("/", 1)
            if (
                owner
                and name
                and all(part not in {".", ".."} for part in (owner, name))
            ):
                repositories.add(repo_id)
    return repositories


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
        self.inference_runtime_resolver = InferenceRuntimeResolver(
            packages, paths.packages_path
        )
        self.inference_runtime_installer = InferenceRuntimeInstaller(
            self.inference_runtime_resolver
        )
        self.supervisor = ManagedServiceSupervisor(
            packages,
            services,
            paths.packages_path,
            inference_runtimes=self.inference_runtime_resolver,
            model_root=paths.base_path / "models",
        )
        self.runtime = PackageRuntimeBinder(services, registry, self.supervisor)
        self.compatibility = compatibility or CompatibilityContext(
            os_name=platform.system().lower(),
            architecture=platform.machine().lower(),
            python_version=".".join(map(str, sys.version_info[:3])),
            os_version=(
                platform.mac_ver()[0]
                if platform.system() == "Darwin"
                else platform.release()
            ),
            accelerator=_detect_local_accelerator(),
        )
        self._install_lock = asyncio.Lock()

    @staticmethod
    def _require_isolated_runtime(package) -> None:
        mode = getattr(package, "runtime_mode", None)
        if mode is None:
            mode = getattr(package.manifest, "runtime_mode", None)
        if mode is ServiceRuntimeMode.IN_PROCESS:
            raise PackageError(
                "third_party_in_process_denied",
                "Installable Service Packages cannot execute in the AI2Apps host process",
            )

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
        minimum_os = value.get("minimum_os_version") or value.get("minimumOsVersion")
        maximum_os = value.get("maximum_os_version_exclusive") or value.get(
            "maximumOsVersionExclusive"
        )
        if minimum_os or maximum_os:
            try:
                current_os = Version(context.os_version)
            except InvalidVersion as error:
                raise PackageError(
                    "os_version_unknown",
                    "The current OS version could not be determined",
                    details={"current": context.os_version},
                ) from error
            if minimum_os and current_os < Version(str(minimum_os)):
                raise PackageError(
                    "os_version_too_old",
                    f"Package requires OS {minimum_os} or later; this device runs {context.os_version}",
                    details={
                        "current": context.os_version,
                        "minimum": str(minimum_os),
                    },
                )
            if maximum_os and current_os >= Version(str(maximum_os)):
                raise PackageError(
                    "os_version_too_new",
                    f"Package requires an OS earlier than {maximum_os}; this device runs {context.os_version}",
                    details={
                        "current": context.os_version,
                        "maximumExclusive": str(maximum_os),
                    },
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
        self._require_isolated_runtime(package)
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

    @staticmethod
    def _tree_size(root: Path, seen: set[tuple[int, int]] | None = None) -> int:
        total = 0
        seen = seen if seen is not None else set()
        if not root.exists():
            return total
        for item in root.rglob("*"):
            try:
                info = item.lstat()
            except OSError:
                continue
            identity = (info.st_dev, info.st_ino)
            if stat.S_ISREG(info.st_mode) and identity not in seen:
                seen.add(identity)
                total += info.st_size
        return total

    @staticmethod
    def _managed_child(root: Path, relative: Path) -> Path | None:
        """Resolve a deletion target without accepting symlink escapes."""

        try:
            resolved_root = root.resolve(strict=True)
            candidate = (resolved_root / relative).resolve(strict=True)
            candidate.relative_to(resolved_root)
            info = candidate.lstat()
        except (FileNotFoundError, OSError, ValueError):
            return None
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            return None
        return candidate

    def checkpoint_deletion_available(self, service_key: str) -> bool:
        return any(
            _package_checkpoint_repositories(item.manifest)
            for item in self.packages.installed(service_key)
        )

    def _delete_package_checkpoints(
        self, service_key: str, repositories: set[str]
    ) -> dict[str, object]:
        protected = set()
        for package in self.packages.installed():
            if package.service_key != service_key:
                protected.update(_package_checkpoint_repositories(package.manifest))

        deletable = sorted(repositories - protected)
        retained = sorted(repositories & protected)
        model_root = self.paths.base_path / "models"
        hub_root = self.supervisor._huggingface_hub_cache()
        deleted_paths: list[str] = []
        reclaimed_bytes = 0
        seen_files: set[tuple[int, int]] = set()
        for repo_id in deletable:
            owner, name = repo_id.split("/", 1)
            candidates = (
                self._managed_child(model_root, Path(owner) / name),
                self._managed_child(
                    hub_root, Path("models--" + repo_id.replace("/", "--"))
                ),
            )
            for candidate in candidates:
                if candidate is None:
                    continue
                reclaimed_bytes += self._tree_size(candidate, seen_files)
                self._remove_tree(candidate)
                if not candidate.exists():
                    deleted_paths.append(str(candidate))
            owner_root = self._managed_child(model_root, Path(owner))
            if owner_root is not None:
                with suppress(OSError):
                    owner_root.rmdir()
        return {
            "requested": True,
            "deletedRepositories": deletable,
            "retainedRepositories": retained,
            "deletedPaths": deleted_paths,
            "reclaimedBytes": reclaimed_bytes,
        }

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

        self._require_isolated_runtime(package)
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
        if is_native_runtime_manifest(package.manifest):
            # DMG verification and the Runtime payload copy are intentionally
            # synchronous filesystem operations. Keep them off the server's
            # event loop so a large Runtime install does not freeze the Local
            # UI or health endpoints.
            await asyncio.to_thread(
                self.inference_runtime_installer.materialize, package
            )
        self.packages.activate(package.service_key, package.package_digest)
        package = self.packages.get_by_digest(package.package_digest)
        self._declare(package)
        await self.runtime.start(package)

    def _compatible_runtime_dependents(
        self, package: InstalledPackageRecord
    ) -> tuple[str, ...]:
        """Validate and return active dependents that can move to a staged Runtime."""

        version = Version(package.package_version)
        provided = set(package.manifest.get("capabilities", []))
        dependent_digests: list[str] = []
        for dependent_key in self.packages.dependents(package.service_key):
            dependent = self.packages.active(dependent_key)
            if dependent is None:
                continue
            requirement = next(
                (
                    item
                    for item in dependent.manifest.get("requires", {}).get(
                        "services", []
                    )
                    if isinstance(item, dict)
                    and item.get("id") == package.service_key
                    and not bool(item.get("optional", False))
                ),
                None,
            )
            if requirement is None:
                raise PackageError(
                    "runtime_dependent_invalid",
                    "Active dependent has no required Runtime declaration",
                    details={"dependent": dependent_key},
                )
            raw_spec = str(requirement.get("version", "*"))
            if version not in SpecifierSet("" if raw_spec == "*" else raw_spec):
                raise PackageError(
                    "dependent_version_conflict",
                    "Runtime upgrade would break an active dependent Service",
                    details={
                        "service_key": package.service_key,
                        "version": package.package_version,
                        "dependent": dependent_key,
                        "required_version": raw_spec,
                    },
                )
            missing = set(requirement.get("capabilities", [])) - provided
            if missing:
                raise PackageError(
                    "runtime_capability_missing",
                    "Runtime upgrade lacks capabilities required by an active Service",
                    details={
                        "dependent": dependent_key,
                        "missing": sorted(missing),
                    },
                )
            dependent_digests.append(dependent.package_digest)
        return tuple(dependent_digests)

    def _activate_staged_inference_runtimes(
        self,
    ) -> tuple[
        tuple[
            InstalledPackageRecord,
            InstalledPackageRecord | None,
            tuple[str, ...],
        ],
        ...,
    ]:
        """Apply verified Runtime Packages only while Local is starting."""

        pending = [
            item
            for item in self.packages.installed()
            if item.status is PackageStatus.INSTALLED
            and is_native_runtime_manifest(item.manifest)
        ]
        pending.sort(key=lambda item: Version(item.package_version))
        activated = []
        try:
            for package in pending:
                self._validate_installed(package)
                prior = self.packages.active(package.service_key)
                dependents = self._compatible_runtime_dependents(package)
                self.packages.activate_with_relocked_dependents(
                    package.service_key,
                    package.package_digest,
                    dependents,
                )
                activated.append((package, prior, dependents))
                self._declare(self.packages.get_by_digest(package.package_digest))
        except BaseException:
            self._rollback_staged_inference_runtimes(tuple(activated))
            raise
        return tuple(activated)

    def _rollback_staged_inference_runtimes(
        self,
        activated: tuple[
            tuple[
                InstalledPackageRecord,
                InstalledPackageRecord | None,
                tuple[str, ...],
            ],
            ...,
        ],
    ) -> None:
        for package, prior, dependents in reversed(activated):
            if prior is None:
                self.packages.set_package_status(
                    package.package_digest, PackageStatus.INSTALLED
                )
                continue
            self.packages.activate_with_relocked_dependents(
                prior.service_key,
                prior.package_digest,
                dependents,
            )
            self.packages.set_package_status(
                package.package_digest, PackageStatus.INSTALLED
            )
            self._declare(self.packages.get_by_digest(prior.package_digest))

    def _validate_installed(self, package: InstalledPackageRecord) -> None:
        self._require_isolated_runtime(package)
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
                package.verification.get("signature", {}).get("trust") == "untrusted"
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
            self._require_isolated_runtime(package)
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
            # Cloud Registry installs arrive one immutable Package at a time.
            # Resolve their already-active dependencies into the same digest
            # locks used by the local multi-archive installer before
            # activation; inference Runtime resolution refuses an unlocked
            # provider by design.
            plan = self.resolver.resolve(package)
            dependency_locks = tuple(
                lock for lock in plan.locks if lock.package_digest == package.digest
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
                self.packages.store_locks(
                    package.manifest.service_key,
                    package.digest,
                    dependency_locks,
                )
                if is_native_runtime_manifest(package.manifest.raw):
                    # Runtime Providers are immutable and fully materialized now,
                    # but activation is deferred until the next Local startup so
                    # active model locks can move atomically with the provider.
                    self._compatible_runtime_dependents(record)
                    await asyncio.to_thread(
                        self.inference_runtime_installer.materialize, record
                    )
                    self.packages.settle_operation(operation_id, "completed")
                    return self.packages.get_by_digest(package.digest)
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
        staged_runtimes: list[
            tuple[InstalledPackageRecord, InstalledPackageRecord | None]
        ] = []
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
                if is_native_runtime_manifest(item.manifest.raw):
                    # Match Registry installs: a Runtime payload is verified and
                    # materialized now, but remains staged until Local restarts.
                    # Startup can then activate it and move every compatible
                    # model Worker's immutable dependency lock atomically.
                    self._compatible_runtime_dependents(record)
                    await asyncio.to_thread(
                        self.inference_runtime_installer.materialize, record
                    )
                    self.packages.set_package_status(
                        record.package_digest, PackageStatus.INSTALLED
                    )
                    staged_runtimes.append((record, current))
                    continue
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
            for record, prior in reversed(staged_runtimes):
                if prior is not None:
                    self.packages.activate(
                        prior.service_key, prior.package_digest
                    )
                else:
                    self.packages.set_package_status(
                        record.package_digest, PackageStatus.INSTALLED
                    )
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
            if package.runtime_mode is ServiceRuntimeMode.IN_PROCESS:
                self.packages.set_package_status(
                    package.package_digest, PackageStatus.REJECTED
                )
                with suppress(ResourceNotFoundError):
                    service = self.services.get_service(package.service_key)
                    self.services.set_service_status(
                        service.id,
                        expected_revision=service.revision,
                        status=ServiceStatus.DISABLED,
                    )
                    instance = self.services.get_instance_for_service(service.id)
                    self.services.set_instance_status(
                        instance.id,
                        ServiceInstanceStatus.DISABLED,
                        last_error=(
                            "Blocked by security policy: third-party in-process "
                            "Services are no longer supported"
                        ),
                    )
                continue
            self._declare(package)

    async def startup(self) -> None:
        await asyncio.to_thread(self.supervisor.recover_orphans)
        had_pending_runtime = any(
            item.status is PackageStatus.INSTALLED
            and is_native_runtime_manifest(item.manifest)
            for item in self.packages.installed()
        )
        staged = ()

        async def start_active() -> None:
            for package in self._active_start_order():
                service = self.services.get_service(package.service_key)
                if service.status is ServiceStatus.ENABLED:
                    try:
                        self._validate_installed(package)
                        await self.runtime.start(package)
                    except Exception as error:
                        # Installed Services are an optional extension layer. A
                        # missing Runtime (or another broken Service Package)
                        # must not prevent the Base App, Discover, or ACPF from
                        # starting and repairing the installation.
                        code = getattr(error, "code", "service_start_failed")
                        dependency_blocked = (
                            code in _RECOVERABLE_DEPENDENCY_START_ERRORS
                        )
                        status = (
                            ServiceInstanceStatus.DEGRADED
                            if dependency_blocked
                            else ServiceInstanceStatus.FAILED
                        )
                        instance = self.services.get_instance_for_service(service.id)
                        instance = self.services.ensure_instance(
                            service_id=service.id,
                            provider_key=instance.provider_key,
                            status=status,
                            endpoint=None,
                            health={
                                "status": "blocked" if dependency_blocked else "failed",
                                "reason": (
                                    "dependency_unavailable"
                                    if dependency_blocked
                                    else "service_start_failed"
                                ),
                                "error_code": code,
                                "recoverable": dependency_blocked,
                            },
                        )
                        self.services.set_instance_status(
                            instance.id,
                            status,
                            last_error=str(error),
                        )
                        self.packages.append_log(
                            package.service_key,
                            "warning" if dependency_blocked else "error",
                            "system",
                            "Service startup was isolated from the Base App",
                            fields={
                                "error": str(error),
                                "error_code": code,
                                "recoverable": dependency_blocked,
                            },
                        )
                        if dependency_blocked:
                            logger.warning(
                                "Service Package %s is waiting for dependency repair (%s); "
                                "continuing Base App startup",
                                package.service_key,
                                code,
                            )
                        else:
                            logger.exception(
                                "Service Package %s failed during startup; "
                                "continuing Base App startup",
                                package.service_key,
                            )

        try:
            staged = self._activate_staged_inference_runtimes()
            await start_active()
        except BaseException:
            if not staged and not had_pending_runtime:
                raise
            logger.exception(
                "Staged inference Runtime activation failed; restoring prior Runtime"
            )
            with suppress(Exception):
                await self.runtime.shutdown()
            if staged:
                self._rollback_staged_inference_runtimes(staged)
            await start_active()

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

    async def evict(
        self,
        service_key: str,
        *,
        reason: str,
        expected_generation: int,
    ) -> dict:
        package = self.packages.active(service_key)
        if package is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        if package.protocol != "ai2apps-model-worker/v1":
            raise PackageError("not_model_worker", "Service is not a Model Worker")
        operation_id = self.packages.begin_operation(
            service_key,
            # Eviction is a policy-driven stop. Keep the persisted operation
            # compatible with the stable service_operations contract and put
            # the lifecycle subtype in the operation plan.
            "stop",
            from_digest=package.package_digest,
            to_digest=package.package_digest,
            plan={
                "lifecycleAction": "evict",
                "reason": reason,
                "generation": expected_generation,
            },
        )
        try:
            result = await self.supervisor.evict(
                service_key,
                reason=reason,
                expected_generation=expected_generation,
            )
            service = self.services.get_service(service_key)
            instance = self.services.get_instance_for_service(service.id)
            self.services.set_instance_status(
                instance.id,
                ServiceInstanceStatus.STOPPED,
                health={"status": "evicted", "reason": reason},
            )
            self.packages.settle_operation(operation_id, "completed")
            return result
        except BaseException as error:
            self.packages.settle_operation(
                operation_id,
                "failed",
                {"code": "eviction_failed", "message": str(error)},
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

    async def uninstall(
        self,
        service_key: str,
        *,
        delete_checkpoints: bool = False,
        force: bool = False,
    ) -> dict[str, object]:
        dependents = self.packages.dependents(service_key)
        if dependents and not force:
            raise PackageError(
                "service_has_dependents",
                "Required dependents prevent uninstalling this Service",
                details={"dependents": list(dependents)},
            )
        active = self.packages.active(service_key)
        if active is None:
            raise ResourceNotFoundError("active_service_package", service_key)
        checkpoint_repositories = set().union(
            *(
                _package_checkpoint_repositories(item.manifest)
                for item in self.packages.installed(service_key)
            )
        )
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
        checkpoint_cleanup: dict[str, object] = {"requested": False}
        if delete_checkpoints and checkpoint_repositories:
            try:
                checkpoint_cleanup = self._delete_package_checkpoints(
                    service_key, checkpoint_repositories
                )
            except Exception as error:
                logger.exception("Checkpoint cleanup failed for %s", service_key)
                checkpoint_cleanup = {
                    "requested": True,
                    "error": str(error),
                    "deletedRepositories": [],
                    "retainedRepositories": sorted(checkpoint_repositories),
                    "deletedPaths": [],
                    "reclaimedBytes": 0,
                }
        return {"checkpointCleanup": checkpoint_cleanup}
