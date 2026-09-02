#!/usr/bin/env python3
"""Download and validate the MLX-required Z-Image checkpoint from ModelScope."""

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLEL_WORKERS", "8")
os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLEL_THRESHOLD_MB", "256")
os.environ.setdefault("MODELSCOPE_DOWNLOAD_PARALLELS", "8")
os.environ.setdefault("MODELSCOPE_PARALLEL_DOWNLOAD_THRESHOLD_MB", "256")

from modelscope import snapshot_download


MODELS = {
    "turbo": (
        "Tongyi-MAI/Z-Image-Turbo",
        "f332072aa78be7aecdf3ee76d5c247082da564a6",
    ),
    "base": ("Tongyi-MAI/Z-Image", None),
}
MLX_PATTERNS = [
    "vae/*.safetensors",
    "vae/*.json",
    "transformer/*.safetensors",
    "transformer/*.json",
    "text_encoder/*.safetensors",
    "text_encoder/*.json",
    "tokenizer/*",
    "scheduler/*",
    "model_index.json",
]


def validate_checkpoint(root: Path) -> None:
    required = [
        root / "model_index.json",
        root / "vae" / "diffusion_pytorch_model.safetensors",
        root / "transformer" / "diffusion_pytorch_model.safetensors.index.json",
        root / "text_encoder" / "model.safetensors.index.json",
        root / "tokenizer" / "tokenizer.json",
    ]
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    for index_path in required[2:4]:
        if not index_path.is_file():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for filename in sorted(set(index.get("weight_map", {}).values())):
            shard = index_path.parent / filename
            if not shard.is_file():
                missing.append(shard.relative_to(root).as_posix())
    if missing:
        raise RuntimeError("ModelScope checkpoint is incomplete: " + ", ".join(sorted(set(missing))))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo_id, hf_revision = MODELS[args.model]
    path = Path(
        snapshot_download(
            repo_id,
            revision="master",
            local_dir=str(args.output),
            allow_patterns=MLX_PATTERNS,
            max_workers=4,
        )
    )
    validate_checkpoint(path)
    record = {
        "provider": "modelscope",
        "repo_id": repo_id,
        "revision": "master",
        "hf_verification_revision": hf_revision,
        "path": str(path.resolve()),
    }
    (args.output / "ai2apps-modelscope-source.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
