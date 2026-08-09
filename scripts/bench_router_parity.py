#!/usr/bin/env python3
"""Compare DeepSeek V4 router choices in Prefill and token-by-token replay."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


DEFAULT_TEXT = """Implement a Python LRU cache with O(1) get and put operations.
Explain the data structures, complexity, edge cases, and include a short test.
The implementation should be thread-safe and use clear type annotations.
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--tokens", type=int, default=32)
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


class _Collector:
    def __init__(self) -> None:
        self.pending: list[tuple[int, Any, Any, Any, bool]] = []
        self.top6: dict[int, list[list[int]]] = defaultdict(list)
        self.top10: dict[int, list[list[int]]] = defaultdict(list)
        self.weights: dict[int, list[list[float]]] = defaultdict(list)
        self.score_layers: set[int] = set()

    def capture(
        self,
        layer_idx: int,
        inds6: Any,
        weights6: Any,
        inds10: Any,
        score_layer: bool,
    ) -> None:
        self.pending.append((layer_idx, inds6, weights6, inds10, score_layer))

    def drain(self) -> None:
        import mlx.core as mx

        if not self.pending:
            return
        arrays = [array for item in self.pending for array in item[1:4]]
        mx.eval(*arrays)
        for layer_idx, inds6, weights6, inds10, score_layer in self.pending:
            self.top6[layer_idx].extend(inds6.tolist()[0])
            self.top10[layer_idx].extend(inds10.tolist()[0])
            self.weights[layer_idx].extend(weights6.tolist()[0])
            if score_layer:
                self.score_layers.add(layer_idx)
        self.pending.clear()


class _CapturingGate:
    """Transparent callable wrapper around one loaded MoEGate."""

    def __init__(self, inner: Any, layer_idx: int, collector: _Collector):
        self.inner = inner
        self.layer_idx = layer_idx
        self.collector = collector

    def __call__(self, x: Any, input_ids: Any = None):
        inds6, weights6 = self.inner(x, input_ids)
        score_layer = not bool(self.inner.hash)
        if score_layer:
            old_top_k = self.inner.top_k
            try:
                self.inner.top_k = 10
                inds10, _ = self.inner(x, input_ids)
            finally:
                self.inner.top_k = old_top_k
        else:
            # Hash-router checkpoints publish exactly the six token-mapped IDs;
            # Top-10 is undefined there, so retain Top-6 and exclude the layer
            # from the Top-10 aggregate.
            inds10 = inds6
        self.collector.capture(
            self.layer_idx,
            inds6,
            weights6,
            inds10,
            score_layer,
        )
        return inds6, weights6


def _install_collectors(model: Any, collector: _Collector) -> list[tuple[Any, Any]]:
    originals = []
    for layer_idx, layer in enumerate(model.layers):
        ffn = getattr(layer, "ffn", None)
        gate = getattr(ffn, "gate", None)
        if gate is None:
            continue
        originals.append((ffn, gate))
        ffn.gate = _CapturingGate(gate, layer_idx, collector)
    if not originals:
        raise RuntimeError("no DeepSeek V4 MoE gates found")
    return originals


def _restore_collectors(originals: list[tuple[Any, Any]]) -> None:
    for ffn, gate in originals:
        ffn.gate = gate


def _run_mode(model: Any, token_ids: list[int], *, token_by_token: bool):
    import mlx.core as mx
    from mlx_lm.models.cache import make_prompt_cache

    collector = _Collector()
    originals = _install_collectors(model, collector)
    cache = make_prompt_cache(model)
    outputs = []
    started = time.perf_counter()
    try:
        if token_by_token:
            for token_id in token_ids:
                output = model(mx.array([[token_id]], dtype=mx.int32), cache=cache)
                mx.eval(output)
                collector.drain()
                outputs.append(output)
            logits = mx.concatenate(outputs, axis=1)
        else:
            logits = model(mx.array([token_ids], dtype=mx.int32), cache=cache)
            mx.eval(logits)
            collector.drain()
        mx.eval(logits)
    finally:
        _restore_collectors(originals)
    return collector, logits, time.perf_counter() - started


def compare_router_traces(
    prefill: _Collector,
    decode: _Collector,
    *,
    max_examples: int = 20,
) -> dict[str, Any]:
    top6_total = top6_ordered = top6_set = top6_overlap = 0
    top10_total = top10_set = top10_overlap = 0
    top5_total = top5_set = top5_overlap = 0
    max_weight_abs = 0.0
    weight_abs_sum = 0.0
    weight_count = 0
    mismatches = []
    per_layer = []
    scope_top60_overlaps = []
    scope_frequency_cosines = []
    scope_prefill_covers_decode = []
    scope_decode_covers_prefill = []
    scope_decode_self_coverage = []
    scope_prefill_self_coverage = []

    layers = sorted(set(prefill.top6) | set(decode.top6))
    for layer_idx in layers:
        p6_rows = prefill.top6.get(layer_idx, [])
        d6_rows = decode.top6.get(layer_idx, [])
        p10_rows = prefill.top10.get(layer_idx, [])
        d10_rows = decode.top10.get(layer_idx, [])
        pw_rows = prefill.weights.get(layer_idx, [])
        dw_rows = decode.weights.get(layer_idx, [])
        if len(p6_rows) != len(d6_rows):
            raise ValueError(
                f"layer {layer_idx} token rows differ: {len(p6_rows)} != {len(d6_rows)}"
            )

        layer_ordered = layer_set = layer_overlap = 0
        layer_top10_set = layer_top10_overlap = 0
        for token_idx, (p6, d6) in enumerate(zip(p6_rows, d6_rows)):
            top6_total += 1
            ordered = p6 == d6
            same_set = set(p6) == set(d6)
            overlap = len(set(p6) & set(d6))
            top6_ordered += int(ordered)
            top6_set += int(same_set)
            top6_overlap += overlap
            layer_ordered += int(ordered)
            layer_set += int(same_set)
            layer_overlap += overlap

            p_weight_by_id = dict(zip(p6, pw_rows[token_idx]))
            d_weight_by_id = dict(zip(d6, dw_rows[token_idx]))
            for expert_id in set(p_weight_by_id) & set(d_weight_by_id):
                delta = abs(p_weight_by_id[expert_id] - d_weight_by_id[expert_id])
                max_weight_abs = max(max_weight_abs, delta)
                weight_abs_sum += delta
                weight_count += 1

            p5 = {
                expert_id
                for expert_id, _ in sorted(
                    zip(p6, pw_rows[token_idx]),
                    key=lambda item: (-item[1], item[0]),
                )[:5]
            }
            d5 = {
                expert_id
                for expert_id, _ in sorted(
                    zip(d6, dw_rows[token_idx]),
                    key=lambda item: (-item[1], item[0]),
                )[:5]
            }
            overlap5 = len(p5 & d5)
            top5_total += 1
            top5_set += int(p5 == d5)
            top5_overlap += overlap5

            if not same_set and len(mismatches) < max_examples:
                mismatches.append(
                    {
                        "layer": layer_idx,
                        "token": token_idx,
                        "prefill_top6": p6,
                        "decode_top6": d6,
                        "overlap": overlap,
                    }
                )

            if layer_idx in prefill.score_layers and layer_idx in decode.score_layers:
                p10 = p10_rows[token_idx]
                d10 = d10_rows[token_idx]
                overlap10 = len(set(p10) & set(d10))
                top10_total += 1
                top10_set += int(set(p10) == set(d10))
                top10_overlap += overlap10
                layer_top10_set += int(set(p10) == set(d10))
                layer_top10_overlap += overlap10

        prefill_counts = Counter(expert for row in p6_rows for expert in row)
        decode_counts = Counter(expert for row in d6_rows for expert in row)
        prefill_top60 = {
            expert
            for expert in sorted(
                range(256), key=lambda expert: (-prefill_counts[expert], expert)
            )[:60]
        }
        decode_top60 = {
            expert
            for expert in sorted(
                range(256), key=lambda expert: (-decode_counts[expert], expert)
            )[:60]
        }
        top60_overlap = len(prefill_top60 & decode_top60)
        dot = sum(prefill_counts[e] * decode_counts[e] for e in range(256))
        p_norm = sum(prefill_counts[e] ** 2 for e in range(256)) ** 0.5
        d_norm = sum(decode_counts[e] ** 2 for e in range(256)) ** 0.5
        frequency_cosine = dot / (p_norm * d_norm) if p_norm and d_norm else 0.0
        prefill_total_routes = sum(prefill_counts.values())
        decode_total_routes = sum(decode_counts.values())
        prefill_covers_decode = (
            sum(decode_counts[e] for e in prefill_top60) / decode_total_routes
            if decode_total_routes
            else 0.0
        )
        decode_covers_prefill = (
            sum(prefill_counts[e] for e in decode_top60) / prefill_total_routes
            if prefill_total_routes
            else 0.0
        )
        decode_self_coverage = (
            sum(decode_counts[e] for e in decode_top60) / decode_total_routes
            if decode_total_routes
            else 0.0
        )
        prefill_self_coverage = (
            sum(prefill_counts[e] for e in prefill_top60) / prefill_total_routes
            if prefill_total_routes
            else 0.0
        )
        is_score_layer = (
            layer_idx in prefill.score_layers and layer_idx in decode.score_layers
        )
        if is_score_layer:
            scope_top60_overlaps.append(top60_overlap)
            scope_frequency_cosines.append(frequency_cosine)
            scope_prefill_covers_decode.append(prefill_covers_decode)
            scope_decode_covers_prefill.append(decode_covers_prefill)
            scope_decode_self_coverage.append(decode_self_coverage)
            scope_prefill_self_coverage.append(prefill_self_coverage)

        count = len(p6_rows)
        per_layer.append(
            {
                "layer": layer_idx,
                "tokens": count,
                "top6_ordered_rate": layer_ordered / count if count else 0.0,
                "top6_set_rate": layer_set / count if count else 0.0,
                "top6_mean_overlap": layer_overlap / count if count else 0.0,
                "top10_set_rate": (
                    layer_top10_set / count if layer_idx in prefill.score_layers else None
                ),
                "top10_mean_overlap": (
                    layer_top10_overlap / count
                    if layer_idx in prefill.score_layers
                    else None
                ),
                "scope_top60_overlap": top60_overlap if is_score_layer else None,
                "scope_frequency_cosine": frequency_cosine if is_score_layer else None,
                "prefill_top60_decode_route_coverage": (
                    prefill_covers_decode if is_score_layer else None
                ),
                "decode_top60_prefill_route_coverage": (
                    decode_covers_prefill if is_score_layer else None
                ),
                "decode_top60_self_coverage": (
                    decode_self_coverage if is_score_layer else None
                ),
                "prefill_top60_self_coverage": (
                    prefill_self_coverage if is_score_layer else None
                ),
                "prefill_top60_decode_coverage_loss": (
                    decode_self_coverage - prefill_covers_decode
                    if is_score_layer
                    else None
                ),
            }
        )

    return {
        "layers": len(layers),
        "top6_rows": top6_total,
        "top6_ordered_rate": top6_ordered / top6_total if top6_total else 0.0,
        "top6_set_rate": top6_set / top6_total if top6_total else 0.0,
        "top6_mean_overlap": top6_overlap / top6_total if top6_total else 0.0,
        "weighted_top5_set_rate": top5_set / top5_total if top5_total else 0.0,
        "weighted_top5_mean_overlap": (
            top5_overlap / top5_total if top5_total else 0.0
        ),
        "top10_rows": top10_total,
        "top10_set_rate": top10_set / top10_total if top10_total else 0.0,
        "top10_mean_overlap": top10_overlap / top10_total if top10_total else 0.0,
        "router_weight_mean_abs": weight_abs_sum / weight_count if weight_count else 0.0,
        "router_weight_max_abs": max_weight_abs,
        "scope_top60_mean_overlap": (
            sum(scope_top60_overlaps) / len(scope_top60_overlaps)
            if scope_top60_overlaps
            else 0.0
        ),
        "scope_top60_min_overlap": min(scope_top60_overlaps, default=0),
        "scope_frequency_mean_cosine": (
            sum(scope_frequency_cosines) / len(scope_frequency_cosines)
            if scope_frequency_cosines
            else 0.0
        ),
        "scope_frequency_min_cosine": min(scope_frequency_cosines, default=0.0),
        "prefill_top60_decode_route_mean_coverage": (
            sum(scope_prefill_covers_decode) / len(scope_prefill_covers_decode)
            if scope_prefill_covers_decode
            else 0.0
        ),
        "decode_top60_prefill_route_mean_coverage": (
            sum(scope_decode_covers_prefill) / len(scope_decode_covers_prefill)
            if scope_decode_covers_prefill
            else 0.0
        ),
        "decode_top60_self_mean_coverage": (
            sum(scope_decode_self_coverage) / len(scope_decode_self_coverage)
            if scope_decode_self_coverage
            else 0.0
        ),
        "prefill_top60_self_mean_coverage": (
            sum(scope_prefill_self_coverage) / len(scope_prefill_self_coverage)
            if scope_prefill_self_coverage
            else 0.0
        ),
        "prefill_top60_decode_mean_coverage_loss": (
            (
                sum(scope_decode_self_coverage) / len(scope_decode_self_coverage)
                - sum(scope_prefill_covers_decode) / len(scope_prefill_covers_decode)
            )
            if scope_decode_self_coverage and scope_prefill_covers_decode
            else 0.0
        ),
        "mismatch_examples": mismatches,
        "per_layer": per_layer,
    }


def _prepare_tokens(tokenizer: Any, text: str, count: int) -> list[int]:
    if count < 2:
        raise ValueError("--tokens must be at least 2")
    source = text
    token_ids = tokenizer.encode(source, add_special_tokens=False)
    while len(token_ids) < count:
        source += "\n" + text
        token_ids = tokenizer.encode(source, add_special_tokens=False)
    return token_ids[:count]


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    import mlx.core as mx

    from omlx.engine.batched import BatchedEngine
    from omlx.engine_core import get_mlx_executor

    model_path = str(args.model.expanduser().resolve())
    engine = BatchedEngine(model_path)
    await engine.start()
    try:
        text = args.text_file.expanduser().read_text() if args.text_file else args.text
        token_ids = _prepare_tokens(engine.tokenizer, text, args.tokens)
        model = engine._model
        scheduler = engine._engine.engine.scheduler
        stream = scheduler._stream
        loop = asyncio.get_running_loop()

        def measure():
            with mx.stream(stream):
                prefill, prefill_logits, prefill_seconds = _run_mode(
                    model, token_ids, token_by_token=False
                )
                mx.clear_cache()
                store = os.environ.get("OMLX_DEEPSEEK_V4_EXPERT_STORE", "").strip()
                if store:
                    from omlx.patches.deepseek_v4.scope_cache import (
                        get_scope_fallback_loader,
                    )

                    get_scope_fallback_loader(store).clear_hot()
                decode, decode_logits, decode_seconds = _run_mode(
                    model, token_ids, token_by_token=True
                )
                top1_equal = mx.argmax(prefill_logits, axis=-1) == mx.argmax(
                    decode_logits, axis=-1
                )
                max_logit_abs = mx.max(
                    mx.abs(
                        prefill_logits.astype(mx.float32)
                        - decode_logits.astype(mx.float32)
                    )
                )
                mx.eval(top1_equal, max_logit_abs)
                result = compare_router_traces(prefill, decode)
                result.update(
                    {
                        "tokens": len(token_ids),
                        "text_source": (
                            str(args.text_file.expanduser().resolve())
                            if args.text_file
                            else "--text"
                        ),
                        "prefill_seconds": prefill_seconds,
                        "decode_replay_seconds": decode_seconds,
                        "logit_top1_rate": sum(top1_equal.tolist()[0])
                        / len(token_ids),
                        "logit_max_abs": float(max_logit_abs.item()),
                    }
                )
                return result

        result = await loop.run_in_executor(get_mlx_executor(), measure)
    finally:
        await engine.stop()
    return result


def main() -> None:
    args = _parse_args()
    result = asyncio.run(_run(args))
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")


if __name__ == "__main__":
    main()
