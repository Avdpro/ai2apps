"""Offline shared-budget union of four-stage and calibrated adjacent lookahead."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from evaluate_four_stage import DATA_ROOT, LAYERS, align_a, all_layer_labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--four-stage-root", type=Path, required=True)
    parser.add_argument("--suffix", default="r512-s17")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads((DATA_ROOT / "plan.json").read_text())
    stage_data = {}
    for name in LAYERS:
        with np.load(args.four_stage_root / f"{name}-{args.suffix}" / "validation-scores.npz") as data:
            values = {key: data[key] for key in ("scores", "resident", "truth")}
        if name == "A":
            values = {key: align_a(value, plan) for key, value in values.items()}
        stage_data[name] = values

    four_scores = np.concatenate([stage_data[name]["scores"] for name in LAYERS], axis=1)
    four_resident = np.concatenate([stage_data[name]["resident"] for name in LAYERS], axis=1)
    four_truth = np.concatenate([stage_data[name]["truth"] for name in LAYERS], axis=1).astype(bool)
    target_layers = np.arange(3, 40, dtype=np.int32)

    lookahead_root = DATA_ROOT / "lookahead-full-extended-r64" / "priority"
    with np.load(lookahead_root / "validation-proposals.npz") as data:
        lookahead = {key: data[key] for key in data.files}
    with np.load(lookahead_root / "priority-policy.npz") as data:
        policy = {key: data[key] for key in data.files}
    gap = lookahead["scores"] - lookahead["scores"][..., 5:6]
    bins = np.searchsorted(policy["edges"], gap)
    probabilities = policy["prob"][np.arange(40)[None, :, None], np.arange(12)[None, None, :], bins]

    all_resident, all_truth = all_layer_labels(plan)
    rows = len(all_truth)
    assert rows == len(four_scores) == len(probabilities)
    all_misses = int((all_truth.astype(bool) & (all_resident == 0)).sum())

    results = {}
    for four_budget in (0, 8, 16, 24, 32, 40, 48):
        for mode in ("global_probability", "causal_reservation"):
            for factor in ((0.0, 0.5, 1.0, 1.25) if mode == "causal_reservation" else (0.0,)):
                useful = 0
                reads = 0
                four_useful = 0
                adjacent_useful = 0
                for row in range(rows):
                    selected: set[int] = set()
                    eligible = four_resident[row] == 0
                    masked = np.where(eligible, four_scores[row], -np.inf).reshape(-1)
                    if four_budget:
                        order = np.argsort(masked)[-four_budget:][::-1]
                        for flat in order:
                            if not np.isfinite(masked[flat]):
                                continue
                            local_layer, expert = divmod(int(flat), 384)
                            code = (local_layer + 3) * 384 + expert
                            if code in selected:
                                continue
                            selected.add(code)
                            reads += 1
                            if four_truth[row, local_layer, expert]:
                                useful += 1
                                four_useful += 1

                    if mode == "global_probability":
                        flat_probability = np.where(lookahead["eligible"][row], probabilities[row], -np.inf).reshape(-1)
                        order = np.argsort(flat_probability)[::-1]
                        for flat in order:
                            if len(selected) >= 64 or not np.isfinite(flat_probability[flat]):
                                break
                            layer, rank = divmod(int(flat), 12)
                            expert = int(lookahead["ids"][row, layer, rank])
                            code = layer * 384 + expert
                            if code in selected:
                                continue
                            selected.add(code)
                            reads += 1
                            if lookahead["correct"][row, layer, rank]:
                                useful += 1
                                adjacent_useful += 1
                    else:
                        for layer in range(40):
                            order = np.argsort(probabilities[row, layer])[::-1]
                            for rank in order:
                                if len(selected) >= 64:
                                    break
                                if not lookahead["eligible"][row, layer, rank]:
                                    continue
                                expert = int(lookahead["ids"][row, layer, rank])
                                code = layer * 384 + expert
                                if code in selected:
                                    continue
                                probability = probabilities[row, layer, rank]
                                reserve = policy["future_better"][layer, min(int(probability * 100), 100)]
                                if 64 - len(selected) <= factor * reserve:
                                    continue
                                selected.add(code)
                                reads += 1
                                if lookahead["correct"][row, layer, rank]:
                                    useful += 1
                                    adjacent_useful += 1
                name = f"four{four_budget}/{mode}/{factor}"
                results[name] = {
                    "coverage": useful / all_misses,
                    "reads_per_token": reads / rows,
                    "useful_per_token": useful / rows,
                    "precision": useful / max(reads, 1),
                    "four_stage_useful_per_token": four_useful / rows,
                    "adjacent_useful_per_token": adjacent_useful / rows,
                }
    result = {
        "rows": rows,
        "all40_misses": all_misses,
        "cap": 64,
        "results": results,
        "scope": "same-token unique proposal union; fixed L0/L1 trace; no cross-token L2 persistence or SSD deadline simulation",
        "global_probability_warning": "uses future adjacent confidence ordering and is an optimistic scheduler ceiling",
        "causal_reservation": "train-calibrated adjacent probabilities and future-opportunity reservation; four-stage quota is spent first",
        "test_opened": False,
    }
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
