"""Normalization and deterministic validation for provisional tool calls."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .types import FusionToolCall


def normalize_tool_calls(raw_calls: Any) -> tuple[FusionToolCall, ...]:
    if not raw_calls:
        return ()
    normalized: list[FusionToolCall] = []
    for raw in raw_calls:
        if isinstance(raw, Mapping):
            function = raw.get("function")
            function = function if isinstance(function, Mapping) else raw
            call_id = raw.get("id") or raw.get("call_id")
            name = function.get("name")
            arguments = function.get("arguments", {})
        else:
            function = getattr(raw, "function", raw)
            call_id = getattr(raw, "id", None) or getattr(raw, "call_id", None)
            name = getattr(function, "name", None)
            arguments = getattr(function, "arguments", {})
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
        normalized.append(
            FusionToolCall(
                id=str(call_id or f"call_{uuid.uuid4().hex[:24]}"),
                name=str(name or ""),
                arguments=arguments,
            )
        )
    return tuple(normalized)


def validate_tool_calls(
    calls: Sequence[FusionToolCall],
    tools: Sequence[Mapping[str, Any]],
    tool_choice: str | Mapping[str, Any] | None,
    *,
    max_calls: int,
) -> tuple[str, ...]:
    errors: list[str] = []
    definitions: dict[str, Mapping[str, Any]] = {}
    for tool in tools:
        function = tool.get("function")
        if isinstance(function, Mapping) and function.get("name"):
            definitions[str(function["name"])] = function

    if len(calls) > max_calls:
        errors.append(f"tool call count exceeds limit {max_calls}")
    ids = [call.id for call in calls]
    if len(ids) != len(set(ids)):
        errors.append("tool call ids must be unique")

    required_name = _required_tool_name(tool_choice)
    choice = (
        str(tool_choice or "auto").lower()
        if not isinstance(tool_choice, Mapping)
        else ""
    )
    if choice == "none" and calls:
        errors.append("tool_choice=none forbids tool calls")
    if (choice == "required" or required_name) and not calls:
        errors.append("tool_choice requires a tool call")

    for index, call in enumerate(calls):
        prefix = f"tool_calls[{index}]"
        definition = definitions.get(call.name)
        if definition is None:
            errors.append(f"{prefix}: unknown tool {call.name!r}")
            continue
        if required_name and call.name != required_name:
            errors.append(f"{prefix}: tool_choice requires {required_name!r}")
        try:
            arguments = json.loads(call.arguments)
        except json.JSONDecodeError as exc:
            errors.append(f"{prefix}: arguments are not valid JSON: {exc.msg}")
            continue
        if not isinstance(arguments, dict):
            errors.append(f"{prefix}: arguments must be a JSON object")
            continue
        schema = definition.get("parameters") or {"type": "object"}
        if not isinstance(schema, Mapping):
            errors.append(f"{prefix}: tool schema is not an object")
            continue
        try:
            validator = Draft202012Validator(dict(schema))
            schema_errors = sorted(
                validator.iter_errors(arguments), key=lambda error: list(error.path)
            )
        except SchemaError as exc:
            errors.append(f"{prefix}: invalid tool schema: {exc.message}")
            continue
        for error in schema_errors:
            location = ".".join(str(item) for item in error.path)
            suffix = f" at {location}" if location else ""
            errors.append(f"{prefix}: {error.message}{suffix}")
    return tuple(errors)


def _required_tool_name(tool_choice: str | Mapping[str, Any] | None) -> str | None:
    if not isinstance(tool_choice, Mapping):
        return None
    function = tool_choice.get("function")
    if isinstance(function, Mapping) and function.get("name"):
        return str(function["name"])
    return None
