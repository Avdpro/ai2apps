#!/usr/bin/env python3
"""Convert split Qwen affine-Q4 records to gate/up-fused runtime records."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from omlx.patches.qwen3_6_flesh.checkpoint import create_qwen36_fused_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--layers", type=int, nargs="+", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source_dir = Path(args.source_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    for layer in args.layers:
        started = time.perf_counter()
        result = create_qwen36_fused_store(
            source_dir / f"layer-{layer:03d}.moe",
            output_dir / f"layer-{layer:03d}.moe",
            force=args.force,
        )
        result["seconds"] = round(time.perf_counter() - started, 3)
        print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
