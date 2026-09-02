#!/usr/bin/env python3
"""Compare MLX Q4 group sizes at Ideogram 4 projection shapes."""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time

import mlx.core as mx
import mlx.nn as nn


def benchmark_linear(
    *,
    input_dim: int,
    output_dim: int,
    sequence: int,
    group_size: int,
    warmup: int,
    repeats: int,
    dtype: mx.Dtype,
) -> dict[str, object]:
    value = mx.random.normal((1, sequence, input_dim), dtype=dtype)
    linear = nn.Linear(input_dim, output_dim, bias=False)
    linear.set_dtype(dtype)
    nn.quantize(linear, group_size=group_size, bits=4)
    mx.eval(value, linear.parameters())
    for _ in range(warmup):
        mx.eval(linear(value))
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        mx.eval(linear(value))
        samples.append(time.perf_counter() - started)
    median = statistics.median(samples)
    macs = sequence * input_dim * output_dim
    result = {
        "input_dim": input_dim,
        "output_dim": output_dim,
        "group_size": group_size,
        "median_seconds": median,
        "minimum_seconds": min(samples),
        "effective_tflops": 2 * macs / median / 1e12,
        "samples_seconds": samples,
    }
    del linear, value
    mx.synchronize()
    gc.collect()
    mx.clear_cache()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence", type=int, default=1235)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="float32")
    args = parser.parse_args()
    dtype = mx.float32 if args.dtype == "float32" else mx.bfloat16

    shapes = (
        (4608, 13824),
        (4608, 12288),
        (12288, 4608),
    )
    results = []
    for group_size in (32, 64, 128):
        for input_dim, output_dim in shapes:
            results.append(
                benchmark_linear(
                    input_dim=input_dim,
                    output_dim=output_dim,
                    sequence=args.sequence,
                    group_size=group_size,
                    warmup=args.warmup,
                    repeats=args.repeats,
                    dtype=dtype,
                )
            )
    print(
        json.dumps(
            {
                "backend": "mlx",
                "mlx_version": getattr(mx, "__version__", "unknown"),
                "bits": 4,
                "dtype": args.dtype,
                "sequence": args.sequence,
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
