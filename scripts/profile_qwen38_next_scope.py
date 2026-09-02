#!/usr/bin/env python3
"""Build Qwen3.8 Flash Next Scope profiles from the shared DMoE dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_rows(path: Path, split: str) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text())
    rows: dict[str, list[dict[str, Any]]] = {}
    for sample in payload["samples"]:
        if sample["split"] == split:
            rows.setdefault(str(sample["scope"]), []).append(sample)
    return rows


def _sample_text(sample: dict[str, Any]) -> str:
    turns = "\n".join(
        f"{message['role']}: {message['content']}" for message in sample["messages"]
    )
    return f"[sample {sample['id']}]\n{turns}"


def _pack_scope(
    processor: Any,
    model_config: Any,
    samples: list[dict[str, Any]],
    token_limit: int,
    samples_per_pack: int | None,
) -> list[tuple[list[str], str, int]]:
    from mlx_vlm.prompt_utils import apply_chat_template

    prefix = (
        "下面是同一知识领域的一组独立问题。请归纳它们需要的知识与推理方式，"
        "再选择其中有代表性的要点作答。\n\n"
    )

    def render(items: list[dict[str, Any]]) -> tuple[str, int]:
        content = prefix + "\n\n".join(_sample_text(item) for item in items)
        prompt = apply_chat_template(
            processor,
            model_config,
            content,
            num_images=0,
            enable_thinking=False,
        )
        return prompt, len(processor.tokenizer.encode(prompt))

    packs: list[tuple[list[str], str, int]] = []
    current: list[dict[str, Any]] = []
    for sample in samples:
        candidate = [*current, sample]
        prompt, tokens = render(candidate)
        if current and (
            tokens > token_limit
            or (
                samples_per_pack is not None
                and len(candidate) > samples_per_pack
            )
        ):
            previous_prompt, previous_tokens = render(current)
            packs.append(
                ([str(item["id"]) for item in current], previous_prompt, previous_tokens)
            )
            current = [sample]
        else:
            current = candidate
    if current:
        prompt, tokens = render(current)
        if tokens > token_limit:
            raise ValueError(f"one Scope sample renders to {tokens} tokens")
        packs.append(([str(item["id"]) for item in current], prompt, tokens))
    return packs


def _numeric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "calls",
        "hit_calls",
        "miss_calls",
        "prefill_calls",
        "experts_loaded",
        "bytes_loaded",
        "read_seconds",
        "patch_seconds",
        "sync_seconds",
    )
    return {key: after[key] - before[key] for key in keys}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("expert_store", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--split", choices=("train", "validation", "test"), default="train"
    )
    parser.add_argument("--scope", action="append")
    parser.add_argument("--max-samples-per-scope", type=int)
    parser.add_argument("--samples-per-pack", type=int, default=10)
    parser.add_argument("--pack-token-limit", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--io-workers", type=int, default=4)
    parser.add_argument("--slots", type=int, default=224)
    parser.add_argument("--hot-slots", type=int, default=10)
    parser.add_argument("--prefill-step-size", type=int, default=2048)
    args = parser.parse_args()
    if args.output.expanduser().exists():
        raise FileExistsError(f"refusing to overwrite Scope artifact: {args.output}")

    checkpoint = args.checkpoint.expanduser().resolve()
    store = args.expert_store.expanduser().resolve()
    dataset = args.dataset.expanduser().resolve()
    output = args.output.expanduser().resolve()
    os.environ["OMLX_QWEN4_DYNAMIC_STORE"] = str(store)
    os.environ["OMLX_QWEN4_DYNAMIC_SLOTS"] = str(args.slots)
    os.environ["OMLX_QWEN4_HOT_SLOTS"] = str(args.hot_slots)
    os.environ["OMLX_QWEN4_L1_PROMOTIONS_PER_LAYER"] = "0"
    os.environ["OMLX_QWEN4_DYNAMIC_IO_WORKERS"] = str(args.io_workers)
    os.environ["OMLX_QWEN4_PREFILL_RESIDENT_FIRST"] = "0"

    import mlx.core as mx

    from omlx.patches.glm5_next_cache.scope_profile import Glm5ScopeCollector
    from omlx.patches.qwen38_next_cache import (
        apply_qwen4_rmsnorm_compat_patch,
        get_qwen4_dynamic_cache,
        qwen4_dynamic_safetensors_on_load,
    )

    apply_qwen4_rmsnorm_compat_patch()
    from mlx_vlm import load
    from mlx_vlm.generate import stream_generate

    with qwen4_dynamic_safetensors_on_load(checkpoint):
        model, processor = load(str(checkpoint), lazy=False, strict=True)
    dynamic = get_qwen4_dynamic_cache(str(store))
    collector = Glm5ScopeCollector(num_experts=512, capacity=args.slots)
    dynamic.set_route_observer(collector.capture)

    rows = _load_rows(dataset, args.split)
    selected_scopes = args.scope or sorted(rows)
    unknown = sorted(set(selected_scopes) - set(rows))
    if unknown:
        raise ValueError(f"dataset has no requested scopes: {unknown}")

    measurements = []
    started_all = time.perf_counter()
    try:
        for scope in selected_scopes:
            samples = rows[scope]
            if args.max_samples_per_scope is not None:
                samples = samples[: args.max_samples_per_scope]
            packs = _pack_scope(
                processor,
                model.config,
                samples,
                args.pack_token_limit,
                args.samples_per_pack,
            )
            for pack_index, (sample_ids, rendered, prompt_tokens) in enumerate(packs):
                before = dynamic.stats().copy()
                started = time.perf_counter()
                last = None
                generated = 0
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
                    generated += response.token is not None
                    collector.drain(scope)
                collector.drain(scope)
                if last is None:
                    raise RuntimeError(f"scope {scope} pack {pack_index} generated none")
                collector.finish_sample(
                    scope, int(last.prompt_tokens), source_samples=len(sample_ids)
                )
                after = dynamic.stats().copy()
                measurement = {
                    "scope": scope,
                    "pack": pack_index,
                    "sample_ids": sample_ids,
                    "prompt_tokens": int(last.prompt_tokens),
                    "generated_tokens": generated,
                    "prompt_tps": float(last.prompt_tps),
                    "generation_tps": float(last.generation_tps),
                    "seconds": time.perf_counter() - started,
                    "cache": _numeric_delta(after, before),
                    "mlx_peak_gib": mx.get_peak_memory() / 2**30,
                }
                measurements.append(measurement)
                print(json.dumps(measurement, ensure_ascii=False), flush=True)
    finally:
        dynamic.set_route_observer(None)

    profile = collector.build(
        metadata={
            "created_utc": datetime.now(UTC).isoformat(),
            "checkpoint": str(checkpoint),
            "expert_store": str(store),
            "dataset": str(dataset),
            "dataset_sha256": _sha256(dataset),
            "split": args.split,
            "selected_scopes": selected_scopes,
            "max_samples_per_scope": args.max_samples_per_scope,
            "samples_per_pack": args.samples_per_pack,
            "pack_token_limit": args.pack_token_limit,
            "decode_tokens_per_pack": args.max_tokens,
            "prefill_step_size": args.prefill_step_size,
            "io_workers": args.io_workers,
            "slots": args.slots,
            "hot_slots": args.hot_slots,
            "elapsed_seconds": time.perf_counter() - started_all,
            "measurements": measurements,
            "status": "bootstrap",
            "model_family": "qwen3.8-flash-next",
        }
    )
    profile["format"] = "omlx-qwen38-next-dynamic-scope-profile"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        json.dump(profile, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({"output": str(output), "scopes": selected_scopes}))


if __name__ == "__main__":
    main()
