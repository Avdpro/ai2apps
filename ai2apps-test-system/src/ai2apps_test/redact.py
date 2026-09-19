from __future__ import annotations

import re

_PATTERNS = (
    re.compile(r"(?im)(authorization\s*[:=]\s*)[^\r\n]+"),
    re.compile(r"(?im)(cookie\s*[:=]\s*)[^\r\n]+"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(
        r'''(?i)((?:["']?(?:password|lease[_-]?token|access[_-]?token|refresh[_-]?token|token|api[_-]?key|credential|secret)["']?)\s*[:=]\s*["']?)[^"'\s,}\r\n]+'''
    ),
    re.compile(r"/Users/[^/\s]+"),
)


def redact_text(value: str) -> str:
    value = _PATTERNS[0].sub(r"\1[REDACTED]", value)
    value = _PATTERNS[1].sub(r"\1[REDACTED]", value)
    value = _PATTERNS[2].sub(r"\1[REDACTED]", value)
    value = _PATTERNS[3].sub(r"\1[REDACTED]", value)
    return _PATTERNS[4].sub("/Users/[USER]", value)
