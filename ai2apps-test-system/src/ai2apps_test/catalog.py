from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from .catalog_store import CatalogStore
from .catalog_validation import (
    CatalogValidationError,
    require_valid,
    validate_case,
    validate_group,
    validate_pipeline,
)
from .model import PRIORITIES, Case, Component, TestGroup, priority_includes

CASE_TEMPLATES: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "app": (("launch-smoke", "Launch and first ready view", "P0", "codex-ui"), ("primary-flow", "Primary navigation and recovery", "P1", "codex-ui"), ("ue-matrix", "Visual, locale and accessibility matrix", "P2", "codex-ui"), ("release-persistence", "Release persistence and upgrade behavior", "P3", "codex-ui")),
    "builtin-mini-entry": (("discover-mount", "Discover, mount and close", "P0", "codex-ui"), ("state-sync", "Host state synchronization and recovery", "P1", "codex-ui"), ("ue-matrix", "Sidebar and inline UE matrix", "P2", "codex-ui"), ("release-context", "Release browser-context continuity", "P3", "codex-ui")),
    "packaged-mini-app": (("discover-mount", "Installed discovery and mount", "P0", "codex-ui"), ("mock-happy-path", "Deterministic capability happy path", "P1", "codex-ui"), ("states-and-recovery", "Dependency, error and recovery matrix", "P2", "codex-ui"), ("real-capability", "Real provider release workflow", "P3", "codex-ui")),
}


def group_id_for_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "catalog-group"


def _revision(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _base_objects(repo_root: Path) -> tuple[list[TestGroup], list[Case]]:
    path = repo_root / "tests" / "ats" / "catalog" / "base.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("migrated") is True:
        return [], []
    names = sorted({str(item["group"]) for item in raw["cases"]})
    groups = [TestGroup(group_id_for_name(name), name, source_path=str(path.relative_to(repo_root)), revision=_revision({"name": name})) for name in names]
    cases = [Case(
        id=item["id"], name=item["name"], priority=item["priority"], group=item["group"], executor=item["executor"],
        command=tuple(item.get("command", [])), timeout_seconds=int(item.get("timeoutSeconds", 300)),
        requires=tuple(item.get("requires", [])), tags=tuple(item.get("tags", [])), description=item.get("description", ""),
        required=bool(item.get("required", True)), group_id=group_id_for_name(item["group"]), source_path=str(path.relative_to(repo_root)), revision=_revision(item),
    ) for item in raw["cases"]]
    return groups, cases


def _component_cases(component: Component) -> list[Case]:
    templates = CASE_TEMPLATES.get(component.kind)
    if templates is None and component.kind.startswith("package-"):
        templates = (("contract", "Manifest and artifact contract", "P0", "builtin"), ("lifecycle", "Install, disable and remove lifecycle", "P1", "codex-ui"), ("upgrade-rollback", "Upgrade and rollback lifecycle", "P2", "codex-ui"), ("clean-release", "Signed clean-instance release acceptance", "P3", "codex-ui"))
    if not templates:
        return []
    required_index = PRIORITIES.index("P1" if component.release_status == "development" else "P3")
    return [Case(
        id=f"component.{component.kind}.{component.id}.{suffix}", name=f"{component.name}: {name}", priority=priority,
        group=component.group, executor=executor, component_id=component.id, requires=("test-account",) if executor == "codex-ui" else (),
        tags=(component.kind, component.release_status), required=PRIORITIES.index(priority) <= required_index,
        description=f"Generated common contract for {component.id}", group_id=group_id_for_name(component.group),
        source_type="generated", source_path=component.source,
    ) for suffix, name, priority, executor in templates]


def _user_objects(repo_root: Path) -> tuple[list[TestGroup], list[Case]]:
    store = CatalogStore(repo_root)
    group_values = store.list_objects("groups")
    by_id = {str(value.get("id")): value for value in group_values}
    groups: list[TestGroup] = []
    errors: list[str] = []
    for value in group_values:
        errors.extend(f"{value.get('sourcePath')}: {error}" for error in validate_group(value))
        source_type = str(value.get("sourceType", "user-authored"))
        groups.append(TestGroup(
            id=str(value.get("id", "")), name=str(value.get("name", "")), description=str(value.get("description", "")), kind=str(value.get("kind", "regular")),
            enabled=bool(value.get("enabled", True)), default_selected=bool(value.get("defaultSelected", False)), order=int(value.get("order", 500)),
            tags=tuple(value.get("tags", [])), lifecycle=str(value.get("lifecycle", "draft")), source_type=source_type, source_path=str(value.get("sourcePath", "")), editable=source_type == "user-authored", revision=str(value.get("revision", "")),
        ))
    cases: list[Case] = []
    for value in store.list_objects("cases"):
        source_type = str(value.get("sourceType", "user-authored"))
        errors.extend(f"{value.get('sourcePath')}: {error}" for error in validate_case(value, by_id, trusted_builtin=source_type == "built-in"))
        group = by_id.get(value.get("groupId"), {})
        cases.append(Case(
            id=str(value.get("id", "")), name=str(value.get("name", "")), priority=value.get("priority"), group=str(group.get("name", value.get("groupId", ""))), executor=str(value.get("executor", "")),
            component_id=value.get("componentId"), timeout_seconds=int(value.get("timeoutSeconds", 300)), requires=tuple(value.get("requires", [])), tags=tuple(value.get("tags", [])), description=str(value.get("description", "")),
            required=bool(value.get("required", False)), group_id=str(value.get("groupId", "")), enabled=bool(value.get("enabled", False)), lifecycle=str(value.get("lifecycle", "draft")),
            source_type=source_type, source_path=str(value.get("sourcePath", "")), editable=source_type == "user-authored", instructions=tuple(value.get("instructions", [])), expectations=tuple(value.get("expectations", [])), cleanup=tuple(value.get("cleanup", [])), fixtures=tuple(value.get("fixtures", [])), revision=str(value.get("revision", "")),
        ))
    require_valid(errors)
    return groups, cases


def build_catalog_bundle(repo_root: Path, components: list[Component]) -> tuple[list[TestGroup], list[Case]]:
    base_groups, base_cases = _base_objects(repo_root)
    generated_cases = [case for component in components for case in _component_cases(component)]
    user_groups, user_cases = _user_objects(repo_root)
    groups_by_id = {group.id: group for group in base_groups}
    for case in generated_cases:
        groups_by_id.setdefault(case.group_id or "", TestGroup(case.group_id or "", case.group, source_type="generated", source_path=case.source_path))
    for group in user_groups:
        if group.id in groups_by_id:
            raise CatalogValidationError([f"duplicate group ID {group.id}: {groups_by_id[group.id].source_path} and {group.source_path}"])
        groups_by_id[group.id] = group
    all_cases = base_cases + generated_cases + user_cases
    content_by_id = {item["id"]: item for item in CatalogStore(repo_root).list_objects("case-content")}
    updated_cases = []
    for case in all_cases:
        content = content_by_id.get(case.id)
        if content:
            fields = content["content"]
            require_valid(validate_pipeline({"id": "validation", "name": "validation", "steps": [{"id": "step", "type": "case", "caseId": case.id, "caseContent": fields}]}, allow_case_content=True))
            updated_cases.append(replace(case, **{
                key: tuple(value) if key in {"instructions", "expectations", "cleanup"} else value
                for key, value in fields.items()
            }, revision=hashlib.sha256((case.revision + content["revision"]).encode()).hexdigest()))
        else:
            updated_cases.append(case)
    all_cases = updated_cases
    seen: dict[str, Case] = {}
    for case in all_cases:
        if case.id in seen:
            raise CatalogValidationError([f"duplicate case ID {case.id}: {seen[case.id].source_path} and {case.source_path}"])
        seen[case.id] = case
    active = [case for case in all_cases if case.enabled and case.lifecycle in {"trial-passed", "enabled"}]
    active.sort(key=lambda item: ((PRIORITIES.index(item.priority) if item.priority in PRIORITIES else len(PRIORITIES)), item.group, item.id))
    return sorted(groups_by_id.values(), key=lambda item: (item.order, item.name, item.id)), active


def build_catalog(repo_root: Path, components: list[Component]) -> list[Case]:
    return build_catalog_bundle(repo_root, components)[1]


def select_cases(cases: list[Case], priority: str | None, selected_ids: set[str] | None = None, groups: set[str] | None = None, *, include_groups: set[str] | None = None, include_case_ids: set[str] | None = None, excluded_ids: set[str] | None = None) -> list[Case]:
    selected: dict[str, Case] = {}
    for case in cases:
        if (
            priority is not None
            and priority_includes(priority, case.priority)
            and (selected_ids is None or case.id in selected_ids)
            and (not groups or case.group in groups or case.group_id in groups)
        ):
            selected[case.id] = case
    for case in cases:
        if include_groups and (case.group_id in include_groups or case.group in include_groups):
            selected[case.id] = case
        if include_case_ids and case.id in include_case_ids:
            selected[case.id] = case
    for case_id in excluded_ids or set():
        selected.pop(case_id, None)
    return [case for case in cases if case.id in selected]


def catalog_digest(cases: list[Case]) -> str:
    value = json.dumps([case.to_dict() for case in cases], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def group_catalog(cases: list[Case], groups: list[TestGroup] | None = None) -> list[dict[str, Any]]:
    metadata = {group.id: group for group in groups or []}
    values: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        values.setdefault(case.group_id or group_id_for_name(case.group), []).append(case.to_dict())
    output = []
    for group_id, group_cases in values.items():
        group = metadata.get(group_id)
        output.append({"id": group_id, "name": group.name if group else group_cases[0]["group"], "kind": group.kind if group else "regular", "sourceType": group.source_type if group else "generated", "editable": group.editable if group else False, "cases": group_cases})
    return sorted(output, key=lambda item: (item["kind"] == "on-demand", item["name"], item["id"]))


def _component_contract(component: Component) -> str:
    value = json.dumps({"kind": component.kind, "releaseStatus": component.release_status, "metadata": component.metadata}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def catalog_diagnostics(components: list[Component], cases: list[Case], archived_counts: dict[str, int] | None = None, repo_root: Path | None = None) -> dict[str, Any]:
    component_ids = {item.id for item in components}
    covered = {case.component_id for case in cases if case.component_id}
    reviewed: dict[str, str] = {}
    if repo_root is not None:
        path = repo_root / "tests" / "ats" / "catalog" / "reviewed-inventory.json"
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            reviewed = value.get("components", {}) if isinstance(value, dict) else {}
    contracts = {item.id: _component_contract(item) for item in components}
    return {"newlyDiscovered": sorted(component_ids - reviewed.keys()), "uncovered": sorted(component_ids - covered), "staleReferences": sorted(case.id for case in cases if case.component_id and case.component_id not in component_ids), "changedContracts": sorted(component_id for component_id in component_ids & reviewed.keys() if reviewed[component_id] != contracts[component_id]), "disabledOrArchived": archived_counts or {"groups": 0, "cases": 0}, "currentContracts": contracts}


def migrate_base_catalog(repo_root: Path, *, apply: bool = False) -> dict[str, Any]:
    base_path = repo_root / "tests" / "ats" / "catalog" / "base.json"
    raw = json.loads(base_path.read_text(encoding="utf-8"))
    if raw.get("migrated") is True:
        return {"status": "already-migrated", "caseCount": len(raw.get("cases", [])), "groupCount": 0}
    cases = raw.get("cases", [])
    names = sorted({str(item["group"]) for item in cases})
    if not apply:
        return {"status": "ready", "checkOnly": True, "caseCount": len(cases), "groupCount": len(names)}
    store = CatalogStore(repo_root)
    if store.list_objects("groups") or store.list_objects("cases"):
        raise CatalogValidationError(["migration requires empty active YAML groups/cases directories"])
    documents: list[tuple[Path, dict[str, Any]]] = []
    for name in names:
        group_id = group_id_for_name(name)
        documents.append((store._path("groups", group_id), {"schemaVersion": 1, "id": group_id, "name": name, "kind": "regular", "enabled": True, "defaultSelected": False, "order": 500, "tags": [], "lifecycle": "enabled", "sourceType": "built-in"}))
    for item in cases:
        value = {"schemaVersion": 1, "id": item["id"], "name": item["name"], "groupId": group_id_for_name(item["group"]), "priority": item["priority"], "enabled": True, "required": bool(item.get("required", True)), "executor": item["executor"], "timeoutSeconds": int(item.get("timeoutSeconds", 300)), "requires": item.get("requires", []), "tags": item.get("tags", []), "description": item.get("description", ""), "lifecycle": "enabled", "sourceType": "built-in"}
        if item.get("command"):
            value["command"] = item["command"]
        documents.append((store._path("cases", item["id"]), value))
    for path, value in documents:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        temporary.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")
        os.replace(temporary, path)
    temporary_base = base_path.with_name(f".{base_path.name}.{os.getpid()}.tmp")
    temporary_base.write_text(json.dumps({**raw, "migrated": True}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary_base, base_path)
    return {"status": "migrated", "checkOnly": False, "caseCount": len(cases), "groupCount": len(names)}
