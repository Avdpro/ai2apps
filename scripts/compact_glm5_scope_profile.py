#!/usr/bin/env python3
"""Compact a GLM5 v2 Scope profile while retaining lossless route sequences."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from omlx.patches.glm5_next_cache.scope_profile import TRANSITION_TARGET_LIMIT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite compact profile: {args.output}")
    profile = json.loads(args.source.expanduser().read_text())
    if int(profile.get("version", 0)) < 2:
        raise ValueError("compaction requires a version 2 Scope profile")
    for scope in profile["scopes"].values():
        for transition in scope["decode_transitions"].values():
            transition["target_limit_per_source"] = TRANSITION_TARGET_LIMIT
            for source in transition["sources"].values():
                source["targets"] = source["targets"][:TRANSITION_TARGET_LIMIT]
    profile["metadata"]["transition_storage"] = {
        "target_limit_per_source": TRANSITION_TARGET_LIMIT,
        "lossless_decode_sequences": True,
        "note": "Full sparse transitions can be reconstructed from decode_sequences.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(profile, target, ensure_ascii=False, separators=(",", ":"))
        target.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()
