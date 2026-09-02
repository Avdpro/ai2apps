#!/usr/bin/env python3
"""Compare trained Qwen3.8 Scope banks with held-out router traces."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


def _global_banks(profile: dict[str, Any], capacity: int) -> dict[str, list[int]]:
    num_experts = int(profile["num_experts"])
    counts: dict[str, list[int]] = defaultdict(lambda: [0] * num_experts)
    mass: dict[str, list[float]] = defaultdict(lambda: [0.0] * num_experts)
    for scope in profile["scopes"].values():
        for layer, stats in scope["layer_stats"].items():
            phase = stats["phases"]["decode"]
            for expert, value in enumerate(phase["counts_by_expert"]):
                counts[layer][expert] += int(value)
            for expert, value in enumerate(phase["mass_by_expert"]):
                mass[layer][expert] += float(value)
    result = {}
    for layer in counts:
        count_total = max(sum(counts[layer]), 1)
        mass_total = max(sum(mass[layer]), 1e-12)
        scores = [
            0.75 * counts[layer][expert] / count_total
            + 0.25 * mass[layer][expert] / mass_total
            for expert in range(num_experts)
        ]
        result[layer] = sorted(
            range(num_experts), key=lambda expert: (-scores[expert], expert)
        )[:capacity]
    return result


def _empty() -> dict[str, int]:
    return {
        "routes": 0,
        "steps": 0,
        "scope_hits": 0,
        "scope_all_hit": 0,
        "global_hits": 0,
        "global_all_hit": 0,
        "previous_hits": 0,
        "previous_all_hit": 0,
        "combined_hits": 0,
        "combined_all_hit": 0,
    }


def _add(target: dict[str, int], source: dict[str, int]) -> None:
    for key in target:
        target[key] += source[key]


def _finish(raw: dict[str, int]) -> dict[str, Any]:
    routes = raw["routes"]
    steps = raw["steps"]
    return {
        "route_count": routes,
        "layer_steps": steps,
        "scope_route_coverage": raw["scope_hits"] / routes,
        "scope_all_hit_rate": raw["scope_all_hit"] / steps,
        "global_route_coverage": raw["global_hits"] / routes,
        "global_all_hit_rate": raw["global_all_hit"] / steps,
        "previous_top10_route_coverage": raw["previous_hits"] / routes,
        "previous_top10_all_hit_rate": raw["previous_all_hit"] / steps,
        "scope_plus_previous_top10_route_coverage": raw["combined_hits"] / routes,
        "scope_plus_previous_top10_all_hit_rate": raw["combined_all_hit"] / steps,
    }


def _evaluate(
    traces: list[dict[str, Any]],
    scope_bank: dict[str, list[int]],
    global_bank: dict[str, list[int]],
) -> tuple[dict[str, Any], dict[str, int]]:
    raw = _empty()
    for pack in traces:
        for layer, routes in pack["layers"].items():
            own = set(scope_bank[layer])
            common = set(global_bank[layer])
            for previous, current in zip(routes, routes[1:], strict=False):
                targets = set(current)
                hot = set(previous)
                combined = own | hot
                raw["routes"] += len(targets)
                raw["steps"] += 1
                raw["scope_hits"] += len(targets & own)
                raw["scope_all_hit"] += targets <= own
                raw["global_hits"] += len(targets & common)
                raw["global_all_hit"] += targets <= common
                raw["previous_hits"] += len(targets & hot)
                raw["previous_all_hit"] += targets <= hot
                raw["combined_hits"] += len(targets & combined)
                raw["combined_all_hit"] += targets <= combined
    return _finish(raw), raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("train_profile", type=Path)
    parser.add_argument("held_out_profile", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite analysis: {args.output}")
    train = json.loads(args.train_profile.expanduser().read_text())
    held_out = json.loads(args.held_out_profile.expanduser().read_text())
    if train["num_experts"] != held_out["num_experts"]:
        raise ValueError("train and held-out expert universes differ")
    capacity = int(train["capacity"])
    global_bank = _global_banks(train, capacity)
    per_scope = {}
    aggregate = _empty()
    banks = {}
    for name, scope in train["scopes"].items():
        if name not in held_out["scopes"]:
            raise ValueError(f"held-out profile is missing scope {name}")
        bank = scope.get("phase_layers", {}).get("decode") or scope["layers"]
        banks[name] = bank
        metrics, raw = _evaluate(
            held_out["scopes"][name]["decode_sequences"], bank, global_bank
        )
        per_scope[name] = metrics
        _add(aggregate, raw)

    overlaps = []
    for left, right in combinations(sorted(banks), 2):
        for layer in global_bank:
            overlaps.append(
                len(set(banks[left][layer]) & set(banks[right][layer])) / capacity
            )
    result = {
        "format": "omlx-qwen38-next-scope-profile-analysis",
        "version": 1,
        "train_profile": str(args.train_profile.expanduser().resolve()),
        "held_out_profile": str(args.held_out_profile.expanduser().resolve()),
        "capacity": capacity,
        "hot_policy": "exact previous-token Top-10 union Scope bank",
        "aggregate": _finish(aggregate),
        "scope_pairwise_overlap": {
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
    print(json.dumps(result["scope_pairwise_overlap"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
