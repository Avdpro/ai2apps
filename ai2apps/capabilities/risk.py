"""Deterministic risk classification and user-facing Tool action previews."""

from __future__ import annotations

from typing import Any

from .effects import effect_profile

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
    order = ('read', 'write', 'external', 'destructive', 'unknown')
    return max((effect_profile(value).operation for value in effects),
               key=order.index, default='read')


def risk_level(effects: tuple[str, ...]) -> str:
    order = ('low', 'medium', 'high', 'critical', 'unknown')
    return max((effect_profile(value).risk for value in effects),
               key=order.index, default='low')


def resource_selector(arguments: dict[str, Any]) -> dict[str, Any]:
    """Bind reusable consent to the concrete resources shown to the user."""

    selected = {
        key: sanitize_value(arguments[key], key=key)
        for key in _RESOURCE_KEYS
        if key in arguments and not is_sensitive_key(key)
    }
    return {} if not selected else {"arguments": selected}


def approval_countdown_seconds(effects: tuple[str, ...]) -> int | None:
    """Only declared routine reads / local artifacts may use timed once consent.

    Unknown effects and effects requiring explicit human confirmation fail closed.
    Network alone is not a read declaration.
    """
    values = set(effects)
    if 'network' in values:
        if 'external_read' not in values or not values <= {'read', 'external_read', 'network'}:
            return None
        values.remove('network')
    return 60 if values and all(effect_profile(value).countdown for value in values) else None


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
        "approval_countdown_seconds": approval_countdown_seconds(effects),
        "operation_class": category,
        "risk_level": risk_level(effects),
        "reversible": category in {"read", "write"} and not any(effect_profile(value).confirm_once for value in effects),
        "summary": summary,
        "arguments": safe_arguments,
        "resource_selector": resource_selector(arguments),
    }
