#!/usr/bin/env python3
"""Build one isolated DeepSeek V4 Scope Top-60 profile from Prefill routes.

This is an experiment-only profiler.  It never updates an existing JSON file:
the output is created with exclusive-create semantics, and the active runtime
profile is treated as a read-only input recorded by path and SHA-256.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--scope", required=True, help="Dotted leaf name, e.g. code.python")
    parser.add_argument(
        "--text-file",
        type=Path,
        action="append",
        required=True,
        help="Corpus file; repeat to distribute --samples equally across corpora",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-tokens", type=int, default=4096)
    parser.add_argument("--samples", type=int, default=4)
    parser.add_argument(
        "--samples-per-file",
        type=int,
        action="append",
        help="Explicit sample count for each --text-file, in the same order",
    )
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _AggregateCollector:
    """Keep aggregate route statistics, not token-sized raw traces."""

    def __init__(self) -> None:
        self.pending: list[tuple[int, Any, Any, Any, bool]] = []
        self.top6_counts: dict[int, Counter[int]] = defaultdict(Counter)
        self.top10_counts: dict[int, Counter[int]] = defaultdict(Counter)
        self.weight_sums: dict[int, Counter[int]] = defaultdict(Counter)
        self.token_rows: Counter[int] = Counter()
        self.ignored_singleton_calls: Counter[int] = Counter()
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

    def _last_singletons(self) -> set[int]:
        """Return pending indices for the last M=1 call of every layer."""

        skipped: set[int] = set()
        seen_layers: set[int] = set()
        for index in range(len(self.pending) - 1, -1, -1):
            layer_idx, inds6, *_ = self.pending[index]
            if layer_idx not in seen_layers and int(inds6.shape[1]) == 1:
                skipped.add(index)
                seen_layers.add(layer_idx)
        return skipped

    def drain(self, *, drop_last_singleton: bool = False) -> None:
        import mlx.core as mx

        if not self.pending:
            return
        skipped = self._last_singletons() if drop_last_singleton else set()
        arrays = [
            array
            for index, item in enumerate(self.pending)
            if index not in skipped
            for array in item[1:4]
        ]
        mx.eval(*arrays)
        for index, (layer_idx, inds6, weights6, inds10, score_layer) in enumerate(
            self.pending
        ):
            if index in skipped:
                self.ignored_singleton_calls[layer_idx] += 1
                continue
            rows6 = inds6.tolist()[0]
            row_weights = weights6.tolist()[0]
            rows10 = inds10.tolist()[0]
            self.token_rows[layer_idx] += len(rows6)
            for ids, weights in zip(rows6, row_weights):
                self.top6_counts[layer_idx].update(ids)
                for expert_id, weight in zip(ids, weights):
                    self.weight_sums[layer_idx][expert_id] += float(weight)
            if score_layer:
                self.score_layers.add(layer_idx)
                for ids in rows10:
                    self.top10_counts[layer_idx].update(ids)
        self.pending.clear()


def _rank_layer(
    top6: Counter[int], top10: Counter[int], weights: Counter[int]
) -> tuple[list[int], list[float]]:
    """Rank experts using selection frequency, routed mass, then Top-10 support."""

    total6 = max(sum(top6.values()), 1)
    total10 = max(sum(top10.values()), 1)
    total_weight = max(sum(weights.values()), 1e-12)
    scores = [
        0.75 * top6[expert] / total6
        + 0.20 * weights[expert] / total_weight
        + 0.05 * top10[expert] / total10
        for expert in range(256)
    ]
    ranking = sorted(range(256), key=lambda expert: (-scores[expert], expert))
    return ranking, scores


def _build_profile(
    collector: _AggregateCollector,
    *,
    scope: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    missing = sorted(set(range(3, 43)) - collector.score_layers)
    if missing:
        raise RuntimeError(f"missing score-router layers: {missing}")

    scope_layers: dict[str, list[int]] = {}
    global_core: dict[str, list[int]] = {}
    layer_stats: dict[str, Any] = {}
    for layer in range(3, 43):
        ranking, scores = _rank_layer(
            collector.top6_counts[layer],
            collector.top10_counts[layer],
            collector.weight_sums[layer],
        )
        scope_layers[str(layer)] = ranking[:60]
        global_core[str(layer)] = ranking[:4]
        total_routes = sum(collector.top6_counts[layer].values())
        selected = sum(collector.top6_counts[layer][e] for e in ranking[:60])
        layer_stats[str(layer)] = {
            "token_rows": collector.token_rows[layer],
            "ignored_singleton_forwards": collector.ignored_singleton_calls[layer],
            "top6_routes": total_routes,
            "top60_self_coverage": selected / total_routes if total_routes else 0.0,
            "rank60_score": scores[ranking[59]],
            "rank61_score": scores[ranking[60]],
            # Preserve the complete aggregate so later experiments can merge,
            # reweight, bootstrap, and compare profiles without replaying the
            # model. Lists are indexed by global expert ID (0..255).
            "top6_counts_by_expert": [
                collector.top6_counts[layer][expert] for expert in range(256)
            ],
            "top10_counts_by_expert": [
                collector.top10_counts[layer][expert] for expert in range(256)
            ],
            "route_weight_by_expert": [
                collector.weight_sums[layer][expert] for expert in range(256)
            ],
        }

    return {
        "version": 1,
        "format": "dmoe-deepseek-tiered-policy",
        "global_core": global_core,
        "scopes": {scope: scope_layers},
        "metadata": {
            **metadata,
            "status": "experimental-prefill-only",
            "scope_hierarchy": "dot-separated",
            "ranking": "0.75*top6_frequency+0.20*route_weight_mass+0.05*top10_frequency",
            "layer_stats": layer_stats,
        },
    }


def _sample_windows(token_ids: list[int], size: int, count: int) -> list[tuple[int, list[int]]]:
    if size < 2 or count < 1:
        raise ValueError("--sample-tokens must be >= 2 and --samples must be >= 1")
    if len(token_ids) < size:
        raise ValueError(f"corpus has {len(token_ids)} tokens, fewer than {size}")
    final_start = len(token_ids) - size
    starts = [round(index * final_start / max(count - 1, 1)) for index in range(count)]
    return [(start, token_ids[start : start + size]) for start in starts]


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    import mlx.core as mx

    from bench_router_parity import _install_collectors, _restore_collectors
    from omlx.admin.benchmark import _run_single_test
    from omlx.engine.batched import BatchedEngine

    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing Scope artifact: {output}")

    text_paths = [path.expanduser().resolve() for path in args.text_file]
    source_profile_raw = os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_PROFILE", "").strip()
    source_scope = os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_NAME", "").strip()
    if not source_profile_raw or not source_scope:
        raise RuntimeError("the read-only runtime Scope profile and name must be explicit")
    source_profile = Path(source_profile_raw).expanduser().resolve()
    if output == source_profile:
        raise ValueError("output must not be the active runtime Scope profile")
    source_profile_sha = _sha256(source_profile)

    engine = BatchedEngine(str(args.model.expanduser().resolve()))
    await engine.start()
    try:
        corpus_tokens = [
            engine.tokenizer.encode(path.read_text(), add_special_tokens=False)
            for path in text_paths
        ]
        if args.samples_per_file is not None:
            if len(args.samples_per_file) != len(text_paths):
                raise ValueError(
                    "--samples-per-file must appear once for each --text-file"
                )
            if any(count < 1 for count in args.samples_per_file):
                raise ValueError("every --samples-per-file value must be >= 1")
            per_file = args.samples_per_file
            if sum(per_file) != args.samples:
                raise ValueError("--samples must equal the sum of --samples-per-file")
        else:
            if args.samples < len(text_paths):
                raise ValueError(
                    "--samples must be at least the number of --text-file inputs"
                )
            per_file = [args.samples // len(text_paths)] * len(text_paths)
            for index in range(args.samples % len(text_paths)):
                per_file[index] += 1
        windows: list[tuple[Path, int, list[int]]] = []
        for path, ids, count in zip(text_paths, corpus_tokens, per_file, strict=True):
            windows.extend(
                (path, start, window)
                for start, window in _sample_windows(ids, args.sample_tokens, count)
            )
        model = engine._model
        engine_core = engine._engine.engine
        loop = asyncio.get_running_loop()
        collector = _AggregateCollector()
        originals = await loop.run_in_executor(
            engine_core._mlx_executor, _install_collectors, model, collector
        )
        measurements = []
        started_all = time.perf_counter()
        try:
            # Use the real request pipeline so each forward executes on the
            # engine-owned thread and Metal stream. max_tokens=1 samples from
            # the Prefill logits and stops before a Decode forward.
            for sample_index, (corpus_path, start, window) in enumerate(windows):
                started = time.perf_counter()
                result = await _run_single_test(engine, window, 1, len(window))
                await loop.run_in_executor(
                    engine_core._mlx_executor,
                    lambda: collector.drain(drop_last_singleton=True),
                )
                elapsed_sample = time.perf_counter() - started
                measurements.append(
                    {
                        "sample": sample_index,
                        "corpus": str(corpus_path),
                        "start_token": start,
                        "tokens": len(window),
                        "seconds": elapsed_sample,
                        "tokens_per_second": result["processing_tps"],
                    }
                )

                def clear_between_samples() -> None:
                    mx.clear_cache()
                    store = os.environ.get(
                        "OMLX_DEEPSEEK_V4_EXPERT_STORE", ""
                    ).strip()
                    if store:
                        from omlx.patches.deepseek_v4.scope_cache import (
                            get_scope_fallback_loader,
                        )

                        get_scope_fallback_loader(store).clear_hot()

                await loop.run_in_executor(
                    engine_core._mlx_executor, clear_between_samples
                )
        finally:
            await loop.run_in_executor(
                engine_core._mlx_executor, _restore_collectors, originals
            )
        elapsed = time.perf_counter() - started_all
    finally:
        await engine.stop()

    # Detect accidental mutation of the read-only source before publishing.
    source_profile_sha_after = _sha256(source_profile)
    if source_profile_sha_after != source_profile_sha:
        raise RuntimeError(f"source Scope profile changed during experiment: {source_profile}")

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "model": str(args.model.expanduser().resolve()),
        "corpora": [
            {
                "path": str(path),
                "sha256": _sha256(path),
                "tokens": len(ids),
                "samples": count,
            }
            for path, ids, count in zip(
                text_paths, corpus_tokens, per_file, strict=True
            )
        ],
        "sample_tokens": args.sample_tokens,
        "samples": args.samples,
        "sample_measurements": measurements,
        "profiled_tokens": args.sample_tokens * args.samples,
        "elapsed_seconds": elapsed,
        "source_runtime_profile": str(source_profile),
        "source_runtime_profile_sha256_before": source_profile_sha,
        "source_runtime_profile_sha256_after": source_profile_sha_after,
        "source_runtime_scope": source_scope,
    }
    return _build_profile(collector, scope=args.scope, metadata=metadata)


def main() -> None:
    args = _parse_args()
    profile = asyncio.run(_run(args))
    rendered = json.dumps(profile, indent=2, sort_keys=True) + "\n"
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(rendered)
    metadata = profile["metadata"]
    print(
        json.dumps(
            {
                "output": str(output),
                "scope": args.scope,
                "profiled_tokens": metadata["profiled_tokens"],
                "elapsed_seconds": metadata["elapsed_seconds"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
