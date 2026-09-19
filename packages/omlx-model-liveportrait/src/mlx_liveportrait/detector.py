"""MLX wrappers for the initial face-replacement model stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import align_face
from .media import blob_from_bgr, resize_bgr
from .onnx_mlx import MLXOnnxGraph


@dataclass(frozen=True)
class FaceDetection:
    bbox: np.ndarray
    score: float
    landmarks: np.ndarray


def _blob(
    image_bgr: np.ndarray,
    size: tuple[int, int],
    *,
    scale: float,
    mean: float,
) -> np.ndarray:
    return blob_from_bgr(image_bgr, size, scale=scale, mean=mean, swap_rb=True)


class MLXArcFace:
    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)
        self.input_name = self.graph.inputs[0]

    def embed_aligned(self, image_bgr: np.ndarray) -> np.ndarray:
        values = self.graph(
            {self.input_name: _blob(image_bgr, (112, 112), scale=1 / 127.5, mean=127.5)}
        )
        self.graph.evaluate(values)
        embedding = np.asarray(values[0], dtype=np.float32)
        norm = np.linalg.norm(embedding, axis=1, keepdims=True)
        return embedding / np.maximum(norm, 1e-12)

    def embed(self, image_bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        crop, _ = align_face(image_bgr, landmarks, 112)
        return self.embed_aligned(crop)


class MLXSCRFD:
    STRIDES = (8, 16, 32)
    ANCHORS = 2

    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)
        self.input_name = self.graph.inputs[0]
        self._centers: dict[tuple[int, int, int], np.ndarray] = {}

    def detect(
        self,
        image_bgr: np.ndarray,
        *,
        input_size: tuple[int, int] = (640, 640),
        threshold: float = 0.5,
        nms_threshold: float = 0.4,
        max_faces: int = 0,
    ) -> list[FaceDetection]:
        input_width, input_height = input_size
        image_height, image_width = image_bgr.shape[:2]
        scale = min(input_width / image_width, input_height / image_height)
        resized_size = (int(image_width * scale), int(image_height * scale))
        resized = resize_bgr(image_bgr, resized_size)
        canvas = np.zeros((input_height, input_width, 3), dtype=np.uint8)
        canvas[: resized_size[1], : resized_size[0]] = resized
        values = self.graph(
            {self.input_name: _blob(canvas, input_size, scale=1 / 128.0, mean=127.5)}
        )
        self.graph.evaluate(values)
        outputs = [np.asarray(value, dtype=np.float32) for value in values]

        candidates: list[np.ndarray] = []
        candidate_landmarks: list[np.ndarray] = []
        for level, stride in enumerate(self.STRIDES):
            scores = outputs[level].reshape(-1)
            bbox_distances = outputs[level + 3].reshape(-1, 4) * stride
            kps_distances = outputs[level + 6].reshape(-1, 10) * stride
            height, width = input_height // stride, input_width // stride
            centers = self._anchor_centers(height, width, stride)
            selected = np.flatnonzero(scores >= threshold)
            if selected.size == 0:
                continue
            boxes = np.stack(
                (
                    centers[:, 0] - bbox_distances[:, 0],
                    centers[:, 1] - bbox_distances[:, 1],
                    centers[:, 0] + bbox_distances[:, 2],
                    centers[:, 1] + bbox_distances[:, 3],
                ),
                axis=1,
            )
            landmarks = np.empty((centers.shape[0], 5, 2), dtype=np.float32)
            for point in range(5):
                landmarks[:, point, 0] = centers[:, 0] + kps_distances[:, point * 2]
                landmarks[:, point, 1] = centers[:, 1] + kps_distances[:, point * 2 + 1]
            candidates.append(
                np.column_stack((boxes[selected] / scale, scores[selected]))
            )
            candidate_landmarks.append(landmarks[selected] / scale)
        if not candidates:
            return []
        detections = np.concatenate(candidates).astype(np.float32)
        landmarks = np.concatenate(candidate_landmarks).astype(np.float32)
        order = detections[:, 4].argsort()[::-1]
        keep = self._nms(detections[order], nms_threshold)
        order = order[keep]
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

    def _anchor_centers(self, height: int, width: int, stride: int) -> np.ndarray:
        key = (height, width, stride)
        if key not in self._centers:
            centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(
                np.float32
            )
            centers = (centers * stride).reshape(-1, 2)
            centers = np.repeat(centers, self.ANCHORS, axis=0)
            self._centers[key] = centers
        return self._centers[key]

    @staticmethod
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
        blob = blob_from_bgr(
            canvas, input_size, scale=1.0, mean=0.0, swap_rb=False
        )
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
        keep = MLXSCRFD._nms(detections[order], nms_threshold)
        order = order[keep]
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
