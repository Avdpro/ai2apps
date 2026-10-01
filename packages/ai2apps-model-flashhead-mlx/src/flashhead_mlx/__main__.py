"""Offline FlashHead CLI. Weight preparation is a separate developer operation."""

import argparse
import json
import time
from pathlib import Path

from .pipeline import FlashHeadPipeline


def main():
    parser = argparse.ArgumentParser(
        description="Generate an avatar video using local FlashHead MLX weights"
    )
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--wav2vec", type=Path, required=True)
    parser.add_argument("--variant", choices=["lite", "pro"], default="lite")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True, help="16 kHz WAV input")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.output.resolve() in {args.audio.resolve(), args.image.resolve()}:
        parser.error("Output must differ from inputs")
    started = time.perf_counter()
    pipeline = FlashHeadPipeline(args.weights, args.wav2vec, variant=args.variant)
    loaded = time.perf_counter()
    result = pipeline.generate(
        args.image,
        args.audio,
        args.output,
        size=args.size,
        steps=args.steps,
        seed=args.seed,
    )
    print(
        json.dumps(
            {
                "output": str(result),
                "variant": args.variant,
                "load_seconds": loaded - started,
                "generation_seconds": time.perf_counter() - loaded,
            }
        )
    )


if __name__ == "__main__":
    main()
