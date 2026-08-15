"""Source-project discovery, validation, preview, and development bundles."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import secrets
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from ai2apps.extensions import UnitKind
from ai2apps.extensions.archive import InteractiveArchive
from ai2apps.packages.archive import ServicePackageArchive

_KINDS = {"app", "mini-app", "agent", "service"}
_MANIFEST_NAMES = {
    "app": "app.yaml",
    "mini-app": "mini-app.yaml",
    "agent": "agent.yaml",
    "service": "service.yaml",
}
_IGNORED_PARTS = {".git", ".pytest_cache", "__pycache__", "dist", "node_modules"}
_MAX_SOURCE_FILES = 10_000
_MAX_SOURCE_BYTES = 512 * 1024 * 1024
_COMPONENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")
_PACKAGE_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")


class ProjectSourceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class SourceComponent:
    id: str
    kind: str
    name: str
    version: str
    root: Path
    manifest_path: Path
    manifest: dict[str, Any]
    synthetic: bool = False

    def public(self) -> dict[str, Any]:
        entry = self.manifest.get("entry")
        previewable = (
            self.kind in {"app", "mini-app"}
            and isinstance(entry, dict)
            and entry.get("kind") in {"sandbox", "safe-html"}
            and isinstance(entry.get("resource"), str)
        )
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "version": self.version,
            "path": str(self.root),
            "manifest_path": str(self.manifest_path),
            "entry": entry if isinstance(entry, dict) else None,
            "runnable": previewable,
            "synthetic": self.synthetic,
        }


@dataclass(slots=True)
class DevSession:
    id: str
    project_id: str
    component: SourceComponent

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "component_id": self.component.id,
            "component": self.component.public(),
            "status": "running",
            "preview_url": f"/admin/coder-dev/{self.id}/preview",
        }


class SourceProject:
    """Read a Coder Project without installing or mutating its components."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()

    def _inside(self, value: Path) -> Path:
        path = value.resolve()
        if not path.is_relative_to(self.root):
            raise ProjectSourceError("unsafe_component_path", "Component leaves Project")
        return path

    def _project_data(self) -> dict[str, Any]:
        path = self.root / ".ai2apps" / "project.json"
        if not path.is_file():
            return {"schema": "ai2apps.project/v1", "name": self.root.name, "components": []}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, TypeError, json.JSONDecodeError) as error:
            raise ProjectSourceError("invalid_project", "Invalid .ai2apps/project.json") from error
        if not isinstance(value, dict) or value.get("schema") != "ai2apps.project/v1":
            raise ProjectSourceError("invalid_project", "Expected ai2apps.project/v1")
        if not isinstance(value.get("components", []), list):
            raise ProjectSourceError("invalid_project", "Project components must be an array")
        return value

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any]:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ProjectSourceError("invalid_manifest", f"Invalid manifest: {path.name}") from error
        if not isinstance(value, dict):
            raise ProjectSourceError("invalid_manifest", f"Manifest must be an object: {path.name}")
        return value

    def _descriptor(self, raw: dict[str, Any]) -> SourceComponent:
        kind = str(raw.get("type") or raw.get("kind") or "").strip()
        if kind not in _KINDS:
            raise ProjectSourceError("invalid_component", f"Unsupported component type: {kind}")
        if raw.get("manifest"):
            manifest_path = self._inside(self.root / str(raw["manifest"]))
            component_root = manifest_path.parent
        else:
            component_root = self._inside(self.root / str(raw.get("path") or "."))
            manifest_path = component_root / _MANIFEST_NAMES[kind]
        if not manifest_path.is_file():
            raise ProjectSourceError("manifest_missing", f"Missing component manifest: {manifest_path}")
        manifest = self._load_manifest(manifest_path)
        component_id = str(manifest.get("id") or raw.get("id") or "").strip()
        if not component_id:
            raise ProjectSourceError("invalid_component", f"Component id is missing: {manifest_path}")
        if not _COMPONENT_ID.fullmatch(component_id):
            raise ProjectSourceError(
                "invalid_component_id",
                f"Component id contains unsupported characters: {component_id}",
            )
        return SourceComponent(
            component_id,
            kind,
            str(manifest.get("name") or component_id),
            str(manifest.get("version") or "0.0.0"),
            component_root,
            manifest_path,
            manifest,
        )

    def components(self) -> list[SourceComponent]:
        data = self._project_data()
        raw_components = data.get("components", [])
        if not raw_components:
            raw_components = [
                {"kind": kind, "path": "."}
                for kind, name in _MANIFEST_NAMES.items()
                if (self.root / name).is_file()
            ]
        result: list[SourceComponent] = []
        ids: set[str] = set()
        for raw in raw_components:
            if not isinstance(raw, dict):
                raise ProjectSourceError("invalid_component", "Component descriptor must be an object")
            component = self._descriptor(raw)
            if component.id in ids:
                raise ProjectSourceError("duplicate_component", f"Duplicate component id: {component.id}")
            ids.add(component.id)
            result.append(component)
            mini = component.manifest.get("mini_entry") if component.kind == "app" else None
            if isinstance(mini, dict):
                mini_id = f"{component.id}:mini"
                mini_manifest = {
                    **component.manifest,
                    "id": mini_id,
                    "name": f"{component.name} Mini-App",
                    "schema": "ai2apps.mini-app/v1",
                    "entry": mini,
                }
                result.append(
                    SourceComponent(
                        mini_id,
                        "mini-app",
                        mini_manifest["name"],
                        component.version,
                        component.root,
                        component.manifest_path,
                        mini_manifest,
                        True,
                    )
                )
                ids.add(mini_id)
        return result

    @staticmethod
    def _component_files(component: SourceComponent) -> set[str]:
        return {
            path.relative_to(component.root).as_posix()
            for path in component.root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and not any(
                part in _IGNORED_PARTS
                for part in path.relative_to(component.root).parts
            )
        }

    def validate(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        try:
            components = self.components()
        except ProjectSourceError as error:
            return {"valid": False, "components": [], "checks": [{"ok": False, "code": error.code, "message": str(error)}]}
        for component in components:
            try:
                files = self._component_files(component)
                if component.kind == "app":
                    InteractiveArchive._validate_manifest(UnitKind.APP, component.manifest, files)
                elif component.kind == "agent":
                    InteractiveArchive._validate_manifest(UnitKind.AGENT, component.manifest, files)
                elif component.kind == "service":
                    ServicePackageArchive._manifest(component.manifest)
                else:
                    entry = component.manifest.get("entry")
                    if not isinstance(entry, dict) or entry.get("kind") not in {"schema", "safe-html", "sandbox"}:
                        raise ProjectSourceError("invalid_mini_app", "Mini-App requires schema, safe-html, or sandbox entry")
                    resource = entry.get("resource")
                    if not isinstance(resource, str) or resource not in files:
                        raise ProjectSourceError("entry_resource_missing", "Mini-App entry resource is missing")
                checks.append({"ok": True, "code": "component.valid", "component_id": component.id, "message": f"{component.kind} manifest and resources are valid"})
            except Exception as error:
                checks.append({"ok": False, "code": getattr(error, "code", "invalid_component"), "component_id": component.id, "message": str(error)})
        return {"valid": all(item["ok"] for item in checks), "components": [item.public() for item in components], "checks": checks}

    def component(self, component_id: str) -> SourceComponent:
        item = next((item for item in self.components() if item.id == component_id), None)
        if item is None:
            raise ProjectSourceError("component_not_found", "Project component not found")
        return item

    def resolve_resource(self, component: SourceComponent, resource: str) -> Path:
        pure = PurePosixPath(resource)
        if not resource or pure.is_absolute() or ".." in pure.parts or "\\" in resource:
            raise ProjectSourceError("unsafe_resource", "Unsafe development resource path")
        path = (component.root / pure.as_posix()).resolve()
        if not path.is_relative_to(component.root) or not path.is_file() or path.is_symlink():
            raise ProjectSourceError("resource_not_found", "Development resource not found")
        return path

    def build(self, destination: str | Path | None = None) -> Path:
        report = self.validate()
        if not report["valid"]:
            raise ProjectSourceError("validation_failed", "Project validation failed")
        data = self._project_data()
        package_id = str(data.get("id") or self.root.name).strip()
        version = str(data.get("version") or "0.1.0-dev").strip()
        if not _COMPONENT_ID.fullmatch(package_id):
            raise ProjectSourceError("invalid_package_id", "Project Bundle id is invalid")
        if not _PACKAGE_VERSION.fullmatch(version):
            raise ProjectSourceError(
                "invalid_package_version", "Project Bundle version is invalid"
            )
        output = Path(destination) if destination else self.root / "dist" / f"{package_id}-{version}.ai2package"
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        files: list[tuple[str, Path]] = []
        total = 0
        components = self.components()
        bundle_components: list[dict[str, Any]] = []
        root_prefixes: dict[Path, str] = {}
        for component_index, component in enumerate(components):
            prefix = root_prefixes.get(component.root)
            new_root = prefix is None
            if prefix is None:
                prefix = f"components/{component_index:04d}-{component.kind}"
                root_prefixes[component.root] = prefix
            bundle_components.append(
                {
                    "id": component.id,
                    "type": component.kind,
                    "name": component.name,
                    "version": component.version,
                    "root": prefix,
                    "manifest": f"{prefix}/{component.manifest_path.relative_to(component.root).as_posix()}",
                    **({"source": "app.mini_entry"} if component.synthetic else {}),
                }
            )
            if not new_root:
                continue
            for source in sorted(component.root.rglob("*")):
                relative = source.relative_to(component.root)
                if not source.is_file() or source.is_symlink() or any(part in _IGNORED_PARTS for part in relative.parts):
                    continue
                total += source.stat().st_size
                files.append((f"{prefix}/{relative.as_posix()}", source))
        if len(files) > _MAX_SOURCE_FILES or total > _MAX_SOURCE_BYTES:
            raise ProjectSourceError("bundle_size_limit", "Project Bundle exceeds development limits")
        index = []
        for name, source in files:
            content = source.read_bytes()
            index.append({"path": name, "sha256": f"sha256:{hashlib.sha256(content).hexdigest()}", "size": len(content)})
        package = {
            "schema": "ai2apps.package/v1",
            "id": package_id,
            "name": data.get("name") or self.root.name,
            "version": version,
            "development": True,
            "installable": False,
            "components": bundle_components,
        }
        sbom = {"spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT", "name": package_id, "dataLicense": "CC0-1.0"}
        temporary = output.with_suffix(output.suffix + ".tmp")
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("META/package.json", json.dumps(package, ensure_ascii=False, indent=2))
            archive.writestr("META/files.json", json.dumps({"files": index}, ensure_ascii=False, indent=2))
            archive.writestr("META/sbom.spdx.json", json.dumps(sbom, ensure_ascii=False, indent=2))
            for name, source in files:
                archive.write(source, name)
        temporary.replace(output)
        return output


def media_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def new_dev_session_id() -> str:
    return f"devs_{secrets.token_hex(16)}"


def test_command(root: Path) -> list[str] | None:
    if (root / "tests").is_dir():
        return [sys.executable, "-m", "pytest", "-q"]
    if (root / "package.json").is_file():
        return ["npm", "test"]
    return None
