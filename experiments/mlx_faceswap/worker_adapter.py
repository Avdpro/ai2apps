"""Model Worker adapter prototype for the release-safe MLX LivePortrait stack."""

from __future__ import annotations

import asyncio
import inspect
import json
import threading
from pathlib import Path

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

from .geometry import align_face, paste_face
from .media import (
    VideoReader,
    VideoWriter,
    read_image_bgr,
    remux_source_audio,
    resize_bgr,
    write_image_bgr,
)
from .tracking import TemporalFaceTracker

CHECKPOINT_SCHEMA = "ai2apps.mlx-liveportrait-checkpoint/v1"


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


class MLXLivePortraitAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._root: Path | None = None
        self._detector = None
        self._pipelines: dict[str, object] = {}
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

    def _ensure_checkpoint(self, model_id: str) -> Path:
        if self._root is not None:
            return self._root
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned MLX LivePortrait checkpoint is not installed",
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
                "The MLX LivePortrait checkpoint manifest is invalid",
                code="invalid_checkpoint",
                status_code=503,
            ) from error
        if manifest.get("schema") != CHECKPOINT_SCHEMA:
            raise ModelWorkerError(
                "The MLX LivePortrait checkpoint layout is unsupported",
                code="invalid_checkpoint",
                status_code=503,
            )
        required = [
            root / "models" / "face_detection_yunet_2023mar.omlx",
            *(
                root / "weights" / f"{name}.npz"
                for name in (
                    "appearance_feature_extractor",
                    "motion_extractor",
                    "spade_generator",
                    "warping_module",
                    "stitching",
                    "stitching_eye",
                    "stitching_lip",
                )
            ),
        ]
        missing = [str(path.relative_to(root)) for path in required if not path.exists()]
        if missing:
            raise ModelWorkerError(
                f"The MLX LivePortrait checkpoint is incomplete: {', '.join(missing)}",
                code="invalid_checkpoint",
                status_code=503,
            )
        self._root = root
        return root

    def _load(self, model_id: str, precision: str):
        from .models import MLXYuNet  # noqa: PLC0415
        from .native_liveportrait import NativeMLXLivePortrait  # noqa: PLC0415

        root = self._ensure_checkpoint(model_id)
        if precision not in {"fp32", "bf16"}:
            raise UnsupportedControlError("precision must be fp32 or bf16")
        if self._detector is None:
            self._detector = MLXYuNet(
                root / "models" / "face_detection_yunet_2023mar.omlx"
            )
        if precision not in self._pipelines:
            self._pipelines[precision] = NativeMLXLivePortrait(
                root / "weights", dtype=precision
            )
        return self._detector, self._pipelines[precision]

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
    def _crop(detector, image, role: str):
        detections = detector.detect(image)
        if not detections:
            raise ValueError(f"{role} does not contain a detectable face")
        return align_face(image, max(detections, key=_area).landmarks, 256)

    @staticmethod
    def _parameters(payload: dict, operation: str) -> dict:
        parameters = payload.get("parameters", payload)
        if not isinstance(parameters, dict):
            raise ValueError("parameters must be an object")
        allowed = {
            "precision",
            "motion_mode",
            "motion_multiplier",
            "crop_only",
            "output_format",
        }
        if operation == "video_generation":
            allowed.add("audio_output_mode")
        # When parameters are not nested, leave envelope fields out of the
        # control check. They are interpreted by the Host/adapter separately.
        envelope = {"model", "inputs", "parameters"} if parameters is payload else set()
        unknown = sorted(set(parameters) - allowed - envelope)
        if unknown:
            raise UnsupportedControlError(
                f"unsupported controls: {', '.join(unknown)}"
            )
        precision = str(parameters.get("precision", "fp32"))
        expected_motion = "absolute" if operation == "image_edit" else "relative"
        motion_mode = str(parameters.get("motion_mode", expected_motion))
        if motion_mode != expected_motion:
            raise UnsupportedControlError(
                f"{operation} supports only motion_mode={expected_motion}"
            )
        multiplier = float(parameters.get("motion_multiplier", 1.0))
        if not 0.0 <= multiplier <= 3.0:
            raise ValueError("motion_multiplier must be between 0 and 3")
        output_format = str(
            parameters.get(
                "output_format", "png" if operation == "image_edit" else "mp4"
            )
        )
        expected_format = "png" if operation == "image_edit" else "mp4"
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
            "motion_mode": motion_mode,
            "motion_multiplier": multiplier,
            "crop_only": _boolean(parameters.get("crop_only"), "crop_only"),
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
            source_part = self._part(request, inputs, "reference_image", "source")
            driving_role = (
                "driving_image" if request.operation == "image_edit" else "reference_video"
            )
            driving_part = self._part(request, inputs, driving_role, "driving")
        except UnsupportedControlError as error:
            raise ModelWorkerError(
                str(error), code="unsupported_control", status_code=400
            ) from error
        except (OSError, TypeError, ValueError) as error:
            raise ModelWorkerError(
                str(error), code="invalid_request", status_code=400
            ) from error
        cancelled = None
        if request.operation == "video_generation":
            cancelled = threading.Event()
            with self._cancellations_lock:
                self._cancellations[request.request_id] = cancelled
        try:
            detector, pipeline = await asyncio.to_thread(
                self._load, model_id, parameters["precision"]
            )
        except ModelWorkerError:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)
            raise
        except UnsupportedControlError as error:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)
            raise ModelWorkerError(
                str(error), code="unsupported_control", status_code=400
            ) from error
        except (OSError, RuntimeError, ValueError) as error:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)
            raise ModelWorkerError(
                str(error), code="invalid_checkpoint", status_code=503
            ) from error
        if cancelled is not None and cancelled.is_set():
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)
            raise ModelWorkerError(
                "LivePortrait generation was cancelled",
                code="generation_cancelled",
                status_code=409,
            )

        if request.operation == "image_edit":
            return await self._animate_image(
                request, detector, pipeline, source_part.path, driving_part.path, parameters
            )
        return await self._animate_video(
            request,
            detector,
            pipeline,
            source_part.path,
            driving_part.path,
            parameters,
            cancelled,
        )

    async def _animate_image(
        self, request, detector, pipeline, source_path, driving_path, parameters
    ):
        try:
            def render():
                source = read_image_bgr(source_path)
                driving = read_image_bgr(driving_path)
                source_crop, source_matrix = self._crop(
                    detector, source, "source image"
                )
                driving_crop, _ = self._crop(detector, driving, "driving image")
                source_state = pipeline.prepare_source(source_crop)
                generated = pipeline.drive_prepared(
                    source_state,
                    pipeline.prepare_driving(driving_crop),
                    multiplier=parameters["motion_multiplier"],
                )
                output = (
                    generated
                    if parameters["crop_only"]
                    else paste_face(
                        source,
                        generated,
                        source_matrix * (generated.shape[1] / source_crop.shape[1]),
                        erosion_fraction=0.035,
                        blur_fraction=0.04,
                    )
                )
                path = request.output_root / "liveportrait.png"
                write_image_bgr(path, output)
                return path

            path = await asyncio.to_thread(render)
        except (OSError, RuntimeError, ValueError) as error:
            raise ModelWorkerError(
                str(error), code="generation_failed", status_code=422
            ) from error
        return ModelWorkerArtifact(
            path,
            media_type="image/png",
            filename=path.name,
            metadata=self._metadata(parameters, audio_applied="none"),
        )

    async def _animate_video(
        self,
        request,
        detector,
        pipeline,
        source_path,
        driving_path,
        parameters,
        cancelled,
    ):
        assert cancelled is not None
        loop = asyncio.get_running_loop()

        def report(current: int, total: int | None) -> None:
            if request.progress is None:
                return
            value = request.progress(
                {
                    "phase": "render",
                    "current": current,
                    "total": max(total or current, 1),
                }
            )
            if inspect.isawaitable(value):
                asyncio.run_coroutine_threadsafe(value, loop)

        def generate():
            source = read_image_bgr(source_path)
            source_crop, source_matrix = self._crop(detector, source, "source image")
            source_state = pipeline.prepare_source(source_crop)
            reader = VideoReader(driving_path)
            total = int(reader.stream.frames) if reader.stream.frames else None
            size = (
                (512, 512)
                if parameters["crop_only"]
                else (source.shape[1], source.shape[0])
            )
            silent = request.output_root / "rendering.mp4"
            output = request.output_root / "liveportrait.mp4"
            writer = VideoWriter(silent, reader.fps, size)
            tracker = TemporalFaceTracker(smoothing=0.5, max_missed=2)
            anchor = None
            last = (
                resize_bgr(source_crop, (512, 512), interpolation="cubic")
                if parameters["crop_only"]
                else source.copy()
            )
            frames = 0
            try:
                for frame in reader:
                    if cancelled.is_set():
                        raise ModelWorkerError(
                            "LivePortrait generation was cancelled",
                            code="generation_cancelled",
                            status_code=409,
                        )
                    tracks = tracker.update(detector.detect(frame))
                    visible = [item for item in tracks if item.missed == 0]
                    if visible:
                        driving_crop, _ = align_face(
                            frame, max(visible, key=_area).landmarks, 256
                        )
                        driving_state = pipeline.prepare_driving(driving_crop)
                        if anchor is None:
                            anchor = driving_state
                        generated = pipeline.drive_prepared(
                            source_state,
                            driving_state,
                            driving_anchor=anchor,
                            multiplier=parameters["motion_multiplier"],
                        )
                        last = (
                            generated
                            if parameters["crop_only"]
                            else paste_face(
                                source,
                                generated,
                                source_matrix
                                * (generated.shape[1] / source_crop.shape[1]),
                                erosion_fraction=0.035,
                                blur_fraction=0.04,
                            )
                        )
                    writer.write(last)
                    frames += 1
                    report(frames, total)
            finally:
                writer.close()
                reader.close()
            if frames == 0:
                raise ValueError("driving video contains no decodable frames")
            if parameters["audio_output_mode"] == "none":
                silent.replace(output)
                audio_applied = "none"
            else:
                copied = remux_source_audio(silent, driving_path, output)
                audio_applied = "preserve_driving_audio" if copied else "none"
                if (
                    parameters["audio_output_mode"] == "preserve_driving_audio"
                    and not copied
                ):
                    raise ValueError("driving video does not contain an audio stream")
            return output, frames, audio_applied

        try:
            output, frames, audio_applied = await asyncio.to_thread(generate)
        except ModelWorkerError:
            raise
        except (OSError, RuntimeError, ValueError) as error:
            raise ModelWorkerError(
                str(error), code="generation_failed", status_code=422
            ) from error
        finally:
            with self._cancellations_lock:
                self._cancellations.pop(request.request_id, None)
        metadata = self._metadata(parameters, audio_applied=audio_applied)
        metadata["frames"] = frames
        return ModelWorkerArtifact(
            output, media_type="video/mp4", filename=output.name, metadata=metadata
        )

    @staticmethod
    def _metadata(parameters: dict, *, audio_applied: str) -> dict:
        return {
            "mode": parameters["motion_mode"],
            "applied_controls": {
                "precision": {
                    "requested": parameters["precision"],
                    "applied": parameters["precision"],
                },
                "motion_multiplier": {
                    "requested": parameters["motion_multiplier"],
                    "applied": parameters["motion_multiplier"],
                },
                "crop_only": {
                    "requested": parameters["crop_only"],
                    "applied": parameters["crop_only"],
                },
                "audio_output_mode": {
                    "requested": parameters["audio_output_mode"],
                    "applied": audio_applied,
                },
            },
            "warnings": (
                ["Driving media did not contain an audio stream."]
                if parameters["audio_output_mode"] == "auto"
                and audio_applied == "none"
                else []
            ),
        }


def create_adapter(context):
    return MLXLivePortraitAdapter(context)
