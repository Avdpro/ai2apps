#!/usr/bin/env python3
"""Balanced real-inference A/B for Scope-cache SSD read parallelism."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("--pp", type=int, default=16)
    parser.add_argument("--gen", type=int, default=32)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--workers", type=int, nargs="+", default=[1, 4])
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.admin.benchmark import _generate_prompt, _run_single_test
    from omlx.engine.batched import BatchedEngine
    from omlx.patches.deepseek_v4.scope_cache import get_scope_fallback_loader

    store = os.environ["OMLX_DEEPSEEK_V4_EXPERT_STORE"]
    loader = get_scope_fallback_loader(store)
    engine = BatchedEngine(str(Path(args.model).expanduser().resolve()))
    await engine.start()
    mx.clear_cache()
    prompt = _generate_prompt(engine.tokenizer, args.pp)
    results: dict[int, list[dict]] = {workers: [] for workers in args.workers}
    try:
        for round_idx in range(args.repeat):
            order = args.workers if round_idx % 2 == 0 else list(reversed(args.workers))
            for workers in order:
                loader.clear_hot()
                loader.set_io_workers(workers)
                mx.clear_cache()
                before = loader.stats()
                started = time.perf_counter()
                result = await _run_single_test(
                    engine, prompt, args.gen, args.pp
                )
                wall = time.perf_counter() - started
                after = loader.stats()
                experts = after["experts_loaded"] - before["experts_loaded"]
                io_time = after["load_seconds"] - before["load_seconds"]
                row = {
                    "tps": result["gen_tps"],
                    "ttft": result["ttft_ms"],
                    "experts": experts,
                    "io_time": io_time,
                    "wall": wall,
                }
                results[workers].append(row)
                print(
                    f"round={round_idx + 1} workers={workers} "
                    f"tps={row['tps']:.3f} ttft={row['ttft']:.0f}ms "
                    f"experts={experts} io={io_time:.3f}s wall={wall:.3f}s"
                )
    finally:
        await engine.stop()

    print("\nmedians")
    for workers in args.workers:
        rows = results[workers]
        print(
            f"workers={workers} "
            f"tps={statistics.median(row['tps'] for row in rows):.3f} "
            f"ttft={statistics.median(row['ttft'] for row in rows):.0f}ms "
            f"experts={statistics.median(row['experts'] for row in rows):.0f} "
            f"io={statistics.median(row['io_time'] for row in rows):.3f}s"
        )


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
