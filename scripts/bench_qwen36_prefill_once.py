#!/usr/bin/env python3
"""Benchmark one Qwen3.6 Cache-MoE prefill backend in a warm process."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("--scope", default="coding")
    parser.add_argument("--backend", choices=("flesh", "arena", "tiered"), default="arena")
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--lengths", default="128,512,1024")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    from omlx.patches.qwen3_6_flesh.scope_policy import configure_qwen36_scope_policy

    configure_qwen36_scope_policy(
        args.profile, args.scope, args.store, args.experts,
        backend=args.backend, arena_tail_slots=args.tail,
    )
    if args.backend == "flesh":
        from omlx.engine.qwen36_flesh import Qwen36FleshEngine as Engine
    elif args.backend == "arena":
        from omlx.engine.qwen36_arena import Qwen36ArenaEngine as Engine
    else:
        from omlx.engine.qwen36_tiered import Qwen36TieredEngine as Engine

    engine = Engine(str(args.model))
    rows = []
    try:
        await engine.start()
        seed = engine._tokenizer.encode(
            "请分析并实现一个可靠的软件系统，说明设计、代码与测试。",
            add_special_tokens=False,
        )
        for length in (int(value) for value in args.lengths.split(",")):
            prompt = (seed * ((length + len(seed) - 1) // len(seed)))[:length]
            for repeat in range(1, args.repeats + 1):
                started = time.perf_counter()
                output = await engine.generate(
                    prompt,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                    skip_cache_store=True,
                    flesh_session_id="prefill-bench",
                    flesh_l1_mode="off",
                    flesh_scope=args.scope,
                )
                rows.append(
                    {
                        "length": length,
                        "repeat": repeat,
                        "ttft_seconds": output.first_token_at - started,
                        "tokens_per_second": length / (output.first_token_at - started),
                        "token": list(output.tokens or []),
                        "text_sha256": hashlib.sha256(
                            output.text.encode("utf-8")
                        ).hexdigest(),
                        "text": output.text,
                    }
                )
        report = {
            "backend": args.backend,
            "experts": args.experts,
            "tail": args.tail,
            "prefill_backend": __import__("os").environ.get(
                "OMLX_QWEN36_PREFILL_BACKEND", "workspace256-direct"
            ),
            "rows": rows,
            "stats": engine.get_stats().get("flesh", {}),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
