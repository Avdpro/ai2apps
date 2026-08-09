#!/usr/bin/env python3
"""Build a non-overwriting leaf profile with a retained parent-policy core."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-profile", type=Path, required=True)
    parser.add_argument("--base-scope", required=True)
    parser.add_argument("--leaf-profile", type=Path, required=True)
    parser.add_argument("--leaf-scope", required=True)
    parser.add_argument("--keep-base", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regularized_bank(base: list[int], leaf: list[int], keep: int) -> list[int]:
    if not 0 <= keep <= 60:
        raise ValueError("--keep-base must be in 0..60")
    retained = list(base[:keep])
    bank = retained + [expert for expert in leaf if expert not in retained]
    if len(bank) < 60:
        raise ValueError("profiles do not provide 60 unique experts")
    return bank[:60]


def main() -> None:
    args = _args()
    base_path = args.base_profile.expanduser().resolve()
    leaf_path = args.leaf_profile.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Scope profile: {output}")
    if output in (base_path, leaf_path):
        raise ValueError("output must differ from both input profiles")
    base_sha = _sha256(base_path)
    leaf_sha = _sha256(leaf_path)
    base = json.loads(base_path.read_text())
    leaf = json.loads(leaf_path.read_text())

    layers = {}
    core = {}
    overlaps = {}
    for layer in range(3, 43):
        key = str(layer)
        base_bank = base["scopes"][args.base_scope][key]
        leaf_bank = leaf["scopes"][args.leaf_scope][key]
        bank = regularized_bank(base_bank, leaf_bank, args.keep_base)
        layers[key] = bank
        core[key] = bank[:4]
        overlaps[key] = len(set(bank) & set(base_bank))

    payload = {
        "version": 1,
        "format": "dmoe-deepseek-tiered-policy",
        "global_core": core,
        "scopes": {args.leaf_scope: layers},
        "metadata": {
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "method": "retain-ranked-base-then-fill-ranked-leaf",
            "keep_base": args.keep_base,
            "base_profile": str(base_path),
            "base_profile_sha256": base_sha,
            "base_scope": args.base_scope,
            "leaf_profile": str(leaf_path),
            "leaf_profile_sha256": leaf_sha,
            "leaf_scope": args.leaf_scope,
            "base_overlap_by_layer": overlaps,
        },
    }
    if _sha256(base_path) != base_sha or _sha256(leaf_path) != leaf_sha:
        raise RuntimeError("an input Scope profile changed during regularization")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        target.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"output": str(output), "keep_base": args.keep_base}))


if __name__ == "__main__":
    main()
