#!/usr/bin/env python3
"""Short DeepSeek V4 SSD-ready Runtime smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path


async def _run(args) -> None:
    checkpoint = args.checkpoint.resolve()
    marker_path = checkpoint / "ai2apps-model.json"
    if marker_path.exists():
        raise FileExistsError(marker_path)
    marker_path.write_text(
        json.dumps(
            {
                "format": "ai2apps-cache-moe-model",
                "checkpoint_layout": {"format": "ai2apps-ssd-checkpoint"},
                "expert_store": str((checkpoint / "experts").resolve()),
            }
        )
    )
    from omlx.patches.deepseek_v4.scope_policy import (
        clear_scope_policy_override,
        configure_scope_policy,
    )

    configure_scope_policy(
        args.profile, "general", checkpoint / "experts", args.resident_experts
    )
    engine = None
    started = time.perf_counter()
    try:
        from omlx.engine.flesh import DeepseekV4FleshEngine

        engine = DeepseekV4FleshEngine(str(checkpoint), trust_remote_code=False)
        await engine.start()
        result = await engine.chat(
            [{"role": "user", "content": args.prompt}],
            max_tokens=args.tokens,
            temperature=0,
        )
        receipt = {
            "status": "complete",
            "checkpoint": str(checkpoint),
            "text": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "elapsed_seconds": time.perf_counter() - started,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt, ensure_ascii=False))
    finally:
        if engine is not None:
            await engine.stop()
        clear_scope_policy_override()
        marker_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--tokens", type=int, default=1)
    parser.add_argument("--resident-experts", type=int, default=60)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
