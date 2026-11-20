"""Detect repeated short Tool cycles before dispatching another iteration."""

from __future__ import annotations

import hashlib
import json


def _key(name, arguments):
    encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode()
    return name, hashlib.sha256(encoded).digest()


def repeats_cycle(steps, name, arguments, *, repetitions=3, max_period=4):
    """Require full repeated cycles and the next call to match their beginning.

    A different argument (including a result-page offset) or output is progress.
    Only the bounded recent tail is inspected; outputs remain in RunSteps.
    """
    recent = [
        (_key(s.tool_name, s.input), _key("output", s.output))
        for s in steps[-repetitions * max_period :]
    ]
    candidate = _key(name, arguments)
    for period in range(2, max_period + 1):
        if len(recent) < repetitions * period:
            continue
        pattern = recent[-period:]
        if (
            candidate == pattern[0][0]
            and recent[-period * repetitions :] == pattern * repetitions
        ):
            return True
    return False


def repeated_failure(steps, name, arguments):
    """Suppress an unchanged rejected call, including fresh transport request IDs.

    Only failures explicitly marked as pre-dispatch are eligible. Execution
    errors may be transient or uncertain and keep their existing policy.
    """
    def canonical(value):
        if not isinstance(value, dict):
            return value
        return {k: v for k, v in value.items() if k not in ('request_id',)}
    candidate = _key(name, canonical(arguments))
    for step in reversed(steps):
        error = step.error or {}
        if step.kind != 'tool' or step.status.value != 'failed':
            continue
        if error.get('phase') != 'prepare' or error.get('outcome_uncertain'):
            continue
        if error.get('code') not in {
            'invalid_app_interaction', 'invalid_tool_arguments',
            'parameter_contract_mismatch', 'invalid_tool_input', 'invalid_question',
        }:
            continue
        if error.get('rejection_kind') == 'unsupported_interaction':
            # A missing interaction route cannot be fixed by changing its
            # business values. Only the capability/provider selects the route.
            keys = ('capability', 'provider')
            if step.tool_name == name and all(step.input.get(k) == arguments.get(k) for k in keys):
                return error
        if _key(step.tool_name, canonical(step.input)) == candidate:
            return error
    return None
