#!/usr/bin/env python3
"""Measure Decode overhead of reviewing all routed experts every N tokens."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any


BALANCED_MODES = ("off", "on", "on", "off", "off", "on")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("sample_id")
    parser.add_argument("--runtime-scope")
    parser.add_argument("--gen", type=int, default=128)
    parser.add_argument("--interval", type=int, default=16)
    parser.add_argument("--warmup-gen", type=int, default=32)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _load_encoder(model: Path):
    path = model / "encoding" / "encoding_dsv4.py"
    spec = importlib.util.spec_from_file_location("omlx_scope_review_encoding", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DeepSeek encoder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.encode_messages


def _accumulate(
    rows: list[list[int]], layers: list[int], counters: dict[int, Counter[int]]
) -> None:
    for layer, row in zip(layers, rows, strict=True):
        counters[layer].update(row)


class _ReviewCollector:
    def __init__(self, interval: int, final_score_layer: int = 42) -> None:
        if interval < 1:
            raise ValueError("--interval must be >= 1")
        self.interval = interval
        self.final_score_layer = final_score_layer
        self.seen_prefill = False
        self.skip_singleton_rounds = 0
        self.decode_steps = 0
        self.pending: list[tuple[int, Any]] = []
        self.counters = {layer: Counter() for layer in range(3, 43)}
        self.reviews = 0
        self.reviewed_ids = 0
        self.review_seconds = 0.0
        self.trace: list[list[list[int]]] = []

    def capture(self, layer: int, inds: Any) -> None:
        length = int(inds.shape[1])
        if length > 1:
            if layer == self.final_score_layer:
                self.seen_prefill = True
                # The scheduler may finish Prefill with a singleton tail before
                # the first real Decode forward. Exclude that whole round.
                self.skip_singleton_rounds = 1
            return
        if not self.seen_prefill:
            return
        if self.skip_singleton_rounds:
            if layer == self.final_score_layer:
                self.skip_singleton_rounds -= 1
            return
        self.pending.append((layer, inds))
        if layer != self.final_score_layer:
            return
        self.decode_steps += 1
        if self.decode_steps % self.interval:
            return
        self.review()

    def review(self) -> None:
        import mlx.core as mx

        if not self.pending:
            return
        started = time.perf_counter()
        layers = [layer for layer, _ in self.pending]
        packed = mx.stack([inds.reshape(-1) for _, inds in self.pending]).astype(
            mx.uint8
        )
        mx.eval(packed)
        rows = packed.tolist()
        if len(rows) % 40:
            raise RuntimeError(f"review rows are not token-aligned: {len(rows)}")
        self.trace.extend(
            [rows[offset : offset + 40] for offset in range(0, len(rows), 40)]
        )
        _accumulate(rows, layers, self.counters)
        self.reviews += 1
        self.reviewed_ids += sum(len(row) for row in rows)
        self.pending.clear()
        self.review_seconds += time.perf_counter() - started

    def summary(self) -> dict[str, int | float]:
        return {
            "decode_steps_seen": self.decode_steps,
            "reviews": self.reviews,
            "reviewed_ids": self.reviewed_ids,
            "counter_total": sum(sum(counter.values()) for counter in self.counters.values()),
            "counter_checksum": sum(
                layer * 257 + expert * count
                for layer, counter in self.counters.items()
                for expert, count in counter.items()
            ),
            "review_seconds": self.review_seconds,
            "trace_tokens": len(self.trace),
        }


class _ReviewGate:
    def __init__(self, inner: Any, layer: int, collector: _ReviewCollector) -> None:
        self.inner = inner
        self.layer = layer
        self.collector = collector

    def __call__(self, x: Any, input_ids: Any = None):
        inds, weights = self.inner(x, input_ids)
        self.collector.capture(self.layer, inds)
        return inds, weights


def _install(model: Any, collector: _ReviewCollector) -> list[tuple[Any, Any]]:
    originals = []
    for layer, block in enumerate(model.layers):
        ffn = getattr(block, "ffn", None)
        gate = getattr(ffn, "gate", None)
        if gate is None or layer < 3:
            continue
        originals.append((ffn, gate))
        ffn.gate = _ReviewGate(gate, layer, collector)
    if len(originals) != 40:
        raise RuntimeError(f"expected 40 score gates, found {len(originals)}")
    return originals


def _restore(originals: list[tuple[Any, Any]]) -> None:
    for ffn, gate in originals:
        ffn.gate = gate


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    import mlx.core as mx

    from omlx.admin.benchmark import _run_single_test
    from omlx.engine.batched import BatchedEngine
    from omlx.patches.deepseek_v4.scope_cache import get_scope_fallback_loader

    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite benchmark output: {output}")
    dataset = json.loads(args.dataset.expanduser().read_text())
    samples = {sample["id"]: sample for sample in dataset["samples"]}
    sample = samples[args.sample_id]
    expected_scope = args.runtime_scope or sample["scope"]
    configured_scope = os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_NAME")
    if configured_scope != expected_scope:
        raise ValueError(
            f"configured scope {configured_scope!r} != expected {expected_scope!r}"
        )

    model_path = args.model.expanduser().resolve()
    encode_messages = _load_encoder(model_path)
    prompt = encode_messages(list(sample["messages"]), thinking_mode="chat")
    engine = BatchedEngine(str(model_path))
    await engine.start()
    prompt_ids = engine.tokenizer.encode(prompt, add_special_tokens=False)
    core = engine._engine.engine
    loop = asyncio.get_running_loop()
    loader = get_scope_fallback_loader(os.environ["OMLX_DEEPSEEK_V4_EXPERT_STORE"])

    async def clear_state() -> None:
        def clear() -> None:
            loader.clear_hot()
            mx.clear_cache()

        await loop.run_in_executor(core._mlx_executor, clear)

    async def one(mode: str, gen: int) -> dict[str, Any]:
        collector = _ReviewCollector(args.interval)
        originals = None
        await clear_state()
        before = loader.stats()
        try:
            if mode == "on":
                originals = await loop.run_in_executor(
                    core._mlx_executor, _install, engine._model, collector
                )
            result = await _run_single_test(engine, prompt_ids, gen, len(prompt_ids))
        finally:
            if originals is not None:
                await loop.run_in_executor(core._mlx_executor, _restore, originals)
        after = loader.stats()
        return {
            "mode": mode,
            "decode_tokens_per_second": result["gen_tps"],
            "prefill_tokens_per_second": result["processing_tps"],
            "ttft_ms": result["ttft_ms"],
            "cache": {
                key: after[key] - before[key]
                for key in (
                    "fallback_calls",
                    "hot_only_calls",
                    "transient_calls",
                    "decode_experts_loaded",
                    "experts_loaded",
                    "bytes_loaded",
                    "load_seconds",
                )
            },
            "review": collector.summary(),
        }

    try:
        # Warm both shapes/paths before the interleaved measured sequence.
        await one("off", args.warmup_gen)
        await one("on", max(args.interval, args.warmup_gen))
        runs = [await one(mode, args.gen) for mode in BALANCED_MODES]
    finally:
        await engine.stop()

    grouped = {mode: [run for run in runs if run["mode"] == mode] for mode in ("off", "on")}
    medians = {
        mode: {
            "decode_tokens_per_second": statistics.median(
                run["decode_tokens_per_second"] for run in mode_runs
            ),
            "prefill_tokens_per_second": statistics.median(
                run["prefill_tokens_per_second"] for run in mode_runs
            ),
            "ttft_ms": statistics.median(run["ttft_ms"] for run in mode_runs),
        }
        for mode, mode_runs in grouped.items()
    }
    off_tps = medians["off"]["decode_tokens_per_second"]
    on_tps = medians["on"]["decode_tokens_per_second"]
    payload = {
        "version": 1,
        "sample_id": args.sample_id,
        "scope": expected_scope,
        "prompt_tokens": len(prompt_ids),
        "requested_decode_tokens": args.gen,
        "review_interval": args.interval,
        "order": list(BALANCED_MODES),
        "runs": runs,
        "medians": medians,
        "decode_tps_loss_fraction": (off_tps - on_tps) / off_tps,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def main() -> None:
    payload = asyncio.run(_run(_args()))
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
