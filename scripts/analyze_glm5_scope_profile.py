#!/usr/bin/env python3
"""Evaluate GLM5 Scope banks and previous-token predictors on held-out packs."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


HOT_SIZES = (8, 10, 12, 16, 24)


def _train(sequences: list[dict[str, Any]]) -> tuple[dict, dict, dict]:
    counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    transitions: dict[str, dict[int, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    observations: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for pack in sequences:
        for layer, routes in pack["layers"].items():
            for route in routes:
                for expert in dict.fromkeys(route):
                    counts[layer][expert] += 1
            for previous, current in zip(routes, routes[1:], strict=False):
                for source in dict.fromkeys(previous):
                    observations[layer][source] += 1
                    for target in dict.fromkeys(current):
                        transitions[layer][source][target] += 1
    return counts, transitions, observations


def _ranking(counts: dict[int, int], num_experts: int) -> list[int]:
    return sorted(range(num_experts), key=lambda expert: (-counts.get(expert, 0), expert))


def _predict(
    previous: list[int],
    size: int,
    static_ranking: list[int],
    transitions: dict[int, dict[int, int]],
    observations: dict[int, int],
) -> set[int]:
    selected = list(dict.fromkeys(previous))
    scores: dict[int, float] = defaultdict(float)
    for source in selected:
        denominator = max(observations.get(source, 0), 1)
        for target, count in transitions.get(source, {}).items():
            if target not in selected:
                scores[target] += count / denominator
    ranked = sorted(scores, key=lambda expert: (-scores[expert], expert))
    for expert in [*ranked, *static_ranking]:
        if expert not in selected:
            selected.append(expert)
        if len(selected) >= size:
            break
    return set(selected[:size])


def _new_metrics() -> dict[str, Any]:
    return {
        "routes": 0,
        "layer_steps": 0,
        "scope_top80_hits": 0,
        "global_top80_hits": 0,
        "scope_top80_all_hit_steps": 0,
        "global_top80_all_hit_steps": 0,
        "hot": {
            str(size): {
                "hits": 0,
                "all_hit_steps": 0,
                "with_scope_hits": 0,
                "with_scope_all_hit_steps": 0,
            }
            for size in HOT_SIZES
        },
    }


def _finish(metrics: dict[str, Any]) -> dict[str, Any]:
    routes = metrics.pop("routes")
    steps = metrics.pop("layer_steps")
    result = {
        "route_count": routes,
        "layer_steps": steps,
        "scope_top80_route_coverage": metrics.pop("scope_top80_hits") / routes,
        "global_top80_route_coverage": metrics.pop("global_top80_hits") / routes,
        "scope_top80_all_hit_rate": metrics.pop("scope_top80_all_hit_steps") / steps,
        "global_top80_all_hit_rate": metrics.pop("global_top80_all_hit_steps") / steps,
        "hot": {},
    }
    for size, values in metrics["hot"].items():
        result["hot"][size] = {
            "route_coverage": values["hits"] / routes,
            "all_hit_rate": values["all_hit_steps"] / steps,
            "with_scope_top80_route_coverage": values["with_scope_hits"] / routes,
            "with_scope_top80_all_hit_rate": (
                values["with_scope_all_hit_steps"] / steps
            ),
        }
    return result


def _evaluate_scope(
    held_out: dict[str, Any],
    static: dict[str, list[int]],
    global_static: dict[str, list[int]],
    transitions: dict,
    observations: dict,
) -> dict[str, Any]:
    metrics = _new_metrics()
    for layer, routes in held_out["layers"].items():
        own_bank = set(static[layer][:80])
        global_bank = set(global_static[layer][:80])
        for previous, current in zip(routes, routes[1:], strict=False):
            targets = set(current)
            metrics["routes"] += len(targets)
            metrics["layer_steps"] += 1
            metrics["scope_top80_hits"] += len(targets & own_bank)
            metrics["global_top80_hits"] += len(targets & global_bank)
            metrics["scope_top80_all_hit_steps"] += targets <= own_bank
            metrics["global_top80_all_hit_steps"] += targets <= global_bank
            for size in HOT_SIZES:
                predicted = _predict(
                    previous,
                    size,
                    static[layer],
                    transitions[layer],
                    observations[layer],
                )
                metrics["hot"][str(size)]["hits"] += len(targets & predicted)
                metrics["hot"][str(size)]["all_hit_steps"] += targets <= predicted
                combined = own_bank | predicted
                metrics["hot"][str(size)]["with_scope_hits"] += len(
                    targets & combined
                )
                metrics["hot"][str(size)]["with_scope_all_hit_steps"] += (
                    targets <= combined
                )
    return _finish(metrics)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    profile = json.loads(args.profile.expanduser().read_text())
    if int(profile.get("version", 0)) < 2:
        raise ValueError("transition analysis requires a version 2 Scope profile")
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite analysis: {args.output}")
    num_experts = int(profile["num_experts"])
    trained: dict[str, Any] = {}
    global_counts: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for name, scope in profile["scopes"].items():
        sequences = scope["decode_sequences"]
        if len(sequences) < 2:
            raise ValueError(f"scope {name} needs at least two packs")
        counts, transitions, observations = _train(sequences[:-1])
        static = {layer: _ranking(values, num_experts) for layer, values in counts.items()}
        trained[name] = (static, transitions, observations, sequences[-1])
        for layer, values in counts.items():
            for expert, count in values.items():
                global_counts[layer][expert] += count
    global_static = {
        layer: _ranking(values, num_experts) for layer, values in global_counts.items()
    }
    per_scope = {
        name: _evaluate_scope(held_out, static, global_static, transitions, observations)
        for name, (static, transitions, observations, held_out) in trained.items()
    }
    aggregate_raw = _new_metrics()
    for values in per_scope.values():
        routes = values["route_count"]
        steps = values["layer_steps"]
        aggregate_raw["routes"] += routes
        aggregate_raw["layer_steps"] += steps
        aggregate_raw["scope_top80_hits"] += round(
            values["scope_top80_route_coverage"] * routes
        )
        aggregate_raw["global_top80_hits"] += round(
            values["global_top80_route_coverage"] * routes
        )
        aggregate_raw["scope_top80_all_hit_steps"] += round(
            values["scope_top80_all_hit_rate"] * steps
        )
        aggregate_raw["global_top80_all_hit_steps"] += round(
            values["global_top80_all_hit_rate"] * steps
        )
        for size in HOT_SIZES:
            source = values["hot"][str(size)]
            aggregate_raw["hot"][str(size)]["hits"] += round(
                source["route_coverage"] * routes
            )
            aggregate_raw["hot"][str(size)]["all_hit_steps"] += round(
                source["all_hit_rate"] * steps
            )
            aggregate_raw["hot"][str(size)]["with_scope_hits"] += round(
                source["with_scope_top80_route_coverage"] * routes
            )
            aggregate_raw["hot"][str(size)]["with_scope_all_hit_steps"] += round(
                source["with_scope_top80_all_hit_rate"] * steps
            )
    overlaps = []
    for left, right in combinations(sorted(trained), 2):
        for layer in global_static:
            left_bank = set(trained[left][0][layer][:80])
            right_bank = set(trained[right][0][layer][:80])
            overlaps.append(len(left_bank & right_bank) / 80)
    result = {
        "format": "omlx-glm5-scope-profile-analysis",
        "version": 1,
        "source_profile": str(args.profile.expanduser().resolve()),
        "split_policy": "first 3 packs train, final pack held out per scope",
        "hot_policy": "retain previous Top-8, fill remaining slots from conditional transitions then Scope rank",
        "aggregate": _finish(aggregate_raw),
        "scope_top80_pairwise_overlap": {
            "mean": sum(overlaps) / len(overlaps),
            "minimum": min(overlaps),
            "maximum": max(overlaps),
        },
        "per_scope": per_scope,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(result, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))
    print(json.dumps(result["scope_top80_pairwise_overlap"], indent=2))


if __name__ == "__main__":
    main()
