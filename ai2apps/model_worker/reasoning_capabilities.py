# SPDX-License-Identifier: Apache-2.0
"""Shared reasoning intent, wire controls and signed Model Package contract."""

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
    if set(normalized) - {"schema", "mode", "format", "default_enabled", "effort_control"}:
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
    if "effort_control" in normalized:
        try:
            control = validate_reasoning_control(normalized["effort_control"])
        except ReasoningEffortError as exc:
            raise ReasoningCapabilitiesError(str(exc)) from exc
        if control is None:
            raise ReasoningCapabilitiesError("effort_control must be an object")
        if mode == "required" and (control.get("can_disable") or control["format"] == "none"
                                   or "none" in control.get("efforts", [])):
            raise ReasoningCapabilitiesError("required reasoning cannot advertise disabling")
        if mode == "none" and control["format"] != "none":
            raise ReasoningCapabilitiesError("non-reasoning models require format none")
        normalized["effort_control"] = control
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
    "ReasoningEffortError",
    "validate_reasoning_effort",
    "validate_reasoning_control",
    "adapt_reasoning_effort",
]


# Inference control protocol: callers express intent; transport declarations own wire syntax.
REASONING_EFFORTS = frozenset({'none','minimal','low','medium','high','xhigh','max','ultra'})


class ReasoningEffortError(ValueError):
    pass


def validate_reasoning_effort(value):
    if value is not None and (not isinstance(value,str) or value not in REASONING_EFFORTS):
        raise ReasoningEffortError('reasoning_effort must be none, minimal, low, medium, high, xhigh, max or ultra')
    return value


def validate_reasoning_control(control):
    if control is None:return None
    if not isinstance(control,dict) or set(control)-{'format','efforts','aliases','can_disable'}:
        raise ReasoningEffortError('Invalid reasoning control declaration')
    if not isinstance(control.get('format'),str) or control.get('format') not in {'openai','thinking','chat_template','responses','output_config','none'}:
        raise ReasoningEffortError('Unsupported reasoning control format')
    efforts=control.get('efforts')
    if efforts is not None and (not isinstance(efforts,list) or not efforts
        or any(not isinstance(v,str) or not v or len(v)>32 for v in efforts) or len(set(efforts))!=len(efforts)):
        raise ReasoningEffortError('Invalid declared reasoning efforts')
    aliases=control.get('aliases',{})
    if not isinstance(aliases,dict) or any(k not in REASONING_EFFORTS or not isinstance(v,str) or not v or len(v)>32
        or efforts is not None and v not in efforts for k,v in aliases.items()):
        raise ReasoningEffortError('Invalid reasoning effort aliases')
    if 'can_disable' in control and type(control['can_disable']) is not bool:
        raise ReasoningEffortError('can_disable must be boolean')
    return {**control,'aliases':dict(aliases)}


def adapt_reasoning_effort(payload,control=None):
    """Pure, name-independent wire adaptation. Omitted intent preserves old requests."""
    from copy import deepcopy
    result=deepcopy(dict(payload));requested=validate_reasoning_effort(result.get('reasoning_effort'))
    if requested is None:return result
    control=validate_reasoning_control(control)
    if control is None:return result  # Existing OpenAI-compatible transport contract.
    fmt=control['format']
    if fmt=='none':
        result.pop('reasoning_effort',None);return result
    effective=control.get('aliases',{}).get(requested,requested)
    disabled=requested=='none' and control.get('can_disable') is True
    if requested=='none' and fmt in {'thinking','chat_template','output_config'} and not disabled:
        raise ReasoningEffortError('Selected model does not declare support for disabling reasoning')
    if not disabled and control.get('efforts') is not None and effective not in control['efforts']:
        raise ReasoningEffortError('Requested reasoning effort is not supported by the selected model: '+requested)
    if fmt=='openai':result['reasoning_effort']=effective;return result
    result.pop('reasoning_effort',None)
    def assign(container,key,value):
        if key in container and container[key]!=value:raise ReasoningEffortError('Conflicting native and unified reasoning controls')
        container[key]=value
    if fmt=='thinking':
        thinking=result.setdefault('thinking',{})
        if not isinstance(thinking,dict):raise ReasoningEffortError('thinking must be an object')
        assign(thinking,'type','disabled' if disabled else 'enabled')
        if not disabled:result['reasoning_effort']=effective
    elif fmt=='chat_template':
        template=result.setdefault('chat_template_kwargs',{})
        if not isinstance(template,dict):raise ReasoningEffortError('chat_template_kwargs must be an object')
        assign(template,'enable_thinking',not disabled)
        if not disabled:assign(template,'reasoning_effort',effective)
    elif fmt=='responses':
        reasoning=result.setdefault('reasoning',{})
        if not isinstance(reasoning,dict):raise ReasoningEffortError('reasoning must be an object')
        assign(reasoning,'effort','none' if disabled else effective)
    elif fmt=='output_config':
        thinking=result.setdefault('thinking',{})
        if not isinstance(thinking,dict):raise ReasoningEffortError('thinking must be an object')
        assign(thinking,'type','disabled' if disabled else 'adaptive')
        if not disabled:
            options=result.setdefault('output_config',{})
            if not isinstance(options,dict):raise ReasoningEffortError('output_config must be an object')
            assign(options,'effort',effective)
    return result
