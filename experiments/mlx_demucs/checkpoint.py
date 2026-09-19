"""Inspection/export helpers for the PyTorch-to-MLX checkpoint boundary."""

from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path
from typing import Any

import numpy as np


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_torch_checkpoint(path: str | Path) -> dict[str, Any]:
    """Inspect a trusted official checkpoint.

    Demucs ``.th`` files are Python pickle containers. Never pass an
    untrusted or user-uploaded file to this offline conversion helper.
    """
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("PyTorch is required only for offline checkpoint conversion") from error
    sys.modules.setdefault("torchaudio", types.ModuleType("torchaudio"))
    package = torch.load(Path(path), map_location="cpu", weights_only=False)
    if not isinstance(package, dict) or not isinstance(package.get("state"), dict):
        raise ValueError("Unsupported Demucs checkpoint package")
    state = package["state"]
    parameters = sum(int(value.numel()) for value in state.values())
    tensor_bytes = sum(int(value.numel() * value.element_size()) for value in state.values())
    kwargs = dict(package.get("kwargs") or {})
    segment = kwargs.get("segment")
    return {
        "architecture": getattr(package.get("klass"), "__name__", None),
        "sources": list(kwargs.get("sources") or []),
        "sample_rate": int(kwargs["samplerate"]) if kwargs.get("samplerate") else None,
        "audio_channels": int(kwargs["audio_channels"]) if kwargs.get("audio_channels") else None,
        "segment_seconds": float(segment) if segment is not None else None,
        "tensor_count": len(state),
        "parameter_count": parameters,
        "tensor_bytes": tensor_bytes,
    }


def export_raw_npz(checkpoint: str | Path, output: str | Path) -> dict[str, Any]:
    """Export a trusted official checkpoint in raw PyTorch tensor layout."""
    import torch

    sys.modules.setdefault("torchaudio", types.ModuleType("torchaudio"))
    package = torch.load(Path(checkpoint), map_location="cpu", weights_only=False)
    state = package.get("state") if isinstance(package, dict) else None
    if not isinstance(state, dict):
        raise ValueError("Unsupported Demucs checkpoint package")
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    arrays = {name: value.detach().cpu().numpy() for name, value in state.items()}
    np.savez(destination, **arrays)
    checkpoint_path = Path(checkpoint)
    manifest = inspect_torch_checkpoint(checkpoint_path)
    manifest.update(
        {
            "layout": "pytorch_raw",
            "source_checkpoint_sha256": _sha256(checkpoint_path),
            "weights": destination.name,
            "weights_sha256": _sha256(destination),
        }
    )
    destination.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
