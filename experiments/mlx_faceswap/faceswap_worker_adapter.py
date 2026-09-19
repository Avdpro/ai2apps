"""Model Worker adapter for MLX actor identity replacement."""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
from pathlib import Path

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

from .media import (
    VideoReader,
    VideoWriter,
    read_image_bgr,
    remux_source_audio,
    write_image_bgr,
)
from .models import MLXFaceSwapPipeline
from .tracking import TemporalFaceTracker

CHECKPOINT_SCHEMA = "ai2apps.mlx-face-swap-checkpoint/v1"


class UnsupportedControlError(ValueError):
    pass


def _area(item) -> float:
    return max(0.0, float(item.bbox[2] - item.bbox[0])) * max(
        0.0, float(item.bbox[3] - item.bbox[1])
    )


def _boolean(value, name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError(f"{name} must be boolean")


class MLXFaceSwapAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._root: Path | None = None
        self._pipelines: dict[tuple[str, str, bool], MLXFaceSwapPipeline] = {}
        self._cancellations: dict[str, threading.Event] = {}
        self._cancellations_lock = threading.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        with self._cancellations_lock:
            for event in self._cancellations.values():
                event.set()
            self._cancellations.clear()
        self._pipelines.clear()
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

    def _ensure_checkpoint(self, model_id: str) -> Path:
        if self._root is not None:
            return self._root
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "A licensed MLX face-swap checkpoint is not installed",
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
                "The MLX face-swap checkpoint manifest is invalid",
                code="invalid_checkpoint",
                status_code=503,
            ) from error
        if manifest.get("schema") != CHECKPOINT_SCHEMA:
            raise ModelWorkerError(
                "The MLX face-swap checkpoint layout is unsupported",
                code="invalid_checkpoint",
                status_code=503,
            )
        expected_components = {
            "detector": "models/face_detection_yunet_2023mar.omlx",
            "recognizer": "models/w600k_r50.omlx",
            "swapper": "models/inswapper_128.fp16.omlx",
        }
        if manifest.get("components") != expected_components:
            raise ModelWorkerError(
                "The MLX face-swap checkpoint component binding is invalid",
                code="invalid_checkpoint",
                status_code=503,
            )
        required = tuple(root / relative for relative in expected_components.values())
        missing = [str(path.relative_to(root)) for path in required if not path.is_dir()]
        if missing:
            raise ModelWorkerError(
                f"The MLX face-swap checkpoint is incomplete: {', '.join(missing)}",
                code="invalid_checkpoint",
                status_code=503,
            )
        self._root = root
        return root

    def _load(self, model_id: str, parameters: dict) -> MLXFaceSwapPipeline:
        root = self._ensure_checkpoint(model_id)
        precision = parameters["precision"]
        mask_mode = parameters["mask_mode"]
        restore = parameters["restore_strength"] > 0
        key = (precision, mask_mode, restore)
        if key in self._pipelines:
            pipeline = self._pipelines[key]
            pipeline.restoration_strength = parameters["restore_strength"]
            return pipeline
        mask_path = root / "models" / "XSeg_model.omlx"
        restorer_path = root / "models" / "GFPGANv1.4.omlx"
        if mask_mode == "semantic" and not mask_path.is_dir():
            raise UnsupportedControlError(
                "mask_mode=semantic requires the optional XSeg model"
            )
        if restore and not restorer_path.is_dir():
            raise UnsupportedControlError(
                "restore_strength requires the optional GFPGAN model"
            )
        pipeline = MLXFaceSwapPipeline(
            root / "models" / "face_detection_yunet_2023mar.omlx",
            root / "models" / "w600k_r50.omlx",
            root / "models" / "inswapper_128.fp16.omlx",
            mask_path if mask_mode == "semantic" else None,
            restorer_path if restore else None,
            restoration_strength=parameters["restore_strength"],
            swapper_precision=precision,
            detector_kind="yunet",
        )
        self._pipelines[key] = pipeline
        return pipeline

    @staticmethod
    def _part(request, inputs: dict, role: str, default_name: str):
        descriptor = inputs.get(role, {})
        name = (
            descriptor.get("part_name", default_name)
            if isinstance(descriptor, dict)
            else default_name
        )
        try:
            return request.part(str(name))
        except (KeyError, ValueError) as error:
            raise ValueError(f"{role} multipart input is required") from error

    @staticmethod
    def _parameters(payload: dict, operation: str) -> dict:
        parameters = payload.get("parameters", payload)
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be an object")
        allowed = {
            "precision",
            "mask_mode",
            "restore_strength",
            "output_format",
        }
        if operation == "video_generation":
            allowed.update(
                {
                    "audio_output_mode",
                    "track_id",
                    "detection_interval",
                    "batch_size",
                }
            )
        envelope = {"model", "inputs", "parameters"} if parameters is payload else set()
        unknown = sorted(set(parameters) - allowed - envelope)
        if unknown:
            raise UnsupportedControlError(
                f"unsupported controls: {', '.join(unknown)}"
            )
        precision = str(parameters.get("precision", "bf16"))
        if precision not in {"bf16", "fp16_compatible"}:
            raise UnsupportedControlError(
                "precision must be bf16 or fp16_compatible"
            )
        mask_mode = str(parameters.get("mask_mode", "feather"))
        if mask_mode not in {"feather", "semantic"}:
            raise UnsupportedControlError(
                "mask_mode must be feather or semantic"
            )
        restore_strength = float(parameters.get("restore_strength", 0.0))
        if not 0.0 <= restore_strength <= 1.0:
            raise ValueError("restore_strength must be between 0 and 1")
        track_id = parameters.get("track_id") if operation == "video_generation" else None
        if track_id is not None:
            if isinstance(track_id, bool) or int(track_id) < 1:
                raise ValueError("track_id must be a positive integer")
            track_id = int(track_id)
        detection_interval = int(
            parameters.get("detection_interval", 2)
            if operation == "video_generation"
            else 1
        )
        if not 1 <= detection_interval <= 8:
            raise ValueError("detection_interval must be between 1 and 8")
        batch_size = int(
            parameters.get("batch_size", 8)
            if operation == "video_generation"
            else 1
        )
        if not 1 <= batch_size <= 16:
            raise ValueError("batch_size must be between 1 and 16")
        expected_format = "png" if operation == "image_edit" else "mp4"
        output_format = str(parameters.get("output_format", expected_format))
        if output_format != expected_format:
            raise UnsupportedControlError(
                f"{operation} supports only output_format={expected_format}"
            )
        audio_mode = str(
            parameters.get(
                "audio_output_mode",
                "none" if operation == "image_edit" else "auto",
            )
        )
        if audio_mode not in {"auto", "none", "preserve_driving_audio"}:
            raise UnsupportedControlError("audio_output_mode is unsupported")
        return {
            "precision": precision,
            "mask_mode": mask_mode,
            "restore_strength": restore_strength,
            "track_id": track_id,
            "detection_interval": detection_interval,
            "batch_size": batch_size,
            "audio_output_mode": audio_mode,
        }

    async def invoke(self, request):
        if request.operation not in {"image_edit", "video_generation"}:
            raise ModelWorkerError(
                f"Unsupported operation: {request.operation}",
                code="operation_not_supported",
                status_code=400,
            )
        payload = dict(request.payload)
        inputs = payload.get("inputs", {})
        if not isinstance(inputs, dict):
            raise ModelWorkerError(
                "inputs must be an object", code="invalid_request", status_code=400
            )
        model_id = str(payload.get("model") or "")
        if not model_id:
            raise ModelWorkerError(
                "model is required", code="invalid_request", status_code=400
            )
        try:
            parameters = self._parameters(payload, request.operation)
            identity_part = self._part(
                request, inputs, "reference_image", "identity"
            )
            target_role = (
                "source_image" if request.operation == "image_edit" else "source_video"
            )
            target_part = self._part(request, inputs, target_role, "target")
        except UnsupportedControlError as error:
            raise ModelWorkerError(
                str(error), code="unsupported_control", status_code=400
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ModelWorkerError(
                str(error), code="invalid_request", status_code=400
            ) from error
        cancelled = threading.Event()
        with self._cancellations_lock:
            self._cancellations[request.request_id] = cancelled
        try:
            pipeline = await asyncio.to_thread(self._load, model_id, parameters)
            if cancelled.is_set():
                raise ModelWorkerError(
                    "Face replacement was cancelled",
                    code="generation_cancelled",
                    status_code=409,
                )
            if request.operation == "image_edit":
                return await self._replace_image(
                    request,
                    pipeline,
                    identity_part.path,
                    target_part.path,
                    parameters,
                )
            return await self._replace_video(
                request,
                pipeline,
                identity_part.path,
                target_part.path,
                parameters,
                cancelled,
            )
        except ModelWorkerError:
            raise
        except UnsupportedControlError as error:
            raise ModelWorkerError(
                str(error), code="unsupported_control", status_code=400
            ) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise ModelWorkerError(
                str(error), code="generation_failed", status_code=422
            ) from error
        finally:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)

    async def _replace_image(
        self, request, pipeline, identity_path, target_path, parameters
    ):
        def render():
            identity_image = read_image_bgr(identity_path)
            target_image = read_image_bgr(target_path)
            output, _, _ = pipeline.swap_largest_face(
                identity_image, target_image
            )
            path = request.output_root / "face-swap.png"
            write_image_bgr(path, output)
            return path

        path = await asyncio.to_thread(render)
        return ModelWorkerArtifact(
            path,
            media_type="image/png",
            filename=path.name,
            metadata=self._metadata(parameters, audio_applied="none"),
        )

    async def _replace_video(
        self,
        request,
        pipeline,
        identity_path,
        target_path,
        parameters,
        cancelled,
    ):
        loop = asyncio.get_running_loop()

        def report(current: int, total: int | None) -> None:
            if request.progress is None:
                return
            value = request.progress(
                {
                    "phase": "replace",
                    "current": current,
                    "total": max(total or current, 1),
                }
            )
            if inspect.isawaitable(value):
                asyncio.run_coroutine_threadsafe(value, loop)

        def generate():
            identity_image = read_image_bgr(identity_path)
            identity, _ = pipeline.prepare_identity(identity_image)
            reader = VideoReader(target_path)
            total = int(reader.stream.frames) if reader.stream.frames else None
            silent = request.output_root / "rendering.mp4"
            output = request.output_root / "face-swap.mp4"
            writer = VideoWriter(silent, reader.fps, (reader.width, reader.height))
            tracker = TemporalFaceTracker(smoothing=0.65, max_missed=3)
            chosen_track = parameters["track_id"]
            selected_seen = False
            frames = 0
            pending: list[tuple[object, object | None]] = []

            def flush() -> None:
                if not pending:
                    return
                if cancelled.is_set():
                    raise ModelWorkerError(
                        "Face replacement was cancelled",
                        code="generation_cancelled",
                        status_code=409,
                    )
                selected = [
                    (frame, detection)
                    for frame, detection in pending
                    if detection is not None
                ]
                swapped = pipeline.swap_detections_batch(selected, identity)
                swapped_iter = iter(swapped)
                for frame, detection in pending:
                    writer.write(
                        next(swapped_iter) if detection is not None else frame
                    )
                pending.clear()
                report(frames, total)

            try:
                for frame in reader:
                    if cancelled.is_set():
                        raise ModelWorkerError(
                            "Face replacement was cancelled",
                            code="generation_cancelled",
                            status_code=409,
                        )
                    if frames % parameters["detection_interval"] == 0:
                        tracks = tracker.update(pipeline.detector.detect(frame))
                    else:
                        tracks = tracker.tracks
                    visible = [item for item in tracks if item.missed == 0]
                    if chosen_track is None and visible:
                        chosen_track = max(visible, key=_area).track_id
                    selected = next(
                        (
                            track
                            for track in tracks
                            if track.track_id == chosen_track
                        ),
                        None,
                    )
                    detection = None
                    if selected is not None and selected.missed <= tracker.max_missed:
                        detection = selected.detection()
                        selected_seen = True
                    pending.append((frame, detection))
                    frames += 1
                    if len(pending) >= parameters["batch_size"]:
                        flush()
                flush()
            finally:
                writer.close()
                reader.close()
            if frames == 0:
                raise ValueError("source video contains no decodable frames")
            if not selected_seen:
                if parameters["track_id"] is None:
                    raise ValueError("source video does not contain a detectable face")
                raise ValueError(
                    f"track_id={parameters['track_id']} was not found in source video"
                )
            if parameters["audio_output_mode"] == "none":
                silent.replace(output)
                audio_applied = "none"
            else:
                copied = remux_source_audio(silent, target_path, output)
                audio_applied = "preserve_driving_audio" if copied else "none"
                if (
                    parameters["audio_output_mode"] == "preserve_driving_audio"
                    and not copied
                ):
                    raise ValueError("source video does not contain an audio stream")
            return output, frames, chosen_track, audio_applied

        output, frames, chosen_track, audio_applied = await asyncio.to_thread(generate)
        metadata = self._metadata(parameters, audio_applied=audio_applied)
        metadata.update({"frames": frames, "track_id": chosen_track})
        return ModelWorkerArtifact(
            output,
            media_type="video/mp4",
            filename=output.name,
            metadata=metadata,
        )

    @staticmethod
    def _metadata(parameters: dict, *, audio_applied: str) -> dict:
        return {
            "mode": "actor_identity_replacement",
            "applied_controls": {
                name: {"requested": value, "applied": value}
                for name, value in parameters.items()
                if name != "audio_output_mode"
            }
            | {
                "audio_output_mode": {
                    "requested": parameters["audio_output_mode"],
                    "applied": audio_applied,
                }
            },
            "warnings": (
                ["Source media did not contain an audio stream."]
                if parameters["audio_output_mode"] == "auto"
                and audio_applied == "none"
                else []
            ),
        }


def create_adapter(context):
    return MLXFaceSwapAdapter(context)
