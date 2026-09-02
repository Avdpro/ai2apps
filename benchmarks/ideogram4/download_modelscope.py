#!/usr/bin/env python3
"""Download the minimum Ideogram 4 FP8 source set needed for MLX conversion."""

from __future__ import annotations

import argparse
import json
import os
import struct
from pathlib import Path

os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLEL_WORKERS", "8")
os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLEL_THRESHOLD_MB", "256")
os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLELS", "8")
os.environ.setdefault("MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", "256")

WEIGHTS_REPO = "Comfy-Org/Ideogram-4"
QWEN_REPO = "Qwen/Qwen3-VL-8B-Instruct"
WEIGHT_FILES = (
    "diffusion_models/ideogram4_fp8_scaled.safetensors",
    "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
    "text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
    "vae/flux2-vae.safetensors",
)
EXPECTED_DTYPES = {
    WEIGHT_FILES[0]: {"BF16", "F32", "F8_E4M3", "U8"},
    WEIGHT_FILES[1]: {"BF16", "F32", "F8_E4M3", "U8"},
    WEIGHT_FILES[2]: {"BF16", "F32", "F8_E4M3", "U8"},
    WEIGHT_FILES[3]: {"F32", "I64"},
}
QWEN_METADATA_PATTERNS = (
    "*.json",
    "*.jinja",
    "*.txt",
    "*.model",
    "tokenizer*",
    "vocab*",
    "merges*",
)


def safetensors_dtypes(path: Path) -> set[str]:
    with path.open("rb") as stream:
        size_bytes = stream.read(8)
        if len(size_bytes) != 8:
            raise RuntimeError(f"invalid safetensors header: {path}")
        header_size = struct.unpack("<Q", size_bytes)[0]
        header = json.loads(stream.read(header_size))
    return {
        value["dtype"]
        for key, value in header.items()
        if key != "__metadata__"
    }


def validate(root: Path, qwen_root: Path) -> None:
    missing = [name for name in WEIGHT_FILES if not (root / name).is_file()]
    for name in WEIGHT_FILES:
        path = root / name
        if path.is_file() and safetensors_dtypes(path) != EXPECTED_DTYPES[name]:
            raise RuntimeError(f"unexpected tensor dtypes in {path}")
    for name in ("config.json", "tokenizer.json", "tokenizer_config.json"):
        if not (qwen_root / name).is_file():
            missing.append(f"qwen/{name}")
    if missing:
        raise RuntimeError("incomplete Ideogram 4 source: " + ", ".join(missing))


def main() -> None:
    from modelscope import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    weights_root = args.output / "ideogram4-fp8"
    qwen_root = args.output / "qwen3-vl-8b-config"
    snapshot_download(
        WEIGHTS_REPO,
        revision="master",
        local_dir=str(weights_root),
        allow_patterns=[*WEIGHT_FILES, "configuration.json", "README.md"],
        max_workers=args.workers,
    )
    snapshot_download(
        QWEN_REPO,
        revision="master",
        local_dir=str(qwen_root),
        allow_patterns=list(QWEN_METADATA_PATTERNS),
        max_workers=args.workers,
    )
    validate(weights_root, qwen_root)
    record = {
        "provider": "modelscope",
        "weights_repo": WEIGHTS_REPO,
        "weights_revision": "master",
        "qwen_config_repo": QWEN_REPO,
        "qwen_config_revision": "master",
        "official_source_commit": "990fe1c4e950bb9e9dc90e01c0ad98ba434f83c2",
        "weights_path": str(weights_root.resolve()),
        "qwen_config_path": str(qwen_root.resolve()),
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "ai2apps-modelscope-source.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
