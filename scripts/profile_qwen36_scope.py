#!/usr/bin/env python3
"""Profile ten Qwen3.6/Ornith Scope banks with the full-resident model."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from functools import partial
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


def _render(tokenizer: Any, samples: list[dict[str, Any]]) -> tuple[str, int]:
    content = (
        "下面是同一知识领域的一组独立问题。请归纳它们需要的知识与推理方式，"
        "再选择其中有代表性的要点作答。\n\n"
        + "\n\n".join(_sample_text(item) for item in samples)
    )
    prompt = tokenizer.apply_chat_template(
        [{"role": "user", "content": content}],
        tokenize=False,
        add_generation_prompt=True,
    )
    return prompt, len(tokenizer.encode(prompt))


def _packs(
    tokenizer: Any,
    samples: list[dict[str, Any]],
    *,
    samples_per_pack: int,
    token_limit: int,
) -> list[tuple[list[dict[str, Any]], str, int]]:
    result = []
    current: list[dict[str, Any]] = []
    for sample in samples:
        candidate = [*current, sample]
        prompt, tokens = _render(tokenizer, candidate)
        if current and (len(candidate) > samples_per_pack or tokens > token_limit):
            previous_prompt, previous_tokens = _render(tokenizer, current)
            result.append((current, previous_prompt, previous_tokens))
            current = [sample]
        else:
            current = candidate
    if current:
        prompt, tokens = _render(tokenizer, current)
        if tokens > token_limit:
            raise ValueError(f"single Scope sample renders to {tokens} tokens")
        result.append((current, prompt, tokens))
    return result


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.batched import BatchedEngine
    from omlx.patches.qwen3_6_flesh.model_patch import (
        set_qwen36_route_profile_observer,
    )
    from omlx.patches.qwen3_6_flesh.scope_profile import Qwen36ScopeCollector

    dataset = args.dataset.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Scope profile: {output}")
    rows = _load_rows(dataset, args.split)
    scopes = args.scope or sorted(rows)
    engine = BatchedEngine(str(args.checkpoint.expanduser().resolve()))
    collector = Qwen36ScopeCollector()
    measurements = []
    started_all = time.perf_counter()
    try:
        # The load-time patch remains a no-op for full-resident inference
        # except while this explicit offline observer is installed.
        set_qwen36_route_profile_observer(collector.capture)
        await engine.start()
        for layer, decoder in enumerate(engine._model.language_model.model.layers):
            decoder.mlp.scope_layer = layer
        for scope in scopes:
            samples = rows[scope]
            if args.max_samples_per_scope is not None:
                samples = samples[: args.max_samples_per_scope]
            for pack_index, (items, prompt, prompt_tokens) in enumerate(
                _packs(
                    engine._tokenizer,
                    samples,
                    samples_per_pack=args.samples_per_pack,
                    token_limit=args.pack_token_limit,
                )
            ):
                started = time.perf_counter()
                result = await engine.generate(
                    prompt,
                    max_tokens=args.max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                    skip_cache_store=True,
                )
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    engine._engine.engine._mlx_executor,
                    partial(collector.drain, scope),
                )
                collector.finish(
                    scope,
                    samples=len(items),
                    prompt_tokens=int(result.prompt_tokens),
                    decode_tokens=int(result.completion_tokens),
                )
                row = {
                    "scope": scope,
                    "pack": pack_index,
                    "sample_ids": [str(item["id"]) for item in items],
                    "prompt_tokens": int(result.prompt_tokens),
                    "decode_tokens": int(result.completion_tokens),
                    "prompt_tps": float(result.prompt_tps),
                    "decode_tps": float(result.generation_tps),
                    "seconds": time.perf_counter() - started,
                    "mlx_peak_gib": mx.get_peak_memory() / 2**30,
                }
                measurements.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        set_qwen36_route_profile_observer(None)
        await engine.stop()

    profile = collector.build(
        metadata={
            "created_utc": datetime.now(UTC).isoformat(),
            "checkpoint": str(args.checkpoint.expanduser().resolve()),
            "dataset": str(dataset),
            "dataset_sha256": _sha256(dataset),
            "split": args.split,
            "scopes": scopes,
            "max_samples_per_scope": args.max_samples_per_scope,
            "samples_per_pack": args.samples_per_pack,
            "pack_token_limit": args.pack_token_limit,
            "decode_tokens_per_pack": args.max_tokens,
            "elapsed_seconds": time.perf_counter() - started_all,
            "measurements": measurements,
            "model_family": "ornith-1.5-qwen3.6",
            "status": "bootstrap",
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        json.dump(profile, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({"output": str(output), "scopes": scopes}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--split", default="train")
    parser.add_argument("--scope", action="append")
    parser.add_argument("--max-samples-per-scope", type=int, default=10)
    parser.add_argument("--samples-per-pack", type=int, default=5)
    parser.add_argument("--pack-token-limit", type=int, default=4096)
    parser.add_argument("--max-tokens", type=int, default=64)
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
