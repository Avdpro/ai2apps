# SPDX-License-Identifier: Apache-2.0
"""Wheel-only, restart-bound package store for model adapters."""

from __future__ import annotations

import configparser
import hashlib
import importlib
import json
import logging
import os
import shutil
import stat
import sys
import tempfile
import threading
import zipfile
from contextlib import suppress
from email.parser import BytesParser
from importlib import metadata
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename

from .registry import ENTRY_POINT_GROUP

MAX_WHEEL_BYTES = 256 * 1024 * 1024
MANIFEST_VERSION = 1
_PACKAGE_MUTATION_LOCK = threading.RLock()
logger = logging.getLogger(__name__)
UNSAFE_HOST_ADAPTER_ENV = "AI2APPS_UNSAFE_IN_PROCESS_MODEL_ADAPTERS"


class ModelAdapterPackageError(RuntimeError):
    """A package could not be safely inspected or installed."""

    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class ModelAdapterPackageManager:
    """Install immutable wheel payloads and atomically select active versions.

    Installation never invokes pip or executes wheel code. A server restart is
    required after every mutation so an upgrade cannot mix old imported modules
    with new files in the same Python process.
    """

    def __init__(self, base_path: str | Path):
        self.root = Path(base_path).expanduser().resolve() / "model-adapters"
        self.store = self.root / "packages"
        self.manifest_path = self.root / "active.json"

    def _manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"version": MANIFEST_VERSION, "packages": {}}
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelAdapterPackageError(
                "manifest_invalid", "Model adapter package manifest is invalid"
            ) from exc
        if (
            not isinstance(value, dict)
            or value.get("version") != MANIFEST_VERSION
            or not isinstance(value.get("packages"), dict)
        ):
            raise ModelAdapterPackageError(
                "manifest_invalid", "Unsupported model adapter package manifest"
            )
        return value

    def _write_manifest(self, value: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        fd, raw_path = tempfile.mkstemp(prefix="active-", suffix=".json", dir=self.root)
        path = Path(raw_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(path, self.manifest_path)
        finally:
            path.unlink(missing_ok=True)

    @staticmethod
    def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
        members = archive.infolist()
        total = 0
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ModelAdapterPackageError(
                    "wheel_unsafe", f"Unsafe wheel member: {member.filename}"
                )
            if path.parts[0].endswith(".data"):
                raise ModelAdapterPackageError(
                    "wheel_unsupported",
                    "Wheels using the .data install scheme are not supported",
                )
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ModelAdapterPackageError(
                    "wheel_unsafe", f"Wheel symlinks are not allowed: {member.filename}"
                )
            total += member.file_size
            if total > MAX_WHEEL_BYTES:
                raise ModelAdapterPackageError(
                    "wheel_too_large", "Expanded wheel exceeds the 256 MiB limit"
                )
        return members

    @staticmethod
    def _check_dependencies(message) -> list[str]:
        requirements = list(message.get_all("Requires-Dist", []))
        for raw in requirements:
            try:
                requirement = Requirement(raw)
            except InvalidRequirement as exc:
                raise ModelAdapterPackageError(
                    "dependency_invalid", f"Invalid dependency declaration: {raw}"
                ) from exc
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            try:
                installed = metadata.version(requirement.name)
            except metadata.PackageNotFoundError as exc:
                raise ModelAdapterPackageError(
                    "dependency_missing",
                    f"Required runtime package is not installed: {requirement.name}",
                    details={"requirement": raw},
                ) from exc
            if requirement.specifier and installed not in requirement.specifier:
                raise ModelAdapterPackageError(
                    "dependency_incompatible",
                    f"Installed {requirement.name} {installed} does not satisfy {raw}",
                    details={"requirement": raw, "installed_version": installed},
                )
        return requirements

    def inspect(self, wheel_path: str | Path) -> dict[str, Any]:
        path = Path(wheel_path).expanduser().resolve()
        if not path.is_file() or path.suffix != ".whl":
            raise ModelAdapterPackageError(
                "wheel_not_found", "A local .whl file is required"
            )
        if path.stat().st_size > MAX_WHEEL_BYTES:
            raise ModelAdapterPackageError(
                "wheel_too_large", "Wheel exceeds the 256 MiB limit"
            )
        try:
            filename_name, filename_version, _build, wheel_tags = parse_wheel_filename(
                path.name
            )
        except Exception as exc:
            raise ModelAdapterPackageError(
                "wheel_invalid", "Invalid wheel filename"
            ) from exc
        if not set(wheel_tags).intersection(sys_tags()):
            raise ModelAdapterPackageError(
                "wheel_incompatible", "Wheel is not compatible with this runtime"
            )

        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            with zipfile.ZipFile(path) as archive:
                members = self._safe_members(archive)
                metadata_names = [
                    item.filename
                    for item in members
                    if item.filename.endswith(".dist-info/METADATA")
                ]
                if len(metadata_names) != 1:
                    raise ModelAdapterPackageError(
                        "wheel_invalid", "Wheel must contain exactly one METADATA file"
                    )
                dist_info = metadata_names[0].rsplit("/", 1)[0]
                message = BytesParser().parsebytes(archive.read(metadata_names[0]))
                entry_name = f"{dist_info}/entry_points.txt"
                if entry_name not in archive.namelist():
                    raise ModelAdapterPackageError(
                        "adapter_entry_point_missing",
                        f"Wheel does not declare {ENTRY_POINT_GROUP}",
                    )
                parser = configparser.ConfigParser(interpolation=None)
                parser.optionxform = str
                parser.read_string(archive.read(entry_name).decode("utf-8"))
                if not parser.has_section(ENTRY_POINT_GROUP):
                    raise ModelAdapterPackageError(
                        "adapter_entry_point_missing",
                        f"Wheel does not declare {ENTRY_POINT_GROUP}",
                    )
                entry_points = dict(parser.items(ENTRY_POINT_GROUP))
                if not entry_points:
                    raise ModelAdapterPackageError(
                        "adapter_entry_point_missing", "Adapter entry-point group is empty"
                    )
        except zipfile.BadZipFile as exc:
            raise ModelAdapterPackageError("wheel_invalid", "Wheel is not a valid ZIP") from exc

        name = message.get("Name")
        version = message.get("Version")
        if not name or not version:
            raise ModelAdapterPackageError(
                "wheel_invalid", "Wheel metadata is missing Name or Version"
            )
        normalized = canonicalize_name(name)
        if normalized != canonicalize_name(filename_name) or version != str(filename_version):
            raise ModelAdapterPackageError(
                "wheel_invalid", "Wheel filename and package metadata do not match"
            )
        requirements = self._check_dependencies(message)
        return {
            "name": name,
            "normalized_name": normalized,
            "version": version,
            "sha256": digest,
            "wheel_path": str(path),
            "entry_points": entry_points,
            "requirements": requirements,
        }

    def install(self, wheel_path: str | Path) -> dict[str, Any]:
        with _PACKAGE_MUTATION_LOCK:
            return self._install(wheel_path)

    def _install(self, wheel_path: str | Path) -> dict[str, Any]:
        inspected = self.inspect(wheel_path)
        source = Path(inspected["wheel_path"])
        relative = Path("packages") / inspected["normalized_name"] / inspected["version"] / inspected["sha256"]
        final = self.root / relative
        if not final.exists():
            self.store.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix="adapter-", dir=self.root))
            try:
                site_packages = staging / "site-packages"
                site_packages.mkdir()
                with zipfile.ZipFile(source) as archive:
                    self._safe_members(archive)
                    archive.extractall(site_packages)
                shutil.copy2(source, staging / source.name)
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, final)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

        manifest = self._manifest()
        previous = manifest["packages"].get(inspected["normalized_name"])
        record = {
            "name": inspected["name"],
            "normalized_name": inspected["normalized_name"],
            "version": inspected["version"],
            "sha256": inspected["sha256"],
            "path": str(relative / "site-packages"),
            "entry_points": inspected["entry_points"],
            "requirements": inspected["requirements"],
        }
        manifest["packages"][inspected["normalized_name"]] = record
        self._write_manifest(manifest)
        return {
            **record,
            "operation": "installed" if previous is None else "upgraded",
            "previous_version": None if previous is None else previous.get("version"),
            "restart_required": True,
        }

    def uninstall(self, package_name: str) -> dict[str, Any]:
        with _PACKAGE_MUTATION_LOCK:
            return self._uninstall(package_name)

    def _uninstall(self, package_name: str) -> dict[str, Any]:
        normalized = canonicalize_name(package_name)
        manifest = self._manifest()
        previous = manifest["packages"].pop(normalized, None)
        if previous is None:
            raise ModelAdapterPackageError(
                "package_not_installed", f"Model adapter package is not installed: {package_name}"
            )
        self._write_manifest(manifest)
        return {
            **previous,
            "operation": "uninstalled",
            "restart_required": True,
        }

    def installed(self) -> list[dict[str, Any]]:
        manifest = self._manifest()
        return [
            {**record, "restart_required": False}
            for _, record in sorted(manifest["packages"].items())
        ]

    def active_paths(self) -> list[Path]:
        paths: list[Path] = []
        for record in self.installed():
            path = (self.root / record["path"]).resolve()
            try:
                path.relative_to(self.root)
            except ValueError:
                continue
            if path.is_dir():
                paths.append(path)
        return paths

    def prune_inactive(self) -> int:
        """Remove payload versions no longer selected by the manifest."""
        manifest = self._manifest()
        active: set[Path] = set()
        for record in manifest["packages"].values():
            payload = (self.root / record["path"]).resolve()
            try:
                payload.relative_to(self.root)
            except ValueError:
                continue
            active.add(payload.parent)

        removed = 0
        if self.store.is_dir():
            for candidate in self.store.glob("*/*/*"):
                resolved = candidate.resolve()
                if resolved in active or not candidate.is_dir():
                    continue
                shutil.rmtree(candidate, ignore_errors=True)
                removed += 1
            for candidate in sorted(self.store.glob("*/*"), reverse=True):
                with suppress(OSError):
                    candidate.rmdir()
            for candidate in sorted(self.store.glob("*"), reverse=True):
                with suppress(OSError):
                    candidate.rmdir()
        return removed


def configure_model_adapter_packages(base_path: str | Path) -> tuple[Path, ...]:
    """Expose installed adapter payloads only in explicit unsafe development mode.

    Downloaded wheel code has Host authority after entering sys.path. Production
    builds therefore fail closed until the model-worker runtime owns discovery,
    loading, and generation outside the Host process.
    """

    manager = ModelAdapterPackageManager(base_path)
    try:
        manager.prune_inactive()
        paths = manager.active_paths()
    except ModelAdapterPackageError:
        return ()
    if not paths:
        return ()
    if os.environ.get(UNSAFE_HOST_ADAPTER_ENV, "").strip() != "1":
        logger.warning(
            "Installed model adapters are present but Host execution is disabled; "
            "migrate them to the model-worker runtime. %s=1 is unsafe and for "
            "isolated development only.",
            UNSAFE_HOST_ADAPTER_ENV,
        )
        return ()
    for path in reversed(paths):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)
    importlib.invalidate_caches()
    return tuple(paths)
