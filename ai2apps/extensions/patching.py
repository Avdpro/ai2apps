"""Semantic Patch composition and three-way rebase precondition checks."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .models import ExtensionError, LocalPatchRecord, PatchStatus, RebasePolicy


def canonical_digest(value: Any) -> str:
    content = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _parent(root: dict, target: str, *, create=False):
    parts = target.split(".") if target else []
    if not parts:
        return None, None
    current: Any = root
    for part in parts[:-1]:
        if not isinstance(current, dict):
            raise ExtensionError(
                "patch_target_kind_changed", f"Patch target changed kind: {target}"
            )
        if part not in current:
            if not create:
                raise ExtensionError(
                    "patch_target_missing", f"Patch target missing: {target}"
                )
            current[part] = {}
        current = current[part]
    return current, parts[-1]


def target_value(root: dict, target: str):
    parent, key = _parent(root, target)
    if parent is None or not isinstance(parent, dict) or key not in parent:
        raise ExtensionError("patch_target_missing", f"Patch target missing: {target}")
    return parent[key]


def apply_operation(root: dict, operation: dict) -> None:
    kind = operation.get("op")
    target = operation.get("target")
    if kind not in {"merge", "replace", "extend", "remove", "add"} or not isinstance(
        target, str
    ):
        raise ExtensionError("invalid_patch_operation", "Patch operation is invalid")
    parent, key = _parent(root, target, create=kind == "add")
    if not isinstance(parent, dict):
        raise ExtensionError(
            "patch_target_kind_changed", f"Patch target is not an object: {target}"
        )
    if kind == "remove":
        if key not in parent:
            raise ExtensionError(
                "patch_target_missing", f"Patch target missing: {target}"
            )
        parent.pop(key)
        return
    value = copy.deepcopy(operation.get("value"))
    if kind in {"replace", "add"}:
        if kind == "replace" and key not in parent:
            raise ExtensionError(
                "patch_target_missing", f"Patch target missing: {target}"
            )
        parent[key] = value
        return
    current = parent.get(key)
    if kind == "merge":
        if not isinstance(current, dict) or not isinstance(value, dict):
            raise ExtensionError(
                "patch_target_kind_changed", f"Merge target changed kind: {target}"
            )
        current.update(value)
    elif kind == "extend":
        if not isinstance(current, list) or not isinstance(value, list):
            raise ExtensionError(
                "patch_target_kind_changed", f"Extend target changed kind: {target}"
            )
        current.extend(value)


def compose(
    upstream: dict, patches: tuple[LocalPatchRecord, ...], upstream_digest: str
):
    result = copy.deepcopy(upstream)
    resources = {}
    conflicts = []
    for patch in patches:
        for operation in patch.operations:
            target = str(operation.get("target", ""))
            try:
                current = (
                    target_value(result, target)
                    if operation.get("op") != "add"
                    else None
                )
                expected_kind = operation.get("expected_kind")
                expected_digest = operation.get("expected_digest")
                kind_name = (
                    "object"
                    if isinstance(current, dict)
                    else "array"
                    if isinstance(current, list)
                    else type(current).__name__
                )
                mismatch = (expected_kind and expected_kind != kind_name) or (
                    expected_digest and canonical_digest(current) != expected_digest
                )
                if mismatch and patch.status is not PatchStatus.REBASED:
                    if (
                        patch.base_digest != upstream_digest
                        and patch.rebase_policy is RebasePolicy.DROP_IF_SATISFIED
                        and current == operation.get("value")
                    ):
                        continue
                    raise ExtensionError(
                        "patch_precondition_changed", "Upstream semantic target changed"
                    )
                apply_operation(result, operation)
            except ExtensionError as error:
                conflicts.append(
                    {
                        "patch_id": patch.id,
                        "target": target,
                        "code": error.code,
                        "message": str(error),
                        "policy": patch.rebase_policy.value,
                    }
                )
                break
        resources.update(patch.resources)
    return result, resources, conflicts
