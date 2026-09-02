#!/usr/bin/env python3
"""Profile Ideogram's head-dim-256 SDPA at image-generation lengths."""

from __future__ import annotations

import argparse
import json
import statistics
import time

import mlx.core as mx


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--heads", type=int, default=18)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--dtype", choices=("float32", "bfloat16"), default="float32")
    args = parser.parse_args()

    dtype = mx.float32 if args.dtype == "float32" else mx.bfloat16
    shape = (1, args.heads, args.sequence, 256)
    query = mx.random.normal(shape, dtype=dtype)
    key = mx.random.normal(shape, dtype=dtype)
    value = mx.random.normal(shape, dtype=dtype)
    mx.eval(query, key, value)

    def attention():
        return mx.fast.scaled_dot_product_attention(
            query, key, value, scale=256**-0.5
        )

    for _ in range(args.warmup):
        mx.eval(attention())
    samples = []
    for _ in range(args.repeats):
        started = time.perf_counter()
        mx.eval(attention())
        samples.append(time.perf_counter() - started)
    print(
        json.dumps(
            {
                "mlx_version": getattr(mx, "__version__", "unknown"),
                "sequence": args.sequence,
                "dtype": args.dtype,
                "median_seconds": statistics.median(samples),
                "minimum_seconds": min(samples),
                "peak_memory_bytes": mx.get_peak_memory(),
                "samples_seconds": samples,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
