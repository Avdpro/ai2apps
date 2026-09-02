#!/usr/bin/env python3
"""Strip Qwen3.8 Scope training traces down to the runtime banks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite runtime profile: {args.output}")
    raw = args.source.expanduser().read_bytes()
    profile = json.loads(raw)
    compact = {
        "format": "omlx-qwen38-next-runtime-scope-profile",
        "version": 1,
        "capacity": int(profile["capacity"]),
        "num_experts": int(profile["num_experts"]),
        "scopes": {
            name: {
                "layers": scope["layers"],
                "phase_layers": scope["phase_layers"],
            }
            for name, scope in profile["scopes"].items()
        },
        "metadata": {
            "model_family": "qwen3.8-flash-next",
            "source": str(args.source.expanduser().resolve()),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "dataset": profile["metadata"].get("dataset"),
            "dataset_sha256": profile["metadata"].get("dataset_sha256"),
            "split": profile["metadata"].get("split"),
            "bank_policy": profile["metadata"].get("bank_policy"),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as target:
        json.dump(compact, target, ensure_ascii=False, separators=(",", ":"))
        target.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": args.output.stat().st_size,
                "scopes": len(compact["scopes"]),
            }
        )
    )


if __name__ == "__main__":
    main()
