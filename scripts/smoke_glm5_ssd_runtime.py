#!/usr/bin/env python3
"""Short GLM-5.3 SSD-ready Runtime smoke."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path


async def _run(args) -> None:
    checkpoint = args.checkpoint.resolve()
    os.environ.update(
        OMLX_GLM5_DYNAMIC_STORE=str(checkpoint / "experts"),
        OMLX_GLM5_DYNAMIC_SLOTS=str(args.slots),
        OMLX_GLM5_TAIL_SLOTS="16",
        OMLX_GLM5_VISION_L1_RESERVE_SLOTS="16",
        OMLX_GLM5_DYNAMIC_IO_WORKERS="4",
        OMLX_GLM5_L1_PROMOTIONS_PER_LAYER="1",
        OMLX_GLM5_BOOST_MODE="natural",
        OMLX_GLM5_PREFILL_RESIDENT_FIRST="1",
        OMLX_GLM5_PREFILL_RETAIN_L1="1",
        OMLX_GLM5_MTP_ENABLED="0",
        OMLX_MOE_DIRECT_L1="1",
    )
    from omlx.engine.glm5_dynamic import Glm5DynamicVLMEngine

    engine = Glm5DynamicVLMEngine(str(checkpoint), trust_remote_code=False)
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
        await engine.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", default="The capital of France is")
    parser.add_argument("--tokens", type=int, default=1)
    parser.add_argument("--slots", type=int, default=96)
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
