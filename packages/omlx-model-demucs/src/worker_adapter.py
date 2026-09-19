"""AI2Apps Model Worker adapter for native MLX HTDemucs separation."""

from __future__ import annotations

import asyncio
import inspect
import json
import zipfile
from pathlib import Path

import mlx.core as mx
from mlx_demucs.backends import MlxDemucsBackend
from mlx_demucs.pipeline import SeparationConfig, separate_file

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

_PROFILES = {"music_4stem", "vocals_instrumental", "dialogue_background"}


class MLXDemucsAdapter:
    def __init__(self, context) -> None:
        self.context = context
        self._backends: dict[str, MlxDemucsBackend] = {}
        self._lock = asyncio.Lock()
        self._worker_cpu_stream = mx.new_thread_local_stream(mx.cpu)
        self._worker_gpu_stream = mx.new_thread_local_stream(mx.gpu)

    async def stop(self) -> None:
        self._backends.clear()
        # Lifecycle-only harness checks can run without an available Metal
        # device. Inference still fails closed when Metal is actually needed.
        try:
            mx.clear_cache()
        except RuntimeError as error:
            if "No Metal device available" not in str(error):
                raise

    def _backend(self, model_id: str) -> MlxDemucsBackend:
        backend = self._backends.get(model_id)
        if backend is not None:
            return backend
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                f"Required checkpoint is not installed: {model_id}",
                code="model_unavailable",
                status_code=503,
            )
        root = Path(checkpoint.path)
        weights = root / "htdemucs.safetensors"
        config = root / "htdemucs_config.json"
        if not weights.is_file() or not config.is_file():
            raise ModelWorkerError(
                "MLX HTDemucs checkpoint is incomplete",
                code="model_unavailable",
                status_code=503,
            )
        try:
            model_config = json.loads(config.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ModelWorkerError(
                "MLX HTDemucs checkpoint config is invalid",
                code="model_unavailable",
                status_code=503,
            ) from error
        kwargs = model_config.get("kwargs") or {}
        if (
            model_config.get("model_name") != "htdemucs"
            or kwargs.get("sources") != ["drums", "bass", "other", "vocals"]
            or kwargs.get("audio_channels") != 2
            or kwargs.get("samplerate") != 44_100
        ):
            raise ModelWorkerError(
                "Unsupported MLX HTDemucs checkpoint layout",
                code="model_unavailable",
                status_code=503,
            )
        backend = MlxDemucsBackend(weights)
        self._backends[model_id] = backend
        return backend

    async def invoke(self, request):
        if request.operation != "audio_process":
            raise ModelWorkerError(
                f"Unsupported operation: {request.operation}",
                code="unsupported_operation",
                status_code=400,
            )
        payload = dict(request.payload)
        if str(payload.get("task") or "source_separation") != "source_separation":
            raise ModelWorkerError(
                "task must be source_separation", code="invalid_request"
            )
        model_id = payload.get("model")
        if not isinstance(model_id, str) or not model_id:
            raise ModelWorkerError("model is required", code="invalid_request")
        profile = str(payload.get("profile") or "dialogue_background")
        if profile not in _PROFILES:
            raise ModelWorkerError(
                f"Unsupported separation profile: {profile}",
                code="unsupported_profile",
                status_code=400,
            )
        float32_wav = payload.get("float32_wav", False)
        if not isinstance(float32_wav, bool):
            raise ModelWorkerError("float32_wav must be boolean", code="invalid_request")
        try:
            source = request.part("file").path
        except (KeyError, ValueError) as error:
            raise ModelWorkerError(
                "file audio is required", code="invalid_request"
            ) from error
        stems_root = request.output_root / "stems"
        if request.progress is not None:
            value = request.progress({"phase": "loading", "current": 2, "total": 100})
            if inspect.isawaitable(value):
                await value
        async with self._lock:

            def separate():
                with (
                    mx.stream(self._worker_cpu_stream),
                    mx.stream(self._worker_gpu_stream),
                ):
                    backend = self._backend(model_id)
                    return separate_file(
                        source,
                        stems_root,
                        backend=backend,
                        config=SeparationConfig(
                            profile=profile, float32_wav=float32_wav
                        ),
                    )

            try:
                result = await asyncio.to_thread(separate)
            except ModelWorkerError:
                raise
            except (OSError, RuntimeError, ValueError) as error:
                raise ModelWorkerError(
                    f"Audio separation failed: {error}",
                    code="audio_processing_failed",
                    status_code=422,
                ) from error
        if request.progress is not None:
            value = request.progress({"phase": "packaging", "current": 95, "total": 100})
            if inspect.isawaitable(value):
                await value
        output = request.output_root / "demucs-stems.zip"
        with zipfile.ZipFile(output, "w", allowZip64=True) as archive:
            archive.write(stems_root / "separation.json", "separation.json")
            for stem in result.stems:
                path = stems_root / stem.path
                archive.write(path, path.name, compress_type=zipfile.ZIP_STORED)
        if request.progress is not None:
            value = request.progress({"phase": "completed", "current": 100, "total": 100})
            if inspect.isawaitable(value):
                await value
        return ModelWorkerArtifact(
            output,
            media_type="application/zip",
            filename=output.name,
            metadata={
                "schema": result.schema,
                "profile": profile,
                "stems": [stem.type for stem in result.stems],
            },
        )


def create_adapter(context):
    return MLXDemucsAdapter(context)
