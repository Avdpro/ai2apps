"""Audit whether the v3 exact-forward corpus can train the four-stage L2 heads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


ROOT = Path("artifacts/dsv41-l2-state-v3-20260916")
TARGET_LAYERS = tuple(range(3, 40))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads((ROOT / "plan.json").read_text())
    assert plan["schema"] == "dsv41.l2-supervision/v3"

    families: dict[str, set[str]] = {"train": set(), "validation": set()}
    split_rows = {"train": 0, "validation": 0}
    aligned_rows = {"train": 0, "validation": 0}
    misses = {"train": 0, "validation": 0}
    early_misses = {"train": 0, "validation": 0}
    oracle_useful = {
        "train": {48: 0, 64: 0},
        "validation": {48: 0, 64: 0},
    }
    sequences = {"train": 0, "validation": 0}

    for sample in plan["samples"]:
        split = sample["split"]
        if split not in families:
            continue
        data_dir = ROOT / "data" / sample["id"]
        verified = json.loads((data_dir / "verified.json").read_text())
        assert verified["rows"] > 1, sample["id"]
        with np.load(data_dir / "supervision.npz", mmap_mode="r") as data:
            required = {
                "previous_ffn",
                "hidden",
                "embedding",
                "router_rank",
                "top6",
                "previous_top6",
                "resident",
                "position",
            }
            assert required <= set(data.files), (sample["id"], required - set(data.files))
            rows = len(data["top6"])
            assert data["previous_ffn"].shape == (rows, 40, 5120)
            assert data["router_rank"].shape == (rows, 40, 384)
            assert data["resident"].shape == (rows, 40, 384)
            assert data["top6"].shape == (rows, 40, 6)
            assert np.array_equal(data["top6"][:-1], data["previous_top6"][1:])
            assert np.all(np.diff(data["position"].astype(np.int64)) > 0)

            # B/C/D consume the current token state from the next row's
            # previous_ffn field, so every sequence contributes rows - 1.
            resident = data["resident"][:-1]
            top6 = data["top6"][:-1].astype(np.int64)
            missing = np.take_along_axis(resident, top6, axis=-1) == 0
            per_token = missing.sum(axis=(1, 2))
            targeted = missing[:, TARGET_LAYERS].sum(axis=(1, 2))

            families[split].add(sample["family_id"])
            sequences[split] += 1
            split_rows[split] += rows
            aligned_rows[split] += rows - 1
            misses[split] += int(per_token.sum())
            early_misses[split] += int(missing[:, :3].sum())
            for budget in (48, 64):
                oracle_useful[split][budget] += int(np.minimum(targeted, budget).sum())

    overlap = sorted(families["train"] & families["validation"])
    assert not overlap, overlap
    result = {
        "schema": plan["schema"],
        "target_layers": [3, 39],
        "stage_triggers": {"A": "previous token", "B": 5, "C": 15, "D": 25},
        "family_overlap": overlap,
        "splits": {},
        "verdict": "existing v3 corpus is sufficient for initial A/B/C/D training",
    }
    for split in ("train", "validation"):
        total = misses[split]
        result["splits"][split] = {
            "sequences": sequences[split],
            "families": len(families[split]),
            "stored_rows": split_rows[split],
            "four_stage_aligned_rows": aligned_rows[split],
            "misses": total,
            "early_layer_0_2_misses": early_misses[split],
            "early_layer_0_2_fraction": early_misses[split] / total,
            "oracle_all40_coverage": {
                str(budget): oracle_useful[split][budget] / total for budget in (48, 64)
            },
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
