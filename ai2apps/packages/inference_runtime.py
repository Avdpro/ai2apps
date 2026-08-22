"""Verified inference Runtime Provider contracts and resolution.

The Base App never imports an inference framework.  A Model Worker may only be
started with an active Runtime Provider that is locked as a dependency of the
model Package and whose immutable descriptor points inside its installed
payload.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .models import InstalledPackageRecord, PackageError, PackageStatus
from .repository import PackageRepository

logger = logging.getLogger(__name__)

RUNTIME_VERIFY_TIMEOUT_SECONDS = 300.0
RUNTIME_ATTACH_TIMEOUT_SECONDS = 120.0
RUNTIME_DETACH_TIMEOUT_SECONDS = 30.0

RUNTIME_PROTOCOL = "ai2apps-inference-runtime/v1"
RUNTIME_ROLE = "inference_provider"
RUNTIME_DESCRIPTOR_SCHEMA = "ai2apps.inference-runtime/v1"


def is_inference_runtime_manifest(manifest: dict[str, Any]) -> bool:
    runtime = manifest.get("runtime", {})
    return (
        isinstance(runtime, dict)
        and runtime.get("role") == RUNTIME_ROLE
        and runtime.get("protocol") == RUNTIME_PROTOCOL
    )


def validate_inference_runtime_manifest(manifest: dict[str, Any]) -> None:
    """Validate the non-executable outer Service contract."""

    runtime = manifest.get("runtime", {})
    if not isinstance(runtime, dict):
        raise PackageError("invalid_inference_runtime", "Runtime policy is invalid")
    if runtime.get("role") != RUNTIME_ROLE or runtime.get("protocol") != RUNTIME_PROTOCOL:
        raise PackageError(
            "invalid_inference_runtime", "Inference Runtime role and protocol must match"
        )
    if runtime.get("mode") != "process" or runtime.get("command"):
        raise PackageError(
            "invalid_inference_runtime",
            "Inference Runtime startup is Host-owned; runtime.command is not allowed",
        )
    descriptor = runtime.get("descriptor")
    if (
        not isinstance(descriptor, str)
        or not descriptor.startswith("META/")
        or descriptor.startswith("/")
        or ".." in descriptor.split("/")
        or not descriptor.endswith(".json")
    ):
        raise PackageError(
            "invalid_inference_runtime",
            "runtime.descriptor must be an immutable META JSON path",
        )
    if manifest.get("models") or manifest.get("tools"):
        raise PackageError(
            "invalid_inference_runtime",
            "Inference Runtime Providers cannot publish models or Tools",
        )
    capabilities = manifest.get("capabilities", [])
    if not isinstance(capabilities, list) or "model-worker-v1" not in capabilities:
        raise PackageError(
            "invalid_inference_runtime",
            "Inference Runtime must provide model-worker-v1",
        )


def _safe_relative(value: Any, field: str) -> Path:
    if not isinstance(value, str) or not value or value.startswith("/"):
        raise PackageError("invalid_runtime_descriptor", f"{field} must be relative")
    path = Path(value)
    if ".." in path.parts:
        raise PackageError("invalid_runtime_descriptor", f"{field} escapes Runtime")
    return path


@dataclass(frozen=True, slots=True)
class ResolvedInferenceRuntime:
    service_key: str
    version: str
    digest: str
    root: Path
    python: Path
    python_home: Path
    framework_site_packages: Path
    launcher: Path
    capabilities: frozenset[str]


class InferenceRuntimeResolver:
    """Resolve a model Package's locked Runtime without accepting arbitrary paths."""

    def __init__(self, packages: PackageRepository, packages_root: Path) -> None:
        self.packages = packages
        self.packages_root = packages_root

    def installation_root(self, package: InstalledPackageRecord) -> Path:
        digest = package.package_digest.removeprefix("sha256:")
        return (
            self.packages_root
            / "inference-runtimes"
            / package.service_key
            / package.package_version
            / digest
        )

    @staticmethod
    def _provider_requirement(model: InstalledPackageRecord) -> dict[str, Any]:
        runtime = model.manifest.get("runtime", {})
        provider = runtime.get("provider") if isinstance(runtime, dict) else None
        if not isinstance(provider, str) or not provider:
            raise PackageError(
                "runtime_dependency_missing",
                "Model Worker Package does not declare runtime.provider",
            )
        requirements = model.manifest.get("requires", {}).get("services", [])
        match = next(
            (
                item
                for item in requirements
                if isinstance(item, dict) and item.get("id") == provider
            ),
            None,
        )
        if match is None or bool(match.get("optional", False)):
            raise PackageError(
                "runtime_dependency_missing",
                "Model Runtime Provider must be a required Service dependency",
            )
        return match

    def resolve(self, model: InstalledPackageRecord) -> ResolvedInferenceRuntime:
        requirement = self._provider_requirement(model)
        provider_key = str(requirement["id"])
        locks = {
            item.dependency_key: item
            for item in self.packages.locks(model.package_digest)
        }
        lock = locks.get(provider_key)
        if lock is None or lock.optional:
            raise PackageError(
                "runtime_dependency_unlocked",
                "Model Runtime Provider is not fixed by the dependency lock",
            )
        provider = self.packages.active(provider_key)
        if (
            provider is None
            or provider.status is not PackageStatus.ACTIVE
            or provider.package_digest != lock.dependency_digest
        ):
            raise PackageError(
                "runtime_dependency_inactive",
                "The locked inference Runtime Provider is not active",
            )
        spec = str(requirement.get("version", "*"))
        if Version(provider.package_version) not in SpecifierSet("" if spec == "*" else spec):
            raise PackageError(
                "runtime_version_mismatch", "Active inference Runtime version is incompatible"
            )
        if not is_inference_runtime_manifest(provider.manifest):
            raise PackageError(
                "runtime_provider_invalid", "Locked dependency is not an inference Runtime"
            )
        provided = frozenset(provider.manifest.get("capabilities", []))
        required = frozenset(requirement.get("capabilities", []))
        if missing := required - provided:
            raise PackageError(
                "runtime_capability_missing",
                "Inference Runtime lacks required capabilities",
                details={"missing": sorted(missing)},
            )
        root = self.installation_root(provider).resolve(strict=True)
        descriptor_path = Path(provider.store_path) / provider.manifest["runtime"]["descriptor"]
        try:
            descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PackageError(
                "runtime_descriptor_unreadable", "Inference Runtime descriptor is unreadable"
            ) from error
        if (
            descriptor.get("schema") != RUNTIME_DESCRIPTOR_SCHEMA
            or descriptor.get("service_id") != provider.service_key
            or descriptor.get("version") != provider.package_version
            or descriptor.get("protocol") != "ai2apps-model-worker/v1"
        ):
            raise PackageError(
                "runtime_descriptor_mismatch", "Inference Runtime descriptor identity differs"
            )

        def inside(field: str, *, directory: bool = False) -> Path:
            candidate = (root / _safe_relative(descriptor.get(field), field)).resolve(strict=True)
            try:
                candidate.relative_to(root)
            except ValueError as error:
                raise PackageError(
                    "runtime_descriptor_escape", f"{field} escapes Runtime installation"
                ) from error
            if directory != candidate.is_dir():
                kind = "directory" if directory else "file"
                raise PackageError(
                    "runtime_descriptor_invalid", f"{field} is not a {kind}"
                )
            return candidate

        python = inside("python")
        if not os.access(python, os.X_OK):
            raise PackageError(
                "runtime_descriptor_invalid", "Runtime Python is not executable"
            )
        return ResolvedInferenceRuntime(
            service_key=provider.service_key,
            version=provider.package_version,
            digest=provider.package_digest,
            root=root,
            python=python,
            python_home=inside("python_home", directory=True),
            framework_site_packages=inside("framework_site_packages", directory=True),
            launcher=inside("launcher"),
            capabilities=provided,
        )


class InferenceRuntimeInstaller:
    """Materialize a verified Runtime payload into an immutable version root."""

    def __init__(self, resolver: InferenceRuntimeResolver) -> None:
        self.resolver = resolver

    @staticmethod
    def _descriptor(package: InstalledPackageRecord) -> dict[str, Any]:
        path = Path(package.store_path) / package.manifest["runtime"]["descriptor"]
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise PackageError(
                "runtime_descriptor_unreadable", "Inference Runtime descriptor is unreadable"
            ) from error
        if (
            value.get("schema") != RUNTIME_DESCRIPTOR_SCHEMA
            or value.get("service_id") != package.service_key
            or value.get("version") != package.package_version
            or value.get("protocol") != "ai2apps-model-worker/v1"
        ):
            raise PackageError(
                "runtime_descriptor_mismatch", "Inference Runtime descriptor identity differs"
            )
        return value

    @staticmethod
    def _run(
        *command: str,
        stage: str,
        timeout_seconds: float = RUNTIME_VERIFY_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess[str]:
        logger.info("Inference Runtime install stage started: %s", stage)
        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            logger.error("Inference Runtime install stage timed out: %s", stage)
            raise PackageError(
                "runtime_payload_verification_timeout",
                f"Runtime payload verification timed out during {stage}",
                details={"stage": stage, "timeout_seconds": timeout_seconds},
            ) from error
        except (OSError, subprocess.CalledProcessError) as error:
            logger.error("Inference Runtime install stage failed: %s", stage)
            raise PackageError(
                "runtime_payload_verification_failed",
                f"Runtime payload verification failed during {stage}",
                details={"stage": stage},
            ) from error
        logger.info("Inference Runtime install stage completed: %s", stage)
        return result

    @staticmethod
    def _copy_directory(source: Path, destination: Path) -> None:
        shutil.copytree(source, destination, symlinks=True)

    def _copy_dmg(
        self, source: Path, destination: Path, descriptor: dict[str, Any]
    ) -> None:
        if platform.system() != "Darwin":
            raise PackageError(
                "runtime_payload_unsupported", "DMG Runtime payload requires macOS"
            )
        self._run(
            "/usr/bin/hdiutil", "verify", str(source), stage="disk image verification"
        )
        distribution = descriptor.get("distribution", {})
        signing = distribution.get("signing", "developer-id")
        if signing == "developer-id":
            self._run(
                "/usr/bin/codesign",
                "--verify",
                "--strict",
                str(source),
                stage="disk image signature verification",
            )
            # Runtime installation must work on a clean consumer Mac.  The
            # xcrun/stapler tool belongs to Xcode's developer toolchain and is
            # therefore unsuitable as an installation-time dependency.
            # Gatekeeper's system spctl validates the Developer ID signature
            # and the stapled notarization ticket without requiring Xcode.
            self._run(
                "/usr/sbin/spctl",
                "--assess",
                "--type",
                "open",
                "--context",
                "context:primary-signature",
                "--verbose=2",
                str(source),
                stage="Gatekeeper assessment",
            )
        elif signing != "development" or os.environ.get(
            "AI2APPS_ALLOW_DEVELOPMENT_RUNTIME"
        ) != "1":
            raise PackageError(
                "runtime_signature_required",
                "Runtime DMG must be Developer ID signed and notarized",
            )
        payload = descriptor.get("payload", {})
        mounted_root = _safe_relative(payload.get("root"), "payload.root")
        with tempfile.TemporaryDirectory(prefix="ai2apps-runtime-mount-") as temporary:
            mount = Path(temporary) / "mount"
            mount.mkdir()
            self._run(
                "/usr/bin/hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mount),
                str(source),
                stage="disk image attach",
                timeout_seconds=RUNTIME_ATTACH_TIMEOUT_SECONDS,
            )
            try:
                canonical_mount = mount.resolve(strict=True)
                candidate = (canonical_mount / mounted_root).resolve(strict=True)
                try:
                    candidate.relative_to(canonical_mount)
                except ValueError as error:
                    raise PackageError(
                        "runtime_payload_escape",
                        "Mounted Runtime payload escapes the read-only image",
                    ) from error
                if signing == "developer-id":
                    self._run(
                        "/usr/bin/codesign",
                        "--verify",
                        "--deep",
                        "--strict",
                        str(candidate),
                        stage="Runtime payload signature verification",
                    )
                    details = self._run(
                        "/usr/bin/codesign",
                        "-dvvv",
                        str(candidate),
                        stage="Runtime payload signing identity inspection",
                    ).stderr
                    team_id = distribution.get("team_id")
                    if not isinstance(team_id, str) or f"TeamIdentifier={team_id}" not in details:
                        raise PackageError(
                            "runtime_team_mismatch",
                            "Runtime payload is not signed by the declared Team ID",
                        )
                logger.info("Inference Runtime install stage started: payload copy")
                self._copy_directory(candidate, destination)
                logger.info("Inference Runtime install stage completed: payload copy")
            finally:
                try:
                    subprocess.run(
                        ["/usr/bin/hdiutil", "detach", str(mount)],
                        check=False,
                        capture_output=True,
                        timeout=RUNTIME_DETACH_TIMEOUT_SECONDS,
                    )
                except (OSError, subprocess.TimeoutExpired):
                    # The TemporaryDirectory cleanup is still attempted. A
                    # detach failure must not mask the original verification
                    # error or leave the install request waiting forever.
                    logger.warning("Inference Runtime disk image detach failed")

    @staticmethod
    def _make_immutable(root: Path) -> None:
        for item in sorted(root.rglob("*"), reverse=True):
            if item.is_symlink():
                continue
            item.chmod(0o555 if item.is_dir() or os.access(item, os.X_OK) else 0o444)
        root.chmod(0o555)

    def materialize(self, package: InstalledPackageRecord) -> Path:
        descriptor = self._descriptor(package)
        payload = descriptor.get("payload", {})
        if not isinstance(payload, dict):
            raise PackageError("invalid_runtime_descriptor", "Runtime payload is invalid")
        source_relative = _safe_relative(payload.get("path"), "payload.path")
        source = (Path(package.store_path) / source_relative).resolve(strict=True)
        try:
            source.relative_to(Path(package.store_path).resolve(strict=True))
        except ValueError as error:
            raise PackageError(
                "runtime_payload_escape", "Runtime payload escapes Package storage"
            ) from error
        final = self.resolver.installation_root(package)
        if final.is_dir():
            return final
        final.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="runtime-", dir=final.parent))
        candidate = staging / "payload"
        try:
            payload_type = payload.get("type")
            if payload_type == "dmg":
                self._copy_dmg(source, candidate, descriptor)
            elif (
                payload_type == "directory"
                and os.environ.get("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME") == "1"
            ):
                self._copy_directory(source, candidate)
            else:
                raise PackageError(
                    "runtime_payload_unsupported",
                    "Only verified DMG Runtime payloads are accepted",
                )
            os.replace(candidate, final)
            self._make_immutable(final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return final
