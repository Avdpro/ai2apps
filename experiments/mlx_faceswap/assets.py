"""Resolve development ONNX files or parser-free oMLX model bundles."""

from __future__ import annotations

from pathlib import Path


def resolve_model(
    root: str | Path,
    filename: str,
    *,
    aliases: tuple[str, ...] = (),
    optional: bool = False,
) -> Path | None:
    """Prefer ``<stem>.omlx/`` and fall back to the original ONNX file.

    Raw ONNX is useful in the trusted conversion and parity environment. A
    production Package is expected to contain only the parser-free directory.
    """

    root = Path(root)
    expected: list[Path] = []
    for name in (filename, *aliases):
        onnx_path = root / name
        bundle_path = root / f"{onnx_path.stem}.omlx"
        expected.extend((bundle_path, onnx_path))
        for candidate in (bundle_path, onnx_path):
            complete_bundle = candidate.is_dir() and all(
                (candidate / child).is_file()
                for child in ("graph.json", "weights.safetensors")
            )
            if complete_bundle or candidate.is_file():
                return candidate
    if optional:
        return None
    raise FileNotFoundError(
        "missing model: expected one of " + ", ".join(str(path) for path in expected)
    )
