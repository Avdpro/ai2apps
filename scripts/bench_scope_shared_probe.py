#!/usr/bin/env python3
"""Validate scope selection from a DeepSeek V4 shared-expert-only probe.

For each held-out prompt this runs two forwards over identical tokens:

1. an exact Prefill whose real router decisions define the performance oracle;
2. a probe that keeps the first three hash MoE layers exact, then runs only
   attention, shared experts, and routers in the forty score-routed layers.

Both route streams score every scope present in the supplied profile. The
experiment never changes the active runtime profile or the DMoE artifacts.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--samples-per-scope", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument(
        "--probe-depths",
        default=None,
        help=(
            "comma-separated total layer counts; defaults to "
            "OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH (16)"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.probe_depths is None:
        from omlx.patches.deepseek_v4.scope_policy import (
            load_scope_probe_depth_from_env,
        )

        args.probe_depths = [load_scope_probe_depth_from_env()]
    else:
        args.probe_depths = _parse_probe_depths(args.probe_depths)
    return args


def _parse_probe_depths(value: str) -> list[int]:
    depths = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not depths or depths[0] < 4 or depths[-1] > 43:
        raise ValueError("probe depths must be unique layer counts in [4, 43]")
    return depths


def _load_encoder(model: Path):
    path = model / "encoding" / "encoding_dsv4.py"
    spec = importlib.util.spec_from_file_location("omlx_scope_probe_encoding", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load DeepSeek encoder from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.encode_messages


def _profile_masks(profile: dict[str, Any]) -> tuple[list[str], list[list[list[int]]]]:
    scopes = profile.get("scopes") or {}
    if not scopes:
        raise ValueError("scope profile contains no scopes")
    scope_ids = sorted(scopes)
    masks: list[list[list[int]]] = []
    for scope_id in scope_ids:
        layers = []
        for layer in range(3, 43):
            experts = [int(value) for value in scopes[scope_id][str(layer)]]
            if len(experts) != 60 or len(set(experts)) != 60:
                raise ValueError(
                    f"scope {scope_id!r} layer {layer} must contain 60 experts"
                )
            mask = [0] * 256
            for expert in experts:
                mask[expert] = 1
            layers.append(mask)
        masks.append(layers)
    return scope_ids, masks


class ScopeScoreCollector:
    """Accumulate route arrays lazily and reduce them to per-scope coverage."""

    def __init__(self, masks: Any, expected_layers: int = 40) -> None:
        self.masks = masks
        self.expected_layers = expected_layers
        self.pending: list[tuple[int, Any, Any]] = []

    def capture(self, layer: int, inds: Any, weights: Any) -> None:
        if 3 <= layer < 43:
            self.pending.append((layer, inds, weights))

    def finish(self) -> dict[str, Any]:
        import mlx.core as mx

        if len(self.pending) != self.expected_layers:
            layers = [layer for layer, _, _ in self.pending]
            raise RuntimeError(
                f"expected {self.expected_layers} route tensors, got {layers}"
            )
        scope_count = self.masks.shape[0]
        top6 = mx.zeros((scope_count,), dtype=mx.float32)
        head2 = mx.zeros((scope_count,), dtype=mx.float32)
        top6_mass = mx.array(0.0, dtype=mx.float32)
        head2_mass = mx.array(0.0, dtype=mx.float32)
        for layer, inds, weights in self.pending:
            layer_mask = self.masks[:, layer - 3, :]
            covered = mx.take(layer_mask, inds, axis=1)
            top6 = top6 + mx.sum(
                covered * weights[None, ...].astype(mx.float32),
                axis=(1, 2, 3),
            )
            top6_mass = top6_mass + mx.sum(weights.astype(mx.float32))

            positions = mx.argpartition(-weights, kth=1, axis=-1)[..., :2]
            head_ids = mx.take_along_axis(inds, positions, axis=-1)
            head_weights = mx.take_along_axis(weights, positions, axis=-1)
            head_covered = mx.take(layer_mask, head_ids, axis=1)
            head2 = head2 + mx.sum(
                head_covered * head_weights[None, ...].astype(mx.float32),
                axis=(1, 2, 3),
            )
            head2_mass = head2_mass + mx.sum(head_weights.astype(mx.float32))

        top6 = top6 / (top6_mass + 1e-20)
        head2 = head2 / (head2_mass + 1e-20)
        mx.eval(top6, head2)
        return {
            "top6": [float(value) for value in top6.tolist()],
            "head2": [float(value) for value in head2.tolist()],
        }


class _CapturingGate:
    def __init__(self, inner: Any, layer: int, collector: ScopeScoreCollector):
        self.inner = inner
        self.layer = layer
        self.collector = collector

    def __call__(self, x: Any, input_ids: Any = None, **kwargs: Any):
        result = self.inner(x, input_ids, **kwargs)
        self.collector.capture(self.layer, result[0], result[1])
        return result


class _SharedOnlyFFN:
    """Keep the target shared expert and router, skipping routed expert compute."""

    def __init__(self, inner: Any, layer: int, collector: ScopeScoreCollector):
        self.inner = inner
        self.layer = layer
        self.collector = collector

    def __call__(self, x: Any, input_ids: Any) -> Any:
        if self.inner.sharding_group is not None:
            raise RuntimeError("shared-only scope probe does not support sharding")
        shared = self.inner.shared_experts(x)
        inds, weights = self.inner.gate(x, input_ids)
        self.collector.capture(self.layer, inds, weights)
        return shared


def _install_exact(model: Any, collector: ScopeScoreCollector) -> list[tuple[Any, Any]]:
    originals = []
    for layer, block in enumerate(model.layers):
        if layer < 3:
            continue
        ffn = block.ffn
        originals.append((ffn, ffn.gate))
        ffn.gate = _CapturingGate(ffn.gate, layer, collector)
    return originals


def _restore_exact(originals: list[tuple[Any, Any]]) -> None:
    for ffn, gate in originals:
        ffn.gate = gate


def _install_probe(
    model: Any, collector: ScopeScoreCollector
) -> list[tuple[Any, Any]]:
    originals = []
    for layer, block in enumerate(model.layers):
        if layer < 3:
            continue
        originals.append((block, block.ffn))
        block.ffn = _SharedOnlyFFN(block.ffn, layer, collector)
    return originals


def _restore_probe(originals: list[tuple[Any, Any]]) -> None:
    for block, ffn in originals:
        block.ffn = ffn


def _choose_samples(dataset: dict[str, Any], count: int) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("--samples-per-scope must be at least 1")
    by_scope: dict[str, list[dict[str, Any]]] = {}
    for sample in dataset["samples"]:
        if "validation" not in sample["id"] and "test" not in sample["id"]:
            continue
        by_scope.setdefault(sample["scope"], []).append(sample)
    selected = []
    for scope in sorted(by_scope):
        candidates = sorted(
            by_scope[scope],
            key=lambda sample: (sample.get("language") != "zh", sample["id"]),
        )
        if len(candidates) < count:
            raise ValueError(f"scope {scope!r} has fewer than {count} held-out samples")
        selected.extend(candidates[:count])
    return selected


def _truncate(ids: list[int], limit: int) -> list[int]:
    if limit < 8:
        raise ValueError("--max-tokens must be at least 8")
    if len(ids) <= limit:
        return ids
    prefix = min(16, limit // 4)
    return ids[:prefix] + ids[-(limit - prefix) :]


def _rank(scope_ids: list[str], values: list[float]) -> list[str]:
    return [
        scope_ids[index]
        for index in sorted(range(len(values)), key=lambda index: -values[index])
    ]


@dataclass
class _ForwardResult:
    scores: dict[str, list[float]]
    seconds: float


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    from omlx.engine.batched import BatchedEngine
    from omlx.patches.deepseek_v4.scope_cache import get_scope_fallback_loader

    if os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "exact").lower() not in (
        "",
        "exact",
        "off",
        "0",
    ):
        raise ValueError("scope probe benchmark requires exact runtime routing")
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite output: {output}")

    profile = json.loads(args.profile.expanduser().read_text())
    scope_ids, raw_masks = _profile_masks(profile)
    dataset = json.loads(args.dataset.expanduser().read_text())
    samples = _choose_samples(dataset, args.samples_per_scope)
    encode_messages = _load_encoder(args.model.expanduser().resolve())

    engine = BatchedEngine(str(args.model.expanduser().resolve()))
    await engine.start()
    core = engine._engine.engine
    loop = asyncio.get_running_loop()
    stream = core.scheduler._stream
    masks = mx.array(raw_masks, dtype=mx.float32)
    mx.eval(masks)
    loader = get_scope_fallback_loader(
        os.environ["OMLX_DEEPSEEK_V4_EXPERT_STORE"]
    )

    def clear_state() -> None:
        loader.clear_hot()
        mx.clear_cache()

    def forward(ids: list[int], probe: bool, depth: int = 43) -> _ForwardResult:
        collector = ScopeScoreCollector(
            masks,
            expected_layers=(depth - 3 if probe else 40),
        )
        originals = None
        all_layers = None
        started = time.perf_counter()
        try:
            with mx.stream(stream):
                if probe:
                    all_layers = engine._model.model.layers
                    engine._model.model.layers = all_layers[:depth]
                originals = (
                    _install_probe(engine._model, collector)
                    if probe
                    else _install_exact(engine._model, collector)
                )
                cache = make_prompt_cache(engine._model)
                logits = engine._model(mx.array([ids], dtype=mx.int32), cache=cache)
                mx.eval(logits)
                scores = collector.finish()
        finally:
            if originals is not None:
                (_restore_probe if probe else _restore_exact)(originals)
            if all_layers is not None:
                engine._model.model.layers = all_layers
        return _ForwardResult(scores=scores, seconds=time.perf_counter() - started)

    rows = []
    try:
        for sample in samples:
            prompt = encode_messages(
                list(sample["messages"]), thinking_mode="chat"
            )
            full_ids = engine.tokenizer.encode(prompt, add_special_tokens=False)
            ids = _truncate(full_ids, args.max_tokens)
            await loop.run_in_executor(core._mlx_executor, clear_state)
            exact = await loop.run_in_executor(core._mlx_executor, forward, ids, False)
            exact_rank = _rank(scope_ids, exact.scores["top6"])
            oracle = exact_rank[0]
            oracle_value = exact.scores["top6"][scope_ids.index(oracle)]
            probes = {}
            for depth in args.probe_depths:
                await loop.run_in_executor(core._mlx_executor, clear_state)
                probe = await loop.run_in_executor(
                    core._mlx_executor, forward, ids, True, depth
                )
                probe_rank = _rank(scope_ids, probe.scores["top6"])
                predicted = probe_rank[0]
                predicted_value = exact.scores["top6"][scope_ids.index(predicted)]
                probes[str(depth)] = {
                    "predicted": predicted,
                    "agreement": predicted == oracle,
                    "label_match": predicted == sample["scope"],
                    "coverage_regret": oracle_value - predicted_value,
                    "probe_margin": (
                        probe.scores["top6"][scope_ids.index(probe_rank[0])]
                        - probe.scores["top6"][scope_ids.index(probe_rank[1])]
                    ),
                    "probe_top3": probe_rank[:3],
                    "seconds": probe.seconds,
                }
            row = {
                "sample_id": sample["id"],
                "label": sample["scope"],
                "language": sample["language"],
                "full_prompt_tokens": len(full_ids),
                "probe_tokens": len(ids),
                "exact_seconds": exact.seconds,
                "oracle": oracle,
                "oracle_label_match": oracle == sample["scope"],
                "oracle_top3": exact_rank[:3],
                "probes": probes,
            }
            rows.append(row)
            print(json.dumps(row, sort_keys=True), flush=True)
    finally:
        await engine.stop()

    summary = {"top6_by_depth": {}}
    warmed = rows[1:] if len(rows) > 1 else rows
    for depth in args.probe_depths:
        key = str(depth)
        entries = [row["probes"][key] for row in rows]
        warmed_entries = [row["probes"][key] for row in warmed]
        summary["top6_by_depth"][key] = {
            "samples": len(entries),
            "oracle_agreement": sum(entry["agreement"] for entry in entries)
            / len(entries),
            "label_accuracy": sum(entry["label_match"] for entry in entries)
            / len(entries),
            "mean_coverage_regret": statistics.mean(
                entry["coverage_regret"] for entry in entries
            ),
            "max_coverage_regret": max(
                entry["coverage_regret"] for entry in entries
            ),
            "median_probe_seconds": statistics.median(
                entry["seconds"] for entry in warmed_entries
            ),
        }
    summary["exact"] = {
        "oracle_label_accuracy": sum(row["oracle_label_match"] for row in rows)
        / len(rows),
        "median_exact_seconds": statistics.median(
            row["exact_seconds"] for row in warmed
        ),
    }
    payload = {
        "version": 2,
        "model": str(args.model.expanduser().resolve()),
        "dataset": str(args.dataset.expanduser().resolve()),
        "profile": str(args.profile.expanduser().resolve()),
        "scope_ids": scope_ids,
        "samples_per_scope": args.samples_per_scope,
        "max_tokens": args.max_tokens,
        "probe_depths": args.probe_depths,
        "summary": summary,
        "rows": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "summary": summary}, sort_keys=True))
    return payload


def main() -> None:
    asyncio.run(_run(_args()))


if __name__ == "__main__":
    main()
