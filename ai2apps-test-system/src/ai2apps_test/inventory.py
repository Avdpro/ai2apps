from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

from .model import Component

SYSTEM_GROUPS = {
    "ai2apps.dashboard",
    "ai2apps.account",
    "ai2apps.models",
    "ai2apps.environment",
    "ai2apps.discover",
    "ai2apps.trust-center",
    "ai2apps.settings",
    "ai2apps.logs",
    "ai2apps.sharing",
}


def _literal_assignment(path: Path, name: str) -> Any:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(
                isinstance(target, ast.Name) and target.id == name for target in targets
            ):
                return ast.literal_eval(node.value)
    raise ValueError(f"{name} was not found in {path}")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def discover_system_components(repo_root: Path) -> list[Component]:
    path = repo_root / "ai2apps" / "apps" / "system.py"
    manifests = _literal_assignment(path, "_SYSTEM_APP_MANIFESTS_BASE")
    components: list[Component] = []
    for manifest in manifests:
        component_id = str(manifest["id"])
        navigation = manifest.get("navigation", {})
        status = navigation.get("status", "shipping")
        group = "System Apps" if component_id in SYSTEM_GROUPS else "Main Apps"
        components.append(
            Component(
                id=component_id,
                kind="app",
                name=str(manifest.get("name", component_id)),
                group=group,
                release_status=status,
                source=str(path.relative_to(repo_root)),
                metadata={"entry": manifest.get("entry")},
            )
        )
        mini_entry = manifest.get("mini_entry")
        if isinstance(mini_entry, dict):
            components.append(
                Component(
                    id=f"{component_id}.mini-entry",
                    kind="builtin-mini-entry",
                    name=f"{manifest.get('name', component_id)} Mini-Entry",
                    group="Built-in Mini-Entries",
                    release_status=status,
                    source=str(path.relative_to(repo_root)),
                    parent_id=component_id,
                    metadata={"mini_entry": mini_entry},
                )
            )
    return components


def discover_packages(repo_root: Path) -> list[Component]:
    components: list[Component] = []
    packages_root = repo_root / "packages"
    if not packages_root.is_dir():
        return components
    for manifest_path in sorted(packages_root.glob("*/ai2apps.json")):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        package = manifest.get("package", {})
        package_id = package.get("id")
        package_type = package.get("type")
        if not isinstance(package_id, str) or not isinstance(package_type, str):
            continue
        group = (
            "Packaged Apps"
            if package_type == "app"
            else "Runtime, Service and Model Packages"
        )
        components.append(
            Component(
                id=package_id,
                kind=f"package-{package_type}",
                name=str(package.get("displayName", package_id)),
                group=group,
                source=str(manifest_path.relative_to(repo_root)),
                metadata={"version": package.get("version")},
            )
        )
        app_yaml = manifest_path.with_name("app.yaml")
        app_definition = _read_yaml(app_yaml) if app_yaml.is_file() else {}
        for mini_app in app_definition.get("mini_apps", []):
            if not isinstance(mini_app, dict) or not isinstance(
                mini_app.get("id"), str
            ):
                continue
            components.append(
                Component(
                    id=mini_app["id"],
                    kind="packaged-mini-app",
                    name=str(mini_app.get("name", mini_app["id"])),
                    group="Packaged Mini-Apps",
                    source=str(app_yaml.relative_to(repo_root)),
                    parent_id=package_id,
                    metadata={
                        "placements": mini_app.get("placements", []),
                        "requirements": mini_app.get("requirements", {}),
                    },
                )
            )
    return components


def discover_inventory(repo_root: Path) -> list[Component]:
    components = discover_system_components(repo_root) + discover_packages(repo_root)
    unique = {f"{component.kind}:{component.id}": component for component in components}
    return sorted(unique.values(), key=lambda item: (item.group, item.kind, item.id))


def inventory_digest(components: list[Component]) -> str:
    payload = json.dumps(
        [component.to_dict() for component in components],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
