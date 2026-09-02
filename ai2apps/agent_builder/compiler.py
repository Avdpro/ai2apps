"""Strict P0 compiler from bounded natural-language Agent Source to local IR."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

COMPILER_VERSION = "ai2apps-site-agent-p1.1/1"
POLICY_VERSION = "ai2apps-web-action-policy-p1/1"
TERMINALS = frozenset({"done", "failed", "pause"})
OUTCOMES = (
    "success",
    "not_found",
    "retryable_error",
    "needs_user",
    "restricted",
    "failed",
)
OPERATIONS = frozenset(
    {
        "open",
        "page_access",
        "inspect",
        "extract_list",
        "ai.classify",
        "ai.extract",
        "ai.transform",
        "approval",
        "click",
        "delete",
        "input",
        "hover",
        "scroll",
        "complete",
    }
)


@dataclass(frozen=True, slots=True)
class CompileResult:
    ir: dict[str, Any]
    report: dict[str, Any]
    source_digest: str

    @property
    def valid(self) -> bool:
        return not self.report["errors"]


def canonical_digest(source: dict[str, Any]) -> str:
    payload = json.dumps(
        source, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _operation(step: dict[str, Any]) -> str | None:
    explicit = str(step.get("operation") or step.get("action") or "").strip().lower()
    if explicit in OPERATIONS:
        return explicit
    text = str(step.get("desc") or "").lower()
    if re.search(r"cookie|隐私|遮挡|弹窗|blocker|page.?access", text):
        return "page_access"
    if re.search(r"提取|extract|获取|收集", text) and re.search(
        r"文章|列表|链接|link|article|item|最新", text
    ):
        return "extract_list"
    if re.search(r"确认|审批|approve|confirm", text):
        return "approval"
    if re.search(r"删除|移除|delete|remove", text):
        return "delete"
    if re.search(r"点击|click|按下", text):
        return "click"
    if re.search(r"输入|填写|键入|type|fill", text):
        return "input"
    if re.search(r"悬停|hover|移到", text):
        return "hover"
    if re.search(r"滚动|scroll|翻到", text):
        return "scroll"
    if re.search(r"打开|访问|导航|open|navigate|go to", text):
        return "open"
    if re.search(r"读取|查看|检查|识别|read|inspect|find|找到", text):
        return "inspect"
    if re.search(r"完成|结束|返回结果|complete|done", text):
        return "complete"
    return None


def _parsed_transitions(description: str) -> dict[str, str]:
    transitions: dict[str, str] = {}
    patterns = {
        "success": r"(?:成功|success).*?(step[-_ ]?\d+|done|完成)",
        "not_found": r"(?:找不到|未找到|not found).*?(step[-_ ]?\d+|failed|失败)",
        "failed": r"(?:失败|错误|failed).*?(step[-_ ]?\d+|failed|失败)",
        "needs_user": r"(?:人工|用户|接管).*?(step[-_ ]?\d+|pause|暂停)",
    }
    for outcome, pattern in patterns.items():
        match = re.search(pattern, description, re.IGNORECASE)
        if not match:
            continue
        target = match.group(1).lower().replace("_", "-").replace(" ", "-")
        transitions[outcome] = {
            "完成": "done",
            "失败": "failed",
            "暂停": "pause",
        }.get(target, target)
    return transitions


def _effect(operation: str) -> str:
    if operation in {
        "inspect", "extract_list", "complete", "ai.classify", "ai.extract",
        "ai.transform", "approval",
    }:
        return "read"
    if operation == "delete":
        return "destructive"
    if operation in {"open", "page_access", "click", "input", "hover", "scroll"}:
        return "interact"
    return "restricted"


def _target_hint(step: dict[str, Any]) -> dict[str, Any]:
    target = step.get("target")
    if isinstance(target, dict):
        return dict(target)
    if isinstance(target, str) and target.strip():
        return {"intent": target.strip()}
    description = str(step.get("desc") or "")
    match = re.search(
        r"(?:找到并|找到|点击|悬停在|输入到|在)\s*(?:页面上的)?(.{1,60}?)(?:，|,|。|成功|如果|$)",
        description,
    )
    return {"intent": (match.group(1).strip() if match else description[:120])}


def _compile_single_source(source: dict[str, Any]) -> CompileResult:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(source, dict):
        raise ValueError("Agent Source must be a JSON object")
    agent_type = str(source.get("agent_type") or "web").strip().lower()
    if agent_type != "web":
        errors.append(
            {
                "path": "agent_type",
                "code": "builder_not_available",
                "message": f"The {agent_type} Builder is not installed in P1",
            }
        )

    inputs = source.get("inputs") or {"type": "object", "properties": {}}
    outputs = source.get("outputs") or {"type": "object", "properties": {}}
    if not isinstance(inputs, dict):
        errors.append({"path": "inputs", "code": "schema_not_object"})
        inputs = {"type": "object", "properties": {}}
    if not isinstance(outputs, dict):
        errors.append({"path": "outputs", "code": "schema_not_object"})
        outputs = {"type": "object", "properties": {}}
    for path, schema in (("inputs", inputs), ("outputs", outputs)):
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as error:
            errors.append(
                {"path": path, "code": "invalid_json_schema", "message": error.message}
            )

    capability_exports = source.get("capability_exports") or []
    if not isinstance(capability_exports, list):
        errors.append(
            {"path": "capability_exports", "code": "exports_not_array"}
        )
        capability_exports = []
    normalized_exports: list[dict[str, Any]] = []
    export_names: set[str] = set()
    for index, item in enumerate(capability_exports):
        if not isinstance(item, dict):
            errors.append(
                {"path": f"capability_exports.{index}", "code": "export_not_object"}
            )
            continue
        name = str(item.get("name") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{2,199}", name):
            errors.append(
                {"path": f"capability_exports.{index}.name", "code": "invalid_capability"}
            )
            continue
        if name in export_names:
            errors.append(
                {"path": f"capability_exports.{index}.name", "code": "duplicate_capability"}
            )
            continue
        export_names.add(name)
        normalized_exports.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
                "input_schema": dict(item.get("input_schema") or inputs),
                "output_schema": dict(item.get("output_schema") or outputs),
                "effects": sorted(
                    {str(value) for value in item.get("effects", ["read"])}
                ),
            }
        )
        for schema_key in ("input_schema", "output_schema"):
            try:
                Draft202012Validator.check_schema(
                    normalized_exports[-1][schema_key]
                )
            except Exception:
                errors.append(
                    {
                        "path": f"capability_exports.{index}.{schema_key}",
                        "code": "invalid_json_schema",
                    }
                )
    steps = source.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append({"path": "steps", "code": "steps_required"})
        steps = []
    names: list[str] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append({"path": f"steps.{index}", "code": "step_not_object"})
            continue
        name = str(step.get("name") or "").strip()
        if not name:
            errors.append({"path": f"steps.{index}.name", "code": "name_required"})
        elif name in names:
            errors.append({"path": f"steps.{index}.name", "code": "duplicate_name"})
        names.append(name)

    compiled_steps: list[dict[str, Any]] = []
    effects: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        name = str(step.get("name") or f"step-{index + 1}").strip()
        description = str(step.get("desc") or "").strip()
        operation = _operation(step)
        if operation is None:
            errors.append(
                {
                    "path": f"steps.{index}.desc",
                    "code": "operation_ambiguous",
                    "message": "Describe one supported browser operation",
                }
            )
            continue
        arguments = dict(step.get("arguments") or {})
        if operation == "open":
            url = str(arguments.get("url") or "").strip()
            if not url:
                match = re.search(r"https?://[^\s，。]+", description)
                url = "" if match is None else match.group(0)
                if url:
                    arguments["url"] = url
            parsed_url = urlparse(url) if url else None
            if (
                parsed_url is None
                or parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
            ):
                errors.append({
                    "path": f"steps.{index}.arguments.url",
                    "code": "open_url_required",
                })
        transitions = step.get("on")
        transitions = dict(transitions) if isinstance(transitions, dict) else {}
        transitions = {**_parsed_transitions(description), **transitions}
        if operation == "complete":
            transitions = {}
        elif "success" not in transitions:
            transitions["success"] = (
                str(steps[index + 1].get("name"))
                if index + 1 < len(steps) and isinstance(steps[index + 1], dict)
                else "done"
            )
        transitions.setdefault("failed", "failed")
        normalized_transitions: dict[str, str] = {}
        for outcome, target in transitions.items():
            outcome = str(outcome)
            target = str(target).strip()
            if outcome not in OUTCOMES:
                errors.append(
                    {
                        "path": f"steps.{index}.on.{outcome}",
                        "code": "invalid_outcome",
                    }
                )
                continue
            if target not in names and target not in TERMINALS:
                errors.append(
                    {
                        "path": f"steps.{index}.on.{outcome}",
                        "code": "unknown_target",
                        "target": target,
                    }
                )
            normalized_transitions[outcome] = target
        effect = _effect(operation)
        effects.add(effect)
        execution = step.get("execution")
        if isinstance(execution, dict):
            raw_mode = execution.get("mode")
        elif isinstance(execution, str):
            raw_mode = execution
        else:
            raw_mode = None
        mode = str(raw_mode or "adaptive")
        if mode not in {"compiled", "interpreted", "adaptive"}:
            errors.append(
                {"path": f"steps.{index}.execution.mode", "code": "invalid_mode"}
            )
            mode = "adaptive"
        compiled_steps.append(
            {
                "id": name,
                "source_index": index,
                "description": description,
                "operation": operation,
                "mode": mode,
                "effect": effect,
                "target": _target_hint(step),
                "arguments": arguments,
                **(
                    {"ai": dict(step["ai"])}
                    if operation.startswith("ai.")
                    and isinstance(step.get("ai"), dict)
                    else {}
                ),
                "interaction": {
                    "profile": str(
                        (
                            step.get("interaction", {}).get("profile")
                            if isinstance(step.get("interaction"), dict)
                            else step.get("interaction")
                            if isinstance(step.get("interaction"), str)
                            else None
                        )
                        or "natural"
                    ),
                    "ensure_visible": True,
                },
                "on": normalized_transitions,
            }
        )

        if operation.startswith("ai."):
            ai = step.get("ai")
            tier = str(ai.get("tier") or "") if isinstance(ai, dict) else ""
            instruction = str(ai.get("instruction") or "") if isinstance(ai, dict) else ""
            output_schema = ai.get("output_schema") if isinstance(ai, dict) else None
            if tier not in {"simple", "standard", "complex"}:
                errors.append({
                    "path": f"steps.{index}.ai.tier", "code": "invalid_ai_tier"
                })
            if not instruction.strip() or len(instruction) > 4000:
                errors.append({
                    "path": f"steps.{index}.ai.instruction",
                    "code": "invalid_ai_instruction",
                })
            if not isinstance(output_schema, dict):
                errors.append({
                    "path": f"steps.{index}.ai.output_schema",
                    "code": "missing_ai_output_schema",
                })
            else:
                try:
                    Draft202012Validator.check_schema(output_schema)
                except SchemaError as error:
                    errors.append({
                        "path": f"steps.{index}.ai.output_schema",
                        "code": "invalid_ai_output_schema",
                        "message": error.message,
                    })

    site_scope = source.get("site_scope") or []
    if not isinstance(site_scope, list):
        errors.append({"path": "site_scope", "code": "scope_not_array"})
        site_scope = []
    for index, scope in enumerate(site_scope):
        parsed = urlparse(str(scope).replace("/**", "/"))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append(
                {"path": f"site_scope.{index}", "code": "invalid_site_scope"}
            )
    for index, step in enumerate(compiled_steps):
        if step.get("operation") != "delete":
            continue
        guarded = any(
            candidate.get("operation") == "approval"
            and candidate.get("on", {}).get("success") == step.get("id")
            for candidate in compiled_steps
        )
        if not guarded:
            errors.append({
                "path": f"steps.{index}",
                "code": "destructive_step_requires_approval",
            })
    if "restricted" in effects:
        errors.append({"path": "steps", "code": "restricted_effect"})

    fixtures = source.get("fixtures") or []
    if not isinstance(fixtures, list):
        errors.append({"path": "fixtures", "code": "fixtures_not_array"})
        fixtures = []
    fixture_results: list[dict[str, Any]] = []
    for index, fixture in enumerate(fixtures):
        result = {"index": index, "name": f"fixture-{index + 1}", "valid": True}
        if not isinstance(fixture, dict):
            result.update(valid=False, error="fixture_not_object")
        else:
            result["name"] = str(fixture.get("name") or result["name"])
            try:
                Draft202012Validator(inputs).validate(fixture.get("input", {}))
                if "expected_output" in fixture:
                    Draft202012Validator(outputs).validate(
                        fixture.get("expected_output")
                    )
            except ValidationError as error:
                result.update(valid=False, error=error.message)
        fixture_results.append(result)
        if not result["valid"]:
            errors.append(
                {"path": f"fixtures.{index}", "code": "fixture_schema_mismatch"}
            )

    validators = source.get("validators") or []
    if not isinstance(validators, list):
        errors.append({"path": "validators", "code": "validators_not_array"})
        validators = []
    validator_results: list[dict[str, Any]] = []
    for index, validator in enumerate(validators):
        valid = isinstance(validator, dict) and str(validator.get("kind") or "") in {
            "json_schema",
            "required_fields",
            "min_items",
        }
        validator_results.append(
            {
                "index": index,
                "kind": validator.get("kind") if isinstance(validator, dict) else None,
                "valid": valid,
            }
        )
        if not valid:
            errors.append(
                {"path": f"validators.{index}", "code": "invalid_validator"}
            )

    digest = canonical_digest(source)
    ir = {
        "schema": "ai2apps.compiled-agent/v1",
        "agent_type": agent_type,
        "source_digest": digest,
        "compiler_version": COMPILER_VERSION,
        "policy_version": POLICY_VERSION,
        "name": str(source.get("name") or "Untitled Agent"),
        "site_scope": site_scope,
        "start": compiled_steps[0]["id"] if compiled_steps else None,
        "effects": sorted(effects),
        "inputs": inputs,
        "outputs": outputs,
        "capability_exports": normalized_exports,
        "validators": validators,
        "steps": compiled_steps,
    }
    report = {
        "status": "validated" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "step_count": len(compiled_steps),
        "effects": sorted(effects),
        "source_digest": digest,
        "compiler_version": COMPILER_VERSION,
        "policy_version": POLICY_VERSION,
        "agent_type": agent_type,
        "capability_exports": normalized_exports,
        "fixture_results": fixture_results,
        "validator_results": validator_results,
    }
    return CompileResult(ir=ir, report=report, source_digest=digest)


def compile_source(source: dict[str, Any]) -> CompileResult:
    """Compile legacy one-pipeline sources or P1.1 multi-capability Site Agents."""

    if not isinstance(source, dict):
        raise ValueError("Agent Source must be a JSON object")
    capabilities = source.get("capabilities")
    if capabilities is None:
        return _compile_single_source(source)
    digest = canonical_digest(source)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    compiled: list[dict[str, Any]] = []
    exports: list[dict[str, Any]] = []
    fixture_results: list[dict[str, Any]] = []
    validator_results: list[dict[str, Any]] = []
    if not isinstance(capabilities, list) or not capabilities:
        capabilities = []
        errors.append({"path": "capabilities", "code": "capabilities_required"})
    ids: set[str] = set()
    export_names: set[str] = set()
    for index, capability in enumerate(capabilities):
        prefix = f"capabilities.{index}"
        if not isinstance(capability, dict):
            errors.append({"path": prefix, "code": "capability_not_object"})
            continue
        if capability.get("enabled") is False:
            warnings.append(
                {"path": prefix, "code": "capability_disabled", "message": "Disabled capability was not compiled"}
            )
            continue
        capability_id = str(capability.get("id") or "").strip()
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,79}", capability_id):
            errors.append({"path": f"{prefix}.id", "code": "invalid_capability_id"})
            continue
        if capability_id in ids:
            errors.append({"path": f"{prefix}.id", "code": "duplicate_capability_id"})
            continue
        ids.add(capability_id)
        export_name = str(capability.get("name") or f"site.{capability_id}").strip()
        if export_name in export_names:
            errors.append({"path": f"{prefix}.name", "code": "duplicate_capability"})
            continue
        export_names.add(export_name)
        subsource = {
            "schema": "ai2apps.agent-source/v1",
            "agent_type": source.get("agent_type", "web"),
            "name": capability.get("title") or capability_id,
            "description": capability.get("description", ""),
            "site_scope": source.get("site_scope", []),
            "inputs": capability.get("inputs") or {"type": "object", "properties": {}},
            "outputs": capability.get("outputs") or {"type": "object", "properties": {}},
            "steps": capability.get("steps", []),
            "fixtures": capability.get("fixtures", []),
            "validators": capability.get("validators", []),
            "capability_exports": [
                {
                    "name": export_name,
                    "description": capability.get("description", ""),
                    "effects": capability.get("effects", ["read"]),
                }
            ],
        }
        result = _compile_single_source(subsource)
        errors.extend(
            {**item, "path": f"{prefix}.{item.get('path', '')}".rstrip(".")}
            for item in result.report["errors"]
        )
        warnings.extend(
            {**item, "path": f"{prefix}.{item.get('path', '')}".rstrip(".")}
            for item in result.report["warnings"]
        )
        fixture_results.extend(
            {**item, "capability_id": capability_id}
            for item in result.report.get("fixture_results", [])
        )
        validator_results.extend(
            {**item, "capability_id": capability_id}
            for item in result.report.get("validator_results", [])
        )
        capability_ir = {
            **result.ir,
            "id": capability_id,
            "name": export_name,
            "title": str(capability.get("title") or capability_id),
            "source_digest": digest,
        }
        compiled.append(capability_ir)
        export = dict(result.ir["capability_exports"][0])
        export["capability_id"] = capability_id
        exports.append(export)

    if not compiled and not errors:
        errors.append({"path": "capabilities", "code": "enabled_capability_required"})

    first = compiled[0] if compiled else {}
    ir = {
        **first,
        "schema": "ai2apps.compiled-site-agent/v1",
        "source_digest": digest,
        "compiler_version": COMPILER_VERSION,
        "name": str(source.get("name") or "Untitled Site Agent"),
        "site_key": str(source.get("site_key") or ""),
        "site_scope": list(source.get("site_scope") or []),
        "capabilities": compiled,
        "capability_exports": exports,
    }
    report = {
        "status": "validated" if not errors else "failed",
        "errors": errors,
        "warnings": warnings,
        "step_count": sum(len(item.get("steps", [])) for item in compiled),
        "capability_count": len(compiled),
        "effects": sorted(
            {effect for item in compiled for effect in item.get("effects", [])}
        ),
        "source_digest": digest,
        "compiler_version": COMPILER_VERSION,
        "policy_version": POLICY_VERSION,
        "agent_type": str(source.get("agent_type") or "web"),
        "capability_exports": exports,
        "fixture_results": fixture_results,
        "validator_results": validator_results,
    }
    return CompileResult(ir=ir, report=report, source_digest=digest)
