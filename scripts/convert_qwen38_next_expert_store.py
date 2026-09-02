#!/usr/bin/env python3
"""Convert Qwen3.8 Flash Next routed experts into direct-load records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from omlx.cache.qwen4_expert_store import (
    create_qwen4_expert_major_store,
    discover_qwen4_expert_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--layers", default="0:48", help="half-open range, e.g. 0:48")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    start_text, end_text = args.layers.split(":", 1)
    start, end = int(start_text), int(end_text)
    if not 0 <= start < end <= 48:
        raise ValueError("--layers must be within 0:48")

    discovered = discover_qwen4_expert_rows(args.checkpoint)
    reports = []
    for layer in range(start, end):
        report = create_qwen4_expert_major_store(
            args.checkpoint,
            layer,
            args.output / f"layer-{layer:03d}.moe",
            force=args.force,
            discovered=discovered,
        )
        print(json.dumps(report, ensure_ascii=False), flush=True)
        reports.append(report)
    manifest = {
        "format": "omlx-qwen4-expert-major-set-v1",
        "checkpoint": str(args.checkpoint.expanduser().resolve()),
        "layers": reports,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
