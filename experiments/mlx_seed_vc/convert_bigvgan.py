"""Offline conversion of NVIDIA BigVGAN v2 to MLX safetensors."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlx.core as mx
import torch
from mlx.utils import tree_flatten


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    from mlx_audio.codec.models.bigvgan.bigvgan import BigVGAN, BigVGANConfig

    values = json.loads((args.source / "config.json").read_text())
    configuration = BigVGANConfig(
        **{name: values[name] for name in BigVGANConfig.__annotations__}
    )
    model = BigVGAN(configuration)
    expected = dict(tree_flatten(model.parameters()))
    raw = torch.load(
        args.source / "bigvgan_generator.pt", map_location="cpu", weights_only=True
    )["generator"]
    weights = model.sanitize({name: mx.array(value.numpy()) for name, value in raw.items()})
    missing = sorted(set(expected) - set(weights))
    extra = sorted(set(weights) - set(expected))
    if missing or extra:
        raise SystemExit(f"BigVGAN conversion mismatch: missing={missing}, extra={extra}")
    args.destination.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(args.destination / "model.safetensors"), weights)
    (args.destination / "config.json").write_text(
        json.dumps(values, indent=2, sort_keys=True) + "\n"
    )
    print(f"saved {len(weights)} tensors to {args.destination}")


if __name__ == "__main__":
    main()
