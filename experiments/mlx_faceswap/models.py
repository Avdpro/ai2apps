"""MLX wrappers for the initial face-replacement model stack."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .geometry import align_face, paste_face
from .media import blob_from_bgr, resize_bgr, resize_float
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


class MLXInSwapper:
    def __init__(
        self,
        model_path: str | Path,
        *,
        precision: str = "fp16_compatible",
    ):
        self.model_path = Path(model_path)
        self.graph = MLXOnnxGraph(model_path, float16_mode=precision)
        emap = self.graph.initializers.get("emap")
        if emap is None:
            emap = self.graph.initializers.get("initializer")
        if emap is None:
            raise ValueError("InSwapper graph does not contain its identity emap")
        self.graph.evaluate((emap,))
        self.emap = np.asarray(emap, dtype=np.float32)

    def identity_latent(self, normalized_embedding: np.ndarray) -> np.ndarray:
        latent = (
            np.asarray(normalized_embedding, dtype=np.float32).reshape(1, -1)
            @ self.emap
        )
        return latent / np.maximum(np.linalg.norm(latent, axis=1, keepdims=True), 1e-12)

    def swap_aligned(
        self, target_crop_bgr: np.ndarray, normalized_embedding: np.ndarray
    ) -> np.ndarray:
        return self.swap_aligned_batch(
            [target_crop_bgr], normalized_embedding
        )[0]

    def swap_aligned_batch(
        self,
        target_crops_bgr: list[np.ndarray],
        normalized_embedding: np.ndarray,
    ) -> list[np.ndarray]:
        if not target_crops_bgr:
            return []
        latent = self.identity_latent(normalized_embedding)
        target = np.concatenate(
            [
                _blob(crop, (128, 128), scale=1 / 255.0, mean=0.0)
                for crop in target_crops_bgr
            ],
            axis=0,
        )
        latent = np.repeat(latent, len(target_crops_bgr), axis=0)
        values = self.graph({"target": target, "source": latent})
        self.graph.evaluate(values)
        rgb = np.asarray(values[0], dtype=np.float32).transpose(0, 2, 3, 1)
        bgr = np.clip(rgb[..., ::-1] * 255.0, 0, 255).astype(np.uint8)
        return [item for item in bgr]


class MLXXSeg:
    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)
        self.input_name = self.graph.inputs[0]

    def mask_aligned(self, image_bgr: np.ndarray, output_size: int = 128) -> np.ndarray:
        values = self.graph(
            {self.input_name: _blob(image_bgr, (256, 256), scale=1 / 255.0, mean=0.0)}
        )
        self.graph.evaluate(values)
        mask = np.asarray(values[0], dtype=np.float32)[0, 0]
        mask = np.clip(mask, 0.0, 1.0)
        if output_size != 256:
            mask = resize_float(mask, (output_size, output_size))
        return mask


class MLXSimSwapArcFace:
    MEAN = np.array((0.485, 0.456, 0.406), dtype=np.float32).reshape(1, 3, 1, 1)
    STD = np.array((0.229, 0.224, 0.225), dtype=np.float32).reshape(1, 3, 1, 1)

    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)
        self.input_name = self.graph.inputs[0]

    def embed(self, image_bgr: np.ndarray, landmarks: np.ndarray) -> np.ndarray:
        crop, _ = align_face(image_bgr, landmarks, 112)
        blob = _blob(crop, (112, 112), scale=1 / 255.0, mean=0.0)
        blob = (blob - self.MEAN) / self.STD
        values = self.graph({self.input_name: blob})
        self.graph.evaluate(values)
        embedding = np.asarray(values[0], dtype=np.float32).reshape(1, -1)
        return embedding / np.maximum(
            np.linalg.norm(embedding, axis=1, keepdims=True), 1e-12
        )


class MLXSimSwap512:
    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)

    def swap_aligned(
        self, target_crop_bgr: np.ndarray, normalized_embedding: np.ndarray
    ) -> np.ndarray:
        target = _blob(target_crop_bgr, (512, 512), scale=1 / 255.0, mean=0.0)
        identity = np.asarray(normalized_embedding, dtype=np.float32).reshape(1, -1)
        identity /= np.maximum(np.linalg.norm(identity, axis=1, keepdims=True), 1e-12)
        values = self.graph({"input": target, "onnx::Gemm_1": identity})
        self.graph.evaluate(values)
        rgb = np.asarray(values[0], dtype=np.float32)[0].transpose(1, 2, 0)
        return np.clip(rgb[..., ::-1] * 255.0, 0, 255).astype(np.uint8)


class MLXGFPGAN:
    def __init__(self, model_path: str | Path):
        self.graph = MLXOnnxGraph(model_path)

    def restore(self, image_bgr: np.ndarray, *, strength: float = 0.5) -> np.ndarray:
        strength = float(np.clip(strength, 0.0, 1.0))
        original_size = (image_bgr.shape[1], image_bgr.shape[0])
        resized = resize_bgr(image_bgr, (512, 512), interpolation="cubic")
        values = self.graph(
            {"input": _blob(resized, (512, 512), scale=1 / 127.5, mean=127.5)}
        )
        self.graph.evaluate(values)
        rgb = np.asarray(values[0], dtype=np.float32)[0].transpose(1, 2, 0)
        restored = np.clip((rgb[..., ::-1] + 1.0) * 127.5, 0, 255)
        blended = restored * strength + resized.astype(np.float32) * (1.0 - strength)
        blended = np.clip(blended, 0, 255).astype(np.uint8)
        if original_size != (512, 512):
            blended = resize_bgr(blended, original_size, interpolation="area")
        return blended


class MLXSimSwapPipeline:
    def __init__(
        self,
        detector_path: str | Path,
        recognizer_path: str | Path,
        swapper_path: str | Path,
        mask_path: str | Path | None = None,
        restorer_path: str | Path | None = None,
        restoration_strength: float = 0.5,
    ):
        self.detector = MLXSCRFD(detector_path)
        self.recognizer = MLXSimSwapArcFace(recognizer_path)
        self.swapper = MLXSimSwap512(swapper_path)
        self.masker = MLXXSeg(mask_path) if mask_path is not None else None
        self.restorer = MLXGFPGAN(restorer_path) if restorer_path is not None else None
        self.restoration_strength = restoration_strength

    def swap_largest_face(
        self, source_bgr: np.ndarray, target_bgr: np.ndarray
    ) -> tuple[np.ndarray, FaceDetection, FaceDetection]:
        source_faces = self.detector.detect(source_bgr)
        target_faces = self.detector.detect(target_bgr)
        if not source_faces or not target_faces:
            raise ValueError("source and target must each contain a detectable face")
        source_face = max(source_faces, key=_face_area)
        target_face = max(target_faces, key=_face_area)
        identity = self.recognizer.embed(source_bgr, source_face.landmarks)
        target_crop, matrix = align_face(target_bgr, target_face.landmarks, 512)
        swapped_crop = self.swapper.swap_aligned(target_crop, identity)
        if self.restorer is not None:
            swapped_crop = self.restorer.restore(
                swapped_crop, strength=self.restoration_strength
            )
        semantic_mask = (
            self.masker.mask_aligned(target_crop, output_size=512)
            if self.masker is not None
            else None
        )
        output = paste_face(
            target_bgr,
            swapped_crop,
            matrix,
            aligned_face_mask=semantic_mask,
            erosion_fraction=0.04,
            blur_fraction=0.025,
        )
        return output, source_face, target_face


class MLXFaceSwapPipeline:
    def __init__(
        self,
        detector_path: str | Path,
        recognizer_path: str | Path,
        swapper_path: str | Path,
        mask_path: str | Path | None = None,
        restorer_path: str | Path | None = None,
        restoration_strength: float = 0.5,
        swapper_precision: str = "fp16_compatible",
        detector_kind: str = "scrfd",
    ):
        if detector_kind == "scrfd":
            self.detector = MLXSCRFD(detector_path)
        elif detector_kind == "yunet":
            self.detector = MLXYuNet(detector_path)
        else:
            raise ValueError("detector_kind must be scrfd or yunet")
        self.recognizer = MLXArcFace(recognizer_path)
        self.swapper = MLXInSwapper(swapper_path, precision=swapper_precision)
        self.masker = MLXXSeg(mask_path) if mask_path is not None else None
        self.restorer = MLXGFPGAN(restorer_path) if restorer_path is not None else None
        self.restoration_strength = restoration_strength

    def swap_largest_face(
        self, source_bgr: np.ndarray, target_bgr: np.ndarray
    ) -> tuple[np.ndarray, FaceDetection, FaceDetection]:
        source_faces = self.detector.detect(source_bgr)
        target_faces = self.detector.detect(target_bgr)
        if not source_faces:
            raise ValueError("no source face detected")
        if not target_faces:
            raise ValueError("no target face detected")
        source_face = max(source_faces, key=_face_area)
        target_face = max(target_faces, key=_face_area)
        embedding = self.recognizer.embed(source_bgr, source_face.landmarks)
        output = self.swap_detection(target_bgr, target_face, embedding)
        return output, source_face, target_face

    def prepare_identity(
        self, source_bgr: np.ndarray
    ) -> tuple[np.ndarray, FaceDetection]:
        faces = self.detector.detect(source_bgr)
        if not faces:
            raise ValueError("no source face detected")
        face = max(faces, key=_face_area)
        return self.recognizer.embed(source_bgr, face.landmarks), face

    def swap_detection(
        self,
        target_bgr: np.ndarray,
        target_face: FaceDetection,
        normalized_embedding: np.ndarray,
    ) -> np.ndarray:
        target_crop, matrix = align_face(target_bgr, target_face.landmarks, 128)
        swapped_crop = self.swapper.swap_aligned(target_crop, normalized_embedding)
        if self.restorer is not None:
            swapped_crop = self.restorer.restore(
                swapped_crop, strength=self.restoration_strength
            )
        semantic_mask = (
            self.masker.mask_aligned(target_crop) if self.masker is not None else None
        )
        return paste_face(
            target_bgr,
            swapped_crop,
            matrix,
            aligned_face_mask=semantic_mask,
        )

    def swap_detections_batch(
        self,
        targets: list[tuple[np.ndarray, FaceDetection]],
        normalized_embedding: np.ndarray,
    ) -> list[np.ndarray]:
        if not targets:
            return []
        aligned = [
            align_face(target, face.landmarks, 128)
            for target, face in targets
        ]
        crops = [item[0] for item in aligned]
        matrices = [item[1] for item in aligned]
        swapped = self.swapper.swap_aligned_batch(crops, normalized_embedding)
        outputs = []
        for (target, _), target_crop, matrix, swapped_crop in zip(
            targets, crops, matrices, swapped, strict=True
        ):
            if self.restorer is not None:
                swapped_crop = self.restorer.restore(
                    swapped_crop, strength=self.restoration_strength
                )
            semantic_mask = (
                self.masker.mask_aligned(target_crop)
                if self.masker is not None
                else None
            )
            outputs.append(
                paste_face(
                    target,
                    swapped_crop,
                    matrix,
                    aligned_face_mask=semantic_mask,
                )
            )
        return outputs


def _face_area(face: FaceDetection) -> float:
    width = max(0.0, float(face.bbox[2] - face.bbox[0]))
    height = max(0.0, float(face.bbox[3] - face.bbox[1]))
    return width * height
