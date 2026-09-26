from __future__ import annotations

import re
from typing import Any

from .model import PRIORITIES

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.-]{0,127}$")
ALLOWED_EXECUTORS = {"builtin", "codex-ui"}
LIFECYCLES = {"draft", "valid", "trial-passed", "enabled", "archived"}
PIPELINE_ACTIONS = {"start-helper", "restart-app", "restart-local", "quit-all-relaunch", "reset-data", "human-test", "include-pipeline"}
EXPECTED_STATUSES = {"passed", "failed", "blocked", "stop-when-failed", "stop-when-succeed"}
CASE_CONTENT_FIELDS = {"name", "description", "instructions", "expectations", "cleanup"}
SECRET_KEYS = {"password", "token", "cookie", "authorization", "credential", "leaseToken"}


class CatalogValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _strings(value: Any, field: str, errors: list[str]) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{field} must be a list of strings")


def _secret_scan(value: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            current = f"{path}.{key}" if path else str(key)
            if str(key).lower() in {item.lower() for item in SECRET_KEYS}:
                errors.append(f"secret-like field is forbidden: {current}")
            errors.extend(_secret_scan(item, current))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_secret_scan(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        if "authorization: bearer " in lowered or "cookie:" in lowered:
            errors.append(f"secret-like content is forbidden: {path}")
    return errors


def validate_group(value: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    group_id = value.get("id")
    if not isinstance(group_id, str) or not ID_PATTERN.fullmatch(group_id):
        errors.append("id must contain only lowercase letters, digits, dots, or hyphens")
    if not isinstance(value.get("name"), str) or not value.get("name", "").strip():
        errors.append("name is required")
    if value.get("kind", "regular") not in {"regular", "on-demand"}:
        errors.append("kind must be regular or on-demand")
    if value.get("kind") == "on-demand" and value.get("defaultSelected", False):
        errors.append("on-demand groups cannot be selected by default")
    if value.get("lifecycle", "draft") not in LIFECYCLES:
        errors.append("invalid lifecycle")
    if value.get("enabled", False) and value.get("lifecycle", "draft") not in {"trial-passed", "enabled"}:
        errors.append("draft or merely valid groups cannot be enabled")
    _strings(value.get("tags", []), "tags", errors)
    errors.extend(_secret_scan(value))
    return errors


def validate_case(
    value: dict[str, Any],
    groups: dict[str, dict[str, Any]],
    *,
    trusted_builtin: bool = False,
) -> list[str]:
    errors: list[str] = []
    case_id = value.get("id")
    if not isinstance(case_id, str) or not ID_PATTERN.fullmatch(case_id):
        errors.append("id must contain only lowercase letters, digits, dots, or hyphens")
    if not isinstance(value.get("name"), str) or not value.get("name", "").strip():
        errors.append("name is required")
    group_id = value.get("groupId")
    group = groups.get(group_id) if isinstance(group_id, str) else None
    if group is None:
        errors.append("groupId must reference an existing group")
    else:
        priority = value.get("priority")
        if group.get("kind", "regular") == "regular" and priority not in PRIORITIES:
            errors.append("regular cases require priority P0-P3")
        if group.get("kind") == "on-demand" and priority is not None:
            errors.append("on-demand cases must use priority: null")
    executor = value.get("executor")
    if executor not in ALLOWED_EXECUTORS and not (
        trusted_builtin and executor == "command"
    ):
        errors.append("user-authored executor must be builtin or codex-ui")
    timeout = value.get("timeoutSeconds", 300)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 5 <= timeout <= 3600:
        errors.append("timeoutSeconds must be between 5 and 3600")
    if value.get("command") and not trusted_builtin:
        errors.append("user-authored cases cannot define arbitrary commands")
    for field in ("requires", "tags", "instructions", "expectations", "cleanup", "fixtures"):
        _strings(value.get(field, []), field, errors)
    if executor == "codex-ui" and not value.get("instructions"):
        errors.append("codex-ui cases require structured instructions")
    if value.get("lifecycle", "draft") not in LIFECYCLES:
        errors.append("invalid lifecycle")
    if value.get("enabled", False) and value.get("lifecycle", "draft") not in {"trial-passed", "enabled"}:
        errors.append("a case must pass trial before it can be enabled")
    errors.extend(_secret_scan(value))
    return errors


def require_valid(errors: list[str]) -> None:
    if errors:
        raise CatalogValidationError(errors)


def validate_pipeline(
    value: dict[str, Any], case_ids: set[str] | None = None, *, allow_case_content: bool = False
) -> list[str]:
    errors: list[str] = []
    pipeline_id = value.get("id")
    if not isinstance(pipeline_id, str) or not ID_PATTERN.fullmatch(pipeline_id):
        errors.append("id must contain only lowercase letters, digits, dots, or hyphens")
    if not isinstance(value.get("name"), str) or not value.get("name", "").strip():
        errors.append("name is required")
    steps = value.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("pipeline requires at least one step")
        steps = []
    seen: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(f"steps[{index}] must be an object")
            continue
        step_id = step.get("id")
        if not isinstance(step_id, str) or not ID_PATTERN.fullmatch(step_id):
            errors.append(f"steps[{index}].id is invalid")
        elif step_id in seen:
            errors.append(f"duplicate pipeline step ID: {step_id}")
        else:
            seen.add(step_id)
        kind = step.get("type")
        if kind == 'action' and step.get('action') == 'include-pipeline':
            if not isinstance(step.get('pipelineId'), str) or not ID_PATTERN.fullmatch(step['pipelineId']):
                errors.append('include-pipeline requires a valid pipelineId')
        elif 'pipelineId' in step:
            errors.append('pipelineId requires include-pipeline')
        if 'executionMode' in step and (kind != 'case' or step['executionMode'] not in {'run', 'skip', 'manual'}):
            errors.append('executionMode requires a Case and run/skip/manual')
        if kind == 'action' and step.get('action') == 'human-test':
            instruction = step.get('humanInstructions')
            timeout = step.get('confirmTimeoutSeconds')
            if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 12000:
                errors.append('humanInstructions requires 1–12000 characters')
            if type(timeout) is not int or not 1 <= timeout <= 86400:
                errors.append('confirmTimeoutSeconds must be 1–86400')
        elif kind == 'case' and step.get('executionMode') == 'manual':
            if 'humanInstructions' in step:
                errors.append('manual Case instructions come from its shared Case')
            timeout = step.get('confirmTimeoutSeconds', 120)
            if type(timeout) is not int or not 1 <= timeout <= 86400:
                errors.append('confirmTimeoutSeconds must be 1–86400')
        elif 'humanInstructions' in step or 'confirmTimeoutSeconds' in step:
            errors.append('human settings are only allowed on human-test')
        if "enabled" in step and not isinstance(step["enabled"], bool):
            errors.append(f"steps[{index}].enabled must be boolean")
        if "loginMode" in step or "accountEmail" in step:
            if kind != "action" or step.get("action") != "start-helper":
                errors.append("login settings are only allowed on start-helper")
            if step.get("loginMode", "none") not in {"none", "auto", "selected"}:
                errors.append("invalid loginMode")
            if step.get("loginMode") == "selected":
                if step.get("accountEmail") not in {f"test{i}@ai2apps.com" for i in range(1, 11)}:
                    errors.append("selected login requires a test pool accountEmail")
            elif "accountEmail" in step:
                errors.append("accountEmail requires selected loginMode")
        if kind == "case":
            case_id = step.get("caseId")
            if not isinstance(case_id, str) or not ID_PATTERN.fullmatch(case_id):
                errors.append(f"steps[{index}].caseId is invalid")
            elif case_ids is not None and case_id not in case_ids:
                errors.append(f"steps[{index}] references a non-runnable Case: {case_id}")
            if step.get("expectedStatus", "passed") not in EXPECTED_STATUSES:
                errors.append(f"steps[{index}].expectedStatus is invalid")
            content = step.get("caseContent", {})
            if "caseContent" in step and not allow_case_content:
                errors.append("Pipeline steps cannot override shared Case content")
            if not isinstance(content, dict):
                errors.append(f"steps[{index}].caseContent must be an object")
            else:
                if set(content) - CASE_CONTENT_FIELDS:
                    errors.append(f"steps[{index}].caseContent cannot change structural fields")
                for field in ("name", "description"):
                    if field in content and not isinstance(content[field], str):
                        errors.append(f"caseContent.{field} must be text")
                if "name" in content and not str(content["name"]).strip():
                    errors.append("caseContent.name is required")
                for field in ("instructions", "expectations", "cleanup"):
                    if field in content:
                        _strings(content[field], f"caseContent.{field}", errors)
                        if content[field] is None:
                            errors.append(f"caseContent.{field} must be a list")
                if "instructions" in content and not content["instructions"]:
                    errors.append("caseContent.instructions requires at least one step")
        elif kind == "action":
            if "caseContent" in step:
                errors.append("actions cannot contain caseContent")
            if step.get("action") not in PIPELINE_ACTIONS:
                errors.append(f"steps[{index}].action is invalid")
        else:
            errors.append(f"steps[{index}].type must be case or action")
    errors.extend(_secret_scan(value))
    return errors
