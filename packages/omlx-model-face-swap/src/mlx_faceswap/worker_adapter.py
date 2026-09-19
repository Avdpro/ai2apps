"""Model Worker adapter for native MLX GhostV2 actor replacement."""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import threading
from pathlib import Path

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

from .detector import MLXYuNet
from .geometry import align_face, paste_face
from .media import (
    VideoReader,
    VideoWriter,
    read_image_bgr,
    remux_source_audio,
    write_image_bgr,
)
from .tracking import FaceTrack, TemporalFaceTracker

CHECKPOINT_SCHEMA = "ai2apps.mlx-ghostv2-checkpoint/v1"
MINIMUM_MEMORY_BYTES = 16 * 1024**3


class UnsupportedControlError(ValueError):
    pass


def _area(item) -> float:
    return max(0.0, float(item.bbox[2] - item.bbox[0])) * max(
        0.0, float(item.bbox[3] - item.bbox[1])
    )


def _physical_memory_bytes() -> int | None:
    """Return installed memory without adding a Runtime dependency."""
    try:
        pages = int(os.sysconf("SC_PHYS_PAGES"))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None
    value = pages * page_size
    return value if value > 0 else None


class MLXFaceSwapAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._root: Path | None = None
        self._detector: MLXYuNet | None = None
        self._model: object | None = None
        self._cancellations: dict[str, threading.Event] = {}
        self._cancellations_lock = threading.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        with self._cancellations_lock:
            for event in self._cancellations.values():
                event.set()
            self._cancellations.clear()
        self._model = None
        self._detector = None
        self._root = None
        try:
            import mlx.core as mx  # noqa: PLC0415

            mx.clear_cache()
        except (ImportError, RuntimeError):
            pass

    def cancel(self, request_id: str) -> None:
        with self._cancellations_lock:
            event = self._cancellations.get(request_id)
        if event is not None:
            event.set()

    @staticmethod
    def _require_supported_memory() -> None:
        available = _physical_memory_bytes()
        if available is not None and available < MINIMUM_MEMORY_BYTES:
            raise ModelWorkerError(
                "GhostV2 requires at least 16 GiB unified memory "
                f"({available / 1024**3:.1f} GiB detected)",
                code="insufficient_resources",
                status_code=409,
            )

    def _ensure_checkpoint(self, model_id: str) -> Path:
        if self._root is not None:
            return self._root
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned MLX GhostV2 checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = Path(checkpoint.path)
        try:
            manifest = json.loads(
                (root / "ai2apps-checkpoint.json").read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ModelWorkerError(
                "The MLX GhostV2 checkpoint manifest is invalid",
                code="invalid_checkpoint",
                status_code=503,
            ) from error
        if manifest.get("schema") != CHECKPOINT_SCHEMA:
            raise ModelWorkerError(
                "The MLX GhostV2 checkpoint layout is unsupported",
                code="invalid_checkpoint",
                status_code=503,
            )
        expected = {
            "detector": "models/face_detection_yunet_2023mar.omlx",
            "recognizer": "models/ghostv2_cvlface.omlx",
            "generator": "models/ghostv2_generator.native",
        }
        components = manifest.get("components")
        if not isinstance(components, dict) or any(
            components.get(role) != relative for role, relative in expected.items()
        ):
            raise ModelWorkerError(
                "The MLX GhostV2 checkpoint component binding is invalid",
                code="invalid_checkpoint",
                status_code=503,
            )
        required = [
            root / expected["detector"] / name
            for name in ("bundle.json", "graph.json", "weights.safetensors")
        ]
        required += [
            root / expected["recognizer"] / name
            for name in ("bundle.json", "graph.json", "weights.safetensors")
        ]
        required += [
            root / expected["generator"] / name
            for name in ("config.json", "weights.safetensors")
        ]
        missing = [str(path.relative_to(root)) for path in required if not path.is_file()]
        if missing:
            raise ModelWorkerError(
                f"The MLX GhostV2 checkpoint is incomplete: {', '.join(missing)}",
                code="invalid_checkpoint",
                status_code=503,
            )
        self._root = root
        return root

    def _load(self, model_id: str) -> tuple[MLXYuNet, object]:
        from .ghostv2 import MLXGhostV2  # noqa: PLC0415

        self._require_supported_memory()
        root = self._ensure_checkpoint(model_id)
        if self._detector is None:
            self._detector = MLXYuNet(root / "models" / "face_detection_yunet_2023mar.omlx")
        if self._model is None:
            self._model = MLXGhostV2(root / "models")
        return self._detector, self._model

    @staticmethod
    def _part(request, inputs: dict, role: str, default_name: str):
        descriptor = inputs.get(role, {})
        name = descriptor.get("part_name", default_name) if isinstance(descriptor, dict) else default_name
        try:
            return request.part(str(name))
        except (KeyError, ValueError) as error:
            raise ValueError(f"{role} multipart input is required") from error

    @staticmethod
    def _parameters(payload: dict, operation: str) -> dict:
        parameters = payload.get("parameters", payload)
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be an object")
        allowed = {"precision", "output_format"}
        if operation == "video_generation":
            allowed.update({"audio_output_mode", "track_id", "detection_interval", "batch_size", "velocity_smoothing"})
        envelope = {"model", "inputs", "parameters"} if parameters is payload else set()
        unknown = sorted(set(parameters) - allowed - envelope)
        if unknown:
            raise UnsupportedControlError(f"unsupported controls: {', '.join(unknown)}")
        precision = str(parameters.get("precision", "fp16"))
        if precision != "fp16":
            raise UnsupportedControlError("GhostV2 MVP supports only precision=fp16")
        track_id = parameters.get("track_id") if operation == "video_generation" else None
        if track_id is not None:
            if isinstance(track_id, bool) or int(track_id) < 1:
                raise ValueError("track_id must be a positive integer")
            track_id = int(track_id)
        detection_interval = int(parameters.get("detection_interval", 1) if operation == "video_generation" else 1)
        if not 1 <= detection_interval <= 8:
            raise ValueError("detection_interval must be between 1 and 8")
        batch_size = int(parameters.get("batch_size", 2) if operation == "video_generation" else 1)
        if not 1 <= batch_size <= 8:
            raise ValueError("batch_size must be between 1 and 8")
        velocity_smoothing = float(parameters.get("velocity_smoothing", 0.5) if operation == "video_generation" else 0.5)
        if not 0.0 <= velocity_smoothing <= 1.0:
            raise ValueError("velocity_smoothing must be between 0 and 1")
        expected_format = "png" if operation == "image_edit" else "mp4"
        output_format = str(parameters.get("output_format", expected_format))
        if output_format != expected_format:
            raise UnsupportedControlError(f"{operation} supports only output_format={expected_format}")
        audio_mode = str(parameters.get("audio_output_mode", "none" if operation == "image_edit" else "auto"))
        if audio_mode not in {"auto", "none", "preserve_driving_audio"}:
            raise UnsupportedControlError("audio_output_mode is unsupported")
        return {
            "precision": precision,
            "track_id": track_id,
            "detection_interval": detection_interval,
            "batch_size": batch_size,
            "velocity_smoothing": velocity_smoothing,
            "audio_output_mode": audio_mode,
        }

    async def invoke(self, request):
        if request.operation not in {"image_edit", "video_generation"}:
            raise ModelWorkerError(f"Unsupported operation: {request.operation}", code="operation_not_supported", status_code=400)
        payload = dict(request.payload)
        inputs = payload.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ModelWorkerError("inputs must be an object", code="invalid_request", status_code=400)
        model_id = str(payload.get("model") or "")
        if not model_id:
            raise ModelWorkerError("model is required", code="invalid_request", status_code=400)
        try:
            parameters = self._parameters(payload, request.operation)
            identity = self._part(request, inputs, "reference_image", "identity")
            target_role = "source_image" if request.operation == "image_edit" else "source_video"
            target = self._part(request, inputs, target_role, "target")
        except UnsupportedControlError as error:
            raise ModelWorkerError(str(error), code="unsupported_control", status_code=400) from error
        except (OSError, TypeError, ValueError) as error:
            raise ModelWorkerError(str(error), code="invalid_request", status_code=400) from error
        cancelled = threading.Event()
        with self._cancellations_lock:
            self._cancellations[request.request_id] = cancelled
        try:
            detector, model = await asyncio.to_thread(self._load, model_id)
            if request.operation == "image_edit":
                return await self._replace_image(request, detector, model, identity.path, target.path, parameters)
            return await self._replace_video(request, detector, model, identity.path, target.path, parameters, cancelled)
        except ModelWorkerError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise ModelWorkerError(str(error), code="generation_failed", status_code=422) from error
        finally:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)

    @staticmethod
    def _prepare_identity(detector, model, path):
        image = read_image_bgr(path)
        faces = detector.detect(image)
        if not faces:
            raise ValueError("reference_image does not contain a detectable face")
        crop, _ = align_face(image, max(faces, key=_area).landmarks, 256)
        return model.encode_aligned(crop)

    async def _replace_image(self, request, detector, model, identity_path, target_path, parameters):
        def render():
            identity = self._prepare_identity(detector, model, identity_path)
            target = read_image_bgr(target_path)
            faces = detector.detect(target)
            if not faces:
                raise ValueError("source_image does not contain a detectable face")
            crop, matrix = align_face(target, max(faces, key=_area).landmarks, 256)
            generated = model.generate_aligned_batch([crop], identity)[0]
            path = request.output_root / "ghostv2-face-swap.png"
            write_image_bgr(path, paste_face(target, generated, matrix))
            return path

        path = await asyncio.to_thread(render)
        return ModelWorkerArtifact(path, media_type="image/png", filename=path.name, metadata=self._metadata(parameters, audio_applied="none"))

    async def _replace_video(self, request, detector, model, identity_path, target_path, parameters, cancelled):
        loop = asyncio.get_running_loop()

        def report(current: int, total: int | None) -> None:
            if request.progress is None:
                return
            value = request.progress({"phase": "replace", "current": current, "total": max(total or current, 1)})
            if inspect.isawaitable(value):
                asyncio.run_coroutine_threadsafe(value, loop)

        def generate():
            identity = self._prepare_identity(detector, model, identity_path)
            reader = VideoReader(target_path)
            total = int(reader.stream.frames) if reader.stream.frames else None
            silent = request.output_root / "rendering.mp4"
            output = request.output_root / "ghostv2-face-swap.mp4"
            writer = VideoWriter(silent, reader.fps, (reader.width, reader.height))
            tracker = TemporalFaceTracker(smoothing=0.65, max_missed=3, velocity_smoothing=parameters["velocity_smoothing"])
            chosen_track = parameters["track_id"]
            selected_seen = False
            frames = 0
            pending: list[tuple[object, object | None]] = []

            def flush() -> None:
                if not pending:
                    return
                if cancelled.is_set():
                    raise ModelWorkerError("Face replacement was cancelled", code="generation_cancelled", status_code=409)
                selected = [(frame, face) for frame, face in pending if face is not None]
                aligned = [align_face(frame, face.landmarks, 256) for frame, face in selected]
                generated = model.generate_aligned_batch([crop for crop, _ in aligned], identity)
                generated_iter = iter(generated)
                aligned_iter = iter(aligned)
                for frame, face in pending:
                    if face is None:
                        writer.write(frame)
                    else:
                        generated_face = next(generated_iter)
                        _, matrix = next(aligned_iter)
                        writer.write(paste_face(frame, generated_face, matrix))
                pending.clear()
                report(frames, total)

            try:
                for frame in reader:
                    if cancelled.is_set():
                        raise ModelWorkerError("Face replacement was cancelled", code="generation_cancelled", status_code=409)
                    tracks = tracker.update(detector.detect(frame)) if frames % parameters["detection_interval"] == 0 else tracker.predict()
                    visible = [track for track in tracks if track.missed == 0]
                    if chosen_track is None and visible:
                        chosen_track = max(visible, key=_area).track_id
                    selected_track: FaceTrack | None = next((track for track in tracks if track.track_id == chosen_track), None)
                    face = selected_track.detection() if selected_track is not None and selected_track.missed <= tracker.max_missed else None
                    selected_seen = selected_seen or face is not None
                    pending.append((frame, face))
                    frames += 1
                    if len(pending) >= parameters["batch_size"]:
                        flush()
                flush()
            finally:
                writer.close()
                reader.close()
            if frames == 0:
                raise ValueError("source_video contains no decodable frames")
            if not selected_seen:
                if parameters["track_id"] is None:
                    raise ValueError("source_video does not contain a detectable face")
                raise ValueError(f"track_id={parameters['track_id']} was not found")
            if parameters["audio_output_mode"] == "none":
                silent.replace(output)
                audio_applied = "none"
            else:
                copied = remux_source_audio(silent, target_path, output)
                audio_applied = "preserve_driving_audio" if copied else "none"
                if parameters["audio_output_mode"] == "preserve_driving_audio" and not copied:
                    raise ValueError("source_video does not contain an audio stream")
            return output, frames, chosen_track, audio_applied

        output, frames, chosen_track, audio_applied = await asyncio.to_thread(generate)
        metadata = self._metadata(parameters, audio_applied=audio_applied)
        metadata.update({"frames": frames, "track_id": chosen_track})
        return ModelWorkerArtifact(output, media_type="video/mp4", filename=output.name, metadata=metadata)

    @staticmethod
    def _metadata(parameters: dict, *, audio_applied: str) -> dict:
        return {
            "mode": "ghostv2_actor_replacement",
            "engine": "ghostv2-native-mlx",
            "applied_controls": {
                name: {"requested": value, "applied": value}
                for name, value in parameters.items()
                if name != "audio_output_mode"
            }
            | {"audio_output_mode": {"requested": parameters["audio_output_mode"], "applied": audio_applied}},
            "warnings": ["Source media did not contain an audio stream."] if parameters["audio_output_mode"] == "auto" and audio_applied == "none" else [],
        }


def create_adapter(context):
    return MLXFaceSwapAdapter(context)
