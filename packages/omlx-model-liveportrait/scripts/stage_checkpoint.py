#!/usr/bin/env python3
"""Build the immutable MLX LivePortrait checkpoint upload directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

WEIGHT_FILES = (
    "appearance_feature_extractor.npz",
    "motion_extractor.npz",
    "spade_generator.npz",
    "warping_module.npz",
    "stitching.npz",
    "stitching_eye.npz",
    "stitching_lip.npz",
)
DETECTOR_FILES = ("bundle.json", "graph.json", "weights.safetensors")
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--detector", type=Path, required=True)
    parser.add_argument("--conversion-receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)
    files = [
        copy_file(args.weights / name, args.output / "weights" / name, args.output)
        for name in WEIGHT_FILES
    ]
    detector_target = args.output / "models" / "face_detection_yunet_2023mar.omlx"
    files.extend(
        copy_file(args.detector / name, detector_target / name, args.output)
        for name in DETECTOR_FILES
    )
    assets = Path(__file__).resolve().parents[1] / "checkpoint-assets"
    files.extend(
        copy_file(assets / name, args.output / name, args.output)
        for name in ASSET_FILES
    )
    files.append(
        copy_file(
            args.conversion_receipt,
            args.output / "conversion-receipt.json",
            args.output,
        )
    )
    manifest = {
        "schema": "ai2apps.mlx-liveportrait-checkpoint/v1",
        "architecture": "liveportrait-human",
        "implementation": "native-mlx",
        "source": {
            "repo_id": "KlingTeam/LivePortrait",
            "revision": "82a4fa6735ca58432b6ce39301b4b9ee066dea47",
        },
        "detector": {
            "family": "yunet-2023mar",
            "license": "MIT",
            "sha256": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        },
        "profiles": {
            "quality": {"precision": "fp32", "default": True},
            "fast": {"precision": "bf16", "default": False},
        },
        "unsupported_precisions": ["fp16"],
        "files": files,
    }
    (args.output / "ai2apps-checkpoint.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "files": len(files),
                "size": sum(item["size"] for item in files),
                "manifest_sha256": sha256(args.output / "ai2apps-checkpoint.json"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
