#!/usr/bin/env python3
"""Benchmark GLM5 fused records loaded directly into final MLX L1 slots."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time

import mlx.core as mx

from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("store")
    parser.add_argument("--batches", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--capacity", type=int, default=16)
    parser.add_argument("--io-workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    if "preadv_fused_experts" not in glm_fast.native_symbols():
        raise RuntimeError("native preadv_fused_experts loader is unavailable")
    if not 1 <= args.batch_size <= args.capacity:
        raise ValueError("batch-size must fit within capacity")

    dtype_map = {
        "U8": mx.uint8,
        "U32": mx.uint32,
        "F16": mx.float16,
        "BF16": mx.bfloat16,
    }
    with ExpertMajorStore(args.store) as store:
        if args.no_cache:
            store.set_no_cache()
        arrays = [
            mx.zeros((args.capacity, *tensor.shape), dtype=dtype_map[tensor.dtype])
            for tensor in store.tensors
        ]
        mx.eval(*arrays)
        mx.synchronize()

        rng = random.Random(args.seed)
        timings = []
        for _ in range(args.batches):
            expert_ids = [
                rng.randrange(store.num_experts) for _ in range(args.batch_size)
            ]
            slots = list(range(args.batch_size))
            started = time.perf_counter()
            loaded = glm_fast.preadv_fused_experts(
                store.fileno(),
                store.data_offset,
                store.record_bytes,
                expert_ids,
                slots,
                *arrays,
                io_workers=args.io_workers,
            )
            timings.append(time.perf_counter() - started)
            if loaded != args.batch_size * store.record_bytes:
                raise RuntimeError("native loader returned an invalid byte count")

        mean = statistics.mean(timings)
        total_bytes = args.batch_size * store.record_bytes
        print(
            json.dumps(
                {
                    "mode": "native-direct-to-l1",
                    "batches": args.batches,
                    "batch_size": args.batch_size,
                    "io_workers": args.io_workers,
                    "record_bytes": store.record_bytes,
                    "mean_ms_per_batch": round(mean * 1000, 3),
                    "mean_ms_per_expert": round(
                        mean * 1000 / args.batch_size, 3
                    ),
                    "median_ms_per_batch": round(
                        statistics.median(timings) * 1000, 3
                    ),
                    "p90_ms_per_batch": round(
                        percentile(timings, 0.90) * 1000, 3
                    ),
                    "effective_gb_per_second": round(
                        total_bytes / mean / 1e9, 3
                    ),
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
