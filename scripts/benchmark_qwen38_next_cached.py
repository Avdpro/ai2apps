#!/usr/bin/env python3
"""Correctness and throughput benchmark for Qwen4 exact Cached-MoE."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("--slots", type=int, default=80)
    parser.add_argument("--hot-slots", type=int, default=0)
    parser.add_argument("--promotions", type=int, default=0)
    parser.add_argument("--promotion-enable-after", type=int, default=128)
    parser.add_argument(
        "--boost-mode",
        choices=(
            "natural",
            "turbo",
            "blast",
            "top7",
            "top6",
            "top5",
            "top4",
            "top3",
        ),
        default="natural",
    )
    parser.add_argument("--io-workers", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--prefill-step-size", type=int, default=512)
    parser.add_argument("--prefill-bank-slots", type=int, default=512)
    parser.add_argument(
        "--ple-mode",
        choices=("auto", "mmap", "resident", "disabled"),
        default="auto",
    )
    parser.add_argument("--long-repeat", type=int, default=0)
    parser.add_argument("--only-long", action="store_true")
    parser.add_argument("--single-short", action="store_true")
    parser.add_argument("--resident-first", action="store_true")
    parser.add_argument("--canonical-reuse", action="store_true")
    parser.add_argument("--retain-prefill-l1", action="store_true")
    parser.add_argument("--profile-output", type=Path)
    parser.add_argument("--scope-profile", type=Path)
    parser.add_argument("--scope", default="general")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    os.environ["OMLX_QWEN4_DYNAMIC_STORE"] = str(args.store.resolve())
    os.environ["OMLX_QWEN4_DYNAMIC_SLOTS"] = str(args.slots)
    os.environ["OMLX_QWEN4_HOT_SLOTS"] = str(args.hot_slots)
    os.environ["OMLX_QWEN4_L1_PROMOTIONS_PER_LAYER"] = str(args.promotions)
    os.environ["OMLX_QWEN4_L1_PROMOTION_ENABLE_AFTER"] = str(
        args.promotion_enable_after
    )
    os.environ["OMLX_QWEN4_DYNAMIC_IO_WORKERS"] = str(args.io_workers)
    os.environ["OMLX_GLM5_PREFILL_BANK_SLOTS"] = str(args.prefill_bank_slots)
    os.environ["OMLX_QWEN4_BOOST_MODE"] = args.boost_mode
    os.environ["OMLX_QWEN4_PLE_MODE"] = args.ple_mode
    os.environ["OMLX_QWEN4_PREFILL_RESIDENT_FIRST"] = (
        "1" if args.resident_first else "0"
    )
    os.environ["OMLX_QWEN4_PREFILL_CANONICAL_REUSE"] = (
        "1" if args.canonical_reuse else "0"
    )
    os.environ["OMLX_QWEN4_PREFILL_RETAIN_L1"] = (
        "1" if args.retain_prefill_l1 else "0"
    )
    if args.scope_profile:
        os.environ["OMLX_QWEN4_SCOPE_PROFILE"] = str(args.scope_profile.resolve())
        os.environ["OMLX_QWEN4_SCOPE"] = args.scope

    import mlx.core as mx
    from omlx.patches.qwen38_next_cache import (
        apply_qwen4_rmsnorm_compat_patch,
        get_qwen4_dynamic_cache,
        qwen4_dynamic_safetensors_on_load,
        set_qwen4_boost_mode,
    )
    from omlx.patches.glm5_next_cache.scope_profile import Glm5ScopeCollector

    apply_qwen4_rmsnorm_compat_patch()
    from mlx_vlm import load
    from mlx_vlm.generate import stream_generate
    from mlx_vlm.prompt_utils import apply_chat_template

    checkpoint = args.checkpoint.resolve()
    mx.reset_peak_memory()
    started = time.perf_counter()
    with qwen4_dynamic_safetensors_on_load(checkpoint):
        model, processor = load(str(checkpoint), lazy=False, strict=True)
    boost_layers = set_qwen4_boost_mode(model, args.boost_mode)
    load_seconds = time.perf_counter() - started
    cache = get_qwen4_dynamic_cache(str(args.store.resolve()))
    collector = (
        Glm5ScopeCollector(num_experts=512, capacity=args.slots)
        if args.profile_output
        else None
    )
    if collector is not None:
        cache.set_route_observer(collector.capture)

    base = (
        "Explain in plain English why a sparse mixture-of-experts model can "
        "use less computation per generated token."
    )
    cases = [] if args.only_long else [("cold-short", base)]
    if not args.only_long and not args.single_short:
        cases.append(("warm-short", base))
    if args.long_repeat:
        cases.append(
            (
                "warm-long",
                ("Context paragraph: " + base + "\n") * args.long_repeat
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
        token_ids, chunks = [], []
        last = None
        started = time.perf_counter()
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
            if (
                response.token is not None
                and len(token_ids) < int(response.generation_tokens)
            ):
                token_ids.append(int(response.token))
            chunks.append(response.text or "")
            if collector is not None:
                collector.drain(args.scope)
        if last is None:
            raise RuntimeError(f"case {name} generated no tokens")
        result = {
            "name": name,
            "prompt_tokens": int(last.prompt_tokens),
            "generation_tokens": int(last.generation_tokens),
            "prompt_tps": float(last.prompt_tps),
            "generation_tps": float(last.generation_tps),
            "elapsed_seconds": time.perf_counter() - started,
            "token_ids": token_ids,
            "text": "".join(chunks),
            "mlx_peak_gib": mx.get_peak_memory() / 2**30,
        }
        print(json.dumps(result, ensure_ascii=False), flush=True)
        results.append(result)
        if collector is not None:
            collector.drain(args.scope)
            collector.finish_sample(args.scope, int(last.prompt_tokens))

    boost_stats = {
        "routes_replaced": 0,
        "misses_before": 0,
        "misses_after": 0,
    }
    for decoder in model.language_model.model.layers:
        counters = getattr(decoder.mlp, "boost_stats", None)
        if counters is None:
            continue
        for key in boost_stats:
            boost_stats[key] += int(counters[key])
    boost_stats["misses_avoided"] = (
        boost_stats["misses_before"] - boost_stats["misses_after"]
    )

    if collector is not None:
        cache.set_route_observer(None)
        profile = collector.build(
            metadata={
                "created_utc": datetime.now(UTC).isoformat(),
                "checkpoint": str(checkpoint),
                "expert_store": str(args.store.resolve()),
                "source": "benchmark_qwen38_next_cached.py",
            }
        )
        args.profile_output.parent.mkdir(parents=True, exist_ok=True)
        args.profile_output.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
        )
    report = {
        "format": "ai2apps-qwen38-next-cached-baseline-v1",
        "checkpoint": str(checkpoint),
        "store": str(args.store.resolve()),
        "slots": args.slots,
        "hot_slots": args.hot_slots,
        "promotions": args.promotions,
        "promotion_enable_after": args.promotion_enable_after,
        "boost_mode": args.boost_mode,
        "ple_mode": args.ple_mode,
        "boost_layers": boost_layers,
        "boost": boost_stats,
        "io_workers": args.io_workers,
        "prefill_bank_slots": args.prefill_bank_slots,
        "resident_first": args.resident_first,
        "canonical_reuse": args.canonical_reuse,
        "retain_prefill_l1": args.retain_prefill_l1,
        "load_seconds": load_seconds,
        "mlx_peak_gib": mx.get_peak_memory() / 2**30,
        "cache": {
            key: getattr(cache, key)
            for key in (
                "calls",
                "hit_calls",
                "miss_calls",
                "prefill_calls",
                "experts_loaded",
                "bytes_loaded",
                "read_seconds",
                "sync_seconds",
                "direct_load_calls",
                "direct_load_bytes",
                "overlap_calls",
                "l1_promotions",
                "l1_promotion_bytes",
                "l1_promotion_seconds",
            )
        },
        "cases": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": report}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
