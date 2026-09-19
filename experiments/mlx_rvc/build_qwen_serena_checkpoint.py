#!/usr/bin/env python3
"""Build the non-executable MLX-RVC Serena test-voice distributions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .checkpoint import (
    export_faiss_index,
    export_hubert_checkpoint,
    export_legacy_checkpoint,
    export_rmvpe_checkpoint,
    sha256,
)


def _prepare_directory(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    path.mkdir(parents=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("index", type=Path)
    parser.add_argument("hubert_directory", type=Path)
    parser.add_argument("rmvpe_checkpoint", type=Path)
    parser.add_argument("dataset_manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--training-revision", required=True)
    parser.add_argument("--asset-revision", required=True)
    args = parser.parse_args()

    inputs = [
        args.checkpoint,
        args.index,
        args.hubert_directory / "pytorch_model.bin",
        args.hubert_directory / "config.json",
        args.rmvpe_checkpoint,
        args.dataset_manifest,
    ]
    for path in inputs:
        path.resolve(strict=True)

    root = args.output.resolve()
    voice = root / "voice"
    contentvec = root / "contentvec"
    rmvpe = root / "rmvpe"
    _prepare_directory(root)
    voice.mkdir()
    contentvec.mkdir()
    rmvpe.mkdir()

    model_manifest = export_legacy_checkpoint(
        args.checkpoint, voice / "model.safetensors"
    )
    index_manifest = export_faiss_index(args.index, voice / "index.safetensors")
    contentvec_manifest = export_hubert_checkpoint(
        args.hubert_directory / "pytorch_model.bin",
        args.hubert_directory / "config.json",
        contentvec / "model.safetensors",
    )
    rmvpe_manifest = export_rmvpe_checkpoint(
        args.rmvpe_checkpoint, rmvpe / "model.safetensors"
    )

    provenance = {
        "schema": "ai2apps.mlx-rvc-voice-build/v1",
        "id": "qwen-serena-synthetic-v1",
        "display_name": "Qwen Serena (synthetic test voice)",
        "synthetic": True,
        "intended_use": "local voice-conversion development and validation",
        "source_voice": {
            "provider": "Qwen3-TTS CustomVoice",
            "preset": "serena",
            "dataset_manifest": {
                "name": args.dataset_manifest.name,
                "sha256": sha256(args.dataset_manifest),
            },
        },
        "training": {
            "upstream": "RVC-Project/Retrieval-based-Voice-Conversion-WebUI",
            "revision": args.training_revision,
            "asset_repository": "lj1995/VoiceConversionWebUI",
            "asset_revision": args.asset_revision,
            "version": "v2",
            "sample_rate": 48000,
            "uses_f0": True,
            "pitch_extractor": "rmvpe",
            "epochs": 100,
            "batch_size": 4,
        },
        "artifacts": {
            "voice_model": model_manifest,
            "retrieval_index": index_manifest,
            "contentvec": contentvec_manifest,
            "rmvpe": rmvpe_manifest,
        },
    }
    provenance_path = root / "provenance.json"
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps({"output": str(root), "provenance": str(provenance_path)}, indent=2)
    )


if __name__ == "__main__":
    main()
