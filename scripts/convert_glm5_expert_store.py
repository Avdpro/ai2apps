#!/usr/bin/env python3
"""Convert a GLM-5 MLX checkpoint to fixed-record routed-expert stores."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from omlx.cache.glm5_expert_store import (
    create_glm5_expert_major_store,
    discover_glm5_experts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint")
    parser.add_argument("output_dir")
    parser.add_argument("--layers", type=int, nargs="*")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    checkpoint = Path(args.checkpoint).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    discovered = discover_glm5_experts(checkpoint)
    layers = sorted(discovered) if not args.layers else args.layers
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for layer in layers:
        started = time.perf_counter()
        result = create_glm5_expert_major_store(
            checkpoint,
            layer,
            output_dir / f"layer-{layer:03d}.moe",
            force=args.force,
            discovered=discovered,
        )
        result["seconds"] = round(time.perf_counter() - started, 3)
        results.append(result)
        print(json.dumps(result, sort_keys=True), flush=True)
    manifest = {
        "format": "omlx-moe-expert-major-set",
        "version": 1,
        "variant": "glm5-next-affine-q4-gate-up-fused-v2",
        "runtime_layout": "fused-switch-glu",
        "source": str(checkpoint),
        "layers": {
            str(item["layer"]): {
                "file": Path(item["path"]).name,
                "num_experts": item["experts"],
                "record_bytes": item["record_bytes"],
                "file_bytes": item["file_bytes"],
            }
            for item in results
        },
    }
    temporary = output_dir / "manifest.json.partial"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(output_dir / "manifest.json")


if __name__ == "__main__":
    main()
