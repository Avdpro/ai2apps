#!/usr/bin/env python3
"""Freeze an EchoMimic MLX checkpoint directory into its production manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "ai2apps.echomimic-mlx-checkpoint/v1"
FILES = (
    "echomimicv3-flash-pro/config.json",
    "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors",
    "Wan2.1_VAE.safetensors",
    "models_t5_umt5-xxl-enc-bf16-local.safetensors",
    "models_clip_open-clip-xlm-roberta-large-vit-huge-14.safetensors",
    "umt5-xxl/tokenizer.json",
    "umt5-xxl/tokenizer_config.json",
    "chinese-wav2vec2-base/config.json",
    "chinese-wav2vec2-base/preprocessor_config.json",
    "chinese-wav2vec2-base/model.safetensors",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(8 * 1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    files = []
    for name in FILES:
        path = root / name
        if not path.is_file():
            raise FileNotFoundError(path)
        files.append({"path": name, "size": path.stat().st_size, "sha256": digest(path)})
    manifest = {
        "schema": SCHEMA,
        "revision": args.revision,
        "implementation_commit": "ed55d4e304216ce4d5e8bb1636d4807be0871443",
        "upstream_commit": "7e89489ca51c0d008fc1963ec6c03fc5bd0b9397",
        "sources": {
            "echomimic": "311e176905a8c4c24b240b530488fe636ce4d249",
            "wan": "fc913c34361f4ec879e2f9c78b4f11ae50a937d1",
            "wav2vec2": "cb511a6498884e41e35686f4b4d6c5188e181773",
        },
        "files": files,
    }
    output = root / "ai2apps-checkpoint.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"manifest": str(output), "files": len(files)}, indent=2))


if __name__ == "__main__":
    main()
