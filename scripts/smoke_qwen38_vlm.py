#!/usr/bin/env python3
"""Load a real Qwen3.8 VLM checkpoint through oMLX and generate tokens."""

from __future__ import annotations

import argparse
import asyncio
import base64
import logging
import mimetypes
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: Qwen3.8 local inference works.",
    )
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--repeat-prompt", type=int, default=1)
    parser.add_argument("--prefill-step-size", type=int)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="WARNING",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.vlm import VLMBatchedEngine
    from omlx.model_adapters import get_model_adapter_registry
    from omlx.scheduler import SchedulerConfig

    adapters = get_model_adapter_registry().adapters()
    print(f"adapters={[adapter.adapter_id for adapter in adapters]}")

    scheduler_config = None
    if args.prefill_step_size is not None:
        scheduler_config = SchedulerConfig(prefill_step_size=args.prefill_step_size)
    engine = VLMBatchedEngine(args.model, scheduler_config=scheduler_config)
    prompt = args.prompt * max(1, args.repeat_prompt)
    started = time.perf_counter()
    try:
        if args.image is None:
            output = await engine.generate(
                prompt=prompt,
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
            )
        else:
            media_type = mimetypes.guess_type(args.image.name)[0] or "image/png"
            encoded = base64.b64encode(args.image.read_bytes()).decode("ascii")
            output = await engine.chat(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{encoded}"
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
            )
        elapsed = time.perf_counter() - started
        print(f"prompt_tokens={output.prompt_tokens}")
        print(f"completion_tokens={output.completion_tokens}")
        print(f"elapsed_seconds={elapsed:.3f}")
        if output.completion_tokens:
            print(f"end_to_end_tps={output.completion_tokens / elapsed:.3f}")
        print(f"mlx_active_gib={mx.get_active_memory() / (1024**3):.3f}")
        print(f"mlx_peak_gib={mx.get_peak_memory() / (1024**3):.3f}")
        print(f"text={output.text!r}")
    finally:
        await engine.stop()


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
