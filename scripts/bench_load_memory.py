#!/usr/bin/env python3
"""Load one oMLX model and report MLX memory without running a forward pass."""

from __future__ import annotations

import argparse
import asyncio
import json
import time

import mlx.core as mx


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    args = parser.parse_args()

    from omlx.engine.batched import BatchedEngine

    engine = BatchedEngine(args.model)
    started = time.perf_counter()
    await engine.start()
    before_clear = {
        "active_gib": round(mx.get_active_memory() / 1024**3, 2),
        "peak_gib": round(mx.get_peak_memory() / 1024**3, 2),
        "cache_gib": round(mx.get_cache_memory() / 1024**3, 2),
    }
    mx.clear_cache()
    print(
        json.dumps(
            {
                "load_seconds": round(time.perf_counter() - started, 2),
                "active_gib": round(mx.get_active_memory() / 1024**3, 2),
                "peak_gib": round(mx.get_peak_memory() / 1024**3, 2),
                "cache_gib": round(mx.get_cache_memory() / 1024**3, 2),
                "before_clear": before_clear,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
