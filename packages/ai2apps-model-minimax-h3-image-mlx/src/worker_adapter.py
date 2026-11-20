"""AI2Apps Model Worker adapter for MiniMax H3-Image using the shared MLX Runtime."""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import threading
from collections.abc import Mapping
from typing import Any

from PIL import Image, UnidentifiedImageError

from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest


UPSTREAM = "MiniMaxAI/MiniMax-H3-Image"
MODEL = "ai2apps.model.minimax-h3-image/default"
ENCODER = "ai2apps.model.minimax-h3/fl2va-4bit"
FORMATS = {"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}
DIT_IDLE_SECONDS = 60


def _references(payload: Mapping[str, Any], edit: bool) -> list[Image.Image]:
    values = payload.get("imageDataUrls", payload.get("image_data_urls", []))
    if not isinstance(values, list) or (not 1 <= len(values) <= 16 if edit else len(values) != 0):
        raise ValueError("Image editing requires 1 to 16 ordered reference images; generation accepts none.")
    images = []
    total_bytes = 0
    for value in values:
        if not isinstance(value, str) or len(value) > 35 * 1024 * 1024:
            raise ValueError("Reference image is missing or too large.")
        prefix, _, encoded = value.partition(",")
        if prefix not in {f"data:image/{fmt};base64" for fmt in FORMATS}:
            raise ValueError("Use a PNG, JPEG, or WebP data URL for the reference image.")
        try:
            content = base64.b64decode(encoded, validate=True)
            total_bytes += len(content)
            if total_bytes > 64 * 1024 * 1024:
                raise ValueError("Reference images exceed the 64 MiB Worker input limit.")
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in FORMATS.values() or min(source.size) < 32 or max(source.size) > 8192:
                    raise ValueError("Reference image format or dimensions are unsupported.")
                if max(source.size) > 4 * min(source.size):
                    raise ValueError("Reference image aspect ratio must be between 1:4 and 4:1.")
                images.append(source.copy())
        except (binascii.Error, OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
            raise ValueError("Reference image could not be decoded.") from exc
    return images


class ImageAdapter:
    def __init__(self, context: Any):
        self.context = context
        self.lock = asyncio.Lock()
        self.reference_cache = None
        self._denoiser_cache = None
        self._denoiser_key = None
        self._denoiser_expiry: asyncio.TimerHandle | None = None

    def _cancel_denoiser_expiry(self) -> None:
        if self._denoiser_expiry is not None:
            self._denoiser_expiry.cancel()
            self._denoiser_expiry = None

    def _release_denoiser(self) -> None:
        self._cancel_denoiser_expiry()
        self._denoiser_key = None
        self._denoiser_cache = None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        async with self.lock:
            self.reference_cache = None
            self._release_denoiser()

    async def invoke(self, request: ModelWorkerRequest) -> dict[str, Any]:
        if request.operation not in {"image_generation", "image_edit"}:
            raise ModelWorkerError("Unsupported operation", code="operation_not_supported")
        edit = request.operation == "image_edit"
        payload = request.payload
        if payload.get("model") not in (None, "", MODEL, UPSTREAM):
            raise ModelWorkerError("Unsupported H3-Image model", code="model_not_found", status_code=404)
        checkpoint = self.context.checkpoint_for(MODEL)
        encoder = self.context.checkpoint_for(ENCODER)
        if checkpoint is None or checkpoint.path is None or encoder is None or encoder.path is None:
            raise ModelWorkerError("H3-Image or its shared H3 text encoder is unavailable",
                                   code="model_unavailable", status_code=503)
        try:
            prompt = payload.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8192:
                raise ValueError("Prompt must contain between 1 and 8192 characters.")
            width, height = map(int, str(payload.get("size") or "2048x2048").lower().split("x"))
            if not all(512 <= side <= 2048 and side % 32 == 0 for side in (width, height)):
                raise ValueError("Output dimensions must be 512–2048 and divisible by 32.")
            if max(width, height) > 3 * min(width, height):
                raise ValueError("Output aspect ratio must be between 1:3 and 3:1.")
            steps = int(payload.get("num_inference_steps", payload.get("steps", 6)))
            guidance = float(payload.get("guidance", payload.get("guidance_scale", 1)))
            if steps != 6 or guidance != 1 or payload.get("negative_prompt"):
                raise ValueError("H3-Image uses six steps, guidance 1, and a single prompt.")
            seed = int(payload.get("seed", 42))
            if not 0 <= seed < 2**32:
                raise ValueError("Seed must be a non-negative 32-bit integer.")
            if str(payload.get("quantization") or "bf16").lower() != "bf16":
                raise ValueError("This H3-Image checkpoint uses BF16 transformer weights.")
            output_format = str(payload.get("outputFormat", payload.get("output_format", "png"))).lower()
            if output_format not in FORMATS:
                raise ValueError("Output format must be PNG, JPEG, or WebP.")
            keep_dit_resident = payload.get("keep_dit_resident", False)
            if type(keep_dit_resident) is not bool:
                raise ValueError("keep_dit_resident must be a boolean.")
            images = _references(payload, edit)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ModelWorkerError(str(exc), code="invalid_request") from exc

        stop = threading.Event()

        def check_cancelled(*_args) -> None:
            if stop.is_set():
                raise InterruptedError("H3-Image cancelled")

        def run() -> bytes:
            from minimax_h3_mlx.image_pipeline import ImageReferenceCache, generate_image

            if edit and self.reference_cache is None:
                self.reference_cache = ImageReferenceCache()
            image = generate_image(
                checkpoint.path, encoder.path, prompt, width=width, height=height,
                seed=seed, references=images, reference_cache=self.reference_cache,
                denoiser_cache=self._denoiser_cache,
                progress=check_cancelled, on_step=check_cancelled,
            )
            output = io.BytesIO()
            image.save(output, format=FORMATS[output_format])
            return output.getvalue()

        async with self.lock:
            if request.progress is not None:
                await request.progress({"phase": "generate", "current": 0, "total": 1})
            if keep_dit_resident:
                from minimax_h3_mlx.image_pipeline import ImageDenoiserCache

                root = checkpoint.path.resolve()
                key = (root, checkpoint.revision)
                self._cancel_denoiser_expiry()
                if self._denoiser_key != key:
                    self._release_denoiser()
                    self._denoiser_cache = ImageDenoiserCache(root)
                    self._denoiser_key = key
            else:
                self._release_denoiser()
            job = asyncio.create_task(asyncio.to_thread(run))
            try:
                result = await asyncio.shield(job)
            except asyncio.CancelledError:
                stop.set()
                try:
                    await job
                except Exception:
                    pass
                self._release_denoiser()
                raise
            except Exception as exc:
                self._release_denoiser()
                raise ModelWorkerError(f"H3-Image inference failed: {exc}",
                                       code="generation_failed", status_code=500) from exc
            if self._denoiser_cache is not None:
                self._denoiser_expiry = asyncio.get_running_loop().call_later(
                    DIT_IDLE_SECONDS, self._release_denoiser,
                )
            if request.progress is not None:
                await request.progress({"phase": "complete", "current": 1, "total": 1})

        encoded = base64.b64encode(result).decode("ascii")
        return {
            "created": 0,
            "data": [{"b64_json": encoded}],
            "image": {
                "dataUrl": f"data:image/{output_format};base64,{encoded}",
                "size": f"{width}x{height}",
                "quality": payload.get("quality", "auto"),
                "format": output_format,
            },
            "model": UPSTREAM,
            "seed": seed,
            "quantization": "bf16",
        }


def create_adapter(context: Any) -> ImageAdapter:
    return ImageAdapter(context)
