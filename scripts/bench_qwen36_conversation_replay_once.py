#!/usr/bin/env python3
"""Replay one multi-turn conversation with identical forced decode tokens."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--backend", choices=("flesh", "arena", "tiered"), required=True)
    parser.add_argument("--mode", choices=("off", "auto"), required=True)
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    from omlx.patches.qwen3_6_flesh.scope_policy import configure_qwen36_scope_policy

    reference = json.loads(args.reference.read_text())
    scope = reference["scope"]
    configure_qwen36_scope_policy(
        args.profile,
        scope,
        args.store,
        args.experts,
        backend=args.backend,
        arena_tail_slots=args.tail,
    )
    if args.backend == "flesh":
        from omlx.engine.qwen36_flesh import Qwen36FleshEngine as Engine
    elif args.backend == "arena":
        from omlx.engine.qwen36_arena import Qwen36ArenaEngine as Engine
    else:
        from omlx.engine.qwen36_tiered import Qwen36TieredEngine as Engine

    engine = Engine(str(args.model))
    turns: list[dict[str, Any]] = []
    messages: list[dict[str, str]] = []
    session_id = f"forced-conversation-{scope}"
    try:
        await engine.start()
        for turn_index, ref_turn in enumerate(reference["turns"], start=1):
            user_text = reference["user_messages"][turn_index - 1]
            messages.append({"role": "user", "content": user_text})
            prompt = engine._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            prompt_ids = engine._tokenizer.encode(prompt, add_special_tokens=False)
            forced = [int(token) for token in ref_turn["token_ids"]]
            await engine._qwen_adaptive.prepare(
                {"flesh_session_id": session_id, "flesh_l1_mode": args.mode}
            )
            cache = make_prompt_cache(engine._model)
            logits = engine._model(mx.array([prompt_ids]), cache=cache)[:, -1, :]
            mx.eval(logits)
            started = time.perf_counter()
            for index, token in enumerate(forced[:-1], start=1):
                engine._qwen_adaptive.between_step(
                    SimpleNamespace(
                        outputs=[SimpleNamespace(completion_tokens=index)]
                    )
                )
                logits = engine._model(
                    mx.array([[token]], dtype=mx.int32), cache=cache
                )[:, -1, :]
                mx.eval(logits)
            elapsed = time.perf_counter() - started
            turns.append(
                {
                    "turn": turn_index,
                    "prompt_tokens": len(prompt_ids),
                    "decode_steps": max(0, len(forced) - 1),
                    "decode_seconds": elapsed,
                    "decode_tps": max(0, len(forced) - 1) / elapsed,
                }
            )
            messages.append({"role": "assistant", "content": ref_turn["text"]})

        total_steps = sum(turn["decode_steps"] for turn in turns)
        total_seconds = sum(turn["decode_seconds"] for turn in turns)
        report = {
            "scope": scope,
            "backend": args.backend,
            "mode": args.mode,
            "turns": turns,
            "overall_decode_tps": total_steps / total_seconds,
            "late_two_turn_decode_tps": sum(t["decode_steps"] for t in turns[-2:])
            / sum(t["decode_seconds"] for t in turns[-2:]),
            "adaptive_l1": engine.get_stats().get("flesh", {}).get("adaptive_l1"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(json.dumps(report, indent=2, ensure_ascii=False))
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
