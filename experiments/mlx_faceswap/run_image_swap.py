#!/usr/bin/env python3
"""Run the first end-to-end MLX single-image face replacement pipeline."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .assets import resolve_model
from .media import read_image_bgr, write_image_bgr
from .models import MLXFaceSwapPipeline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--restore-strength", type=float, default=0.0)
    parser.add_argument(
        "--swapper-precision",
        choices=("fp16_compatible", "bf16"),
        default="fp16_compatible",
    )
    parser.add_argument(
        "--detector", choices=("yunet", "scrfd"), default="yunet"
    )
    args = parser.parse_args()
    source = read_image_bgr(args.source)
    target = read_image_bgr(args.target)
    pipeline = MLXFaceSwapPipeline(
        resolve_model(
            args.models,
            (
                "face_detection_yunet_2023mar.onnx"
                if args.detector == "yunet"
                else "scrfd_2.5g_bnkps.onnx"
            ),
        ),
        resolve_model(args.models, "w600k_r50.onnx"),
        resolve_model(args.models, "inswapper_128.fp16.onnx"),
        resolve_model(args.models, "XSeg_model.onnx", optional=True),
        resolve_model(args.models, "GFPGANv1.4.onnx", optional=True)
        if args.restore_strength > 0
        else None,
        restoration_strength=args.restore_strength,
        swapper_precision=args.swapper_precision,
        detector_kind=args.detector,
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
