#!/usr/bin/env python3
"""Benchmark one scope-matched DeepSeek V4 validation sample in oMLX."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sys
import time
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("sample_id")
    parser.add_argument("--gen", type=int, default=32)
    parser.add_argument("--warmup-sample-id")
    parser.add_argument("--warmup-gen", type=int, default=1)
    parser.add_argument(
        "--runtime-scope",
        help="Explicit profile scope for benchmarking a narrower alias of the dataset scope",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_encoder(model: Path):
    path = model / "encoding" / "encoding_dsv4.py"
    spec = importlib.util.spec_from_file_location("omlx_scope_matrix_encoding", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DeepSeek encoder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.encode_messages


async def _run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.admin.benchmark import _run_single_test
    from omlx.engine.batched import BatchedEngine
    from omlx.patches.deepseek_v4.scope_cache import get_scope_fallback_loader

    dataset = json.loads(args.dataset.read_text())
    samples = {sample["id"]: sample for sample in dataset["samples"]}
    sample = samples[args.sample_id]
    configured_scope = os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_NAME")
    expected_scope = args.runtime_scope or sample["scope"]
    if configured_scope != expected_scope:
        raise ValueError(
            f"configured scope {configured_scope!r} != expected runtime scope "
            f"{expected_scope!r}"
        )

    model = args.model.expanduser().resolve()
    engine = BatchedEngine(str(model))
    load_started = time.perf_counter()
    await engine.start()
    mx.clear_cache()
    load_seconds = time.perf_counter() - load_started
    encode_messages = _load_encoder(model)
    prompt = encode_messages(list(sample["messages"]), thinking_mode="chat")
    prompt_ids = engine.tokenizer.encode(prompt, add_special_tokens=False)

    store = os.environ["OMLX_DEEPSEEK_V4_EXPERT_STORE"]
    loader = get_scope_fallback_loader(store)
    if args.warmup_sample_id:
        warmup_sample = samples[args.warmup_sample_id]
        if warmup_sample["scope"] != sample["scope"]:
            raise ValueError("warmup sample must use the measured scope")
        warmup_prompt = encode_messages(
            list(warmup_sample["messages"]), thinking_mode="chat"
        )
        warmup_ids = engine.tokenizer.encode(warmup_prompt, add_special_tokens=False)
        await _run_single_test(engine, warmup_ids, args.warmup_gen, len(warmup_ids))
        loader.clear_hot()
        mx.clear_cache()
    before = loader.stats()
    try:
        result = await _run_single_test(engine, prompt_ids, args.gen, len(prompt_ids))
        after = loader.stats()
        cache_delta = {
            key: after[key] - before[key]
            for key in (
                "fallback_calls",
                "hot_only_calls",
                "transient_calls",
                "transient_experts_loaded",
                "decode_experts_loaded",
                "experts_loaded",
                "bytes_loaded",
                "load_seconds",
                "lossy_routes_replaced",
                "lossy_l3_misses_avoided",
                "lossy_l3_layers_avoided",
                "direct_load_calls",
                "direct_load_experts",
                "direct_load_bytes",
                "direct_load_seconds",
            )
        }
        payload = {
            "version": 1,
            "runtime": "omlx-scope-top60-hot8",
            "direct_l1_mode": os.environ.get("OMLX_MOE_DIRECT_L1", "auto"),
            "direct_prefill": os.environ.get("OMLX_DEEPSEEK_V4_DIRECT_PREFILL", "0"),
            "lossy_mode": os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "exact"),
            "lossy_threshold": os.environ.get(
                "OMLX_DEEPSEEK_V4_SCOPE_LOSSY_THRESHOLD", "0.10"
            ),
            "sample_id": sample["id"],
            "dataset_scope": sample["scope"],
            "scope": expected_scope,
            "language": sample["language"],
            "prompt_tokens": len(prompt_ids),
            "decode_steps": args.gen,
            "model_load_seconds": load_seconds,
            "ttft_ms": result["ttft_ms"],
            "prefill_tokens_per_second": result["processing_tps"],
            "decode_tokens_per_second": result["gen_tps"],
            "peak_memory_bytes": result["peak_memory_bytes"],
            "cache": cache_delta,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
    finally:
        await engine.stop()


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
