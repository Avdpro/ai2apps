#!/usr/bin/env python3
"""Run the 512px MLX SimSwap image pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .assets import resolve_model
from .media import read_image_bgr, write_image_bgr
from .models import MLXSimSwapPipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore-strength", type=float, default=0.0)
    args = parser.parse_args()
    source = read_image_bgr(args.source)
    target = read_image_bgr(args.target)
    pipeline = MLXSimSwapPipeline(
        resolve_model(args.models, "scrfd_2.5g_bnkps.onnx"),
        resolve_model(args.models, "simswap_arcface_model.onnx"),
        resolve_model(args.models, "simswap_512_unoff.onnx"),
        resolve_model(args.models, "XSeg_model.onnx", optional=True),
        resolve_model(args.models, "GFPGANv1.4.onnx", optional=True)
        if args.restore_strength > 0
        else None,
        restoration_strength=args.restore_strength,
    )
    started = time.perf_counter()
    output, source_face, target_face = pipeline.swap_largest_face(source, target)
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_image_bgr(args.output, output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "seconds": elapsed,
                "source_score": source_face.score,
                "target_score": target_face.score,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
