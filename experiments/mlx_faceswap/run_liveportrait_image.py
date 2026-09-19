#!/usr/bin/env python3
"""Render one MLX LivePortrait source/driving image pair."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .assets import resolve_model
from .geometry import align_face, paste_face
from .liveportrait import MLXLivePortrait
from .media import read_image_bgr, write_image_bgr
from .models import MLXSCRFD, MLXYuNet
from .native_liveportrait import NativeMLXLivePortrait


def _face_area(face) -> float:
    return float((face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--driving", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--detector", choices=("scrfd", "yunet"), default="scrfd")
    parser.add_argument("--native-weights", type=Path)
    parser.add_argument("--dtype", choices=("fp32", "bf16"), default="fp32")
    parser.add_argument(
        "--crop-only", action="store_true", help="write the generated face crop only"
    )
    args = parser.parse_args()
    source = read_image_bgr(args.source)
    driving = read_image_bgr(args.driving)
    if args.detector == "yunet":
        detector = MLXYuNet(
            resolve_model(args.models, "face_detection_yunet_2023mar.onnx")
        )
    else:
        detector = MLXSCRFD(resolve_model(args.models, "scrfd_2.5g_bnkps.onnx"))
    source_faces = detector.detect(source)
    driving_faces = detector.detect(driving)
    if not source_faces or not driving_faces:
        raise ValueError("source and driving images must contain detectable faces")
    source_crop, source_matrix = align_face(
        source, max(source_faces, key=_face_area).landmarks, 256
    )
    driving_crop, _ = align_face(
        driving, max(driving_faces, key=_face_area).landmarks, 256
    )
    pipeline = (
        NativeMLXLivePortrait(args.native_weights, dtype=args.dtype)
        if args.native_weights is not None
        else MLXLivePortrait(args.models)
    )
    started = time.perf_counter()
    generated_crop = pipeline.reenact(source_crop, driving_crop)
    if args.crop_only:
        output = generated_crop
    else:
        output_scale = generated_crop.shape[1] / source_crop.shape[1]
        output_matrix = source_matrix * output_scale
        output = paste_face(
            source,
            generated_crop,
            output_matrix,
            erosion_fraction=0.035,
            blur_fraction=0.04,
        )
    elapsed = time.perf_counter() - started
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_image_bgr(args.output, output)
    print(json.dumps({"output": str(args.output), "seconds": elapsed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
