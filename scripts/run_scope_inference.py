#!/usr/bin/env python3
"""Run one real generation and report DeepSeek V4 scope-cache activity."""

from __future__ import annotations

import argparse
import asyncio
import os
import time


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("prompt")
    parser.add_argument("--max-tokens", type=int, default=64)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    from omlx.engine.batched import BatchedEngine
    from omlx.patches.deepseek_v4.scope_cache import get_scope_fallback_loader

    engine = BatchedEngine(args.model)
    started = time.perf_counter()
    try:
        output = await engine.generate(
            prompt=args.prompt,
            max_tokens=args.max_tokens,
            temperature=0.0,
            top_p=1.0,
            skip_cache_store=True,
        )
        elapsed = time.perf_counter() - started
        print(f"completion_tokens={output.completion_tokens} elapsed={elapsed:.3f}s")
        print(output.text)
        store = os.environ.get("OMLX_DEEPSEEK_V4_EXPERT_STORE", "").strip()
        if store:
            print(f"scope_cache={get_scope_fallback_loader(store).stats()}")
    finally:
        await engine.stop()


def main() -> None:
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
