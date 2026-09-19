#!/usr/bin/env python3
"""Compare decoded MLX YuNet detections with OpenCV FaceDetectorYN."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from .models import MLXYuNet


def _iou(left: np.ndarray, right: np.ndarray) -> float:
    xy1 = np.maximum(left[:2], right[:2])
    xy2 = np.minimum(left[2:], right[2:])
    intersection = float(np.prod(np.maximum(0.0, xy2 - xy1)))
    left_area = float(np.prod(np.maximum(0.0, left[2:] - left[:2])))
    right_area = float(np.prod(np.maximum(0.0, right[2:] - right[:2])))
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_path", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("--threshold", type=float, default=0.6)
    args = parser.parse_args()
    image = cv2.imread(str(args.image))
    if image is None:
        raise ValueError(f"could not read {args.image}")

    input_size = (640, 640)
    scale = min(input_size[0] / image.shape[1], input_size[1] / image.shape[0])
    resized_size = (int(image.shape[1] * scale), int(image.shape[0] * scale))
    canvas = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
    canvas[: resized_size[1], : resized_size[0]] = cv2.resize(image, resized_size)
    reference_detector = cv2.FaceDetectorYN.create(
        str(args.model_path), "", input_size, args.threshold, 0.3, 5000
    )
    _, reference_rows = reference_detector.detect(canvas)
    reference_rows = (
        np.empty((0, 15), dtype=np.float32)
        if reference_rows is None
        else reference_rows.astype(np.float32)
    )
    reference_boxes = reference_rows[:, :4].copy()
    reference_boxes[:, 2:] += reference_boxes[:, :2]
    reference_boxes /= scale
    reference_landmarks = reference_rows[:, 4:14].reshape(-1, 5, 2) / scale

    candidate = MLXYuNet(args.model_path).detect(image, threshold=args.threshold)
    unmatched = set(range(len(candidate)))
    matches = []
    for ref_index, ref_box in enumerate(reference_boxes):
        if not unmatched:
            break
        candidate_index = max(
            unmatched, key=lambda index: _iou(ref_box, candidate[index].bbox)
        )
        unmatched.remove(candidate_index)
        item = candidate[candidate_index]
        matches.append(
            {
                "iou": _iou(ref_box, item.bbox),
                "bbox_max_abs": float(np.max(np.abs(ref_box - item.bbox))),
                "landmark_max_abs": float(
                    np.max(np.abs(reference_landmarks[ref_index] - item.landmarks))
                ),
                "score_abs": abs(float(reference_rows[ref_index, 14]) - item.score),
            }
        )
    print(
        json.dumps(
            {
                "reference_faces": len(reference_rows),
                "mlx_faces": len(candidate),
                "matched_faces": len(matches),
                "minimum_iou": min((item["iou"] for item in matches), default=None),
                "maximum_bbox_error": max(
                    (item["bbox_max_abs"] for item in matches), default=None
                ),
                "maximum_landmark_error": max(
                    (item["landmark_max_abs"] for item in matches), default=None
                ),
                "maximum_score_error": max(
                    (item["score_abs"] for item in matches), default=None
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
