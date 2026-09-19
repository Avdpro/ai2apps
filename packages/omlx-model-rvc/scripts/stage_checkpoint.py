#!/usr/bin/env python3
"""Build the immutable composite MLX-RVC checkpoint upload directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
from pathlib import Path

COMPONENT_FILES = {
    "voice": ("model.safetensors", "model.json", "index.safetensors", "index.json"),
    "contentvec": ("model.safetensors", "config.json", "manifest.json"),
    "rmvpe": ("model.safetensors", "mel_basis.safetensors", "manifest.json"),
    "training": ("generator.safetensors", "discriminator.safetensors", "manifest.json"),
}
ASSET_FILES = ("README.md", "NOTICE.md", "LICENSE", "config.json")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stage_component(source: Path, output: Path, names: tuple[str, ...]) -> list[dict]:
    output.mkdir()
    result = []
    for name in names:
        source_file = source / name
        if not source_file.is_file():
            raise FileNotFoundError(source_file)
        target = output / name
        shutil.copyfile(source_file, target)
        result.append(
            {
                "path": str(target.relative_to(output.parent)),
                "size": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    return result


def stage_root_marker(output: Path) -> dict:
    """Write a tiny valid safetensors marker for generic Host completeness checks."""

    target = output / "model.safetensors"
    header = json.dumps(
        {
            "format_version": {
                "dtype": "F32",
                "shape": [1],
                "data_offsets": [0, 4],
            }
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    header += b" " * ((8 - len(header) % 8) % 8)
    target.write_bytes(struct.pack("<Q", len(header)) + header + struct.pack("<f", 1.0))
    return {
        "path": target.name,
        "size": target.stat().st_size,
        "sha256": sha256(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--contentvec", type=Path, required=True)
    parser.add_argument("--rmvpe", type=Path, required=True)
    parser.add_argument("--training", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"output already exists: {args.output}")
    args.output.mkdir(parents=True)
    files = []
    for component, names in COMPONENT_FILES.items():
        files.extend(
            stage_component(getattr(args, component), args.output / component, names)
        )
    files.append(stage_root_marker(args.output))
    asset_root = Path(__file__).resolve().parents[1] / "checkpoint-assets"
    for name in ASSET_FILES:
        source = asset_root / name
        target = args.output / name
        shutil.copyfile(source, target)
        files.append(
            {"path": name, "size": target.stat().st_size, "sha256": sha256(target)}
        )
    manifest = {
        "schema": "ai2apps.mlx-rvc-composite/v1",
        "architecture": "rvc-v2-48khz-f0",
        "default_voice": "qwen3-tts-serena-mlx-e70",
        "synthetic_test_voice": True,
        "components": {name: name for name in COMPONENT_FILES},
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
