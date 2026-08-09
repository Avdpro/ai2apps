#!/usr/bin/env python3
"""Load a real Qwen3.6 checkpoint with a static Flesh bank and report shape/RSS."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import resource
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("profile")
    parser.add_argument("store")
    parser.add_argument("--scope", default="coding")
    parser.add_argument("--experts", type=int, default=96)
    parser.add_argument("--prompt")
    parser.add_argument("--chat-template", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=8)
    parser.add_argument("--full-resident", action="store_true")
    parser.add_argument(
        "--backend", choices=("flesh", "arena", "tiered"), default="flesh"
    )
    parser.add_argument("--arena-tail-slots", type=int, default=24)
    parser.add_argument("--omit-text", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.batched import BatchedEngine
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )

    mx.reset_peak_memory()
    if not args.full_resident:
        configure_qwen36_scope_policy(
            args.profile,
            args.scope,
            args.store,
            args.experts,
            backend=args.backend,
            arena_tail_slots=args.arena_tail_slots,
        )
    if args.backend == "arena" and not args.full_resident:
        from omlx.engine.qwen36_arena import Qwen36ArenaEngine

        engine = Qwen36ArenaEngine(args.model)
    elif args.backend == "tiered" and not args.full_resident:
        from omlx.engine.qwen36_tiered import Qwen36TieredEngine

        engine = Qwen36TieredEngine(args.model)
    elif args.backend == "flesh" and not args.full_resident:
        from omlx.engine.qwen36_flesh import Qwen36FleshEngine

        engine = Qwen36FleshEngine(args.model)
    else:
        engine = BatchedEngine(args.model)
    started = time.perf_counter()
    try:
        await engine.start()
        model = engine._model
        layers = model.language_model.model.layers
        physical = [
            int(layer.mlp.switch_mlp.down_proj.weight.shape[0]) for layer in layers
        ]
        tail_physical = [
            int(layer.mlp.tail_switch_mlp.down_proj.weight.shape[0])
            for layer in layers
            if hasattr(layer.mlp, "tail_switch_mlp")
        ]
        report = {
            "requested_max_tokens": args.max_tokens,
            "load_seconds": time.perf_counter() - started,
            "layers": len(layers),
            "physical_experts": sorted(set(physical)),
            "all_layers_match": all(
                value
                == args.experts
                + (
                    args.arena_tail_slots
                    if args.backend == "arena" and not args.full_resident
                    else 0
                )
                for value in physical
            ),
            "max_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024**3),
            "peak_mlx_gb": mx.get_peak_memory() / (1024**3),
        }
        if tail_physical:
            report["tail_physical_experts"] = sorted(set(tail_physical))
            report["all_layers_match"] = report["all_layers_match"] and all(
                value == args.arena_tail_slots for value in tail_physical
            )
        if args.prompt:
            prompt = args.prompt
            if args.chat_template:
                prompt = engine._tokenizer.apply_chat_template(
                    [{"role": "user", "content": prompt}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
            generated = time.perf_counter()
            output = await engine.generate(
                prompt,
                max_tokens=args.max_tokens,
                temperature=0.0,
                top_p=1.0,
                skip_cache_store=True,
            )
            finished = time.perf_counter()
            ttft = (
                output.first_token_at - generated
                if output.first_token_at is not None
                else None
            )
            decode_seconds = (
                finished - output.first_token_at
                if output.first_token_at is not None
                else None
            )
            report["generation"] = {
                "seconds": finished - generated,
                "ttft_seconds": ttft,
                "decode_seconds_after_first_token": decode_seconds,
                "prompt_tokens": output.prompt_tokens,
                "completion_tokens": output.completion_tokens,
                "prompt_tokens_per_second": output.prompt_tps,
                "generation_tokens_per_second": output.generation_tps,
                "derived_decode_tokens_per_second": (
                    (output.completion_tokens - 1) / decode_seconds
                    if decode_seconds and output.completion_tokens > 1
                    else None
                ),
                "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
            }
            if not args.omit_text:
                report["generation"]["text"] = output.text
                report["generation"]["token_ids"] = (
                    output.tokens
                    or engine._tokenizer.encode(
                        output.text, add_special_tokens=False
                    )
                )
            if not args.full_resident:
                if args.backend == "arena":
                    from omlx.patches.qwen3_6_flesh.arena_cache import (
                        get_qwen36_decode_arena,
                    )

                    report["generation"]["expert_store"] = (
                        get_qwen36_decode_arena(
                            str(Path(args.store).expanduser().resolve())
                        ).stats()
                    )
                elif args.backend == "tiered":
                    from omlx.patches.qwen3_6_flesh.tiered_cache import (
                        get_qwen36_tiered_cache,
                    )

                    report["generation"]["expert_store"] = (
                        get_qwen36_tiered_cache(
                            str(Path(args.store).expanduser().resolve())
                        ).stats()
                    )
                else:
                    from omlx.patches.qwen3_6_flesh.scope_cache import (
                        get_qwen36_fallback_loader,
                    )

                    report["generation"]["expert_store"] = (
                        get_qwen36_fallback_loader(
                            str(Path(args.store).expanduser().resolve())
                        ).stats()
                    )
                engine_stats = engine.get_stats().get("flesh", {})
                if "expert_store" in engine_stats:
                    report["generation"]["prefill_store"] = engine_stats[
                        "expert_store"
                    ]
                if "adaptive_l1" in engine_stats:
                    report["generation"]["adaptive_l1"] = engine_stats[
                        "adaptive_l1"
                    ]
            report["peak_mlx_gb"] = mx.get_peak_memory() / (1024**3)
        rendered = json.dumps(report, indent=2, sort_keys=True)
        if args.output:
            args.output.write_text(rendered)
        print(rendered)
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
