"""FlashHead Lite/Pro Model Worker. Runtime and weights are supplied by Host."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
from contextlib import suppress
from typing import Any

from flashhead_mlx.checkpoint import validate_checkpoint

from ai2apps.model_worker import (
    ModelWorkerArtifact,
    ModelWorkerError,
    ModelWorkerRequest,
)

SERVICE_ID = "ai2apps.model.flashhead-mlx"
MODEL_IDS = {f"{SERVICE_ID}/{variant}": variant for variant in ("lite", "pro")}


class GenerationCancelledError(Exception):
    pass


class FlashHeadAdapter:
    def __init__(self, context: Any, *, pipeline_factory=None):
        self.context = context
        self._factory = pipeline_factory
        self._pipeline = None
        self._loaded = None
        self._lock = asyncio.Lock()
        self._tokens = {}
        self._tokens_lock = threading.Lock()
        self._closing = False

    async def start(self):
        # Missing weights must not turn service health into an automatic download.
        self._closing = False

    def cancel(self, request_id):
        with self._tokens_lock:
            token = self._tokens.get(request_id)
            if token is not None:
                token.set()

    async def stop(self):
        self._closing = True
        with self._tokens_lock:
            for token in self._tokens.values():
                token.set()
        async with self._lock:
            await asyncio.to_thread(self._unload)

    def _unload(self):
        self._pipeline = None
        self._loaded = None
        if self._factory is None:
            import mlx.core as mx

            mx.clear_cache()

    def _model(self, payload):
        name = payload.get("model")
        if not isinstance(name, str):
            raise ModelWorkerError("model must be a string", code="invalid_request")
        for model in self.context.models:
            if (
                name in {model["id"], model.get("upstream_id")}
                and model["id"] in MODEL_IDS
            ):
                return model["id"], MODEL_IDS[model["id"]]
        raise ModelWorkerError(
            "Select an installed FlashHead Lite or Pro model",
            code="model_not_found",
            status_code=404,
        )

    @staticmethod
    def _inputs(request):
        import soundfile as sf
        from PIL import Image

        # Multipart transport represents all non-file fields as strings.
        payload = dict(request.payload)
        for key in ("inputs", "parameters", "reference_parts"):
            if isinstance(payload.get(key), str):
                payload[key] = json.loads(payload[key])
        inputs = payload.get("inputs", {})
        parameters = payload.get("parameters", payload)
        if not isinstance(inputs, dict) or not isinstance(parameters, dict):
            raise ValueError("inputs and parameters must be objects")
        for role in inputs:
            if role not in {"reference_image", "driving_audio"}:
                raise ValueError("Unsupported input role: " + str(role))
        parameters = dict(parameters)
        for key in ("width", "height", "fps", "framespersecond", "seed", "steps"):
            value = parameters.get(key)
            if isinstance(value, str) and value.isascii() and value.isdecimal():
                parameters[key] = int(value)
        references = payload.get("reference_parts", [])
        if references:
            if (
                not isinstance(references, list)
                or len(references) != 1
                or not isinstance(references[0], dict)
                or references[0].get("kind") != "image"
                or not isinstance(references[0].get("part_name"), str)
            ):
                raise ValueError("FlashHead expects exactly one reference image")
            if "reference_image" in inputs:
                raise ValueError("Ambiguous reference image input")
            inputs = {
                **inputs,
                "reference_image": {"part_name": references[0]["part_name"]},
            }
        parts = []
        for role, fallback in [
            ("reference_image", "image"),
            ("driving_audio", "audio"),
        ]:
            item = inputs.get(role, {"part_name": fallback})
            if not isinstance(item, dict) or not isinstance(item.get("part_name"), str):
                raise ValueError("Input must reference a request part")
            parts.append(request.part(item["part_name"]))
        image, audio = parts
        with Image.open(image.path) as picture:
            if (
                picture.format not in {"PNG", "JPEG", "WEBP"}
                or picture.width * picture.height > 40_000_000
            ):
                raise ValueError("Expected PNG/JPEG/WebP image up to 40 million pixels")
            picture.verify()
        info = sf.info(str(audio.path))
        if (
            info.format not in {"WAV", "WAVEX"}
            or info.samplerate != 16000
            or info.channels != 1
        ):
            raise ValueError("Expected mono 16 kHz WAV driving audio")
        if not 1 <= info.frames <= 16000 * 60:
            raise ValueError("Supported audio duration is one sample to 60 seconds")
        for key, expected in [
            ("width", 512),
            ("height", 512),
            ("fps", 25),
            ("framespersecond", 25),
        ]:
            value = parameters.get(key, expected)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value != expected
            ):
                raise ValueError("FlashHead Package supports 512x512 at 25 FPS")
        for key, expected in [
            ("resolution", "512x512"),
            ("ratio", "1:1"),
            ("preset", "standard"),
            ("output_format", "mp4"),
            ("audio_output_mode", "preserve_driving_audio"),
        ]:
            if parameters.get(key, expected) != expected:
                raise ValueError("Unsupported " + key)
        if parameters.get("prompt") or parameters.get("negative_prompt"):
            raise ValueError("FlashHead does not accept text conditioning")
        seed = parameters.get("seed", 0)
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
            raise ValueError("seed must be a uint32 integer")
        if parameters.get("steps", 4) != 4 or isinstance(parameters.get("steps"), bool):
            raise ValueError("The standard preset uses four steps")
        return image.path, audio.path, seed, (info.frames + 639) // 640

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "video_generation":
            raise ModelWorkerError(
                "Unsupported operation", code="operation_not_supported"
            )
        if request.output_root is None:
            raise ModelWorkerError(
                "Missing controlled output root",
                code="runtime_protocol_error",
                status_code=500,
            )
        if self._closing:
            raise ModelWorkerError(
                "Worker is stopping", code="service_stopping", status_code=503
            )
        model_id, variant = self._model(request.payload)
        try:
            image, audio, seed, frames = self._inputs(request)
            if variant == "pro" and frames > 250:
                raise ValueError(
                    "FlashHead Pro Package supports up to 10 seconds in this release"
                )
        except (ValueError, TypeError, OSError, RuntimeError) as error:
            raise ModelWorkerError(str(error), code="invalid_request") from error
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "Install the selected FlashHead checkpoint first",
                code="model_unavailable",
                status_code=503,
            )
        output = request.output_root / (
            "flashhead-"
            + hashlib.sha256(request.request_id.encode()).hexdigest()[:24]
            + ".mp4"
        )
        token = threading.Event()
        with self._tokens_lock:
            if request.request_id in self._tokens:
                raise ModelWorkerError(
                    "Duplicate active request ID",
                    code="request_conflict",
                    status_code=409,
                )
            self._tokens[request.request_id] = token
        loop = asyncio.get_running_loop()

        def check():
            if token.is_set() or self._closing:
                raise GenerationCancelledError()

        def progress(current, total):
            check()
            if request.progress is None:
                return

            async def emit():
                value = request.progress(
                    {
                        "phase": "render",
                        "current": current,
                        "total": total,
                        "percent": current / total * 100,
                    }
                )
                if inspect.isawaitable(value):
                    await value

            future = asyncio.run_coroutine_threadsafe(emit(), loop)
            future.result(timeout=30)

        def generate():
            check()
            try:
                root = validate_checkpoint(checkpoint.path, variant)
            except (ValueError, OSError, json.JSONDecodeError) as error:
                raise ModelWorkerError(
                    "Invalid FlashHead checkpoint: " + str(error),
                    code="invalid_checkpoint",
                    status_code=503,
                ) from error
            identity = (model_id, str(root), checkpoint.revision)
            if self._loaded != identity:
                self._unload()
                check()
                factory = self._factory
                if factory is None:
                    from flashhead_mlx.pipeline import FlashHeadPipeline

                    factory = FlashHeadPipeline
                pipeline = factory(root, root / "wav2vec2", variant=variant)
                check()
                self._pipeline, self._loaded = pipeline, identity
            self._pipeline.generate(
                image,
                audio,
                output,
                size=512,
                seed=seed,
                steps=4,
                cancel_check=check,
                progress=progress,
            )
            check()

        try:
            async with self._lock:
                check()
                work = asyncio.create_task(asyncio.to_thread(generate))
                try:
                    await asyncio.shield(work)
                except asyncio.CancelledError:
                    token.set()
                    # Do not release the model lock while its native thread is running.
                    while not work.done():
                        try:
                            await asyncio.shield(work)
                        except asyncio.CancelledError:
                            continue
                        except Exception:
                            break
                    with suppress(Exception, asyncio.CancelledError):
                        work.result()
                    raise
            return ModelWorkerArtifact(
                output,
                "video/mp4",
                output.name,
                metadata={
                    "model": model_id,
                    "variant": variant,
                    "width": 512,
                    "height": 512,
                    "framespersecond": 25,
                    "frame_count": frames,
                    "audio_output_mode": "preserve_driving_audio",
                    "preset": "standard",
                    "seed": seed,
                },
            )
        except GenerationCancelledError as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(
                "FlashHead generation cancelled",
                code="generation_cancelled",
                status_code=409,
            ) from error
        except asyncio.CancelledError:
            output.unlink(missing_ok=True)
            raise
        except ModelWorkerError:
            output.unlink(missing_ok=True)
            raise
        except Exception as error:
            output.unlink(missing_ok=True)
            raise ModelWorkerError(
                "FlashHead generation failed", code="generation_failed", status_code=500
            ) from error
        finally:
            with self._tokens_lock:
                self._tokens.pop(request.request_id, None)


def create_adapter(context):
    return FlashHeadAdapter(context)
