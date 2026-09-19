#!/usr/bin/env python3
"""Short Qwen3.6/Ornith SSD-ready Runtime smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path


async def _run(args) -> None:
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        clear_qwen36_scope_policy,
        configure_qwen36_scope_policy,
    )

    configure_qwen36_scope_policy(
        args.profile,
        "general",
        args.checkpoint / "experts",
        args.resident_experts,
        backend="tiered",
        arena_tail_slots=24,
    )
    if args.vlm:
        from omlx.engine.vlm import VLMBatchedEngine as Engine
    else:
        from omlx.engine.batched import BatchedEngine as Engine
    engine = Engine(str(args.checkpoint), trust_remote_code=False)
    started = time.perf_counter()
    try:
        await engine.start()
        result = await engine.chat(
            [{"role": "user", "content": args.prompt}],
            max_tokens=args.tokens,
            temperature=0,
        )
        receipt = {
            "status": "complete",
            "checkpoint": str(args.checkpoint.resolve()),
            "text": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "elapsed_seconds": time.perf_counter() - started,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        await engine.stop()
        clear_qwen36_scope_policy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--tokens", type=int, default=1)
    parser.add_argument("--resident-experts", type=int, default=80)
    parser.add_argument("--vlm", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
