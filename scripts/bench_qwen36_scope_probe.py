#!/usr/bin/env python3
"""Benchmark Qwen3.6 shared-only scope selection against exact Router coverage."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("model", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--depths", default="8,12,16,24,40")
    parser.add_argument("--samples-per-scope", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument(
        "--expand-to-tokens",
        type=int,
        default=0,
        help="repeat each rendered prompt to this many tokens for a synthetic long-context sweep",
    )
    parser.add_argument("--resident-experts", type=int, default=96)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def choose_samples(
    dataset: dict[str, Any], scopes: tuple[str, ...], count: int
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in dataset["samples"]:
        if sample.get("scope") in scopes and sample.get("split") in (
            "validation",
            "test",
        ):
            grouped[sample["scope"]].append(sample)
    selected = []
    for scope in scopes:
        by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in grouped[scope]:
            by_language[str(row.get("language") or "unknown")].append(row)
        for rows in by_language.values():
            rows.sort(key=lambda row: row["id"])
        balanced = []
        offset = 0
        languages = sorted(by_language)
        while len(balanced) < count:
            added = False
            for language in languages:
                rows = by_language[language]
                if offset < len(rows):
                    balanced.append(rows[offset])
                    added = True
                    if len(balanced) == count:
                        break
            if not added:
                break
            offset += 1
        if len(balanced) < count:
            raise ValueError(
                f"scope {scope!r} has only {len(balanced)} held-out rows"
            )
        selected.extend(balanced)
    return selected


async def run(args: argparse.Namespace) -> None:
    import mlx.core as mx

    from omlx.engine.qwen36_flesh import Qwen36FleshEngine
    from omlx.patches.qwen3_6_flesh.model_patch import (
        set_qwen36_parity_observer,
    )
    from omlx.patches.qwen3_6_flesh.scope_policy import (
        configure_qwen36_scope_policy,
    )
    from omlx.patches.qwen3_6_flesh.scope_runtime import (
        Qwen36ScopeSelector,
        _Top8Collector,
    )

    profile = json.loads(args.profile.read_text())
    scopes = tuple(sorted(profile["phases"]["decode"]))
    initial_scope = "general" if "general" in scopes else scopes[0]
    configure_qwen36_scope_policy(
        args.profile,
        initial_scope,
        args.store,
        args.resident_experts,
        backend="flesh",
    )
    engine = Qwen36FleshEngine(str(args.model))
    rows = []
    depths = [int(value) for value in args.depths.split(",")]
    try:
        await engine.start()
        policy = engine._qwen_scope_policy
        core = engine._engine.engine
        stream = core.scheduler._stream
        masks = mx.array(
            policy.catalog.masks(args.resident_experts, phase="decode"),
            dtype=mx.float32,
        )
        mx.eval(masks)
        selectors = {
            depth: Qwen36ScopeSelector(
                engine._model,
                policy.catalog,
                resident_experts=args.resident_experts,
                depth=depth,
                max_tokens=args.max_tokens,
                stream=stream,
            )
            for depth in depths
        }
        samples = choose_samples(
            json.loads(args.dataset.read_text()), scopes, args.samples_per_scope
        )

        for sample in samples:
            prompt = engine._tokenizer.apply_chat_template(
                sample["messages"], tokenize=False, add_generation_prompt=True
            )
            token_ids = engine._tokenizer.encode(prompt, add_special_tokens=False)
            source_tokens = len(token_ids)
            if args.expand_to_tokens > source_tokens:
                repeats = (args.expand_to_tokens + source_tokens - 1) // source_tokens
                token_ids = (token_ids * repeats)[: args.expand_to_tokens]
            ids = selectors[depths[0]]._truncate(token_ids)

            def exact_oracle() -> tuple[list[float], float]:
                collector = _Top8Collector(masks, 40)

                def observe(block, _x, inds, scores, _routed, _output):
                    collector.capture(block.scope_layer, inds, scores)

                started = time.perf_counter()
                set_qwen36_parity_observer(observe)
                try:
                    with mx.stream(stream):
                        hidden = engine._model.language_model.model(
                            mx.array([ids], dtype=mx.int32), cache=None
                        )
                        mx.eval(hidden)
                        scores = collector.finish()
                finally:
                    set_qwen36_parity_observer(None)
                return scores, time.perf_counter() - started

            oracle_scores, oracle_seconds = await asyncio.get_running_loop().run_in_executor(
                core._mlx_executor, exact_oracle
            )
            oracle_rank = sorted(
                range(len(scopes)), key=lambda index: -oracle_scores[index]
            )
            probes = {}
            for depth, selector in selectors.items():
                selection = await asyncio.get_running_loop().run_in_executor(
                    core._mlx_executor, selector.select, token_ids
                )
                selected_index = scopes.index(selection.scope)
                probes[str(depth)] = {
                    "scope": selection.scope,
                    "margin": selection.margin,
                    "top3": list(selection.top3),
                    "scores": list(selection.scores),
                    "seconds": selection.seconds,
                    "oracle_regret": (
                        oracle_scores[oracle_rank[0]]
                        - oracle_scores[selected_index]
                    ),
                }
            rows.append(
                {
                    "id": sample["id"],
                    "label": sample["scope"],
                    "language": sample.get("language"),
                    "source_tokens": source_tokens,
                    "tokens": len(ids),
                    "oracle_scope": scopes[oracle_rank[0]],
                    "oracle_top3": [scopes[index] for index in oracle_rank[:3]],
                    "oracle_scores": oracle_scores,
                    "oracle_seconds": oracle_seconds,
                    "probes": probes,
                }
            )

        summary = {}
        for depth in depths:
            key = str(depth)
            times = [row["probes"][key]["seconds"] for row in rows]
            regrets = [row["probes"][key]["oracle_regret"] for row in rows]
            summary[key] = {
                "oracle_agreement": sum(
                    row["probes"][key]["scope"] == row["oracle_scope"]
                    for row in rows
                )
                / len(rows),
                "label_accuracy": sum(
                    row["probes"][key]["scope"] == row["label"] for row in rows
                )
                / len(rows),
                "oracle_in_top3": sum(
                    row["oracle_scope"] in row["probes"][key]["top3"]
                    for row in rows
                )
                / len(rows),
                "mean_regret": statistics.fmean(regrets),
                "worst_regret": max(regrets),
                "median_seconds": statistics.median(times[1:] or times),
            }
        report = {
            "scopes": list(scopes),
            "depths": depths,
            "max_tokens": args.max_tokens,
            "expand_to_tokens": args.expand_to_tokens,
            "resident_experts": args.resident_experts,
            "samples": len(rows),
            "summary": summary,
            "rows": rows,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(run(parse_args()))
