"""AI2Apps Model Worker adapter for native EchoMimicV3 MLX."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from echomimic_mlx import (
    AvatarPipeline,
    CancellationToken,
    GenerationCancelled,
    GenerationRequest,
    PipelineModelPaths,
    select_memory_profile,
)

from ai2apps.model_worker import (
    ModelWorkerArtifact,
    ModelWorkerError,
    ModelWorkerRequest,
)

MODEL_ID = "ai2apps.model.echomimic-v3-mlx/default"
UPSTREAM_ID = "ai2apps/EchoMimicV3-MLX"
CHECKPOINT_SCHEMA = "ai2apps.echomimic-mlx-checkpoint/v1"


class EchoMimicAdapter:
    def __init__(self, context: Any, *, pipeline_factory: Callable[..., Any] | None = None) -> None:
        self.context = context
        self._pipeline_factory = pipeline_factory or AvatarPipeline.from_pretrained
        self._checkpoint: Path | None = None
        self._pipeline: Any | None = None
        self._profile = None
        self._tokens: dict[str, CancellationToken] = {}
        self._tokens_lock = threading.Lock()

    async def start(self) -> None:
        # Keep the Service healthy while the pinned checkpoint is being
        # downloaded.  The Host restarts the Worker after model installation,
        # and requests made before then receive a structured 503 below.
        return None

    def _ensure_checkpoint(self) -> None:
        if self._checkpoint is not None:
            return
        checkpoint = self.context.checkpoint_for(MODEL_ID)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned EchoMimicV3 MLX checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = checkpoint.path.resolve()
        manifest_path = root / "ai2apps-checkpoint.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelWorkerError(
                "EchoMimic checkpoint manifest is missing or invalid",
                code="invalid_checkpoint",
                status_code=503,
            ) from exc
        if manifest.get("schema") != CHECKPOINT_SCHEMA:
            raise ModelWorkerError(
                "EchoMimic checkpoint layout is unsupported",
                code="invalid_checkpoint",
                status_code=503,
            )
        try:
            PipelineModelPaths.from_directory(root).validate()
            self._profile = select_memory_profile()
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise ModelWorkerError(
                str(exc), code="invalid_checkpoint", status_code=503
            ) from exc
        self._checkpoint = root

    async def stop(self) -> None:
        with self._tokens_lock:
            for token in self._tokens.values():
                token.cancel()
            self._tokens.clear()
        if self._pipeline is not None:
            self._pipeline.clear_condition_cache()
        self._pipeline = None
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (ImportError, RuntimeError):
            pass

    def cancel(self, request_id: str) -> None:
        with self._tokens_lock:
            token = self._tokens.get(request_id)
        if token is not None:
            token.cancel()

    def _load_pipeline(self) -> Any:
        if self._pipeline is None:
            assert self._checkpoint is not None and self._profile is not None
            self._pipeline = self._pipeline_factory(
                self._checkpoint, cache_conditions=self._profile.cache_conditions
            )
        return self._pipeline

    @staticmethod
    def _inputs(request: ModelWorkerRequest) -> tuple[Path, Path, str, dict[str, Any]]:
        payload = dict(request.payload)
        inputs = payload.get("inputs", {})
        parameters = payload.get("parameters", payload)
        if not isinstance(inputs, dict) or not isinstance(parameters, dict):
            raise ValueError("inputs and parameters must be objects")
        image_name = inputs.get("reference_image", {}).get("part_name", "image") \
            if isinstance(inputs.get("reference_image", {}), dict) else "image"
        audio_name = inputs.get("driving_audio", {}).get("part_name", "audio") \
            if isinstance(inputs.get("driving_audio", {}), dict) else "audio"
        image = request.part(str(image_name))
        audio = request.part(str(audio_name))
        if image.media_type not in {"image/png", "image/jpeg", "image/webp", "application/octet-stream"}:
            raise ValueError("reference_image must be PNG, JPEG, or WebP")
        if audio.media_type not in {"audio/wav", "audio/x-wav", "application/octet-stream"}:
            raise ValueError("driving_audio must be a 16 kHz WAV")
        prompt = str(inputs.get("prompt", payload.get("prompt", "A person is speaking."))).strip()
        return image.path, audio.path, prompt or "A person is speaking.", parameters

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "video_generation":
            raise ModelWorkerError(
                f"Unsupported operation: {request.operation}",
                code="operation_not_supported",
                status_code=400,
            )
        if request.output_root is None:
            raise ModelWorkerError(
                "The Runtime did not provide a controlled output root",
                code="runtime_protocol_error",
                status_code=500,
            )
        self._ensure_checkpoint()
        try:
            image, audio, prompt, parameters = self._inputs(request)
            width = int(parameters.get("width", 512))
            height = int(parameters.get("height", 512))
            fps = int(parameters.get("fps", parameters.get("framespersecond", 25)))
            seed = int(parameters.get("seed", 43))
            preset = str(parameters.get("preset", "exact"))
            long_value = parameters.get("long", False)
            if isinstance(long_value, str) and long_value.lower() in {"true", "false"}:
                long_video = long_value.lower() == "true"
            else:
                long_video = long_value
            if (width, height) not in {(512, 512), (768, 768)} or fps != 25:
                raise ValueError("EchoMimic supports only 512/768 square video at 25 FPS")
            if preset not in {"exact", "fast"} or not isinstance(long_video, bool):
                raise ValueError("preset or long parameter is invalid")
            if long_video and preset == "fast":
                raise ValueError("long video currently requires exact preset")
            generation = GenerationRequest(
                str(image), str(audio), prompt=prompt, width=width, height=height,
                fps=fps, seed=seed,
                teacache_threshold=0.15 if preset == "fast" else 0.0,
                teacache_skip_start_steps=2 if preset == "fast" else 5,
                use_fused_norms=preset == "fast",
            )
            assert self._profile is not None
            self._profile.validate(generation)
        except (OSError, TypeError, ValueError) as exc:
            raise ModelWorkerError(
                str(exc), code="invalid_request", status_code=400
            ) from exc

        token = CancellationToken()
        with self._tokens_lock:
            self._tokens[request.request_id] = token
        loop = asyncio.get_running_loop()

        def progress(phase: str, current: int, total: int) -> None:
            if request.progress is None:
                return

            async def emit() -> None:
                result = request.progress(
                    {"phase": phase, "current": current, "total": total}
                )
                if inspect.isawaitable(result):
                    await result

            asyncio.run_coroutine_threadsafe(emit(), loop)

        output = request.output_root / f"echomimic-{request.request_id}.mp4"
        checkpoint = (
            self.context.data_root / "checkpoints"
            / hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
            / "denoise.safetensors"
        )
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        pipeline = self._load_pipeline()

        def generate() -> None:
            if long_video:
                pipeline.generate_long_to_file(
                    generation, output, progress=progress, cancellation=token
                )
            else:
                pipeline.generate_to_file(
                    generation,
                    output,
                    progress=progress,
                    cancellation=token,
                    checkpoint_path=None if preset == "fast" else checkpoint,
                )

        try:
            await asyncio.to_thread(generate)
        except GenerationCancelled as exc:
            raise ModelWorkerError(
                "EchoMimic generation was cancelled",
                code="generation_cancelled",
                status_code=409,
            ) from exc
        except Exception as exc:
            raise ModelWorkerError(
                f"EchoMimic generation failed: {exc}",
                code="generation_failed",
                status_code=500,
            ) from exc
        finally:
            with self._tokens_lock:
                self._tokens.pop(request.request_id, None)
        return ModelWorkerArtifact(
            output,
            "video/mp4",
            output.name,
            metadata={
                "width": width,
                "height": height,
                "framespersecond": fps,
                "audio_output_mode": "preserve_driving_audio",
                "preset": preset,
            },
        )


def create_adapter(context: Any) -> EchoMimicAdapter:
    return EchoMimicAdapter(context)
