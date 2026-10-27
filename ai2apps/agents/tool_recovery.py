"""Host-independent policy for bounded, model-visible tool failures.

Inspired by DeepSeek Harness tools/agent-loop error-result semantics (MIT,
5badb15009ae1756c3afe0ae0cef1faafc290ccc). This is an independent implementation.
Recovery means requesting a new model decision, never replaying a tool invocation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

MAX_RECOVERIES = 3
PREFLIGHT_CODES = frozenset(
    {"invalid_tool_arguments", "tool_not_available", "invalid_question",
     "provider_incompatible", "provider_unavailable", "uncertain_execution", "invalid_app_interaction"}
)
READ_ONLY_CODES = frozenset(
    {
        "invalid_tool_input",
        "tool_timeout",
        "provider_error",
        "invalid_tool_output",
        "service_unavailable",
        "provider_unavailable",
        "tool_disabled",
        "tool_not_found",
    }
)


def has_mutating_effects(effects: Iterable[str]) -> bool:
    """Network transport plus an explicit external_read is a read-only operation.

    Bare network, billing, writes and unknown effect declarations remain
    conservative: a transport error can hide their completion.
    """
    values=set(effects)
    if values <= {'read'}:
        return False
    if 'external_read' in values and values <= {'read','external_read','network'}:
        return False
    return bool(values)


def model_visible(error: Mapping[str, Any] | None) -> bool:
    return bool(
        error
        and (
            error.get("model_visible_error") is True
            or error.get("recoverable_input_error") is True
        )
    )


def recoverable(
    code: str,
    *,
    effects: Iterable[str],
    prior_errors: int,
    enabled: bool,
    preflight: bool = False,
    diagnose_effectful: bool = False,
) -> bool:
    if enabled and preflight and code == 'tool_declaration_required':
        return True  # preparation is bounded by Run steps, not the failure allowance
    if not enabled or prior_errors >= MAX_RECOVERIES:
        return False
    if preflight:
        return code in PREFLIGHT_CODES
    return (not tuple(effects) or diagnose_effectful) and code in READ_ONLY_CODES


def error_result(
    code: str, message: str, *, retryable: bool = False, preflight: bool = False, outcome_uncertain: bool = False
) -> dict[str, Any]:
    # Gateway owns redaction. Bound model context without serializing exception
    # details, arguments, stack traces or injected credentials.
    result = {
        "code": code,
        "message": message[:2048],
        "retryable": retryable,
        "model_visible_error": True,
        "is_error": True,
        "phase": "prepare"
        if preflight
        or code
        in {
            "invalid_tool_input",
            "service_unavailable",
            "provider_unavailable",
            "tool_disabled",
            "tool_not_found",
        }
        else "execute",
        "next_action": "Correct the call or choose another approach. Do not assume success.",
    }
    if outcome_uncertain:
        result["outcome_uncertain"] = True
        result["next_action"] = "Analyze the failure and use read-only status/recovery tools if available. The operation may have completed or billed. Do not submit another effectful operation in this Run. If status cannot be confirmed, ask the user and explain the uncertainty."
    elif preflight:
        result["next_action"] = "No operation was submitted. Analyze the rejection, correct arguments, select a compatible enabled provider, or collect genuinely missing parameters. Request a new call only after correcting the cause."
    if code == "invalid_tool_input":
        result["recoverable_input_error"] = True  # legacy durable records/readers
    return result


def recovery_count(steps):
    return sum(model_visible(step.error) and (step.error or {}).get('code') != 'tool_declaration_required' for step in steps)
