#!/usr/bin/env python3
"""Run the native MLX Ideogram 4 baseline without using Spark."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import mlx.core as mx
from PIL import Image
from pipeline import Ideogram4MLXPipeline, PipelinePaths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--derived-root", type=Path, required=True)
    parser.add_argument("--qwen-config-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--image", type=Path)
    parser.add_argument(
        "--strength",
        type=float,
        help="input-image transformation strength in (0, 1]; defaults to 0.75",
    )
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=20260603)
    parser.add_argument("--bits", type=int, choices=(4, 8, 16), default=8)
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument(
        "--eager",
        action="store_true",
        help="keep the text encoder and diffusion models resident together",
    )
    parser.add_argument(
        "--compile-denoisers",
        action="store_true",
        help="compile the positive and negative denoiser graphs",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    mx.reset_peak_memory()
    started = time.perf_counter()
    pipeline = Ideogram4MLXPipeline(
        PipelinePaths(args.derived_root, args.qwen_config_root),
        bits=args.bits,
        staged=not args.eager,
        compile_denoisers=args.compile_denoisers,
    )
    load_seconds = time.perf_counter() - started
    if args.runs <= 0:
        raise ValueError("--runs must be positive")
    if args.image is None and args.strength is not None:
        raise ValueError("--strength requires --image")
    source_image = None
    if args.image is not None:
        with Image.open(args.image) as opened:
            opened.load()
            source_image = opened.copy()
    reports = []
    for run in range(args.runs):
        image, run_report = pipeline.generate(
            args.prompt,
            height=args.height,
            width=args.width,
            steps=args.steps,
            seed=args.seed,
            image=source_image,
            strength=args.strength,
        )
        image.save(
            args.output / ("image.png" if args.runs == 1 else f"image-{run + 1}.png")
        )
        reports.append(run_report)
    report = reports[0] if args.runs == 1 else {"runs": reports}
    report["load_seconds"] = load_seconds
    report["backend"] = "mlx"
    report["implementation"] = f"ai2apps-ideogram4-q{args.bits}-baseline"
    (args.output / "metrics.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
