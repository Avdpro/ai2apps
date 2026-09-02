#!/usr/bin/env python3
"""Build a GLM-5.3 Flash Scope bootstrap from labeled prompts."""

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
    if "samples" in payload:
        rows: dict[str, list[dict[str, Any]]] = {}
        for sample in payload["samples"]:
            if sample["split"] == split:
                rows.setdefault(str(sample["scope"]), []).append(sample)
        return rows
    return {
        str(scope): [
            {
                "id": f"{scope}-{index:02d}",
                "scope": scope,
                "messages": [{"role": "user", "content": prompt}],
            }
            for index, prompt in enumerate(prompts)
        ]
        for scope, prompts in payload["scopes"].items()
    }


def _sample_text(sample: dict[str, Any]) -> str:
    turns = "\n".join(
        f"{message['role']}: {message['content']}" for message in sample["messages"]
    )
    return f"[sample {sample['id']}]\n{turns}"


def _pack_scope(
    tokenizer: Any,
    samples: list[dict[str, Any]],
    token_limit: int,
    samples_per_pack: int | None = None,
) -> list[tuple[list[str], str, int]]:
    prefix = (
        "下面是同一知识领域的一组独立问题。请归纳它们需要的知识与推理方式，"
        "再选择其中有代表性的要点作答。\n\n"
    )
    packs: list[tuple[list[str], str, int]] = []
    current: list[dict[str, Any]] = []

    def render(rows: list[dict[str, Any]]) -> tuple[str, int]:
        content = prefix + "\n\n".join(_sample_text(row) for row in rows)
        prompt = tokenizer.apply_chat_template(
            [{"role": "user", "content": content}],
            tokenize=False,
            add_generation_prompt=True,
        )
        return prompt, len(tokenizer.encode(prompt))

    for sample in samples:
        candidate = [*current, sample]
        prompt, tokens = render(candidate)
        if current and (
            tokens > token_limit
            or (samples_per_pack is not None and len(candidate) > samples_per_pack)
        ):
            previous_prompt, previous_tokens = render(current)
            packs.append(
                ([str(row["id"]) for row in current], previous_prompt, previous_tokens)
            )
            current = [sample]
        else:
            current = candidate
    if current:
        prompt, tokens = render(current)
        if tokens > token_limit:
            raise ValueError(
                f"one Scope sample renders to {tokens} tokens, above {token_limit}"
            )
        packs.append(([str(row["id"]) for row in current], prompt, tokens))
    return packs


def _numeric_delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return {
        key: after[key] - before[key]
        for key in (
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
    }


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
    parser.add_argument(
        "--samples-per-pack",
        type=int,
        help="Bound independent prompts per generation pack to retain route diversity.",
    )
    parser.add_argument("--pack-token-limit", type=int, default=2048)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--io-workers", type=int, default=4)
    parser.add_argument("--slots", type=int, default=80)
    args = parser.parse_args()
    if min(args.pack_token_limit, args.max_tokens, args.io_workers, args.slots) <= 0:
        parser.error("token, worker, and slot arguments must be positive")
    if not 8 <= args.slots <= 96:
        parser.error("--slots must be in [8, 96]")
    if args.max_samples_per_scope is not None and args.max_samples_per_scope <= 0:
        parser.error("--max-samples-per-scope must be positive")
    if args.samples_per_pack is not None and args.samples_per_pack <= 0:
        parser.error("--samples-per-pack must be positive")

    checkpoint = args.checkpoint.expanduser().resolve()
    store = args.expert_store.expanduser().resolve()
    dataset = args.dataset.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Scope artifact: {output}")
    os.environ["OMLX_GLM5_DYNAMIC_STORE"] = str(store)
    os.environ["OMLX_GLM5_DYNAMIC_SLOTS"] = str(args.slots)
    os.environ["OMLX_GLM5_TAIL_SLOTS"] = "0"
    os.environ["OMLX_GLM5_VISION_L1_RESERVE_SLOTS"] = "0"
    os.environ["OMLX_GLM5_DYNAMIC_IO_WORKERS"] = str(args.io_workers)

    import mlx.core as mx
    from mlx_vlm.generate import generate_step
    from mlx_vlm.utils import load_model
    from transformers import AutoTokenizer

    from omlx.patches.glm5_next_cache.runtime import (
        get_glm5_dynamic_cache,
        glm5_dynamic_safetensors_on_load,
    )
    from omlx.patches.glm5_next_cache.scope_profile import Glm5ScopeCollector
    from omlx.utils.model_loading import maybe_apply_pre_load_patches

    tokenizer = AutoTokenizer.from_pretrained(checkpoint)
    maybe_apply_pre_load_patches(str(checkpoint), for_vlm=True)
    with glm5_dynamic_safetensors_on_load(checkpoint):
        model = load_model(checkpoint, lazy=False, strict=True)

    rows = _load_rows(dataset, args.split)
    selected_scopes = args.scope or sorted(rows)
    unknown = sorted(set(selected_scopes) - set(rows))
    if unknown:
        raise ValueError(f"dataset has no requested scopes: {unknown}")
    collector = Glm5ScopeCollector(capacity=args.slots)
    dynamic = get_glm5_dynamic_cache(str(store))
    dynamic.set_route_observer(collector.capture)
    measurements = []
    started_all = time.perf_counter()
    try:
        for scope in selected_scopes:
            samples = rows[scope]
            if args.max_samples_per_scope is not None:
                samples = samples[: args.max_samples_per_scope]
            packs = _pack_scope(
                tokenizer,
                samples,
                args.pack_token_limit,
                args.samples_per_pack,
            )
            for pack_index, (sample_ids, rendered, prompt_tokens) in enumerate(packs):
                input_ids = mx.array([tokenizer.encode(rendered)], dtype=mx.int32)
                before = dynamic.stats().copy()
                started = time.perf_counter()
                generated = 0
                for _token, _ in generate_step(
                    input_ids,
                    model,
                    pixel_values=None,
                    mask=None,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    prefill_step_size=None,
                ):
                    generated += 1
                    collector.drain(scope)
                collector.drain(scope)
                elapsed = time.perf_counter() - started
                collector.finish_sample(
                    scope,
                    prompt_tokens,
                    source_samples=len(sample_ids),
                )
                after = dynamic.stats().copy()
                measurement = {
                    "scope": scope,
                    "pack": pack_index,
                    "sample_ids": sample_ids,
                    "prompt_tokens": prompt_tokens,
                    "generated_tokens": generated,
                    "seconds": elapsed,
                    "cache": _numeric_delta(after, before),
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
            "io_workers": args.io_workers,
            "slots": args.slots,
            "elapsed_seconds": time.perf_counter() - started_all,
            "measurements": measurements,
            "status": "bootstrap",
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        json.dump(profile, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({"output": str(output), "scopes": selected_scopes}))


if __name__ == "__main__":
    main()
