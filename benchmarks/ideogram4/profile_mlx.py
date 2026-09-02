#!/usr/bin/env python3
"""Micro-profile the native Ideogram 4 MLX denoiser on Apple Silicon."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Callable
from pathlib import Path

import mlx.core as mx
from mlx.utils import tree_flatten
from mlx_model import load_quantized_transformer


def evaluate(value):
    if isinstance(value, tuple):
        mx.eval(*value)
    else:
        mx.eval(value)


def benchmark(
    name: str,
    function: Callable[[], object],
    *,
    warmup: int,
    repeats: int,
) -> dict[str, object]:
    for _ in range(warmup):
        evaluate(function())
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        evaluate(function())
        samples.append(time.perf_counter() - started)
    return {
        "name": name,
        "median_seconds": statistics.median(samples),
        "minimum_seconds": min(samples),
        "samples_seconds": samples,
    }


def array_bytes(value: mx.array) -> int:
    return value.size * value.itemsize


def module_parameter_bytes(module) -> int:
    leaves = tree_flatten(module.parameters())
    return sum(array_bytes(value) for _, value in leaves)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--bits", type=int, choices=(4, 8, 16), default=4)
    parser.add_argument("--sequence", type=int, default=1235)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    model = load_quantized_transformer(
        args.checkpoint,
        bits=args.bits,
        group_size=64,
    )
    layer = model.layers[0]
    compute_dtype = model.compute_dtype
    hidden = mx.random.normal(
        (1, args.sequence, model.config.emb_dim), dtype=compute_dtype
    )
    conditioning = mx.random.normal(
        (1, 1, model.config.adaln_dim), dtype=compute_dtype
    )
    positions = mx.zeros((1, args.sequence, 3), dtype=mx.int32)
    positions[:, :, 0] = mx.arange(args.sequence)
    cos, sin = model.rotary_emb(positions)
    cos, sin = cos.astype(hidden.dtype), sin.astype(hidden.dtype)
    mx.eval(hidden, conditioning, cos, sin)

    cases: list[tuple[str, Callable[[], object], object]] = [
        ("qkv", lambda: layer.attention.qkv(hidden), layer.attention.qkv),
        ("attention", lambda: layer.attention(hidden, None, cos, sin), layer.attention),
        ("mlp", lambda: layer.feed_forward(hidden), layer.feed_forward),
        (
            "block",
            lambda: layer(hidden, None, cos, sin, conditioning),
            layer,
        ),
    ]
    results = []
    for name, function, module in cases:
        result = benchmark(
            name,
            function,
            warmup=args.warmup,
            repeats=args.repeats,
        )
        parameter_bytes = module_parameter_bytes(module)
        result["parameter_bytes"] = parameter_bytes
        result["parameter_read_gib_per_second"] = (
            parameter_bytes / result["median_seconds"] / (1 << 30)
        )
        results.append(result)

    report = {
        "backend": "mlx",
        "mlx_version": getattr(mx, "__version__", "unknown"),
        "bits": args.bits,
        "sequence": args.sequence,
        "warmup": args.warmup,
        "repeats": args.repeats,
        "active_memory_bytes": mx.get_active_memory(),
        "peak_memory_bytes": mx.get_peak_memory(),
        "results": results,
    }
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
