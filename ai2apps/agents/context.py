"""Deterministic request-size admission without altering the current tool trace."""

from __future__ import annotations

import hashlib
import json


class ContextBudgetError(ValueError):
    pass


def bound_request(
    request: dict, *, base_count: int, max_bytes: int, preserve_history: bool = False
) -> tuple[dict, dict]:
    """Drop complete old user turns; preserve systems, current input and Run steps.

    This is a serialized UTF-8 byte guard, not a tokenizer or an image-token
    estimate. Original Messages and RunSteps remain the authoritative archive.
    preserve_history forbids the legacy turn-dropping fallback when checkpoint
    user evidence is protected; oversized requests then fail without losing it.
    """

    def encode(value):
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()

    original = encode(request)
    messages = list(request["messages"])
    users = [i for i in range(base_count) if messages[i].get("role") == "user"]
    # Only completed historical user turns can be removed. The last user and
    # all following base messages, plus the whole current Run, are protected.
    boundaries = [] if preserve_history else users[1:]
    removed = 0
    bounded = dict(request)
    payload = original
    for cutoff in boundaries:
        if len(payload) <= max_bytes:
            break
        retained = [
            m
            for i, m in enumerate(messages)
            if i >= cutoff or m.get("role") == "system"
        ]
        removed = len(messages) - len(retained)
        notice = {
            "role": "system",
            "content": (
                f"{removed} older context messages were omitted by the request byte budget. "
                "Their contents are not available in this request; do not infer missing facts."
            ),
        }
        bounded["messages"] = [notice, *retained]
        payload = encode(bounded)
    if len(payload) > max_bytes:
        raise ContextBudgetError(
            f"Required Agent context exceeds the request byte budget ({len(payload)}/{max_bytes}); "
            "current input, system instructions and active Tool history were preserved."
        )
    return bounded, {
        "policy": "protected-history-byte-budget/v2" if preserve_history else "whole-turn-byte-budget/v1",
        "max_bytes": max_bytes,
        "original_bytes": len(original),
        "request_bytes": len(payload),
        "omitted_messages": removed,
        "request_sha256": hashlib.sha256(payload).hexdigest(),
    }
