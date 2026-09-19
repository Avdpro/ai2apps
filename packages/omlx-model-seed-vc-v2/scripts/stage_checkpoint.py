#!/usr/bin/env python3
"""Build the immutable composite MLX Seed-VC v2 checkpoint upload directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

CORE_FILES = (
    "ar.safetensors",
    "ar_length_regulator.safetensors",
    "astral_narrow.safetensors",
    "astral_wide.safetensors",
    "campplus.safetensors",
    "cfm.safetensors",
    "cfm_length_regulator.safetensors",
)
DIRECTORIES = {
    "hubert": ("model.safetensors", "config.json"),
    "bigvgan": ("model.safetensors", "config.json"),
}
ASSET_FILES = ("README.md", "NOTICE.md", "LICENSE", "config.json")


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
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--hubert", type=Path, required=True)
    parser.add_argument("--bigvgan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)
    files = [
        copy_file(args.core / name, args.output / name, args.output)
        for name in CORE_FILES
    ]
    for directory, names in DIRECTORIES.items():
        source_root = getattr(args, directory)
        files.extend(
            copy_file(source_root / name, args.output / directory / name, args.output)
            for name in names
        )
    asset_root = Path(__file__).resolve().parents[1] / "checkpoint-assets"
    files.extend(
        copy_file(asset_root / name, args.output / name, args.output)
        for name in ASSET_FILES
    )
    manifest = {
        "schema": "ai2apps.mlx-seed-vc-v2-composite/v1",
        "architecture": "seed-vc-v2",
        "implementation": "native-mlx",
        "default_profile": "timbre-quality",
        "profiles": {
            "timbre-fast": {"mode": "timbre", "diffusion_steps": 10},
            "timbre-quality": {"mode": "timbre", "diffusion_steps": 30},
            "voice-quality": {"mode": "voice", "diffusion_steps": 30},
        },
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
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
