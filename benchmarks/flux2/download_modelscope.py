#!/usr/bin/env python3
"""Download a FLUX.2 checkpoint from ModelScope before immutable HF verification."""

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
    "4b": ("black-forest-labs/FLUX.2-klein-4B", "e7b7dc27f91deacad38e78976d1f2b499d76a294"),
    "9b": ("black-forest-labs/FLUX.2-klein-9B", "92196c8e11f7b6cf2b7493e037d8c5345c559216"),
}
MLX_PATTERNS = [
    "vae/*.safetensors", "vae/*.json",
    "transformer/*.safetensors", "transformer/*.json",
    "text_encoder/*.safetensors", "text_encoder/*.json",
    "tokenizer/**", "added_tokens.json", "chat_template.jinja", "model_index.json",
]


def validate_checkpoint(root: Path) -> None:
    """Reject ModelScope's partial-success return before writing a receipt."""
    required = [
        root / "model_index.json",
        root / "vae" / "diffusion_pytorch_model.safetensors",
        root / "text_encoder" / "model.safetensors.index.json",
        root / "tokenizer" / "tokenizer.json",
    ]
    missing = [path.relative_to(root).as_posix() for path in required if not path.is_file()]
    transformer_index = root / "transformer" / "diffusion_pytorch_model.safetensors.index.json"
    transformer_single = root / "transformer" / "diffusion_pytorch_model.safetensors"
    if not transformer_index.is_file() and not transformer_single.is_file():
        missing.append("transformer/diffusion_pytorch_model.safetensors[.index.json]")
    for index_path in (transformer_index, root / "text_encoder" / "model.safetensors.index.json"):
        if not index_path.is_file():
            continue
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for filename in sorted(set(index.get("weight_map", {}).values())):
            shard = index_path.parent / filename
            if not shard.is_file():
                missing.append(shard.relative_to(root).as_posix())
    if missing:
        raise RuntimeError(
            "ModelScope checkpoint is incomplete: " + ", ".join(sorted(set(missing)))
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo_id, hf_revision = MODELS[args.model]
    path = Path(snapshot_download(
        repo_id,
        revision="master",
        local_dir=str(args.output),
        allow_patterns=MLX_PATTERNS,
        max_workers=2,
    ))
    validate_checkpoint(path)
    record = {
        "provider": "modelscope", "repo_id": repo_id, "revision": "master",
        "hf_verification_revision": hf_revision, "path": str(path.resolve()),
    }
    (args.output / "ai2apps-modelscope-source.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
