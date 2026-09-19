"""Isolated AI2Apps Model Worker adapter for native MLX Seed-VC v2."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from mlx_seed_vc_v2 import SeedVCV2
from scipy.signal import resample_poly

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError


def _number(payload: dict, name: str, default, cast):
    value = payload.get(name)
    if value in {None, ""}:
        return default
    try:
        return cast(value)
    except (TypeError, ValueError) as error:
        raise ModelWorkerError(f"{name} is invalid", code="invalid_request") from error


def _load_audio(path: Path) -> np.ndarray:
    values, rate = sf.read(path, dtype="float32", always_2d=False)
    if values.ndim == 2:
        values = values.mean(axis=1)
    if rate != 22_050:
        divisor = np.gcd(rate, 22_050)
        values = resample_poly(values, 22_050 // divisor, rate // divisor)
    return values.astype(np.float32)


class MLXSeedVCV2Adapter:
    def __init__(self, context) -> None:
        self.context = context
        self._models: dict[str, SeedVCV2] = {}
        self._lock = asyncio.Lock()
        self._worker_cpu_stream = mx.new_thread_local_stream(mx.cpu)
        self._worker_gpu_stream = mx.new_thread_local_stream(mx.gpu)

    async def stop(self) -> None:
        self._models.clear()
        mx.clear_cache()

    def _load_model(self, model_id: str) -> SeedVCV2:
        loaded = self._models.get(model_id)
        if loaded is not None:
            return loaded
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                f"Required checkpoint is not installed: {model_id}",
                code="model_unavailable",
                status_code=503,
            )
        checkpoint_root = Path(checkpoint.path)
        try:
            manifest = json.loads(
                (checkpoint_root / "ai2apps-checkpoint.json").read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, json.JSONDecodeError) as error:
            raise ModelWorkerError(
                "Invalid MLX Seed-VC v2 checkpoint manifest",
                code="model_unavailable",
                status_code=503,
            ) from error
        if manifest.get("schema") != "ai2apps.mlx-seed-vc-v2-composite/v1":
            raise ModelWorkerError(
                "Unsupported MLX Seed-VC v2 checkpoint layout",
                code="model_unavailable",
                status_code=503,
            )
        loaded = SeedVCV2(checkpoint_root)
        self._models[model_id] = loaded
        return loaded

    async def invoke(self, request):
        if request.operation != "audio_process":
            raise ModelWorkerError(f"Unsupported operation: {request.operation}")
        payload = dict(request.payload)
        if str(payload.get("task") or "voice_conversion") != "voice_conversion":
            raise ModelWorkerError(
                "task must be voice_conversion", code="invalid_request"
            )
        model_id = payload.get("model")
        if not isinstance(model_id, str) or not model_id:
            raise ModelWorkerError("model is required", code="invalid_request")
        mode = str(payload.get("mode") or payload.get("profile") or "timbre")
        if mode not in {"timbre", "voice"}:
            raise ModelWorkerError(
                "mode must be timbre or voice", code="invalid_request"
            )
        # The 30-step path matched the pinned Torch reference in the release
        # comparison.  Ten steps remains available as the explicit fast tier.
        steps = _number(payload, "diffusion_steps", 30, int)
        if not 1 <= steps <= 100:
            raise ModelWorkerError(
                "diffusion_steps must be between 1 and 100", code="invalid_request"
            )
        intelligibility = _number(payload, "guidance_intelligibility", 0.5, float)
        similarity = _number(payload, "guidance_similarity", 0.5, float)
        if not 0 <= intelligibility <= 5 or not 0 <= similarity <= 5:
            raise ModelWorkerError(
                "guidance values must be between zero and five",
                code="invalid_request",
            )
        length_adjust = _number(payload, "length_adjust", 1.0, float)
        if not 0.5 <= length_adjust <= 2.0:
            raise ModelWorkerError(
                "length_adjust must be between 0.5 and 2.0",
                code="invalid_request",
            )
        source = _load_audio(request.part("file").path)
        try:
            reference = _load_audio(request.part("reference").path)
        except (KeyError, ValueError) as error:
            raise ModelWorkerError(
                "reference audio is required for Seed-VC v2", code="invalid_request"
            ) from error
        async with self._lock:

            def convert():
                with (
                    mx.stream(self._worker_cpu_stream),
                    mx.stream(self._worker_gpu_stream),
                ):
                    model = self._load_model(model_id)
                    return model.convert(
                        source,
                        reference,
                        mode=mode,
                        diffusion_steps=steps,
                        guidance=(intelligibility, similarity),
                        length_adjust=length_adjust,
                        seed=_number(payload, "seed", 0, int),
                    )

            output = await asyncio.to_thread(
                convert,
            )
        path = request.output_root / "voice-converted.wav"
        sf.write(path, output, 22_050, subtype="PCM_16")
        return ModelWorkerArtifact(path, media_type="audio/wav", filename=path.name)


def create_adapter(context):
    return MLXSeedVCV2Adapter(context)
