"""Seed-VC v2 BigVGAN loader for offline-converted MLX weights."""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx


def load_bigvgan(path: str | Path):
    from mlx_audio.codec.models.bigvgan.bigvgan import BigVGAN, BigVGANConfig

    root = Path(path)
    values = json.loads((root / "config.json").read_text())
    configuration = BigVGANConfig(
        **{name: values[name] for name in BigVGANConfig.__annotations__}
    )
    model = BigVGAN(configuration)
    weights = mx.load(str(root / "model.safetensors"), format="safetensors")
    model.load_weights(list(weights.items()), strict=True)
    model.eval()
    mx.eval(model.parameters())
    return model
