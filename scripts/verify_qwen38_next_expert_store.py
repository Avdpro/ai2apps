#!/usr/bin/env python3
"""Byte-for-byte sampled verification of a Qwen4 expert-major store."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from omlx.cache.qwen4_expert_store import (
    discover_qwen4_expert_rows,
    verify_qwen4_expert_major_store,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("store", type=Path)
    parser.add_argument("--experts", default="0,127,255,511")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    experts = tuple(int(value) for value in args.experts.split(","))
    discovered = discover_qwen4_expert_rows(args.checkpoint)
    reports = []
    for layer in range(48):
        report = verify_qwen4_expert_major_store(
            args.checkpoint,
            layer,
            args.store / f"layer-{layer:03d}.moe",
            experts=experts,
            discovered=discovered,
        )
        print(json.dumps(report), flush=True)
        reports.append(report)
    result = {
        "format": "omlx-qwen4-expert-store-verification-v1",
        "checkpoint": str(args.checkpoint.expanduser().resolve()),
        "store": str(args.store.expanduser().resolve()),
        "layers": reports,
        "checked_bytes": sum(item["checked_bytes"] for item in reports),
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"summary": result}), flush=True)


if __name__ == "__main__":
    main()
