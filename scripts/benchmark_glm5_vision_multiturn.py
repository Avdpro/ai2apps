#!/usr/bin/env python3
"""Exercise same-image follow-up and appended-image GLM-5 sessions."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import mimetypes
import time
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("first_image", type=Path)
    parser.add_argument("second_image", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--ssd-cache-dir", type=Path)
    parser.add_argument("--log-level", default="WARNING")
    return parser.parse_args()


def _image_part(path: Path) -> dict:
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{media_type};base64,{encoded}"},
    }


async def _wait_for_reclaim(engine, timeout: float = 10.0) -> None:
    scheduler = engine._engine.engine.scheduler
    deadline = time.monotonic() + timeout
    while scheduler.has_pending_route_preflight_cleanup():
        if time.monotonic() >= deadline:
            raise TimeoutError("VLM request cleanup did not settle")
        await asyncio.sleep(0.05)


async def _run(args: argparse.Namespace) -> None:
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    import mlx.core as mx

    from omlx.engine.vlm import VLMBatchedEngine
    from omlx.scheduler import SchedulerConfig

    scheduler_config = None
    if args.ssd_cache_dir is not None:
        scheduler_config = SchedulerConfig(
            paged_ssd_cache_dir=str(args.ssd_cache_dir),
        )
    engine = VLMBatchedEngine(args.model, scheduler_config=scheduler_config)
    messages: list[dict] = []
    results = []
    session_namespace = ("ai2apps-session-v1", "glm5-vision-multiturn-baseline")

    async def turn(turn_id: str, content: str | list[dict]) -> None:
        messages.append({"role": "user", "content": content})
        mx.reset_peak_memory()
        cache_before = dict(engine._vision_cache.stats)
        started = time.perf_counter()
        output = await engine.chat(
            messages=messages,
            max_tokens=args.max_tokens,
            temperature=0.0,
            top_p=1.0,
            chat_template_kwargs={"reasoning_effort": "low"},
            cache_extra_keys=session_namespace,
            kv_cache_policy="session",
        )
        elapsed = time.perf_counter() - started
        messages.append({"role": "assistant", "content": output.text})
        await _wait_for_reclaim(engine)
        cache_after = dict(engine._vision_cache.stats)
        scheduler = engine._engine.engine.scheduler
        result = {
            "turn": turn_id,
            "prompt_tokens": output.prompt_tokens,
            "cached_tokens": output.cached_tokens,
            "completion_tokens": output.completion_tokens,
            "elapsed_seconds": round(elapsed, 3),
            "end_to_end_tps": round(output.completion_tokens / elapsed, 3),
            "active_gib_after_reclaim": round(mx.get_active_memory() / (1024**3), 3),
            "peak_gib": round(mx.get_peak_memory() / (1024**3), 3),
            "vision_cache_delta": {
                key: cache_after.get(key, 0) - cache_before.get(key, 0)
                for key in cache_after
            },
            "batch_generator_released": scheduler.batch_generator is None,
            "text": output.text,
        }
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)

    try:
        await engine.start()
        await turn(
            "image_then_question",
            [
                _image_part(args.first_image),
                {
                    "type": "text",
                    "text": "直接用中文简短回答：记住这张账单图，列出两笔交易的商户和金额。",
                },
            ],
        )
        await turn(
            "same_image_text_followup",
            "不重新上传图片：第二笔交易用了哪家银行、卡尾号多少、状态标签是什么？",
        )
        await turn(
            "append_second_image",
            [
                _image_part(args.second_image),
                {
                    "type": "text",
                    "text": "现在新增第二张图。它是什么类型的应用？说出搜索词，并说明它与第一张账单图的用途差异。",
                },
            ],
        )
    finally:
        await engine.stop()

    args.output.write_text(
        json.dumps(
            {
                "model": args.model,
                "session_namespace": list(session_namespace),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
