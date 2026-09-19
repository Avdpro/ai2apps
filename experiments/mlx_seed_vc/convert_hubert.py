"""Offline conversion of the fixed HuBERT checkpoint to MLX safetensors."""

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
    from mlx_audio.stt.models.wav2vec.wav2vec import ModelConfig, Wav2Vec2Model

    config_values = json.loads((args.source / "config.json").read_text())
    config_values["num_hidden_layers"] = 18
    config_values["apply_spec_augment"] = False
    model = Wav2Vec2Model(ModelConfig.from_dict(config_values))
    expected = dict(tree_flatten(model.parameters()))
    raw = torch.load(args.source / "pytorch_model.bin", map_location="cpu", weights_only=True)
    weights = model.sanitize({name: mx.array(value.numpy()) for name, value in raw.items()})
    weights = {name: value for name, value in weights.items() if name in expected}
    missing = sorted(set(expected) - set(weights))
    mismatched = sorted(
        name for name in weights if weights[name].shape != expected[name].shape
    )
    if missing or mismatched:
        raise SystemExit(f"HuBERT conversion mismatch: missing={missing}, shapes={mismatched}")
    args.destination.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(args.destination / "model.safetensors"), weights)
    (args.destination / "config.json").write_text(
        json.dumps(config_values, indent=2, sort_keys=True) + "\n"
    )
    print(f"saved {len(weights)} tensors to {args.destination}")


if __name__ == "__main__":
    main()
