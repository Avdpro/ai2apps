#!/usr/bin/env python3
"""Benchmark raw and MLX-materialized reads from an expert-major layer file."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time

import mlx.core as mx
import numpy as np

from omlx.cache.moe_expert_store import ExpertMajorStore


NP_DTYPES = {"U8": np.uint8, "U32": np.uint32}


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * p))]


def summarize(name: str, values: list[float], record_bytes: int) -> dict:
    mean_ms = statistics.mean(values) * 1000
    return {
        "mode": name,
        "reads": len(values),
        "mean_ms_per_expert": round(mean_ms, 3),
        "median_ms_per_expert": round(statistics.median(values) * 1000, 3),
        "p90_ms_per_expert": round(percentile(values, 0.90) * 1000, 3),
        "effective_gb_per_second": round(record_bytes / (mean_ms / 1000) / 1e9, 3),
    }


def materialize(store: ExpertMajorStore, record: object) -> None:
    arrays = []
    for tensor, raw in store.tensor_views(record):
        dtype = NP_DTYPES[tensor.dtype]
        value = np.frombuffer(raw, dtype=dtype).reshape(tensor.shape)
        arrays.append(mx.array(value))
    mx.eval(*arrays)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("store")
    parser.add_argument("--reads", type=int, default=64)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument(
        "--mode",
        choices=(
            "pread",
            "pread-reuse",
            "mmap",
            "mlx-pread",
            "mlx-mmap",
            "mlx-copy-pread",
            "mlx-copy-mmap",
        ),
        nargs="+",
        default=(
            "pread",
            "pread-reuse",
            "mmap",
            "mlx-pread",
            "mlx-mmap",
            "mlx-copy-pread",
            "mlx-copy-mmap",
        ),
    )
    args = parser.parse_args()

    with ExpertMajorStore(args.store) as store:
        if args.no_cache:
            store.set_no_cache()
        rng = random.Random(args.seed)
        expert_ids = [rng.randrange(store.num_experts) for _ in range(args.reads)]
        for mode in args.mode:
            staging = store.allocate_staging()
            if mode.startswith("mlx-copy"):
                # Compile the copy kernel outside the measured loop.
                mx.eval(*store.mlx_tensor_views(staging, copy_record=True).values())
            timings = []
            for expert_id in expert_ids:
                started = time.perf_counter()
                if mode == "pread":
                    record = store.read(expert_id)
                elif mode == "pread-reuse":
                    record = store.read_into(expert_id, staging)
                elif mode == "mmap":
                    record = store.mmap_view(expert_id)
                    # Force every page so this mode measures page faults/readout.
                    sum(record[::4096])
                elif mode == "mlx-pread":
                    record = store.read_into(expert_id, staging)
                    materialize(store, record)
                elif mode == "mlx-mmap":
                    record = store.mmap_view(expert_id)
                    materialize(store, record)
                elif mode == "mlx-copy-pread":
                    record = store.read_into(expert_id, staging)
                    mx.eval(*store.mlx_tensor_views(record, copy_record=True).values())
                else:
                    record = store.mmap_view(expert_id)
                    mx.eval(*store.mlx_tensor_views(record, copy_record=True).values())
                timings.append(time.perf_counter() - started)
                del record
            print(
                json.dumps(
                    summarize(mode, timings, store.record_bytes), sort_keys=True
                )
            )


if __name__ == "__main__":
    main()
