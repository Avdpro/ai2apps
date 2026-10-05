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
    {"invalid_tool_arguments", "tool_not_available", "invalid_question"}
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
) -> bool:
    if not enabled or prior_errors >= MAX_RECOVERIES:
        return False
    if preflight:
        return code in PREFLIGHT_CODES
    return not tuple(effects) and code in READ_ONLY_CODES


def error_result(
    code: str, message: str, *, retryable: bool = False, preflight: bool = False
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
    if code == "invalid_tool_input":
        result["recoverable_input_error"] = True  # legacy durable records/readers
    return result
