"""Provider-confirmed overflow classification; unrelated failures never retry."""

import json
import re


def provider_overflow(status, body):
    if status not in {400, 413, 422}:
        return False
    try:
        value = json.loads(body)
    except (ValueError, TypeError):
        return False
    if not isinstance(value, dict):
        return False
    error = value.get("error")
    if isinstance(error, dict) and error.get("code") in {
        "context_length_exceeded",
        "context_window_exceeded",
    }:
        return True
    detail = value.get("detail")
    return (
        isinstance(detail, str)
        and re.fullmatch(
            r"Prompt too long: \d+ tokens exceeds max context window of \d+ tokens",
            detail,
        )
        is not None
    )
