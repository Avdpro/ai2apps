#!/usr/bin/env python3
"""Create page-aligned expert-major layer files from a DMoE offset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from omlx.cache.moe_expert_store import (
    HEADER_BYTES,
    ExpertMajorStore,
    create_expert_major_store,
)


def payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        handle.seek(HEADER_BYTES)
        while chunk := handle.read(16 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_directory_manifest(output_dir: Path) -> None:
    layers = {}
    for path in sorted(output_dir.glob("layer-*.moe")):
        with ExpertMajorStore(path) as store:
            layers[str(store.layer)] = {
                "file": path.name,
                "num_experts": store.num_experts,
                "record_bytes": store.record_bytes,
                "file_bytes": path.stat().st_size,
            }
    manifest = {
        "format": "omlx-moe-expert-major-set",
        "version": 1,
        "layers": layers,
    }
    temporary = output_dir / "manifest.json.partial"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    temporary.replace(output_dir / "manifest.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("offset_manifest")
    parser.add_argument("output_dir")
    parser.add_argument("--layers", type=int, nargs="+", required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    for layer in args.layers:
        started = time.perf_counter()
        result = create_expert_major_store(
            args.offset_manifest,
            layer,
            output_dir / f"layer-{layer:03d}.moe",
            force=args.force,
        )
        result["seconds"] = round(time.perf_counter() - started, 3)
        result["gb_per_second"] = round(
            result["record_bytes"] * result["experts"] / result["seconds"] / 1e9,
            3,
        )
        if args.verify:
            result["verified"] = (
                payload_sha256(Path(result["path"])) == result["sha256_payload"]
            )
            if not result["verified"]:
                raise RuntimeError(f"payload checksum mismatch for layer {layer}")
        print(json.dumps(result, sort_keys=True), flush=True)
    write_directory_manifest(output_dir)


if __name__ == "__main__":
    main()
