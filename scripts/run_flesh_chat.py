#!/usr/bin/env python3
"""Run multi-session DeepSeek V4 Flesh chat and report scope/KV activity."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model")
    parser.add_argument(
        "--turn",
        action="append",
        required=True,
        help="SESSION_ID:prompt; repeat for multiple sessions/turns",
    )
    parser.add_argument("--system", default="You are a helpful assistant.")
    parser.add_argument("--system-repeat", type=int, default=1)
    parser.add_argument("--between-turn-seconds", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--kv-cache-dir", type=Path)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    from omlx.engine.flesh import DeepseekV4FleshEngine
    from omlx.scheduler import SchedulerConfig

    config = SchedulerConfig(
        max_num_seqs=1,
        completion_batch_size=1,
        model_name=Path(args.model).name,
        model_path=str(Path(args.model).expanduser().resolve()),
        paged_ssd_cache_dir=(
            str(args.kv_cache_dir.expanduser().resolve())
            if args.kv_cache_dir is not None
            else None
        ),
    )
    engine = DeepseekV4FleshEngine(args.model, scheduler_config=config)
    sessions: dict[str, list[dict[str, str]]] = {}
    system_prompt = " ".join([args.system] * args.system_repeat)
    try:
        await engine.start()
        for raw_turn in args.turn:
            if ":" not in raw_turn:
                raise ValueError(f"turn must be SESSION_ID:prompt, got {raw_turn!r}")
            session_id, prompt = raw_turn.split(":", 1)
            messages = sessions.setdefault(
                session_id,
                [{"role": "system", "content": system_prompt}],
            )
            messages.append({"role": "user", "content": prompt})
            output = await engine.chat(
                messages,
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
            )
            messages.append({"role": "assistant", "content": output.text})
            flesh = engine.get_stats().get("flesh", {})
            print(
                json.dumps(
                    {
                        "session": session_id,
                        "prompt": prompt,
                        "text": output.text,
                        "prompt_tokens": output.prompt_tokens,
                        "completion_tokens": output.completion_tokens,
                        "cached_tokens": output.cached_tokens,
                        "flesh": flesh,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            if args.between_turn_seconds:
                await asyncio.sleep(args.between_turn_seconds)
    finally:
        await engine.stop()


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
