#!/usr/bin/env python3
"""Compare decoded SCRFD detections from ONNX Runtime and MLX."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from .models import MLXSCRFD


class _OrtGraph:
    def __init__(self, model_path: Path):
        self.session = ort.InferenceSession(
            str(model_path), providers=["CPUExecutionProvider"]
        )
        self.inputs = (self.session.get_inputs()[0].name,)

    def __call__(self, feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        return self.session.run(None, feeds)

    @staticmethod
    def evaluate(values: list[np.ndarray]) -> None:
        del values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("--size", type=int, default=640)
    args = parser.parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError(f"could not read {args.image}")

    mlx_detector = MLXSCRFD(args.model_path)
    ort_detector = MLXSCRFD(args.model_path)
    ort_detector.graph = _OrtGraph(args.model_path)  # type: ignore[assignment]
    kwargs = {"input_size": (args.size, args.size)}
    mlx_faces = mlx_detector.detect(image, **kwargs)
    ort_faces = ort_detector.detect(image, **kwargs)
    paired = min(len(mlx_faces), len(ort_faces))
    bbox_errors = []
    landmark_errors = []
    score_errors = []
    for index in range(paired):
        bbox_errors.append(
            float(np.max(np.abs(mlx_faces[index].bbox - ort_faces[index].bbox)))
        )
        landmark_errors.append(
            float(
                np.max(np.abs(mlx_faces[index].landmarks - ort_faces[index].landmarks))
            )
        )
        score_errors.append(abs(mlx_faces[index].score - ort_faces[index].score))
    print(
        json.dumps(
            {
                "input_size": args.size,
                "mlx_face_count": len(mlx_faces),
                "ort_face_count": len(ort_faces),
                "paired_by_score": paired,
                "max_bbox_error_pixels": max(bbox_errors, default=0.0),
                "max_landmark_error_pixels": max(landmark_errors, default=0.0),
                "max_score_error": max(score_errors, default=0.0),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
