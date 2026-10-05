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
