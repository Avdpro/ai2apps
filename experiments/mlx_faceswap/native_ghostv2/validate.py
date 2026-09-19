#!/usr/bin/env python3
"""Validate and benchmark the native MLX GhostV2 generator."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
from PIL import Image

from .model import NativeGhostV2Generator


def _target(path: Path, dtype) -> mx.array:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    return mx.array((rgb[None] / 127.5) - 1.0).astype(dtype)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--embedding", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--precision", choices=("fp16", "bf16"), default="fp16")
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()

    mx.reset_peak_memory()
    model = NativeGhostV2Generator(args.model, precision=args.precision)
    target = _target(args.target, model.dtype)
    identity = mx.array(np.load(args.embedding)).astype(model.dtype)
    timings = []
    output = None
    for _ in range(args.runs):
        started = time.perf_counter()
        output = model(target, identity)
        mx.eval(output)
        timings.append(time.perf_counter() - started)
    assert output is not None
    values = np.asarray(output, dtype=np.float32).transpose(0, 3, 1, 2)
    reference = np.load(args.reference).astype(np.float32)
    delta = values - reference
    rgb = np.clip(
        np.rint((np.asarray(output[0], dtype=np.float32) + 1.0) * 127.5), 0, 255
    ).astype(np.uint8)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "precision": args.precision,
                "runs": timings,
                "warm_fps": 1.0 / timings[-1],
                "peak_memory_bytes": mx.get_peak_memory(),
                "max_abs": float(np.max(np.abs(delta))),
                "mean_abs": float(np.mean(np.abs(delta))),
                "rmse": float(np.sqrt(np.mean(delta * delta))),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
