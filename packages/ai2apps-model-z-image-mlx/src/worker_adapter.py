"""AI2Apps Model Worker adapter for optimized Z-Image MLX inference."""

from __future__ import annotations

import asyncio
import base64
import binascii
import fcntl
import hashlib
import io
import json
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PIL import Image

from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest

UPSTREAM_ID = "Tongyi-MAI/Z-Image-Turbo"
PACKAGE_MODEL_ID = "ai2apps.model.z-image-mlx/turbo"
MODEL_IDS = {UPSTREAM_ID, PACKAGE_MODEL_ID}
_DERIVED_FORMAT = "ai2apps.z-image-mlx-quantized/v1"
_LOG = logging.getLogger(__name__)
_DATA_URL = re.compile(
    r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)",
    re.IGNORECASE,
)


def _checkpoint_quantization(root: Path) -> int | None:
    index = root / "transformer" / "model.safetensors.index.json"
    try:
        value = (
            json.loads(index.read_text(encoding="utf-8"))
            .get("metadata", {})
            .get("quantization_level")
        )
        return int(value) if value is not None else None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _derived_checkpoint_complete(root: Path, bits: int) -> bool:
    try:
        receipt = json.loads(
            (root / ".ai2apps-derived.json").read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False
    required = (
        root / "transformer" / "model.safetensors.index.json",
        root / "text_encoder" / "model.safetensors.index.json",
        root / "vae" / "model.safetensors.index.json",
        root / "tokenizer" / "tokenizer.json",
    )
    return (
        receipt.get("format") == _DERIVED_FORMAT
        and receipt.get("quantization_bits") == bits
        and receipt.get("quantization_group_size") == 64
        and all(path.is_file() for path in required)
        and _checkpoint_quantization(root) == bits
    )


def _derived_cache_key(checkpoint: Path, revision: str, bits: int) -> str:
    identity = (
        f"{checkpoint.resolve()}\0{revision}\0turbo\0q{bits}\0group64\0mflux-0.19.0\0v1"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class ZImageAdapter:
    def __init__(
        self,
        context: Any,
        *,
        pipeline_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.context = context
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any | None = None
        self._pipeline_key: tuple[str, str, int | None] | None = None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self._pipeline = None
        self._pipeline_key = None
        try:
            import mlx.core as mx

            mx.clear_cache()
        except (ImportError, RuntimeError):
            pass

    @staticmethod
    def _model(payload: dict[str, Any]) -> str:
        model = str(payload.get("model") or "")
        if model not in MODEL_IDS:
            raise ModelWorkerError(
                "Unsupported Z-Image model",
                code="model_not_found",
                status_code=404,
            )
        return PACKAGE_MODEL_ID

    def _checkpoint(self, package_id: str) -> tuple[Path, str]:
        checkpoint = self.context.checkpoint_for(package_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned Z-Image checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = checkpoint.path.resolve()
        required = (
            root / "transformer",
            root / "text_encoder",
            root / "vae",
            root / "tokenizer",
        )
        if not all(path.exists() for path in required):
            raise ModelWorkerError(
                "Z-Image checkpoint is incomplete",
                code="invalid_checkpoint",
                status_code=503,
            )
        return root, str(getattr(checkpoint, "revision", "unknown"))

    def _cache_target(self, checkpoint: Path, revision: str, bits: int) -> Path:
        key = _derived_cache_key(checkpoint, revision, bits)
        return (
            Path(self.context.data_root)
            / "derived-models"
            / "z-image"
            / f"turbo-q{bits}-g64-{key}"
        )

    @staticmethod
    def _required_cache_bytes(checkpoint: Path, bits: int) -> int:
        source_bytes = sum(
            path.stat().st_size for path in checkpoint.rglob("*.safetensors")
        )
        return max(2 << 30, int(source_bytes * (bits / 16) * 1.2))

    def _materialize_quantized_checkpoint(
        self,
        *,
        pipeline: Any,
        source: Path,
        revision: str,
        bits: int,
    ) -> Path | None:
        target = self._cache_target(source, revision, bits)
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_suffix(".lock")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _derived_checkpoint_complete(target, bits):
                return target
            required = self._required_cache_bytes(source, bits)
            if shutil.disk_usage(target.parent).free < required:
                _LOG.warning(
                    "Skipping Z-Image Q%s cache: need %s free bytes",
                    bits,
                    required,
                )
                return None
            staging = Path(
                tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent)
            )
            try:
                pipeline.save_model(str(staging))
                receipt = {
                    "format": _DERIVED_FORMAT,
                    "source": str(source),
                    "source_revision": revision,
                    "variant": "turbo",
                    "quantization_bits": bits,
                    "quantization_group_size": 64,
                    "mflux_version": "0.19.0",
                }
                (staging / ".ai2apps-derived.json").write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if not _derived_checkpoint_complete(staging, bits):
                    raise RuntimeError(
                        "mflux produced an incomplete Z-Image checkpoint"
                    )
                if target.exists():
                    stale = target.with_name(f".{target.name}.stale-{os.getpid()}")
                    os.replace(target, stale)
                    shutil.rmtree(stale, ignore_errors=True)
                os.replace(staging, target)
                return target
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                _LOG.warning("Z-Image derived checkpoint creation failed: %s", exc)
                return None
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)

    def _load_pipeline(
        self,
        checkpoint: Path,
        *,
        revision: str,
        bits: int | None,
    ) -> Any:
        key = (str(checkpoint), revision, bits)
        if self._pipeline is not None and self._pipeline_key == key:
            return self._pipeline
        self._pipeline = None
        try:
            if self._pipeline_factory is not None:
                pipeline = self._pipeline_factory(checkpoint=checkpoint, bits=bits)
            else:
                import mlx.core as mx
                from mflux.models.common.config.model_config import ModelConfig
                from mflux.models.z_image.weights.z_image_weight_definition import (
                    ZImageWeightDefinition,
                )
                from optimized_pipeline import OptimizedZImage

                mx.clear_cache()
                ZImageWeightDefinition.quantization_group_size = 64
                load_path = checkpoint
                if bits is not None:
                    cached = self._cache_target(checkpoint, revision, bits)
                    if _derived_checkpoint_complete(cached, bits):
                        load_path = cached
                pipeline = OptimizedZImage(
                    model_config=ModelConfig.z_image_turbo(),
                    model_path=str(load_path),
                    quantize=bits,
                )
                source_quantization = _checkpoint_quantization(checkpoint)
                if (
                    bits is not None
                    and load_path == checkpoint
                    and source_quantization != bits
                ):
                    cached = self._materialize_quantized_checkpoint(
                        pipeline=pipeline,
                        source=checkpoint,
                        revision=revision,
                        bits=bits,
                    )
                    if cached is not None:
                        pipeline = None
                        mx.clear_cache()
                        pipeline = OptimizedZImage(
                            model_config=ModelConfig.z_image_turbo(),
                            model_path=str(cached),
                            quantize=bits,
                        )
            self._pipeline = pipeline
            self._pipeline_key = key
            return pipeline
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ModelWorkerError(
                f"Z-Image model loading failed: {exc}",
                code="model_load_failed",
                status_code=503,
            ) from exc

    @staticmethod
    def _parameters(
        payload: dict[str, Any],
    ) -> tuple[str, int, int, int, float, int | None, str, int]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt or len(prompt) > 8192:
            raise ValueError("prompt must contain 1-8192 characters")
        size = str(payload.get("size") or "1024x1024").lower()
        try:
            width, height = (int(item) for item in size.split("x", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("size must be WIDTHxHEIGHT") from exc
        if not (
            256 <= width <= 2048
            and 256 <= height <= 2048
            and width % 32 == 0
            and height % 32 == 0
        ):
            raise ValueError("dimensions must be 256-2048 pixels and divisible by 32")
        steps = int(payload.get("num_inference_steps", payload.get("steps", 8)))
        guidance = float(payload.get("guidance", payload.get("guidance_scale", 0.0)))
        seed = int(payload.get("seed", 0))
        if not 1 <= steps <= 50 or guidance != 0.0 or not 0 <= seed < 2**32:
            raise ValueError(
                "steps must be 1-50, Turbo guidance must be 0, and seed must be uint32"
            )
        quantization = str(payload.get("quantization", "q8")).strip().lower()
        if quantization in {"bf16", "none"}:
            bits = None
        elif quantization in {"8", "q8"}:
            bits = 8
        elif quantization in {"4", "q4"}:
            bits = 4
        else:
            raise ValueError("quantization must be bf16, q8, or q4")
        output_format = str(
            payload.get("outputFormat", payload.get("output_format", "png"))
        ).lower()
        if output_format not in {"png", "jpeg", "webp"}:
            raise ValueError("output format must be png, jpeg, or webp")
        return prompt, width, height, steps, guidance, bits, output_format, seed

    @staticmethod
    def _reference_image(
        payload: dict[str, Any], output_root: Path
    ) -> tuple[Path, float]:
        values = payload.get("imageDataUrls", payload.get("image_data_urls", []))
        if not isinstance(values, list) or len(values) != 1:
            raise ValueError("Z-Image editing requires exactly one imageDataUrl")
        match = _DATA_URL.fullmatch(str(values[0]))
        if match is None:
            raise ValueError("reference image must be a PNG, JPEG, or WebP data URL")
        try:
            content = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("reference image base64 is invalid") from exc
        if not content or len(content) > 25 * 1024 * 1024:
            raise ValueError("reference image is empty or too large")
        try:
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("reference image format is not supported")
                width, height = image.size
                if (
                    width <= 0
                    or height <= 0
                    or width > 8192
                    or height > 8192
                    or width * height > 64 * 1024 * 1024
                ):
                    raise ValueError("reference image dimensions are too large")
                image.verify()
        except Exception as exc:
            raise ValueError("reference image cannot be decoded") from exc
        strength = float(
            payload.get(
                "strength",
                payload.get("imageStrength", payload.get("image_strength", 0.75)),
            )
        )
        if not 0.0 < strength <= 1.0:
            raise ValueError("image strength must be greater than 0 and at most 1")
        extension = match.group(1).lower()
        path = output_root / f"reference-0.{extension}"
        path.write_bytes(content)
        return path, strength

    async def invoke(self, request: ModelWorkerRequest) -> dict[str, Any]:
        if request.operation not in {"image_generation", "image_edit"}:
            raise ModelWorkerError(
                "Unsupported operation",
                code="operation_not_supported",
                status_code=400,
            )
        if request.output_root is None:
            raise ModelWorkerError(
                "Runtime output root is missing",
                code="runtime_protocol_error",
                status_code=500,
            )
        payload = dict(request.payload)
        try:
            package_id = self._model(payload)
            (
                prompt,
                width,
                height,
                steps,
                guidance,
                bits,
                output_format,
                seed,
            ) = self._parameters(payload)
            checkpoint, revision = self._checkpoint(package_id)
            reference = (
                self._reference_image(payload, request.output_root)
                if request.operation == "image_edit"
                else None
            )
        except (OSError, TypeError, ValueError) as exc:
            raise ModelWorkerError(
                str(exc), code="invalid_request", status_code=400
            ) from exc

        if request.progress is not None:
            await request.progress({"phase": "loading", "current": 0, "total": steps})
        pipeline = await asyncio.to_thread(
            self._load_pipeline,
            checkpoint,
            revision=revision,
            bits=bits,
        )

        try:
            generation = {
                "seed": seed,
                "prompt": prompt,
                "num_inference_steps": steps,
                "height": height,
                "width": width,
                "guidance": guidance,
            }
            if reference is not None:
                generation["image_path"] = reference[0]
                generation["image_strength"] = reference[1]
            generated = await asyncio.to_thread(pipeline.generate_image, **generation)
            image = generated.image
            if output_format == "jpeg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(
                buffer,
                format={"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[output_format],
            )
        except Exception as exc:
            raise ModelWorkerError(
                f"Z-Image generation failed: {exc}",
                code="generation_failed",
                status_code=500,
            ) from exc
        if request.progress is not None:
            await request.progress(
                {"phase": "complete", "current": steps, "total": steps}
            )
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
        stats = (
            pipeline.ai2apps_optimization_stats()
            if hasattr(pipeline, "ai2apps_optimization_stats")
            else None
        )
        return {
            "created": 0,
            "data": [{"b64_json": encoded}],
            "image": {
                "dataUrl": f"data:{mime};base64,{encoded}",
                "size": f"{width}x{height}",
                "quality": payload.get("quality", "auto"),
                "format": output_format,
            },
            "model": payload.get("model"),
            "seed": seed,
            "operation": request.operation,
            "imageStrength": reference[1] if reference is not None else None,
            "quantization": "bf16" if bits is None else f"q{bits}",
            "optimization": stats,
        }


def create_adapter(context: Any) -> ZImageAdapter:
    return ZImageAdapter(context)
