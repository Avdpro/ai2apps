"""AI2Apps Model Worker adapter for SAM 2.1 Small MLX video masks."""

from __future__ import annotations

import asyncio
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np

from ai2apps.model_worker import (
    ModelWorkerArtifact,
    ModelWorkerError,
    ModelWorkerRequest,
)

MODEL_ID = "ai2apps.model.sam21-mlx/small"
WEIGHTS_FILE = "sam2.1_hiera_small.safetensors"
MAX_FRAMES = 450
MAX_PIXELS = 1920 * 1080


class SAM21Adapter:
    def __init__(self, context: Any, *, predictor_factory=None):
        self.context = context
        self._factory = predictor_factory
        self._predictor = None
        self._checkpoint = None
        self._lock = asyncio.Lock()

    async def start(self):
        return None

    async def stop(self):
        async with self._lock:
            loaded = self._predictor is not None
            self._predictor = None
            self._checkpoint = None
            if loaded and self._factory is None:
                import mlx.core as mx
                mx.clear_cache()

    def _model(self, payload):
        selected = payload.get("model")
        if selected not in {MODEL_ID, "eisneim/sam2.1_mlx"}:
            raise ModelWorkerError("Select the installed SAM 2.1 MLX model", code="model_not_found", status_code=404)
        return MODEL_ID

    @staticmethod
    def _parameters(payload):
        raw = payload.get("parameters", payload)
        if isinstance(raw, str):
            raw = json.loads(raw)
        if not isinstance(raw, dict):
            raise ValueError("parameters must be an object")
        frame = raw.get("prompt_frame", 0)
        points = raw.get("points")
        if isinstance(frame, str) and frame.isdecimal():
            frame = int(frame)
        if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
            raise ValueError("prompt_frame must be a non-negative integer")
        if not isinstance(points, list) or not 1 <= len(points) <= 32:
            raise ValueError("points must contain 1 to 32 point prompts")
        coordinates, labels = [], []
        for point in points:
            if not isinstance(point, dict):
                raise ValueError("each point must be an object")
            x, y, label = point.get("x"), point.get("y"), point.get("label", 1)
            if any(isinstance(value, bool) for value in (x, y, label)) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)) or label not in {0, 1}:
                raise ValueError("point x/y must be numbers and label must be 0 or 1")
            coordinates.append((float(x), float(y)))
            labels.append(int(label))
        if 1 not in labels:
            raise ValueError("at least one positive point is required")
        threshold = raw.get("threshold", 0.5)
        feather = raw.get("feather", 1.5)
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0.05 <= threshold <= 0.95:
            raise ValueError("threshold must be between 0.05 and 0.95")
        if not isinstance(feather, (int, float)) or isinstance(feather, bool) or not 0 <= feather <= 8:
            raise ValueError("feather must be between 0 and 8 pixels")
        return frame, np.asarray(coordinates, np.float32), np.asarray(labels, np.int32), float(threshold), float(feather)

    @staticmethod
    def _decode(path: Path):
        import av
        frames = []
        with av.open(str(path), mode="r") as container:
            stream = next((item for item in container.streams if item.type == "video"), None)
            if stream is None:
                raise ValueError("source is not a video")
            rate = stream.average_rate or stream.guessed_rate or Fraction(24, 1)
            for decoded in container.decode(stream):
                frame = decoded.to_ndarray(format="rgb24")
                if frame.shape[0] * frame.shape[1] > MAX_PIXELS:
                    raise ValueError("video resolution exceeds 1920x1080")
                frames.append(frame)
                if len(frames) > MAX_FRAMES:
                    raise ValueError("video exceeds the 450-frame MVP limit")
        if not frames:
            raise ValueError("video contains no decodable frames")
        return np.stack(frames), Fraction(rate)

    @staticmethod
    def _write_masks(path: Path, masks, rate: Fraction, threshold: float, feather: float):
        import av
        from scipy.ndimage import gaussian_filter
        first = masks[0]
        height, width = first.shape
        with av.open(str(path), mode="w", format="mp4") as container:
            try:
                stream = container.add_stream("libx264", rate=rate)
            except av.FFmpegError:
                stream = container.add_stream("h264", rate=rate)
            stream.width = width
            stream.height = height
            stream.pix_fmt = "yuv420p"
            for logits in masks:
                alpha = 1.0 / (1.0 + np.exp(-np.clip(logits, -30.0, 30.0)))
                if feather:
                    alpha = gaussian_filter(alpha, sigma=feather)
                alpha = np.where(alpha >= threshold, alpha, 0.0)
                plane = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
                rgb = np.repeat(plane[:, :, None], 3, axis=2)
                for packet in stream.encode(av.VideoFrame.from_ndarray(rgb, format="rgb24")):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)

    def _load(self, checkpoint: Path):
        if self._predictor is not None and self._checkpoint == checkpoint:
            return self._predictor
        if self._factory is not None:
            predictor = self._factory(checkpoint)
        else:
            from sam2_mlx import SAM2VideoPredictor, build_model
            predictor = SAM2VideoPredictor(build_model("small", str(checkpoint)))
        self._predictor, self._checkpoint = predictor, checkpoint
        return predictor

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "video_segmentation":
            raise ModelWorkerError("Unsupported operation", code="operation_not_supported")
        if request.output_root is None:
            raise ModelWorkerError("Missing controlled output root", code="runtime_protocol_error", status_code=500)
        model_id = self._model(request.payload)
        try:
            prompt_frame, points, labels, threshold, feather = self._parameters(request.payload)
            source = request.part("video")
            frames, rate = await asyncio.to_thread(self._decode, source.path)
            if prompt_frame >= len(frames):
                raise ValueError("prompt_frame is outside the source video")
        except (ValueError, TypeError, OSError, RuntimeError, json.JSONDecodeError) as error:
            raise ModelWorkerError(str(error), code="invalid_request") from error
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError("Install the SAM 2.1 MLX checkpoint first", code="model_unavailable", status_code=503)
        weights = Path(checkpoint.path) / WEIGHTS_FILE
        if not weights.is_file():
            raise ModelWorkerError("SAM 2.1 MLX checkpoint is incomplete", code="checkpoint_incomplete", status_code=503)
        output = request.output_root / ("sam21-mask-" + hashlib.sha256(request.request_id.encode()).hexdigest()[:20] + ".mp4")
        async with self._lock:
            predictor = await asyncio.to_thread(self._load, weights)
            await asyncio.to_thread(predictor.init_state, frames, preload_features=True)
            await asyncio.to_thread(predictor.add_new_points, prompt_frame, 1, points, labels)
            collected = []
            for _index, _ids, candidates, ious in predictor.propagate_in_video(start_frame=prompt_frame, max_frames=len(frames) - prompt_frame):
                best = int(np.argmax(np.asarray(ious[0])))
                collected.append(np.asarray(candidates[0][best], dtype=np.float32))
            if prompt_frame:
                empty = np.full_like(collected[0], -30.0)
                collected = [empty.copy() for _ in range(prompt_frame)] + collected
            await asyncio.to_thread(self._write_masks, output, collected, rate, threshold, feather)
        return ModelWorkerArtifact(path=output, media_type="video/mp4", filename="sam21-mask.mp4", metadata={"kind": "video_mask", "frames": len(collected), "soft": True})


def create_adapter(context):
    return SAM21Adapter(context)
