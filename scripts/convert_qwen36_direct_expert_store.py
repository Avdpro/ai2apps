#!/usr/bin/env python3
"""Convert a Qwen3.5/3.6 MLX checkpoint directly to final expert records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from omlx.cache.qwen36_expert_store import (
    create_qwen36_direct_store,
    discover_qwen36_expert_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    checkpoint = args.checkpoint.expanduser().resolve()
    output = args.output.expanduser().resolve()
    discovered = discover_qwen36_expert_rows(checkpoint)
    results = []
    for layer in sorted(discovered):
        result = create_qwen36_direct_store(
            checkpoint,
            layer,
            output / f"layer-{layer:03d}.moe",
            force=args.force,
            discovered=discovered,
        )
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)

    manifest = {
        "format": "omlx-qwen36-expert-major-set-v1",
        "variant": "qwen3.6-affine-q4-gate-up-fused-direct-v3",
        "checkpoint": str(checkpoint),
        "layers": results,
        "total_bytes": sum(int(item["file_bytes"]) for item in results),
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({"summary": manifest}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
