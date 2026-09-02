#!/usr/bin/env python3
"""Run a JSON image-quality suite through one warm VLM engine instance."""

from __future__ import annotations

import argparse
import asyncio
import base64
import gc
import json
import mimetypes
import time
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="low")
    parser.add_argument("--case-id", help="Run only one manifest case")
    return parser.parse_args()


def _image_part(path: Path) -> dict:
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
    }


async def _run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.vlm import VLMBatchedEngine

    cases = json.loads(args.manifest.read_text())
    if args.case_id:
        cases = [case for case in cases if case["id"] == args.case_id]
        if not cases:
            raise ValueError(f"Unknown case id: {args.case_id}")
    engine = VLMBatchedEngine(args.model)
    results = []
    suite_started = time.perf_counter()
    try:
        await engine.start()
        for index, case in enumerate(cases, 1):
            image_path = Path(case["image"])
            mx.reset_peak_memory()
            started = time.perf_counter()
            output = await engine.chat(
                messages=[
                    {
                        "role": "user",
                        "content": [
                            _image_part(image_path),
                            {"type": "text", "text": case["prompt"]},
                        ],
                    }
                ],
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
                chat_template_kwargs={"reasoning_effort": args.reasoning_effort},
                skip_cache_store=True,
            )
            elapsed = time.perf_counter() - started
            result = {
                "id": case["id"],
                "image": str(image_path),
                "prompt_tokens": output.prompt_tokens,
                "completion_tokens": output.completion_tokens,
                "elapsed_seconds": round(elapsed, 3),
                "end_to_end_tps": round(output.completion_tokens / elapsed, 3),
                "peak_gib": round(mx.get_peak_memory() / (1024**3), 3),
                "finish_reason": output.finish_reason,
                "text": output.text,
            }
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
            del output
            gc.collect()
            mx.clear_cache()
    finally:
        await engine.stop()

    report = {
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "max_tokens": args.max_tokens,
        "suite_elapsed_seconds": round(time.perf_counter() - suite_started, 3),
        "results": results,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
