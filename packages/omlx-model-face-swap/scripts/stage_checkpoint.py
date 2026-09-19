#!/usr/bin/env python3
"""Build a local immutable MLX GhostV2 checkpoint directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

BUNDLE_FILES = ("bundle.json", "graph.json", "weights.safetensors")
GENERATOR_FILES = ("config.json", "weights.safetensors")
ASSET_FILES = ("LICENSE", "YUNET_LICENSE", "NOTICE.md", "README.md")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def copy_file(source: Path, target: Path, root: Path) -> dict:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return {
        "path": str(target.relative_to(root)),
        "size": target.stat().st_size,
        "sha256": sha256(target),
    }


def copy_group(source: Path, target: Path, names: tuple[str, ...], root: Path) -> list[dict]:
    return [copy_file(source / name, target / name, root) for name in names]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector", type=Path, required=True)
    parser.add_argument("--recognizer", type=Path, required=True)
    parser.add_argument("--generator", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)

    detector_target = args.output / "models" / "face_detection_yunet_2023mar.omlx"
    recognizer_target = args.output / "models" / "ghostv2_cvlface.omlx"
    generator_target = args.output / "models" / "ghostv2_generator.native"
    files = copy_group(args.detector, detector_target, BUNDLE_FILES, args.output)
    files += copy_group(args.recognizer, recognizer_target, BUNDLE_FILES, args.output)
    files += copy_group(args.generator, generator_target, GENERATOR_FILES, args.output)

    assets = Path(__file__).resolve().parents[1] / "checkpoint-assets"
    files += [copy_file(assets / name, args.output / name, args.output) for name in ASSET_FILES]
    conversion_receipt = {
        "schema": "ai2apps.mlx-ghostv2-conversion/v1",
        "source": {
            "repo_id": "dimitribarbot/ghostv2",
            "revision": "bc53ed086dbe8ea38e165aec7aaac90d1749a335",
            "generator_sha256": "6e45013c280f0afb7ad2760e6d2f80f4e754e6f4096f11edf0faf8dec29f4c22",
            "cvlface_sha256": "5fafd6b7d599a3ede5fac5bd1d01ad05e9e93e89b39b7687d4a3bc93ff2aebc0",
        },
        "output": {
            "native_generator_sha256": sha256(generator_target / "weights.safetensors"),
            "layout": "NHWC",
            "precision": "fp16",
            "batch_norm_fused": True,
        },
        "validation": {
            "torch_mps_tensor_mae": 0.000627,
            "torch_mps_tensor_rmse": 0.001176,
        },
    }
    receipt_path = args.output / "conversion-receipt.json"
    receipt_path.write_text(
        json.dumps(conversion_receipt, indent=2) + "\n", encoding="utf-8"
    )
    files.append(
        {
            "path": "conversion-receipt.json",
            "size": receipt_path.stat().st_size,
            "sha256": sha256(receipt_path),
        }
    )
    manifest = {
        "schema": "ai2apps.mlx-ghostv2-checkpoint/v1",
        "architecture": "ghostv2",
        "implementation": "native-nhwc-mlx",
        "source": {
            "repo_id": "dimitribarbot/ghostv2",
            "revision": "bc53ed086dbe8ea38e165aec7aaac90d1749a335",
        },
        "components": {
            "detector": "models/face_detection_yunet_2023mar.omlx",
            "recognizer": "models/ghostv2_cvlface.omlx",
            "generator": "models/ghostv2_generator.native",
        },
        "profiles": {
            "quality": {"precision": "fp16", "batch_size": 2, "detection_interval": 1, "default": True},
            "fast_export": {"precision": "fp16", "batch_size": 8, "detection_interval": 2, "default": False},
        },
        "minimum_unified_memory_bytes": 16 * 1024**3,
        "license": {"id": "BSD-3-Clause", "redistribution": "allowed"},
        "files": files,
    }
    manifest_path = args.output / "ai2apps-checkpoint.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "files": len(files),
                "size": sum(item["size"] for item in files),
                "manifest_sha256": sha256(manifest_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
