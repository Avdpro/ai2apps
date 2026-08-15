"""Deterministic risk classification and user-facing Tool action previews."""

from __future__ import annotations

from typing import Any

_SENSITIVE_FRAGMENTS = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "credential", "private_key",
)
_RESOURCE_KEYS = (
    "path", "url", "target", "selector", "name", "id", "destination",
    "repository", "branch", "recipient", "channel",
)


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(fragment in normalized for fragment in _SENSITIVE_FRAGMENTS)


def sanitize_value(value: Any, *, key: str = "") -> Any:
    """Produce a bounded value safe for approval UI, events, and audit prompts."""

    if key and is_sensitive_key(key):
        return "[secret]"
    if isinstance(value, dict):
        return {
            str(k): sanitize_value(v, key=str(k))
            for k, v in list(value.items())[:40]
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_value(item) for item in list(value)[:40]]
    if isinstance(value, str):
        if value.startswith("secret://"):
            return value
        return value if len(value) <= 240 else value[:237] + "..."
    return value


def operation_class(effects: tuple[str, ...]) -> str:
    values = {value.lower() for value in effects}
    if values & {"destructive", "delete", "purchase", "payment"}:
        return "destructive"
    if values & {"external", "network", "export", "upload", "send", "publish"}:
        return "external"
    if values & {
        "write", "write-host", "execute", "process", "clipboard",
        "host-control", "privileged", "credential",
    }:
        return "write"
    return "read"


def risk_level(effects: tuple[str, ...]) -> str:
    category = operation_class(effects)
    values = {value.lower() for value in effects}
    if category == "destructive" or values & {"privileged", "credential"}:
        return "critical"
    if values & {"network", "send", "publish", "execute", "process", "host-control"}:
        return "high"
    if category in {"write", "external"}:
        return "medium"
    return "low"


def resource_selector(arguments: dict[str, Any]) -> dict[str, Any]:
    """Bind reusable consent to the concrete resources shown to the user."""

    selected = {
        key: sanitize_value(arguments[key], key=key)
        for key in _RESOURCE_KEYS
        if key in arguments and not is_sensitive_key(key)
    }
    return {} if not selected else {"arguments": selected}


def action_preview(
    tool_name: str,
    effects: tuple[str, ...],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    safe_arguments = sanitize_value(arguments)
    resources = [
        f"{key}={safe_arguments[key]}"
        for key in _RESOURCE_KEYS
        if key in safe_arguments
    ][:3]
    summary = tool_name + (f" ({', '.join(resources)})" if resources else "")
    category = operation_class(effects)
    return {
        "tool_name": tool_name,
        "operation_class": category,
        "risk_level": risk_level(effects),
        "reversible": category not in {"destructive", "external"},
        "summary": summary,
        "arguments": safe_arguments,
        "resource_selector": resource_selector(arguments),
    }
