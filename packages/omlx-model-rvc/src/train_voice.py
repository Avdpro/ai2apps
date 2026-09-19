#!/usr/bin/env python3
"""Offline CLI entry point for native MLX-RVC voice training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlx.core as mx
from mlx_rvc.contentvec import ContentVec
from mlx_rvc.rmvpe import RMVPE
from mlx_rvc.voice_training import (
    MLXRVCVoiceTrainer,
    VoiceDatasetPreprocessor,
    VoiceTrainingConfig,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_directory", type=Path)
    parser.add_argument("training_checkpoint", type=Path)
    parser.add_argument("contentvec", type=Path)
    parser.add_argument("rmvpe", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument(
        "--precision",
        choices=("float32", "float16", "bfloat16"),
        default="float16",
    )
    parser.add_argument("--cache", type=Path)
    parser.add_argument(
        "--resume",
        type=Path,
        help="Complete training-state.safetensors checkpoint to resume",
    )
    parser.add_argument("--adaptation", choices=("safe", "full"), default="safe")
    args = parser.parse_args()
    audio_files = sorted(
        path for path in args.audio_directory.rglob("*.wav") if path.is_file()
    )
    if not audio_files:
        raise SystemExit("audio directory contains no WAV files")
    cache = args.cache or args.output.with_name(f"{args.output.name}-cache")
    if not (cache / "manifest.json").is_file():
        VoiceDatasetPreprocessor(
            ContentVec.from_directory(args.contentvec), RMVPE.from_directory(args.rmvpe)
        ).prepare(audio_files, cache)
    trainer = MLXRVCVoiceTrainer(
        mx.load(
            str(args.training_checkpoint / "generator.safetensors"),
            format="safetensors",
        ),
        mx.load(
            str(args.training_checkpoint / "discriminator.safetensors"),
            format="safetensors",
        ),
    )
    report = trainer.fit(
        cache,
        args.output,
        VoiceTrainingConfig(
            epochs=args.epochs,
            batch_size=args.batch_size,
            precision=args.precision,
            adaptation=args.adaptation,
        ),
        resume=args.resume,
        progress=lambda event: print(json.dumps(event), flush=True),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
