"""Combine frozen A/B/C/D validation scores under one per-token read budget."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


DATA_ROOT = Path("artifacts/dsv41-l2-state-v3-20260916")
LAYERS = {"A": tuple(range(3, 10)), "B": tuple(range(10, 20)), "C": tuple(range(20, 30)), "D": tuple(range(30, 40))}
EXPERT_MB = 18.800640


def align_a(values: np.ndarray, plan: dict) -> np.ndarray:
    """Drop the final row of every validation conversation, matching B/C/D."""
    pieces = []
    offset = 0
    for sample in plan["samples"]:
        if sample["split"] != "validation":
            continue
        with np.load(DATA_ROOT / "data" / sample["id"] / "supervision.npz") as data:
            rows = len(data["top6"])
        pieces.append(values[offset : offset + rows - 1])
        offset += rows
    assert offset == len(values)
    return np.concatenate(pieces)


def all_layer_labels(plan: dict) -> tuple[np.ndarray, np.ndarray]:
    residents = []
    truths = []
    for sample in plan["samples"]:
        if sample["split"] != "validation":
            continue
        with np.load(DATA_ROOT / "data" / sample["id"] / "supervision.npz") as data:
            resident = data["resident"][:-1].astype(np.uint8)
            top6 = data["top6"][:-1].astype(np.int64)
        truth = np.zeros(resident.shape, dtype=np.uint8)
        np.put_along_axis(truth, top6, 1, axis=-1)
        residents.append(resident)
        truths.append(truth)
    return np.concatenate(residents), np.concatenate(truths)


def stage_curves(scores: np.ndarray, resident: np.ndarray, truth: np.ndarray, maximum: int) -> np.ndarray:
    rows = len(scores)
    eligible = resident == 0
    flattened = np.where(eligible, scores, -np.inf).reshape(rows, -1)
    order = np.argsort(flattened, axis=-1)[:, -maximum:][:, ::-1]
    good = np.take_along_axis((truth.astype(bool) & eligible).reshape(rows, -1), order, axis=-1)
    cumulative = np.concatenate([np.zeros((rows, 1), dtype=np.int64), np.cumsum(good, axis=1)], axis=1)
    return cumulative.sum(axis=0)


def best_allocation(curves: dict[str, np.ndarray], budget: int) -> tuple[dict[str, int], int]:
    names = tuple(curves)
    # Dynamic programming over four stage reservation sizes. This is a
    # validation-selected development diagnostic, not an independent result.
    states: dict[int, tuple[int, tuple[int, ...]]] = {0: (0, ())}
    for name in names:
        next_states: dict[int, tuple[int, tuple[int, ...]]] = {}
        for used, (value, allocation) in states.items():
            for take in range(budget - used + 1):
                candidate = value + int(curves[name][take])
                total = used + take
                if total not in next_states or candidate > next_states[total][0]:
                    next_states[total] = (candidate, allocation + (take,))
        states = next_states
    useful, allocation = states[budget]
    return dict(zip(names, allocation)), useful


def evaluate_global(scores: np.ndarray, resident: np.ndarray, truth: np.ndarray, budget: int) -> int:
    rows = len(scores)
    eligible = resident == 0
    flattened = np.where(eligible, scores, -np.inf).reshape(rows, -1)
    order = np.argsort(flattened, axis=-1)[:, -budget:]
    good = np.take_along_axis((truth.astype(bool) & eligible).reshape(rows, -1), order, axis=-1)
    return int(good.sum())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--suffix", default="r256-s17")
    parser.add_argument(
        "--stage-suffix",
        action="append",
        default=[],
        metavar="STAGE=SUFFIX",
        help="override --suffix for one stage; may be repeated",
    )
    args = parser.parse_args()
    plan = json.loads((DATA_ROOT / "plan.json").read_text())

    suffixes = {name: args.suffix for name in LAYERS}
    for item in args.stage_suffix:
        try:
            name, suffix = item.split("=", 1)
        except ValueError as exc:
            raise SystemExit(f"invalid --stage-suffix {item!r}; expected STAGE=SUFFIX") from exc
        if name not in suffixes or not suffix:
            raise SystemExit(f"invalid --stage-suffix {item!r}; stage must be one of {tuple(LAYERS)}")
        suffixes[name] = suffix

    stage_data = {}
    for name in LAYERS:
        with np.load(args.root / f"{name}-{suffixes[name]}" / "validation-scores.npz") as data:
            values = {key: data[key] for key in ("scores", "resident", "truth")}
        if name == "A":
            values = {key: align_a(value, plan) for key, value in values.items()}
        stage_data[name] = values

    all_resident, all_truth = all_layer_labels(plan)
    rows = len(all_resident)
    assert all(len(values["scores"]) == rows for values in stage_data.values())
    all_misses = int((all_truth.astype(bool) & (all_resident == 0)).sum())

    result = {
        "rows": rows,
        "all40_misses": all_misses,
        "all40_misses_per_token": all_misses / rows,
        "stage_suffixes": suffixes,
        "selection_warning": "fixed reservations are optimized on this validation set; independent acceptance remains unopened",
        "variants": {},
    }
    for variant, first_layers in {"A3": LAYERS["A"], "A5": tuple(range(5, 10))}.items():
        selected = {}
        for name, values in stage_data.items():
            if name == "A" and variant == "A5":
                selected[name] = {key: value[:, 2:] for key, value in values.items()}
            else:
                selected[name] = values
        scores = np.concatenate([selected[name]["scores"] for name in LAYERS], axis=1)
        resident = np.concatenate([selected[name]["resident"] for name in LAYERS], axis=1)
        truth = np.concatenate([selected[name]["truth"] for name in LAYERS], axis=1)
        target_misses = int((truth.astype(bool) & (resident == 0)).sum())
        variant_result = {
            "target_layers": [first_layers[0], 39],
            "target_misses": target_misses,
            "uncovered_early_misses": all_misses - target_misses,
            "budgets": {},
        }
        for budget in (48, 64):
            curves = {
                name: stage_curves(values["scores"], values["resident"], values["truth"], budget)
                for name, values in selected.items()
            }
            allocation, fixed_useful = best_allocation(curves, budget)
            raw_useful = evaluate_global(scores, resident, truth, budget)
            variant_result["budgets"][str(budget)] = {
                "validation_optimized_fixed_reservations": {
                    "allocation": allocation,
                    "useful_per_token": fixed_useful / rows,
                    "all40_miss_coverage": fixed_useful / all_misses,
                    "precision": fixed_useful / (rows * budget),
                    "wasted_MB_per_token": (budget - fixed_useful / rows) * EXPERT_MB,
                },
                "raw_cross_stage_logits": {
                    "useful_per_token": raw_useful / rows,
                    "all40_miss_coverage": raw_useful / all_misses,
                    "precision": raw_useful / (rows * budget),
                    "wasted_MB_per_token": (budget - raw_useful / rows) * EXPERT_MB,
                },
            }
        result["variants"][variant] = variant_result
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
