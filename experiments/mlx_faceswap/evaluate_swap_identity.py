#!/usr/bin/env python3
"""Measure whether a swapped face moves from target identity toward source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .media import read_image_bgr
from .models import MLXArcFace, MLXYuNet


def _largest_face(detector: MLXYuNet, path: Path):
    image = read_image_bgr(path)
    faces = detector.detect(image)
    if not faces:
        raise ValueError(f"no face detected in {path}")
    face = max(
        faces,
        key=lambda item: float(item.bbox[2] - item.bbox[0])
        * float(item.bbox[3] - item.bbox[1]),
    )
    return image, face


def _embedding(detector: MLXYuNet, recognizer: MLXArcFace, path: Path) -> np.ndarray:
    image, face = _largest_face(detector, path)
    return recognizer.embed(image, face.landmarks)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector-model", type=Path, required=True)
    parser.add_argument("--recognizer-model", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, action="append", required=True)
    args = parser.parse_args()

    detector = MLXYuNet(args.detector_model)
    recognizer = MLXArcFace(args.recognizer_model)
    source = _embedding(detector, recognizer, args.source)
    target = _embedding(detector, recognizer, args.target)
    baseline = float(np.dot(source, target))
    results = []
    for path in args.output:
        output = _embedding(detector, recognizer, path)
        source_similarity = float(np.dot(source, output))
        target_similarity = float(np.dot(target, output))
        results.append(
            {
                "path": str(path),
                "source_similarity": source_similarity,
                "target_similarity": target_similarity,
                "source_gain_over_baseline": source_similarity - baseline,
                "identity_margin": source_similarity - target_similarity,
            }
        )
    print(
        json.dumps(
            {"source_target_baseline": baseline, "outputs": results}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
