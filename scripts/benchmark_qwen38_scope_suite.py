#!/usr/bin/env python3
"""Run one held-out prompt per Scope through Qwen3.8 Cached-MoE."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_samples(path: Path, split: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    selected = {}
    for sample in payload["samples"]:
        if sample["split"] == split and sample["scope"] not in selected:
            selected[str(sample["scope"])] = sample
    return [selected[name] for name in sorted(selected)]


def _prompt(sample: dict[str, Any]) -> str:
    if len(sample["messages"]) == 1:
        return str(sample["messages"][0]["content"])
    return "\n".join(
        f"{message['role']}: {message['content']}" for message in sample["messages"]
    )


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "calls",
        "hit_calls",
        "miss_calls",
        "prefill_calls",
        "experts_loaded",
        "bytes_loaded",
        "read_seconds",
        "sync_seconds",
    )
    return {key: after[key] - before[key] for key in keys}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scope-profile", type=Path)
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--slots", type=int, default=224)
    parser.add_argument("--hot-slots", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--prefill-step-size", type=int, default=2048)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite report: {args.output}")

    checkpoint = args.checkpoint.expanduser().resolve()
    store = args.store.expanduser().resolve()
    dataset = args.dataset.expanduser().resolve()
    os.environ["OMLX_QWEN4_DYNAMIC_STORE"] = str(store)
    os.environ["OMLX_QWEN4_DYNAMIC_SLOTS"] = str(args.slots)
    os.environ["OMLX_QWEN4_HOT_SLOTS"] = str(args.hot_slots)
    os.environ["OMLX_QWEN4_L1_PROMOTIONS_PER_LAYER"] = "0"
    os.environ["OMLX_QWEN4_DYNAMIC_IO_WORKERS"] = "4"
    os.environ["OMLX_QWEN4_PREFILL_RESIDENT_FIRST"] = "0"
    if args.scope_profile:
        os.environ["OMLX_QWEN4_SCOPE_PROFILE"] = str(
            args.scope_profile.expanduser().resolve()
        )

    import mlx.core as mx

    from omlx.patches.qwen38_next_cache import (
        apply_qwen4_rmsnorm_compat_patch,
        get_qwen4_dynamic_cache,
        qwen4_dynamic_safetensors_on_load,
    )
    from omlx.patches.qwen38_next_cache import runtime as qwen_runtime

    apply_qwen4_rmsnorm_compat_patch()
    from mlx_vlm import load
    from mlx_vlm.generate import stream_generate
    from mlx_vlm.prompt_utils import apply_chat_template

    mx.reset_peak_memory()
    load_started = time.perf_counter()
    with qwen4_dynamic_safetensors_on_load(checkpoint):
        model, processor = load(str(checkpoint), lazy=False, strict=True)
    load_seconds = time.perf_counter() - load_started
    cache = get_qwen4_dynamic_cache(str(store))

    results = []
    for sample in _load_samples(dataset, args.split):
        scope = str(sample["scope"])
        os.environ["OMLX_QWEN4_SCOPE"] = scope
        qwen_runtime._scope_layers.cache_clear()
        rendered = apply_chat_template(
            processor,
            model.config,
            _prompt(sample),
            num_images=0,
            enable_thinking=False,
        )
        before = cache.stats().copy()
        started = time.perf_counter()
        token_ids = []
        text_parts = []
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
            text_parts.append(response.text or "")
        if last is None:
            raise RuntimeError(f"scope {scope} generated no tokens")
        after = cache.stats().copy()
        row = {
            "scope": scope,
            "sample_id": sample["id"],
            "prompt_tokens": int(last.prompt_tokens),
            "generation_tokens": int(last.generation_tokens),
            "prompt_tps": float(last.prompt_tps),
            "generation_tps": float(last.generation_tps),
            "elapsed_seconds": time.perf_counter() - started,
            "token_ids": token_ids,
            "text": "".join(text_parts),
            "cache": _delta(after, before),
            "mlx_peak_gib": mx.get_peak_memory() / 2**30,
        }
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    report = {
        "format": "omlx-qwen38-next-scope-live-suite",
        "version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "checkpoint": str(checkpoint),
        "store": str(store),
        "dataset": str(dataset),
        "split": args.split,
        "scope_profile": (
            str(args.scope_profile.expanduser().resolve())
            if args.scope_profile
            else None
        ),
        "slots": args.slots,
        "hot_slots": args.hot_slots,
        "max_tokens": args.max_tokens,
        "load_seconds": load_seconds,
        "mlx_peak_gib": mx.get_peak_memory() / 2**30,
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(report, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({"output": str(args.output), "cases": len(results)}))


if __name__ == "__main__":
    main()
