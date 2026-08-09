#!/usr/bin/env python3
"""Replay Decode route traces through static and frequency-swap caches."""

from __future__ import annotations

import argparse
import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("scope")
    parser.add_argument("traces", type=Path, nargs="+")
    parser.add_argument("--l2-slots", type=int, nargs="+", default=[8, 12, 16])
    parser.add_argument("--interval", type=int, default=16)
    parser.add_argument("--min-candidate", type=int, nargs="+", default=[3, 5])
    parser.add_argument("--margin", type=int, default=2)
    parser.add_argument("--ratio", type=float, nargs="+", default=[1.5, 2.0])
    parser.add_argument("--pinned", type=int, nargs="+", default=[4, 20, 40])
    parser.add_argument("--cooldown", type=int, nargs="+", default=[32, 64])
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _touch(l2: OrderedDict[int, None], expert: int) -> None:
    if expert in l2:
        l2.move_to_end(expert)


def replay(
    routes: list[list[list[int]]],
    banks: dict[int, list[int]],
    *,
    l2_slots: int,
    interval: int,
    dynamic: bool,
    min_candidate: int = 3,
    margin: int = 2,
    ratio: float = 1.5,
    pinned: int = 4,
    cooldown: int = 0,
) -> dict[str, Any]:
    l1 = {layer: set(bank) for layer, bank in banks.items()}
    pinned_ids = {layer: set(bank[:pinned]) for layer, bank in banks.items()}
    l2 = {layer: OrderedDict() for layer in banks}
    counts = {layer: Counter() for layer in banks}
    l1_routes = l2_routes = ssd_loads = swaps = reloads = 0
    ever_loaded = {layer: set() for layer in banks}
    last_swap = {layer: -10**9 for layer in banks}
    layer_all_l1 = layer_no_ssd = 0
    layer_steps = 0

    for token_index, token_layers in enumerate(routes, start=1):
        if len(token_layers) != 40:
            raise ValueError(f"expected 40 score layers, found {len(token_layers)}")
        for offset, selected in enumerate(token_layers):
            layer = offset + 3
            before_ssd = ssd_loads
            all_l1 = True
            for expert in selected:
                counts[layer][expert] += 1
                if expert in l1[layer]:
                    l1_routes += 1
                    continue
                all_l1 = False
                if expert in l2[layer]:
                    l2_routes += 1
                    _touch(l2[layer], expert)
                    continue
                ssd_loads += 1
                reloads += int(expert in ever_loaded[layer])
                ever_loaded[layer].add(expert)
                if len(l2[layer]) >= l2_slots:
                    l2[layer].popitem(last=False)
                l2[layer][expert] = None
            layer_all_l1 += int(all_l1)
            layer_no_ssd += int(ssd_loads == before_ssd)
            layer_steps += 1

        if dynamic and token_index % interval == 0:
            for layer, bank in banks.items():
                if not l2[layer]:
                    continue
                if token_index - last_swap[layer] < cooldown:
                    continue
                candidate = max(
                    l2[layer], key=lambda expert: (counts[layer][expert], -expert)
                )
                victims = l1[layer] - pinned_ids[layer]
                if not victims:
                    continue
                victim = min(
                    victims, key=lambda expert: (counts[layer][expert], expert)
                )
                candidate_count = counts[layer][candidate]
                victim_count = counts[layer][victim]
                if (
                    candidate_count >= min_candidate
                    and candidate_count >= victim_count + margin
                    and candidate_count >= ratio * max(victim_count, 1)
                ):
                    del l2[layer][candidate]
                    l1[layer].remove(victim)
                    l1[layer].add(candidate)
                    l2[layer][victim] = None
                    swaps += 1
                    last_swap[layer] = token_index

    total_routes = len(routes) * 40 * 6
    return {
        "decode_tokens": len(routes),
        "l2_slots": l2_slots,
        "dynamic": dynamic,
        "min_candidate": min_candidate if dynamic else None,
        "margin": margin if dynamic else None,
        "ratio": ratio if dynamic else None,
        "pinned": pinned if dynamic else None,
        "cooldown": cooldown if dynamic else None,
        "l1_route_hit_rate": l1_routes / total_routes,
        "l2_route_hit_rate": l2_routes / total_routes,
        "layer_all_l1_rate": layer_all_l1 / layer_steps,
        "layer_no_ssd_rate": layer_no_ssd / layer_steps,
        "ssd_experts_per_token": ssd_loads / len(routes),
        "ssd_loads": ssd_loads,
        "reloads": reloads,
        "swaps": swaps,
    }


def main() -> None:
    args = _args()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite simulation: {output}")
    profile = json.loads(args.profile.expanduser().read_text())
    banks = {
        layer: list(profile["scopes"][args.scope][str(layer)])
        for layer in range(3, 43)
    }
    traces = [json.loads(path.expanduser().read_text()) for path in args.traces]
    results = []
    for trace in traces:
        routes = trace["routes"]
        for slots in args.l2_slots:
            results.append(
                {
                    "sample_id": trace["sample_id"],
                    **replay(
                        routes,
                        banks,
                        l2_slots=slots,
                        interval=args.interval,
                        dynamic=False,
                    ),
                }
            )
            for minimum in args.min_candidate:
                for ratio in args.ratio:
                    for pinned in args.pinned:
                        for cooldown in args.cooldown:
                            results.append(
                                {
                                    "sample_id": trace["sample_id"],
                                    **replay(
                                        routes,
                                        banks,
                                        l2_slots=slots,
                                        interval=args.interval,
                                        dynamic=True,
                                        min_candidate=minimum,
                                        margin=args.margin,
                                        ratio=ratio,
                                        pinned=pinned,
                                        cooldown=cooldown,
                                    ),
                                }
                            )
    payload = {
        "version": 1,
        "profile": str(args.profile.expanduser().resolve()),
        "scope": args.scope,
        "interval": args.interval,
        "trace_samples": [trace["sample_id"] for trace in traces],
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "results": len(results)}))


if __name__ == "__main__":
    main()
