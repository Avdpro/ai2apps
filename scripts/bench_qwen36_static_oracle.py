#!/usr/bin/env python3
"""Measure Qwen's fail-closed, zero-miss Arena decode ceiling."""

from __future__ import annotations

import argparse
import asyncio
import gc
import hashlib
import json
import time
from pathlib import Path

import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model")
    parser.add_argument("profile")
    parser.add_argument("store")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope", default="coding")
    parser.add_argument("--experts", type=int, default=120)
    parser.add_argument("--tail", type=int, default=24)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--warmup-rounds", type=int, default=3)
    parser.add_argument("--max-prime-attempts", type=int, default=512)
    parser.add_argument("--logits-reference", type=Path)
    parser.add_argument(
        "--compact-slab",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument(
        "--prompt", default="Explain in one sentence why mmap is useful."
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.qwen36_arena import Qwen36ArenaEngine
    from omlx.patches.qwen3_6_flesh.arena_cache import get_qwen36_decode_arena
    from omlx.patches.qwen3_6_flesh.model_patch import (
        Qwen36StrictArenaMiss,
        begin_qwen36_strict_arena_run,
        set_qwen36_parity_observer,
        validate_qwen36_strict_arena_run,
    )
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )

    configure_qwen36_scope_policy(
        args.profile,
        args.scope,
        args.store,
        args.experts,
        backend="arena",
        arena_tail_slots=args.tail,
    )
    engine = Qwen36ArenaEngine(args.model)
    try:
        mx.reset_peak_memory()
        await engine.start()
        arena = get_qwen36_decode_arena(str(Path(args.store).resolve()))
        capacity = args.experts + args.tail
        oracle_required = [set() for _ in range(40)]
        cache_nonce = f"qwen36-static-oracle-{time.time_ns()}"
        original_prepare = engine._prepare_request

        async def isolated_prepare(prompt, kwargs):
            await original_prepare(prompt, kwargs)
            kwargs["cache_extra_keys"] = (
                *tuple(kwargs.get("cache_extra_keys") or ()),
                cache_nonce,
            )

        # Benchmark runs must never restore a persistent KV generated with a
        # different physical expert layout.
        engine._prepare_request = isolated_prepare

        def activate_oracle() -> int:
            l1_layout: list[tuple[int, ...]] = []
            tail_layout: list[tuple[int, ...]] = []
            for layer, required in enumerate(oracle_required):
                if len(required) > capacity:
                    raise RuntimeError(
                        f"layer {layer} oracle needs {len(required)} experts, "
                        f"capacity={capacity}"
                    )
                current = arena.expert_ids(layer)
                ordered = [*sorted(required)]
                ordered.extend(expert for expert in current if expert not in required)
                ordered.extend(expert for expert in range(256) if expert not in ordered)
                oracle = tuple(ordered[:capacity])
                l1_layout.append(oracle[: args.experts])
                tail_layout.append(oracle[args.experts :])
            changed = engine._qwen_adaptive.bank.activate(
                l1_layout, mutable_layout=tail_layout
            )
            # Adaptive-Off normally restores the semantic scope L1 before
            # every request. Pin the offline oracle layout instead, while the
            # existing Arena metadata keeps the sealed Tail unchanged.
            frozen_l1 = tuple(l1_layout)
            engine._qwen_adaptive._scope_layout = (
                lambda _scope, layout=frozen_l1: list(layout)
            )
            engine._qwen_adaptive.base_layout = list(frozen_l1)
            return changed

        warmup_rounds = []
        for round_index in range(args.warmup_rounds):
            routes = [set() for _ in range(40)]

            def observe(block, x, inds, _scores, _routed, _output):
                if int(x.shape[-2]) == 1:
                    routes[block.scope_layer].update(
                        int(value) for value in inds.reshape(-1).tolist()
                    )

            set_qwen36_parity_observer(observe)
            warmup = await engine.generate(
                args.prompt,
                # The scheduler may submit the logits-producing step after
                # the last emitted token. Seal one extra deterministic step
                # so the strict transaction also covers that in-flight graph.
                max_tokens=args.max_tokens + 1,
                temperature=0.0,
                top_p=1.0,
                skip_cache_store=True,
                flesh_scope=args.scope,
                flesh_l1_mode="off",
            )
            set_qwen36_parity_observer(None)

            for layer, required in enumerate(routes):
                oracle_required[layer].update(required)
            union_sizes = [len(required) for required in oracle_required]
            changed = activate_oracle()
            warmup_rounds.append(
                {
                    "round": round_index + 1,
                    "changed_layers": changed,
                    "text_sha256": hashlib.sha256(warmup.text.encode()).hexdigest(),
                    "decode_union_max": max(union_sizes),
                }
            )

        compact_loader = None
        if args.compact_slab:
            from omlx.patches.qwen3_6_flesh.scope_cache import (
                get_qwen36_fallback_loader,
            )

            compact_loader = get_qwen36_fallback_loader(
                str(Path(args.store).resolve())
            )

            def seal_compact_layers(layers=range(40)) -> None:
                for layer in layers:
                    ids = tuple(sorted(oracle_required[layer]))
                    if not ids:
                        raise RuntimeError(f"layer {layer} has an empty oracle slab")
                    block = engine._model.language_model.model.layers[layer].mlp
                    switch, ids = compact_loader.build_switch(
                        layer, list(ids), block.switch_mlp
                    )
                    block.switch_mlp = switch
                    block.scope_expert_ids = ids
                    block.scope_protected_expert_ids = ids
                    lookup = [-1] * 256
                    for slot, expert_id in enumerate(ids):
                        lookup[expert_id] = slot
                    block.scope_expert_to_slot_values = tuple(lookup)
                    block.scope_expert_to_slot_device = mx.array(
                        lookup, dtype=mx.int32
                    )
                mx.synchronize()

            seal_compact_layers()

            async def fixed_oracle_prepare(_prompt, kwargs):
                for key in ("flesh_scope", "flesh_l1_mode", "flesh_session_id"):
                    kwargs.pop(key, None)
                kwargs["cache_extra_keys"] = (cache_nonce,)

            engine._prepare_request = fixed_oracle_prepare
            gc.collect()
            mx.clear_cache()

        loop = asyncio.get_running_loop()
        mlx_executor = engine._engine.engine._mlx_executor
        prime_attempts = []
        for attempt in range(args.max_prime_attempts):
            begin_qwen36_strict_arena_run()
            try:
                await engine.generate(
                    args.prompt,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                    skip_cache_store=True,
                    flesh_scope=args.scope,
                    flesh_l1_mode="off",
                )
                await loop.run_in_executor(
                    mlx_executor, validate_qwen36_strict_arena_run
                )
                break
            except Qwen36StrictArenaMiss as miss:
                oracle_required[miss.layer].update(miss.expert_ids)
                if compact_loader is None:
                    activate_oracle()
                else:
                    seal_compact_layers((miss.layer,))
                prime_attempts.append(
                    {
                        "attempt": attempt + 1,
                        "layer": miss.layer,
                        "expert_ids": list(miss.expert_ids),
                    }
                )
                if (attempt + 1) % 10 == 0:
                    print(
                        f"oracle prime {attempt + 1}: layer={miss.layer} "
                        f"max_union={max(len(ids) for ids in oracle_required)}",
                        flush=True,
                    )
        else:
            raise RuntimeError("Qwen static oracle did not converge")

        baseline = arena.stats()
        runs = []
        for index in range(args.repeat):
            begin_qwen36_strict_arena_run()
            started = time.perf_counter()
            try:
                output = await engine.generate(
                    args.prompt,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                    skip_cache_store=True,
                    flesh_scope=args.scope,
                    flesh_l1_mode="off",
                )
                generation_finished = time.perf_counter()
                misses = await loop.run_in_executor(
                    mlx_executor, validate_qwen36_strict_arena_run
                )
            except BaseException:
                try:
                    await loop.run_in_executor(
                        mlx_executor, validate_qwen36_strict_arena_run
                    )
                except RuntimeError:
                    pass
                raise
            finished = time.perf_counter()
            decode_seconds = (
                generation_finished - output.first_token_at
                if output.first_token_at is not None
                else None
            )
            runs.append(
                {
                    "run": index + 1,
                    "completion_tokens": output.completion_tokens,
                    "generation_wall_seconds": generation_finished - started,
                    "validated_wall_seconds": finished - started,
                    "validation_seconds": finished - generation_finished,
                    "decode_seconds": decode_seconds,
                    "decode_tps": (
                        (output.completion_tokens - 1) / decode_seconds
                        if decode_seconds and output.completion_tokens > 1
                        else None
                    ),
                    "zero_runtime_misses": misses == 0,
                    "text_sha256": hashlib.sha256(output.text.encode()).hexdigest(),
                }
            )

        top10_parity = None
        if args.logits_reference is not None:
            reference = np.load(args.logits_reference)
            reference_keys = sorted(reference.files)
            scheduler = engine._engine.engine.scheduler
            original_build = scheduler._build_sampler_and_processors
            oracle_logits: list[np.ndarray] = []

            def capture_build(sampling_params, request=None):
                sampler, processors = original_build(sampling_params, request)

                def capture_sampler(logits):
                    current = logits.astype(mx.float32)
                    mx.eval(current)
                    oracle_logits.append(np.asarray(current))
                    return sampler(logits)

                return capture_sampler, processors

            scheduler._build_sampler_and_processors = capture_build
            begin_qwen36_strict_arena_run()
            try:
                parity_output = await engine.generate(
                    args.prompt,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                    skip_cache_store=True,
                    flesh_scope=args.scope,
                    flesh_l1_mode="off",
                )
                replay_misses = await loop.run_in_executor(
                    mlx_executor, validate_qwen36_strict_arena_run
                )
            except BaseException:
                try:
                    await loop.run_in_executor(
                        mlx_executor, validate_qwen36_strict_arena_run
                    )
                except RuntimeError:
                    pass
                raise
            finally:
                scheduler._build_sampler_and_processors = original_build

            if len(reference_keys) != len(oracle_logits):
                raise RuntimeError(
                    "logits reference length does not match oracle decode: "
                    f"{len(reference_keys)} != {len(oracle_logits)}"
                )

            step_results = []
            for index, (key, actual) in enumerate(
                zip(reference_keys, oracle_logits, strict=True)
            ):
                expected = reference[key]
                expected_order = np.argsort(expected[0])[-10:][::-1]
                actual_order = np.argsort(actual[0])[-10:][::-1]
                step_results.append(
                    {
                        "step": index,
                        "ordered_equal": bool(
                            np.array_equal(expected_order, actual_order)
                        ),
                        "expected": expected_order.tolist(),
                        "actual": actual_order.tolist(),
                        "max_abs_logit_error": float(
                            np.max(np.abs(expected - actual))
                        ),
                    }
                )
            top10_parity = {
                "reference": str(args.logits_reference),
                "steps": len(step_results),
                "zero_runtime_misses": replay_misses == 0,
                "text_sha256": hashlib.sha256(
                    parity_output.text.encode()
                ).hexdigest(),
                "ordered_top10_equal": all(
                    step["ordered_equal"] for step in step_results
                ),
                "max_abs_logit_error": max(
                    step["max_abs_logit_error"] for step in step_results
                ),
                "step_results": step_results,
            }
        final = arena.stats()
        report = {
            "format": "dynamoe-qwen36-static-oracle",
            "version": 1,
            "scope": args.scope,
            "initial_physical_experts": capacity,
            "compact_slab": args.compact_slab,
            "compact_layer_sizes": [
                len(required) for required in oracle_required
            ],
            "decode_union_sizes": union_sizes,
            "decode_union_max": max(union_sizes),
            "decode_union_mean": sum(union_sizes) / len(union_sizes),
            "warmup_tokens": warmup.completion_tokens,
            "warmup_rounds": warmup_rounds,
            "prime_attempts": prime_attempts,
            "warmup_text_sha256": hashlib.sha256(warmup.text.encode()).hexdigest(),
            "runs": runs,
            "top10_parity": top10_parity,
            "arena_delta": {
                key: final[key] - baseline[key]
                for key in ("patch_calls", "experts_loaded", "bytes_loaded")
            },
            "peak_mlx_gb": mx.get_peak_memory() / (1024**3),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    finally:
        set_qwen36_parity_observer(None)
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
