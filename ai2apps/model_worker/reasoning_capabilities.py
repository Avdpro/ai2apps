# SPDX-License-Identifier: Apache-2.0
"""Signed reasoning-mode contract for conversational Model Packages."""

from __future__ import annotations

import json
from typing import Any

REASONING_CAPABILITIES_SCHEMA = "ai2apps.reasoning/v1"
REASONING_MODES = frozenset({"required", "optional", "none"})
REASONING_FORMATS = frozenset({"think_tags"})


class ReasoningCapabilitiesError(ValueError):
    pass


def validate_reasoning_capabilities(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ReasoningCapabilitiesError("reasoning must be an object")
    try:
        normalized = json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise ReasoningCapabilitiesError("reasoning must contain JSON values") from exc
    if normalized.get("schema") != REASONING_CAPABILITIES_SCHEMA:
        raise ReasoningCapabilitiesError(
            f"reasoning.schema must be {REASONING_CAPABILITIES_SCHEMA!r}"
        )
    if set(normalized) - {"schema", "mode", "format", "default_enabled"}:
        raise ReasoningCapabilitiesError("reasoning contains unsupported fields")
    mode = normalized.get("mode")
    if mode not in REASONING_MODES:
        raise ReasoningCapabilitiesError(
            "reasoning.mode must be 'required', 'optional', or 'none'"
        )
    output_format = normalized.get("format", "think_tags")
    if output_format not in REASONING_FORMATS:
        raise ReasoningCapabilitiesError("reasoning.format must be 'think_tags'")
    default_enabled = normalized.get("default_enabled")
    if default_enabled is not None and not isinstance(default_enabled, bool):
        raise ReasoningCapabilitiesError("reasoning.default_enabled must be boolean")
    if mode == "required" and default_enabled is False:
        raise ReasoningCapabilitiesError(
            "required reasoning cannot declare default_enabled: false"
        )
    if mode == "none" and default_enabled is True:
        raise ReasoningCapabilitiesError(
            "non-reasoning models cannot declare default_enabled: true"
        )
    normalized["format"] = output_format
    normalized["default_enabled"] = (
        mode == "required"
        if default_enabled is None
        else default_enabled
    )
    return normalized


__all__ = [
    "REASONING_CAPABILITIES_SCHEMA",
    "ReasoningCapabilitiesError",
    "validate_reasoning_capabilities",
]
