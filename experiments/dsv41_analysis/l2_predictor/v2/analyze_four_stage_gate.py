"""Check whether confidence can gate Block6 for a useful fraction of tokens."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from evaluate_four_stage import DATA_ROOT, LAYERS, align_a, all_layer_labels


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--suffix", default="r512-s17")
    parser.add_argument("--stage-suffix", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    suffixes = dict(item.split("=", 1) for item in args.stage_suffix)
    plan = json.loads((DATA_ROOT / "plan.json").read_text())
    chunks = []
    stage_values = {}
    for name in LAYERS:
        suffix = suffixes.get(name, args.suffix)
        with np.load(args.root / f"{name}-{suffix}" / "validation-scores.npz") as data:
            scores = data["scores"]
        scores = align_a(scores, plan) if name == "A" else scores
        chunks.append(scores)
        stage_values[name] = scores
    scores = np.concatenate(chunks, axis=1)
    resident, truth = all_layer_labels(plan)
    target_resident = resident[:, 3:]
    target_truth = truth[:, 3:].astype(bool)
    eligible = target_resident == 0
    flattened = np.where(eligible, scores, -np.inf).reshape(len(scores), -1)
    order = np.argsort(flattened, axis=-1)[:, -64:][:, ::-1]
    selected_scores = np.take_along_axis(flattened, order, axis=-1)
    correct = np.take_along_axis((target_truth & eligible).reshape(len(scores), -1), order, axis=-1)
    useful = correct.sum(axis=1)
    misses = (truth.astype(bool) & (resident == 0)).sum(axis=(1, 2))
    coverage = useful / np.maximum(misses, 1)
    # Logits are trained with the same objective but not calibrated. Ranking by
    # their top-candidate mean is enough to test confidence separability.
    confidence = selected_scores[:, :16].mean(axis=1)
    ranked = np.argsort(confidence)[::-1]
    curves = {}
    for fraction in (0.01, 0.05, 0.1, 0.2, 0.5, 1.0):
        count = max(1, int(round(len(scores) * fraction)))
        chosen = ranked[:count]
        curves[str(fraction)] = {
            "tokens": count,
            "weighted_miss_coverage": int(useful[chosen].sum()) / int(misses[chosen].sum()),
            "mean_token_coverage": float(coverage[chosen].mean()),
            "fraction_tokens_at_least_70pct": float((coverage[chosen] >= 0.7).mean()),
        }
    stage_gates = {}
    allocations = {"A": 12, "B": 22, "C": 15, "D": 15}
    for name, layers in LAYERS.items():
        stage_scores = stage_values[name]
        stage_resident = resident[:, layers]
        stage_truth = truth[:, layers].astype(bool)
        stage_eligible = stage_resident == 0
        flattened = np.where(stage_eligible, stage_scores, -np.inf).reshape(len(scores), -1)
        take = allocations[name]
        order = np.argsort(flattened, axis=-1)[:, -take:][:, ::-1]
        chosen_scores = np.take_along_axis(flattened, order, axis=-1)
        correct = np.take_along_axis((stage_truth & stage_eligible).reshape(len(scores), -1), order, axis=-1)
        stage_useful = correct.sum(axis=1)
        stage_misses = (stage_truth & stage_eligible).sum(axis=(1, 2))
        stage_coverage = stage_useful / np.maximum(stage_misses, 1)
        stage_confidence = chosen_scores[:, : min(8, take)].mean(axis=1)
        stage_ranked = np.argsort(stage_confidence)[::-1]
        stage_curves = {}
        for fraction in (0.05, 0.1, 0.2, 0.5, 1.0):
            count = max(1, int(round(len(scores) * fraction)))
            chosen = stage_ranked[:count]
            stage_curves[str(fraction)] = {
                "weighted_miss_coverage": int(stage_useful[chosen].sum()) / max(int(stage_misses[chosen].sum()), 1),
                "fraction_at_least_70pct": float((stage_coverage[chosen] >= 0.7).mean()),
            }
        stage_gates[name] = {
            "budget": take,
            "oracle_fraction_at_least_70pct": float((stage_coverage >= 0.7).mean()),
            "confidence_curves": stage_curves,
        }

    result = {
        "rows": len(scores),
        "confidence": "mean raw logit of top16 eligible proposals",
        "curves": curves,
        "oracle_fraction_tokens_at_least_70pct": float((coverage >= 0.7).mean()),
        "oracle_fraction_tokens_at_least_60pct": float((coverage >= 0.6).mean()),
        "stage_gates": stage_gates,
        "test_opened": False,
        "warning": "validation diagnostic only; confidence threshold cannot be accepted on this same split",
    }
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
