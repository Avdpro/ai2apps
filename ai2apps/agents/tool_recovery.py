"""Host-independent policy for bounded, model-visible tool failures.

Inspired by DeepSeek Harness tools/agent-loop error-result semantics (MIT,
5badb15009ae1756c3afe0ae0cef1faafc290ccc). This is an independent implementation.
Recovery means requesting a new model decision, never replaying a tool invocation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ai2apps.capabilities.effects import has_mutating_effects as has_mutating_effects

PREFLIGHT_CODES = frozenset(
    {"parameter_contract_mismatch", "parameter_contract_required", "invalid_tool_arguments", "invalid_tool_input", "tool_not_available", "invalid_question",
     "provider_incompatible", "provider_unavailable", "provider_selection_required", "provider_binding_changed", "uncertain_execution", "invalid_app_interaction", "repeated_tool_error"}
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
    # Ordinary failures settle as model-visible results; Run step/time/token
    # budgets bound execution. A task-wide error counter is not a stop reason.
    if not enabled:
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
    if preflight and not outcome_uncertain and code in ('parameter_contract_required','parameter_contract_mismatch','invalid_app_interaction'):
        import json
        try:
            detail=json.loads(message)
            if detail.get('rejection_kind') == 'unsupported_interaction':
                result.update(rejection_kind='unsupported_interaction', submitted=False, side_effects=False)
                result['message']=detail.get('message','Unsupported interaction')[:2048]
            contract=detail.get('parameter_contract')
            if isinstance(contract,dict) and len(json.dumps(contract).encode())<=128*1024:
                result.update(parameter_contract=contract,validation_errors=detail.get('errors',[]),
                    submitted=False,side_effects=False,original_values_preserved=True)
                result['message']=detail.get('message','Parameter contract mismatch')[:2048]
        except (ValueError,TypeError):
            pass
    if outcome_uncertain:
        result["outcome_uncertain"] = True
        result["next_action"] = "Use an available read-only status tool for the original operation or its returned job reference. The operation may have completed or billed. Do not submit another effectful operation in this Run. If status cannot be confirmed, ask the user and explain the uncertainty."
    elif preflight:
        result["next_action"] = "No operation was submitted. Analyze the rejection, correct arguments, select a compatible enabled provider, or collect genuinely missing parameters. Request a new call only after correcting the cause."
        if code == "provider_selection_required":
            result["next_action"] = "Use an exact Provider ID from the candidates and preserve the original arguments. No operation was submitted."
        if code == "tool_not_available":
            result["submitted"] = False
            result["next_action"] = "Use the exact function name specified in the message or select an available tool from the current definitions."
    if code == "invalid_tool_input":
        result["recoverable_input_error"] = True  # legacy durable records/readers
    return result


def recovery_count(steps):
    return sum(model_visible(step.error) and (step.error or {}).get('code') != 'tool_declaration_required' for step in steps)
