"""Shared payload policy for isolated Model Worker Packages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import PurePosixPath
from typing import Any

MODEL_WORKER_PROTOCOL = "ai2apps-model-worker/v1"

_NATIVE_SUFFIXES = frozenset(
    {
        ".a",
        ".bundle",
        ".c",
        ".cc",
        ".cpp",
        ".cu",
        ".cxx",
        ".dll",
        ".dylib",
        ".exe",
        ".h",
        ".hpp",
        ".m",
        ".metal",
        ".metallib",
        ".mm",
        ".node",
        ".o",
        ".rs",
        ".so",
        ".swift",
        ".wasm",
    }
)
_NATIVE_MAGICS = frozenset(
    {
        b"\x7fELF",
        b"\xfe\xed\xfa\xce",
        b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe",
        b"\xcf\xfa\xed\xfe",
        b"\xca\xfe\xba\xbe",
        b"\xca\xfe\xba\xbf",
        b"\xbe\xba\xfe\xca",
        b"\xbf\xba\xfe\xca",
    }
)


def is_model_worker_service(value: Any) -> bool:
    runtime = value.get("runtime") if isinstance(value, dict) else None
    return isinstance(runtime, dict) and runtime.get("protocol") == MODEL_WORKER_PROTOCOL


def native_payload_paths(entries: Iterable[tuple[str, bytes]]) -> tuple[str, ...]:
    """Return native-code payload paths by extension, bundle path, or magic."""

    result: set[str] = set()
    for path, header in entries:
        pure = PurePosixPath(path)
        lower_parts = tuple(part.lower() for part in pure.parts)
        suffix = pure.suffix.lower()
        magic = header[:4]
        if (
            suffix in _NATIVE_SUFFIXES
            or any(part.endswith(".framework") for part in lower_parts)
            or magic in _NATIVE_MAGICS
            or magic[:2] == b"MZ"
        ):
            result.add(path)
    return tuple(sorted(result))


__all__ = [
    "MODEL_WORKER_PROTOCOL",
    "is_model_worker_service",
    "native_payload_paths",
]
