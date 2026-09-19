"""Trusted source-tree discovery for Development Bundle App Packages."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ai2apps.localization import package_localizations_for_manifest
from ai2apps.packages.contract_v1 import (
    PackageContractError,
    mini_app_catalog_from_app_manifest,
    validate_manifest,
)

from .archive import MAX_BYTES, MAX_FILES, InteractiveArchive
from .models import ExtensionError, UnitKind

_IGNORED_DIRECTORIES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
}


@dataclass(frozen=True, slots=True)
class DevelopmentAppPackage:
    """One validated App Package mounted directly from a trusted source tree."""

    package_id: str
    package_version: str
    definition_version: str
    effective_digest: str
    source_root: Path
    files: frozenset[str]
    manifest: dict[str, Any]


class DevelopmentPackageLoader:
    """Discover direct child Packages below a Bundle-provided repository root."""

    def __init__(self, source_root: Path) -> None:
        self.source_root = source_root.resolve(strict=True)
        if not (self.source_root / "ai2apps" / "__init__.py").is_file():
            raise ExtensionError(
                "development_source_invalid",
                "Development source root must contain ai2apps/__init__.py",
            )
        self.packages_root = (self.source_root / "packages").resolve(strict=True)
        if not self.packages_root.is_dir():
            raise ExtensionError(
                "development_source_invalid",
                "Development source root must contain a packages directory",
            )

    def discover(self) -> tuple[DevelopmentAppPackage, ...]:
        result: list[DevelopmentAppPackage] = []
        for candidate in sorted(self.packages_root.iterdir(), key=lambda item: item.name):
            if (
                not candidate.is_dir()
                or candidate.is_symlink()
                or not (candidate / "ai2apps.json").is_file()
                or not (candidate / "app.yaml").is_file()
            ):
                continue
            result.append(self._load(candidate))
        return tuple(result)

    def _load(self, candidate: Path) -> DevelopmentAppPackage:
        root = candidate.resolve(strict=True)
        if root.parent != self.packages_root:
            raise ExtensionError(
                "development_package_escaped",
                "Development Packages must be direct children of the packages root",
            )
        files = self._source_files(root)
        try:
            outer = json.loads((root / "ai2apps.json").read_text(encoding="utf-8"))
            validation_copy = json.loads(json.dumps(outer))
            validation_copy["files"] = [
                {
                    "path": name,
                    "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
                    "size": (root / name).stat().st_size,
                }
                for name in sorted(files - {"ai2apps.json"})
            ]
            outer = validate_manifest(validation_copy)
        except (OSError, json.JSONDecodeError, PackageContractError) as error:
            raise ExtensionError(
                "development_package_invalid",
                f"Invalid development Package metadata in {candidate.name}: {error}",
            ) from error
        package = outer["package"]
        if package["type"] != "app":
            raise ExtensionError(
                "development_package_unsupported",
                "Only App Packages can be source-mounted in this development path",
            )
        try:
            app_manifest = yaml.safe_load((root / "app.yaml").read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ExtensionError(
                "development_app_definition_invalid",
                f"app.yaml is invalid in {candidate.name}",
            ) from error
        if not isinstance(app_manifest, dict):
            raise ExtensionError(
                "development_app_definition_invalid",
                f"app.yaml must contain an object in {candidate.name}",
            )
        runtime_key = package["id"].replace("/", ".")
        app_manifest = dict(app_manifest)
        localizations = package_localizations_for_manifest(
            package.get("localizations"), app_manifest.get("localizations")
        )
        publisher = app_manifest.get("publisher")
        publisher_id = (
            publisher.get("id")
            if isinstance(publisher, dict) and isinstance(publisher.get("id"), str)
            else "development.local"
        )
        app_manifest.update(
            {
                "id": runtime_key,
                "name": package["displayName"],
                "description": package.get("description", ""),
                "version": package["version"],
                "publisher": {"id": publisher_id},
                "development": {
                    "mode": "source",
                    "packageId": package["id"],
                    "sourceRoot": str(root),
                },
            }
        )
        if localizations:
            app_manifest["localizations"] = localizations
        entrypoint = outer["entrypoints"][0]
        entry = app_manifest.get("entry")
        if not isinstance(entry, dict) or entry.get("resource") != entrypoint["path"]:
            raise ExtensionError(
                "development_app_entrypoint_mismatch",
                "app.yaml entry must match the Package entrypoint",
            )
        declared_mini_apps = outer.get("miniApps")
        if (
            declared_mini_apps is not None
            and declared_mini_apps != mini_app_catalog_from_app_manifest(app_manifest)
        ):
            raise ExtensionError(
                "development_mini_app_catalog_mismatch",
                "Package Mini-App catalog does not match app.yaml",
            )
        InteractiveArchive._validate_manifest(UnitKind.APP, app_manifest, set(files))
        path_hash = hashlib.sha256(str(root).encode("utf-8")).hexdigest()
        return DevelopmentAppPackage(
            package_id=runtime_key,
            package_version=package["version"],
            definition_version=f"{package['version']}+development.{path_hash[:8]}",
            effective_digest=f"sha256:{path_hash}",
            source_root=root,
            files=frozenset(files),
            manifest=app_manifest,
        )

    @staticmethod
    def _source_files(root: Path) -> set[str]:
        files: set[str] = set()
        total = 0
        for directory, names, filenames in os.walk(root, followlinks=False):
            current = Path(directory)
            kept_names: list[str] = []
            for name in names:
                child = current / name
                if name in _IGNORED_DIRECTORIES:
                    continue
                if child.is_symlink():
                    raise ExtensionError(
                        "development_package_link_denied",
                        "Development Package source links are forbidden",
                    )
                kept_names.append(name)
            names[:] = kept_names
            for name in filenames:
                path = current / name
                if path.is_symlink():
                    raise ExtensionError(
                        "development_package_link_denied",
                        "Development Package source links are forbidden",
                    )
                relative = path.relative_to(root).as_posix()
                if PurePosixPath(relative).parts[0] in _IGNORED_DIRECTORIES:
                    continue
                total += path.stat().st_size
                files.add(relative)
                if len(files) > MAX_FILES or total > MAX_BYTES:
                    raise ExtensionError(
                        "development_package_limit",
                        "Development Package exceeds the App Package file limits",
                    )
        return files
