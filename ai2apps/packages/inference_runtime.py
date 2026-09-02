"""Verified inference Runtime Provider contracts and resolution.

The Base App never imports an inference framework.  A Model Worker may only be
started with an active Runtime Provider that is locked as a dependency of the
model Package and whose immutable descriptor points inside its installed
payload.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import platform
import posixpath
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
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
NATIVE_RUNTIME_PROTOCOL = "ai2apps-native-runtime/v1"
KNOWLEDGE_RUNTIME_ROLE = "knowledge_backend_provider"
KNOWLEDGE_RUNTIME_DESCRIPTOR_SCHEMA = "ai2apps.knowledge-runtime/v1"
MAX_RUNTIME_ARCHIVE_FILES = 1_000_000
MAX_RUNTIME_UNPACKED_BYTES = 64 * 1024**3

_RUNTIME_CONTRACTS = {
    (RUNTIME_PROTOCOL, RUNTIME_ROLE): {
        "descriptor_schema": RUNTIME_DESCRIPTOR_SCHEMA,
        "worker_protocol": "ai2apps-model-worker/v1",
        "required_capability": "model-worker-v1",
        "installation_kind": "inference-runtimes",
        "launcher_required": True,
    },
    (NATIVE_RUNTIME_PROTOCOL, KNOWLEDGE_RUNTIME_ROLE): {
        "descriptor_schema": KNOWLEDGE_RUNTIME_DESCRIPTOR_SCHEMA,
        "worker_protocol": "ai2apps-knowledge-vector-worker/v1",
        "required_capability": "knowledge-runtime-v1",
        "installation_kind": "native-runtimes",
        "launcher_required": False,
    },
}


def _runtime_contract(manifest: dict[str, Any]) -> dict[str, Any] | None:
    runtime = manifest.get("runtime", {})
    if not isinstance(runtime, dict):
        return None
    return _RUNTIME_CONTRACTS.get((runtime.get("protocol"), runtime.get("role")))


def is_inference_runtime_manifest(manifest: dict[str, Any]) -> bool:
    runtime = manifest.get("runtime", {})
    return (
        isinstance(runtime, dict)
        and runtime.get("role") == RUNTIME_ROLE
        and runtime.get("protocol") == RUNTIME_PROTOCOL
    )


def is_native_runtime_manifest(manifest: dict[str, Any]) -> bool:
    """Return true for any Host-materialized, non-executable Runtime Provider."""

    return _runtime_contract(manifest) is not None


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


def validate_native_runtime_manifest(manifest: dict[str, Any]) -> None:
    """Validate legacy inference and generic native Runtime Providers."""

    if is_inference_runtime_manifest(manifest):
        validate_inference_runtime_manifest(manifest)
        return
    contract = _runtime_contract(manifest)
    runtime = manifest.get("runtime", {})
    if contract is None:
        raise PackageError("invalid_native_runtime", "Native Runtime role is unsupported")
    if runtime.get("mode") != "process" or runtime.get("command"):
        raise PackageError(
            "invalid_native_runtime",
            "Native Runtime startup is Host-owned; runtime.command is not allowed",
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
            "invalid_native_runtime",
            "runtime.descriptor must be an immutable META JSON path",
        )
    if manifest.get("models") or manifest.get("tools"):
        raise PackageError(
            "invalid_native_runtime",
            "Native Runtime Providers cannot publish models or Tools",
        )
    capabilities = manifest.get("capabilities", [])
    required = contract["required_capability"]
    if not isinstance(capabilities, list) or required not in capabilities:
        raise PackageError(
            "invalid_native_runtime", f"Native Runtime must provide {required}"
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
        contract = _runtime_contract(package.manifest)
        installation_kind = (
            str(contract["installation_kind"])
            if contract is not None
            else "inference-runtimes"
        )
        return (
            self.packages_root
            / installation_kind
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
        if not is_native_runtime_manifest(provider.manifest):
            raise PackageError(
                "runtime_provider_invalid", "Locked dependency is not a native Runtime"
            )
        contract = _runtime_contract(provider.manifest)
        assert contract is not None
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
            descriptor.get("schema") != contract["descriptor_schema"]
            or descriptor.get("service_id") != provider.service_key
            or descriptor.get("version") != provider.package_version
            or descriptor.get("protocol") != contract["worker_protocol"]
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
        launcher = (
            inside("launcher")
            if contract["launcher_required"] or descriptor.get("launcher")
            else python
        )
        return ResolvedInferenceRuntime(
            service_key=provider.service_key,
            version=provider.package_version,
            digest=provider.package_digest,
            root=root,
            python=python,
            python_home=inside("python_home", directory=True),
            framework_site_packages=inside("framework_site_packages", directory=True),
            launcher=launcher,
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
        contract = _runtime_contract(package.manifest)
        # Older installer tests and pre-v2 repository rows only persisted the
        # descriptor path in manifest.runtime.  They are unambiguously legacy
        # inference Runtime records because generic native providers did not
        # exist yet; keep their materialization path compatible without
        # weakening validation for newly imported Packages.
        if contract is None:
            contract = _RUNTIME_CONTRACTS[(RUNTIME_PROTOCOL, RUNTIME_ROLE)]
        if (
            value.get("schema") != contract["descriptor_schema"]
            or value.get("service_id") != package.service_key
            or value.get("version") != package.package_version
            or value.get("protocol") != contract["worker_protocol"]
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

    @staticmethod
    def _verify_payload_digest(source: Path, expected: Any) -> None:
        if not isinstance(expected, str):
            raise PackageError(
                "invalid_runtime_descriptor", "Runtime payload sha256 is required"
            )
        expected = expected.removeprefix("sha256:").lower()
        if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
            raise PackageError(
                "invalid_runtime_descriptor", "Runtime payload sha256 is invalid"
            )
        digest = hashlib.sha256()
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        if not hmac.compare_digest(digest.hexdigest(), expected):
            raise PackageError(
                "runtime_payload_digest_mismatch",
                "Runtime payload does not match its declared sha256",
            )

    @staticmethod
    def _safe_tar_member(member: tarfile.TarInfo) -> PurePosixPath:
        name = member.name
        path = PurePosixPath(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in name
            or "\x00" in name
            or name != path.as_posix()
        ):
            raise PackageError(
                "runtime_payload_escape", f"Unsafe Runtime archive path: {name}"
            )
        if member.islnk() or member.isdev() or member.isfifo():
            raise PackageError(
                "runtime_payload_unsupported_entry",
                f"Unsupported Runtime archive entry: {name}",
            )
        if not (member.isdir() or member.isfile() or member.issym()):
            raise PackageError(
                "runtime_payload_unsupported_entry",
                f"Unsupported Runtime archive entry: {name}",
            )
        if member.issym():
            link = member.linkname
            if not link or "\\" in link or "\x00" in link:
                raise PackageError(
                    "runtime_payload_escape", f"Unsafe Runtime symlink: {name}"
                )
            target = posixpath.normpath(posixpath.join(path.parent.as_posix(), link))
            if link.startswith("/") or target == ".." or target.startswith("../"):
                raise PackageError(
                    "runtime_payload_escape", f"Runtime symlink escapes payload: {name}"
                )
        return path

    def _copy_tar_archive(
        self, source: Path, destination: Path, descriptor: dict[str, Any]
    ) -> None:
        if platform.system() != "Linux":
            raise PackageError(
                "runtime_payload_unsupported", "Tar Runtime payload requires Linux"
            )
        payload = descriptor.get("payload", {})
        self._verify_payload_digest(source, payload.get("sha256"))
        maximum = payload.get("max_unpacked_bytes")
        if (
            not isinstance(maximum, int)
            or isinstance(maximum, bool)
            or maximum < 1
            or maximum > MAX_RUNTIME_UNPACKED_BYTES
        ):
            raise PackageError(
                "invalid_runtime_descriptor",
                "Runtime max_unpacked_bytes must be a positive bounded integer",
            )
        archive_root = _safe_relative(payload.get("root"), "payload.root")
        extraction = destination.parent / f".{destination.name}-archive"
        extraction.mkdir()
        try:
            try:
                archive = tarfile.open(source, mode="r:gz")  # noqa: SIM115
            except (OSError, tarfile.TarError) as error:
                raise PackageError(
                    "runtime_payload_verification_failed",
                    "Runtime payload is not a valid tar.gz archive",
                ) from error
            with archive:
                members = archive.getmembers()
                if len(members) > MAX_RUNTIME_ARCHIVE_FILES:
                    raise PackageError(
                        "runtime_payload_size_limit", "Runtime archive has too many entries"
                    )
                paths: set[str] = set()
                expanded = 0
                validated: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
                for member in members:
                    path = self._safe_tar_member(member)
                    if path.as_posix() in paths:
                        raise PackageError(
                            "runtime_payload_duplicate", "Runtime archive has duplicate paths"
                        )
                    paths.add(path.as_posix())
                    expanded += member.size if member.isfile() else 0
                    if expanded > maximum:
                        raise PackageError(
                            "runtime_payload_size_limit",
                            "Runtime archive exceeds its declared expanded size limit",
                        )
                    validated.append((member, path))
                for member, path in validated:
                    target = extraction.joinpath(*path.parts)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    elif member.isfile():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source_stream = archive.extractfile(member)
                        if source_stream is None:
                            raise PackageError(
                                "runtime_payload_verification_failed",
                                f"Runtime archive file is unreadable: {member.name}",
                            )
                        with source_stream, target.open("xb") as output:
                            shutil.copyfileobj(source_stream, output, length=1024 * 1024)
                        target.chmod(member.mode & 0o777)
                for member, path in validated:
                    if not member.issym():
                        continue
                    target = extraction.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(member.linkname)
            candidate = (extraction / archive_root).resolve(strict=True)
            try:
                candidate.relative_to(extraction.resolve(strict=True))
            except ValueError as error:
                raise PackageError(
                    "runtime_payload_escape", "Runtime archive root escapes payload"
                ) from error
            if not candidate.is_dir() or candidate.is_symlink():
                raise PackageError(
                    "runtime_payload_verification_failed",
                    "Runtime archive root is not a directory",
                )
            self._copy_directory(candidate, destination)
        finally:
            shutil.rmtree(extraction, ignore_errors=True)

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
            # Runtime installation must work on a clean consumer Mac.  The
            # xcrun/stapler tool belongs to Xcode's developer toolchain and is
            # therefore unsuitable as an installation-time dependency.
            # Gatekeeper's system spctl validates both the Developer ID
            # signature and the stapled notarization ticket without requiring
            # Xcode. Do not additionally run a bare codesign check on the DMG:
            # stapling appends the ticket after the original signature and can
            # make codesign reject otherwise valid, Gatekeeper-accepted media.
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
            elif payload_type == "tar.gz":
                self._copy_tar_archive(source, candidate, descriptor)
            elif (
                payload_type == "directory"
                and os.environ.get("AI2APPS_ALLOW_DEVELOPMENT_RUNTIME") == "1"
            ):
                self._copy_directory(source, candidate)
            else:
                raise PackageError(
                    "runtime_payload_unsupported",
                    "Only verified DMG and tar.gz Runtime payloads are accepted",
                )
            os.replace(candidate, final)
            self._make_immutable(final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return final
