"""Convert Seed-VC v2 PyTorch component checkpoints to MLX safetensors."""

from __future__ import annotations

import argparse
from pathlib import Path

import mlx.core as mx
import torch


def _save(path: Path, values: dict) -> None:
    converted = {}
    for name, value in values.items():
        if name.endswith("freqs_cis") or name.endswith("causal_mask") or name.endswith("num_batches_tracked"):
            continue
        if value.dtype == torch.bfloat16:
            value = value.float()
        converted[name] = mx.array(value.numpy())
    mx.save_safetensors(str(path), converted)
    print(f"saved {len(converted)} tensors to {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cfm", type=Path)
    parser.add_argument("ar", type=Path)
    parser.add_argument("astral_narrow", type=Path)
    parser.add_argument("astral_wide", type=Path)
    parser.add_argument("campplus", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    cfm = torch.load(args.cfm, map_location="cpu", weights_only=True)["net"]
    ar = torch.load(args.ar, map_location="cpu", weights_only=True)["net"]
    _save(args.destination / "cfm.safetensors", cfm["cfm"])
    _save(args.destination / "cfm_length_regulator.safetensors", cfm["length_regulator"])
    _save(args.destination / "ar.safetensors", ar["ar"])
    _save(args.destination / "ar_length_regulator.safetensors", ar["length_regulator"])
    _save(args.destination / "astral_narrow.safetensors", torch.load(args.astral_narrow, map_location="cpu", weights_only=True))
    _save(args.destination / "astral_wide.safetensors", torch.load(args.astral_wide, map_location="cpu", weights_only=True))
    _save(args.destination / "campplus.safetensors", torch.load(args.campplus, map_location="cpu", weights_only=True))


if __name__ == "__main__":
    main()
