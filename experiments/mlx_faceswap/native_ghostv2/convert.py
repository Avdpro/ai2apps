#!/usr/bin/env python3
"""Convert official GhostV2 generator weights for native NHWC MLX inference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from safetensors.numpy import load_file, save_file


def _fold_batch_norm(
    weight: np.ndarray,
    gamma: np.ndarray,
    beta: np.ndarray,
    mean: np.ndarray,
    variance: np.ndarray,
    *,
    transposed: bool,
    epsilon: float = 1e-5,
) -> tuple[np.ndarray, np.ndarray]:
    scale = gamma / np.sqrt(variance + epsilon)
    axis_shape = (1, -1, 1, 1) if transposed else (-1, 1, 1, 1)
    return weight * scale.reshape(axis_shape), beta - mean * scale


def convert(source: Path, destination: Path) -> dict[str, object]:
    raw = {
        key.removeprefix("_orig_mod."): np.asarray(value, dtype=np.float32)
        for key, value in load_file(source).items()
    }
    converted: dict[str, np.ndarray] = {}

    for index in range(1, 8):
        prefix = f"encoder.conv{index}"
        weight, bias = _fold_batch_norm(
            raw[f"{prefix}.0.weight"],
            raw[f"{prefix}.1.weight"],
            raw[f"{prefix}.1.bias"],
            raw[f"{prefix}.1.running_mean"],
            raw[f"{prefix}.1.running_var"],
            transposed=False,
        )
        converted[f"{prefix}.weight"] = weight.transpose(0, 2, 3, 1)
        converted[f"{prefix}.bias"] = bias

    for index in range(1, 7):
        prefix = f"encoder.deconv{index}"
        weight, bias = _fold_batch_norm(
            raw[f"{prefix}.deconv.weight"],
            raw[f"{prefix}.bn.weight"],
            raw[f"{prefix}.bn.bias"],
            raw[f"{prefix}.bn.running_mean"],
            raw[f"{prefix}.bn.running_var"],
            transposed=True,
        )
        converted[f"{prefix}.weight"] = weight.transpose(1, 2, 3, 0)
        converted[f"{prefix}.bias"] = bias

    for key, value in raw.items():
        if not key.startswith("generator."):
            continue
        if key == "generator.up1.weight":
            converted[key] = value.transpose(1, 2, 3, 0)
        elif value.ndim == 4:
            converted[key] = value.transpose(0, 2, 3, 1)
        else:
            converted[key] = value

    destination.mkdir(parents=True, exist_ok=True)
    output = destination / "weights.safetensors"
    save_file(
        {
            key: np.ascontiguousarray(value.astype(np.float16))
            for key, value in converted.items()
        },
        output,
    )
    manifest = {
        "schema_version": 1,
        "format": "ai2apps.mlx.ghostv2.generator",
        "precision": "float16",
        "layout": "NHWC",
        "batch_norm_fused": True,
        "tensors": len(converted),
    }
    (destination / "config.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert(args.source, args.destination), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
