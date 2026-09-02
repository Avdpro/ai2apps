#!/usr/bin/env python3
"""Benchmark a full-resident Qwen3.8-Flash-Next MLX checkpoint.

The process loads the model once and runs multiple cases so cold PLE/model page
touches are not confused with steady-state prefill throughput.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--prefill-step-size", type=int, default=512)
    parser.add_argument("--long-repeat", type=int, default=0)
    parser.add_argument("--only-long", action="store_true")
    parser.add_argument("--single-short", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def _rss_gib() -> float:
    # macOS reports ru_maxrss in bytes.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**30


def main() -> None:
    args = _parse_args()
    checkpoint = args.checkpoint.expanduser().resolve()

    import mlx.core as mx
    from omlx.patches.qwen38_next_cache import (
        apply_qwen4_rmsnorm_compat_patch,
        qwen4_dynamic_safetensors_on_load,
    )

    apply_qwen4_rmsnorm_compat_patch()

    from mlx_vlm import load
    from mlx_vlm.generate import stream_generate
    from mlx_vlm.prompt_utils import apply_chat_template

    mx.reset_peak_memory()
    load_started = time.perf_counter()
    with qwen4_dynamic_safetensors_on_load(checkpoint):
        model, processor = load(str(checkpoint), lazy=False, strict=True)
    load_seconds = time.perf_counter() - load_started

    base_prompt = (
        "Explain in plain English why a sparse mixture-of-experts model can "
        "use less computation per generated token."
    )
    cases = [] if args.only_long else [
        ("cold-short", base_prompt),
    ]
    if not args.only_long and not args.single_short:
        cases.append(("warm-short", base_prompt))
    if args.long_repeat:
        cases.append(
            (
                "warm-long",
                ("Context paragraph: " + base_prompt + "\n") * args.long_repeat
                + "\nSummarize the context in three points.",
            )
        )

    results = []
    for name, prompt in cases:
        rendered = apply_chat_template(
            processor,
            model.config,
            prompt,
            num_images=0,
            enable_thinking=False,
        )
        token_ids = []
        chunks = []
        started = time.perf_counter()
        last = None
        for response in stream_generate(
            model,
            processor,
            rendered,
            max_tokens=args.max_tokens,
            temperature=0.0,
            prefill_step_size=args.prefill_step_size,
            stopping_criteria=lambda _tokens: False,
            verbose=False,
        ):
            last = response
            if response.token is not None:
                token_ids.append(int(response.token))
            if response.text:
                chunks.append(response.text)
        elapsed = time.perf_counter() - started
        if last is None:
            raise RuntimeError(f"case {name} generated no responses")
        result = {
            "name": name,
            "prompt_tokens": int(last.prompt_tokens),
            "generation_tokens": int(last.generation_tokens),
            "prompt_tps": float(last.prompt_tps),
            "generation_tps": float(last.generation_tps),
            "elapsed_seconds": elapsed,
            "finish_reason": last.finish_reason,
            "token_ids": token_ids,
            "text": "".join(chunks),
            "mlx_peak_gib": mx.get_peak_memory() / 2**30,
            "rss_peak_gib": _rss_gib(),
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        results.append(result)

    report = {
        "format": "ai2apps-qwen38-next-full-baseline-v1",
        "checkpoint": str(checkpoint),
        "platform": platform.platform(),
        "load_seconds": load_seconds,
        "mlx_peak_gib": mx.get_peak_memory() / 2**30,
        "rss_peak_gib": _rss_gib(),
        "prefill_step_size": args.prefill_step_size,
        "max_tokens": args.max_tokens,
        "cases": results,
    }
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": report}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
