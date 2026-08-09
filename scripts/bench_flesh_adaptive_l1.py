#!/usr/bin/env python3
"""Benchmark one adaptive-L1 mode directly through DeepseekV4FleshEngine."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import resource
import time
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--mode", choices=("auto", "off"), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--tail-tokens", type=int, default=128)
    parser.add_argument("--warmup-tokens", type=int, default=1)
    parser.add_argument(
        "--trigger-token",
        type=int,
        help="request one manual L1 optimization after this generated token",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


async def _consume(
    engine,
    *,
    prompt: str,
    max_tokens: int,
    mode: str,
    session_id: str,
    trigger_token: int | None = None,
) -> dict:
    started = time.perf_counter()
    first_generated_at = None
    last_generated_at = None
    last_output = None
    text = ""
    triggered = False
    async for output in engine.stream_chat(
        [{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.0,
        top_p=1.0,
        flesh_session_id=session_id,
        flesh_l1_mode=mode,
    ):
        last_output = output
        text = output.text
        generated_at = output.generated_until or output.generated_at
        if generated_at is not None:
            if first_generated_at is None:
                first_generated_at = generated_at
            last_generated_at = generated_at
        if (
            trigger_token is not None
            and not triggered
            and output.completion_tokens >= trigger_token
        ):
            engine.request_l1_optimization(session_id)
            triggered = True
    response_done = time.perf_counter()
    if last_output is None:
        raise RuntimeError("engine produced no output")
    decode_seconds = (
        last_generated_at - first_generated_at
        if first_generated_at is not None and last_generated_at is not None
        else None
    )
    return {
        "prompt_tokens": last_output.prompt_tokens,
        "completion_tokens": last_output.completion_tokens,
        "finish_reason": last_output.finish_reason,
        "cached_tokens": last_output.cached_tokens,
        "ttft_seconds": (
            first_generated_at - started if first_generated_at is not None else None
        ),
        "decode_seconds": decode_seconds,
        "decode_tokens_per_second": (
            last_output.completion_tokens / decode_seconds
            if decode_seconds and decode_seconds > 0
            else None
        ),
        "response_wall_seconds": response_done - started,
        "manual_triggered": triggered,
        "text": text,
    }


async def _run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.flesh import DeepseekV4FleshEngine
    from omlx.scheduler import SchedulerConfig

    model = args.model.expanduser().resolve()
    config = SchedulerConfig(
        max_num_seqs=1,
        completion_batch_size=1,
        model_name=model.name,
        model_path=str(model),
    )
    engine = DeepseekV4FleshEngine(str(model), scheduler_config=config)

    def memory_snapshot() -> dict[str, float | None]:
        mx.synchronize()
        gib = 1024**3
        return {
            "mlx_active_gb": mx.get_active_memory() / gib,
            "mlx_peak_gb": mx.get_peak_memory() / gib,
            "mlx_cache_gb": mx.get_cache_memory() / gib,
            # ru_maxrss is bytes on macOS (KiB on Linux). This benchmark is
            # specifically for the local Apple-Silicon release gate.
            "process_peak_rss_gb": resource.getrusage(
                resource.RUSAGE_SELF
            ).ru_maxrss
            / gib,
        }

    mx.reset_peak_memory()
    load_started = time.perf_counter()
    try:
        await engine.start()
        load_seconds = time.perf_counter() - load_started
        after_load_memory = memory_snapshot()
        warmup = await _consume(
            engine,
            prompt=args.prompt,
            max_tokens=args.warmup_tokens,
            mode="off",
            session_id=f"bench-{args.mode}-warmup",
        )
        after_warmup_memory = memory_snapshot()
        benchmark = await _consume(
            engine,
            prompt=args.prompt,
            max_tokens=args.max_tokens,
            mode=args.mode,
            session_id=f"bench-html-{args.mode}",
            trigger_token=args.trigger_token,
        )
        after_benchmark_memory = memory_snapshot()
        response_stats = engine.get_stats().get("flesh", {})
        tail = response_stats.get("last_decode_tail")
        # Turn-end optimization is intentionally outside response latency, but
        # wait for it here so the result records whether it fired.
        maintenance_started = time.perf_counter()
        tasks = tuple(engine._maintenance_tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        maintenance_seconds = time.perf_counter() - maintenance_started
        final_stats = engine.get_stats().get("flesh", {})
        result = {
            "mode": args.mode,
            "prompt": args.prompt,
            "max_tokens": args.max_tokens,
            "tail_tokens_requested": args.tail_tokens,
            "trigger_token": args.trigger_token,
            "load_seconds": load_seconds,
            "warmup": {k: v for k, v in warmup.items() if k != "text"},
            "benchmark": benchmark,
            "text_sha256": hashlib.sha256(
                benchmark["text"].encode()
            ).hexdigest(),
            "tail": tail,
            "memory": {
                "after_load": after_load_memory,
                "after_warmup": after_warmup_memory,
                "after_benchmark": after_benchmark_memory,
            },
            "maintenance_wait_seconds": maintenance_seconds,
            "adaptive_l1": final_stats.get("adaptive_l1"),
            "bank": final_stats.get("bank"),
            "expert_store": final_stats.get("expert_store"),
            "last_selection": final_stats.get("last_selection"),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        printable = dict(result)
        printable["benchmark"] = {
            k: v for k, v in benchmark.items() if k != "text"
        }
        print(json.dumps(printable, ensure_ascii=False, indent=2), flush=True)
    finally:
        await engine.stop()


def main() -> None:
    args = _args()
    if args.tail_tokens != 128:
        raise ValueError("engine observability currently records a 128-token tail")
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
