#!/usr/bin/env python3
"""Profile the experimental native MLX Q4 dual-QMM SwiGLU primitive."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx_model import load_quantized_transformer


def measure(function, warmup: int, repeats: int):
    for _ in range(warmup):
        mx.eval(function())
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        mx.eval(function())
        samples.append(time.perf_counter() - started)
    return {
        "median_seconds": statistics.median(samples),
        "minimum_seconds": min(samples),
        "samples_seconds": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sequence", type=int, default=1235)
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=15)
    args = parser.parse_args()

    model = load_quantized_transformer(args.checkpoint, bits=4, group_size=64)
    mlp = model.layers[0].feed_forward
    value = mx.random.normal(
        (1, args.sequence, model.config.emb_dim), dtype=mx.bfloat16
    )
    mx.eval(value)

    def eager_hidden():
        return nn.silu(mlp.w1(value)) * mlp.w3(value)

    def fused_hidden():
        return mx.quantized_swiglu(
            value,
            mlp.w1.weight,
            mlp.w1.scales,
            mlp.w1.biases,
            mlp.w3.weight,
            mlp.w3.scales,
            mlp.w3.biases,
        )

    reference = eager_hidden()
    candidate = fused_hidden()
    mx.eval(reference, candidate)
    difference = reference.astype(mx.float32) - candidate.astype(mx.float32)
    report = {
        "max_absolute_error": mx.max(mx.abs(difference)).item(),
        "mean_absolute_error": mx.mean(mx.abs(difference)).item(),
        "cosine_similarity": (
            mx.sum(reference.astype(mx.float32) * candidate.astype(mx.float32))
            / mx.sqrt(
                mx.sum(reference.astype(mx.float32) ** 2)
                * mx.sum(candidate.astype(mx.float32) ** 2)
            )
        ).item(),
        "eager_hidden": measure(eager_hidden, args.warmup, args.repeats),
        "fused_hidden": measure(fused_hidden, args.warmup, args.repeats),
        "eager_mlp": measure(
            lambda: mlp.w2(eager_hidden()), args.warmup, args.repeats
        ),
        "fused_mlp": measure(
            lambda: mlp.w2(fused_hidden()), args.warmup, args.repeats
        ),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
