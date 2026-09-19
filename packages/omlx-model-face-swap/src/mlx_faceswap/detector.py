"""MLX YuNet face detector used by the GhostV2 Package."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .media import blob_from_bgr, resize_bgr
from .onnx_mlx import MLXOnnxGraph


@dataclass(frozen=True)
class FaceDetection:
    bbox: np.ndarray
    score: float
    landmarks: np.ndarray


def _nms(detections: np.ndarray, threshold: float) -> np.ndarray:
    x1, y1, x2, y2 = (
        detections[:, 0],
        detections[:, 1],
        detections[:, 2],
        detections[:, 3],
    )
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = np.arange(len(detections))
    keep: list[int] = []
    while order.size:
        current = int(order[0])
        keep.append(current)
        intersection_width = np.maximum(
            0.0,
            np.minimum(x2[current], x2[order[1:]])
            - np.maximum(x1[current], x1[order[1:]])
            + 1,
        )
        intersection_height = np.maximum(
            0.0,
            np.minimum(y2[current], y2[order[1:]])
            - np.maximum(y1[current], y1[order[1:]])
            + 1,
        )
        intersection = intersection_width * intersection_height
        overlap = intersection / (areas[current] + areas[order[1:]] - intersection)
        order = order[np.flatnonzero(overlap <= threshold) + 1]
    return np.asarray(keep, dtype=np.int64)


class MLXYuNet:
    """MIT-licensed OpenCV Zoo YuNet detector decoded on the host."""

    STRIDES = (8, 16, 32)

    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)
        self.input_name = self.graph.inputs[0]

    def detect(
        self,
        image_bgr: np.ndarray,
        *,
        input_size: tuple[int, int] = (640, 640),
        threshold: float = 0.6,
        nms_threshold: float = 0.3,
        max_faces: int = 0,
        top_k: int = 5000,
    ) -> list[FaceDetection]:
        input_width, input_height = input_size
        image_height, image_width = image_bgr.shape[:2]
        scale = min(input_width / image_width, input_height / image_height)
        resized_width = int(image_width * scale)
        resized_height = int(image_height * scale)
        canvas = np.zeros((input_height, input_width, 3), dtype=np.uint8)
        canvas[:resized_height, :resized_width] = resize_bgr(
            image_bgr, (resized_width, resized_height)
        )
        blob = blob_from_bgr(canvas, input_size, scale=1.0, mean=0.0, swap_rb=False)
        values = self.graph({self.input_name: blob})
        self.graph.evaluate(values)
        outputs = [np.asarray(value, dtype=np.float32) for value in values]

        candidates: list[np.ndarray] = []
        candidate_landmarks: list[np.ndarray] = []
        for level, stride in enumerate(self.STRIDES):
            cls = np.clip(outputs[level].reshape(-1), 0.0, 1.0)
            obj = np.clip(outputs[level + 3].reshape(-1), 0.0, 1.0)
            scores = np.sqrt(cls * obj)
            selected = np.flatnonzero(scores >= threshold)
            if selected.size == 0:
                continue
            rows, cols = input_height // stride, input_width // stride
            grid_x, grid_y = np.meshgrid(
                np.arange(cols, dtype=np.float32),
                np.arange(rows, dtype=np.float32),
            )
            centers = np.column_stack((grid_x.reshape(-1), grid_y.reshape(-1)))
            boxes = outputs[level + 6].reshape(-1, 4)
            center_xy = (centers + boxes[:, :2]) * stride
            size_wh = np.exp(boxes[:, 2:]) * stride
            xy1 = center_xy - size_wh / 2.0
            xy2 = xy1 + size_wh
            keypoints = outputs[level + 9].reshape(-1, 5, 2)
            keypoints = (keypoints + centers[:, None, :]) * stride
            candidates.append(
                np.column_stack((xy1[selected], xy2[selected], scores[selected]))
                / np.array((scale, scale, scale, scale, 1.0), dtype=np.float32)
            )
            candidate_landmarks.append(keypoints[selected] / scale)
        if not candidates:
            return []
        detections = np.concatenate(candidates).astype(np.float32)
        landmarks = np.concatenate(candidate_landmarks).astype(np.float32)
        order = detections[:, 4].argsort()[::-1][:top_k]
        order = order[_nms(detections[order], nms_threshold)]
        if max_faces > 0:
            order = order[:max_faces]
        return [
            FaceDetection(
                bbox=detections[index, :4],
                score=float(detections[index, 4]),
                landmarks=landmarks[index],
            )
            for index in order
        ]
