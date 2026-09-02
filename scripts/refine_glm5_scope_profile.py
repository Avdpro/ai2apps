#!/usr/bin/env python3
"""Derive phase banks and corrected sample counts without replaying GLM5."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from omlx.patches.glm5_next_cache.scope_profile import refine_glm5_scope_profile


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--capacity", type=int)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite Scope artifact: {output}")
    raw = source.read_bytes()
    profile = json.loads(raw)
    if args.capacity is not None:
        if not 1 <= args.capacity <= int(profile["num_experts"]):
            raise ValueError("capacity must be within the expert universe")
        profile["capacity"] = args.capacity
    profile = refine_glm5_scope_profile(profile)
    measurements = profile["metadata"].get("measurements", [])
    for scope_name, scope in profile["scopes"].items():
        rows = [row for row in measurements if row["scope"] == scope_name]
        scope["samples"] = sum(len(row["sample_ids"]) for row in rows)
        scope["packs"] = len(rows)
    profile["metadata"]["refined_from"] = {
        "path": str(source),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as target:
        json.dump(profile, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps({"output": str(output), "scopes": len(profile["scopes"])}))


if __name__ == "__main__":
    main()
