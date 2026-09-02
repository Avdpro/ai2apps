"""AI2Apps Model Worker adapter for Qwen Image generation and editing on MLX."""

from __future__ import annotations

import asyncio
import base64
import binascii
import copy
import fcntl
import hashlib
import io
import json
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest


MODEL_IDS = {
    "Qwen/Qwen-Image-2512": ("generation", "ai2apps.model.qwen-image-mlx/2512"),
    "Qwen/Qwen-Image-Edit-2511": ("edit", "ai2apps.model.qwen-image-mlx/edit-2511"),
}
_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
_DERIVED_FORMAT = "ai2apps.qwen-image-mlx-quantized/v1"
_MFLUX_VERSION = "0.19.0"
_LOG = logging.getLogger(__name__)


def _checkpoint_quantization(root: Path) -> int | None:
    index = root / "transformer" / "model.safetensors.index.json"
    try:
        value = json.loads(index.read_text(encoding="utf-8")).get("metadata", {}).get(
            "quantization_level"
        )
        return int(value) if value is not None else None
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _derived_checkpoint_complete(root: Path, bits: int) -> bool:
    try:
        receipt = json.loads((root / ".ai2apps-derived.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
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
        and all(path.is_file() for path in required)
        and _checkpoint_quantization(root) == bits
    )


def _derived_cache_key(checkpoint: Path, revision: str, kind: str, bits: int) -> str:
    identity = (
        f"{checkpoint.resolve()}\0{revision}\0{kind}\0q{bits}\0"
        f"mflux-{_MFLUX_VERSION}\0v1"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class QwenImageAdapter:
    def __init__(self, context: Any, *, pipeline_factory: Callable[..., Any] | None = None) -> None:
        self.context = context
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any | None = None
        self._pipeline_key: tuple[str, int | None] | None = None

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
    def _model(payload: dict[str, Any], operation: str) -> tuple[str, str, str]:
        upstream = str(payload.get("model") or "")
        selected = MODEL_IDS.get(upstream)
        if selected is None:
            raise ModelWorkerError(
                "Unsupported Qwen Image model", code="model_not_found", status_code=404
            )
        kind, package_id = selected
        expected = "image_edit" if kind == "edit" else "image_generation"
        if operation != expected:
            raise ModelWorkerError(
                f"{upstream} supports {expected} only",
                code="operation_not_supported",
                status_code=400,
            )
        return kind, package_id, upstream

    def _checkpoint(self, package_id: str) -> tuple[Path, str]:
        checkpoint = self.context.checkpoint_for(package_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned Qwen Image checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = checkpoint.path.resolve()
        required = (
            root / "model_index.json",
            root / "transformer",
            root / "text_encoder",
            root / "vae",
            root / "tokenizer",
        )
        if not all(item.exists() for item in required):
            raise ModelWorkerError(
                "Qwen Image checkpoint is incomplete",
                code="invalid_checkpoint",
                status_code=503,
            )
        return root, str(getattr(checkpoint, "revision", "unknown"))

    def _cache_target(self, checkpoint: Path, revision: str, kind: str, bits: int) -> Path:
        key = _derived_cache_key(checkpoint, revision, kind, bits)
        return (
            Path(self.context.data_root)
            / "derived-models"
            / "qwen-image"
            / f"{kind}-q{bits}-{key}"
        )

    @staticmethod
    def _required_cache_bytes(checkpoint: Path, bits: int) -> int:
        source_bytes = sum(path.stat().st_size for path in checkpoint.rglob("*.safetensors"))
        # The 7B text encoder intentionally remains BF16 in mflux. This estimate
        # therefore keeps more headroom than a uniform bits/16 conversion.
        return max(8 << 30, int(source_bytes * (0.72 if bits == 8 else 0.56) * 1.15))

    def _materialize_quantized_checkpoint(
        self,
        *,
        pipeline: Any,
        source: Path,
        revision: str,
        kind: str,
        bits: int,
    ) -> Path | None:
        target = self._cache_target(source, revision, kind, bits)
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_suffix(".lock")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _derived_checkpoint_complete(target, bits):
                return target
            if shutil.disk_usage(target.parent).free < self._required_cache_bytes(source, bits):
                _LOG.warning("Skipping Qwen Image Q%s derived cache: insufficient free disk", bits)
                return None
            staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
            try:
                pipeline.save_model(str(staging))
                (staging / ".ai2apps-derived.json").write_text(
                    json.dumps(
                        {
                            "format": _DERIVED_FORMAT,
                            "source": str(source),
                            "source_revision": revision,
                            "kind": kind,
                            "quantization_bits": bits,
                            "mflux_version": _MFLUX_VERSION,
                        },
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                if not _derived_checkpoint_complete(staging, bits):
                    raise RuntimeError("mflux produced an incomplete derived Qwen checkpoint")
                if target.exists():
                    stale = target.with_name(f".{target.name}.stale-{os.getpid()}")
                    os.replace(target, stale)
                    shutil.rmtree(stale, ignore_errors=True)
                os.replace(staging, target)
                return target
            except (OSError, RuntimeError, ValueError) as exc:
                _LOG.warning("Qwen Image derived checkpoint creation failed: %s", exc)
                return None
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _model_config(kind: str, upstream: str):
        from mflux.models.common.config.model_config import ModelConfig

        base = ModelConfig.qwen_image_edit() if kind == "edit" else ModelConfig.qwen_image()
        config = copy.copy(base)
        # mflux 0.19 accepts the 2511 alias but its cached edit config still
        # names the older 2509 repository. Never mutate that shared singleton.
        config.model_name = upstream
        return config

    def _load_pipeline(
        self,
        kind: str,
        upstream: str,
        checkpoint: Path,
        *,
        revision: str,
        bits: int | None,
    ) -> Any:
        key = (kind, bits)
        if self._pipeline is not None and self._pipeline_key == key:
            return self._pipeline
        self._pipeline = None
        try:
            if self._pipeline_factory is not None:
                pipeline = self._pipeline_factory(
                    kind=kind, upstream=upstream, checkpoint=checkpoint, bits=bits
                )
            else:
                import mlx.core as mx
                from optimized_pipeline import OptimizedQwenImage, OptimizedQwenImageEdit

                mx.clear_cache()
                config = self._model_config(kind, upstream)
                pipeline_type = OptimizedQwenImageEdit if kind == "edit" else OptimizedQwenImage
                load_path = checkpoint
                if bits is not None:
                    cached = self._cache_target(checkpoint, revision, kind, bits)
                    if _derived_checkpoint_complete(cached, bits):
                        load_path = cached
                pipeline = pipeline_type(
                    model_config=config,
                    model_path=str(load_path),
                    quantize=bits,
                )
                if bits is not None and load_path == checkpoint and _checkpoint_quantization(checkpoint) != bits:
                    cached = self._materialize_quantized_checkpoint(
                        pipeline=pipeline,
                        source=checkpoint,
                        revision=revision,
                        kind=kind,
                        bits=bits,
                    )
                    if cached is not None:
                        pipeline = None
                        mx.clear_cache()
                        pipeline = pipeline_type(
                            model_config=config,
                            model_path=str(cached),
                            quantize=bits,
                        )
            self._pipeline = pipeline
            self._pipeline_key = key
            return pipeline
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            raise ModelWorkerError(
                f"Qwen Image model loading failed: {exc}",
                code="model_load_failed",
                status_code=503,
            ) from exc

    @staticmethod
    def _parameters(payload: dict[str, Any], *, edit: bool):
        prompt = str(payload.get("prompt") or "").strip()
        negative_prompt = str(payload.get("negative_prompt") or "").strip()
        if not prompt or len(prompt) > 8192 or len(negative_prompt) > 8192:
            raise ValueError("prompt must contain 1-8192 characters")
        size = str(payload.get("size") or ("1024x1024" if edit else "1328x1328")).lower()
        try:
            width, height = (int(item) for item in size.split("x", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("size must be WIDTHxHEIGHT") from exc
        if not (
            256 <= width <= 2048
            and 256 <= height <= 2048
            and width % 16 == height % 16 == 0
        ):
            raise ValueError("dimensions must be 256-2048 pixels and divisible by 16")
        default_steps = 30 if edit else 20
        steps = int(payload.get("num_inference_steps", payload.get("steps", default_steps)))
        guidance = float(payload.get("guidance", payload.get("guidance_scale", 2.5 if edit else 4.0)))
        seed = int(payload.get("seed", 0))
        if not 1 <= steps <= 100 or not 0.0 <= guidance <= 20.0 or not 0 <= seed < 2**32:
            raise ValueError("steps, guidance, or seed is out of range")
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
        return prompt, negative_prompt or None, width, height, steps, guidance, seed, bits, output_format

    @staticmethod
    def _reference_images(payload: dict[str, Any], output_root: Path) -> list[str]:
        values = payload.get("imageDataUrls", payload.get("image_data_urls", []))
        if not isinstance(values, list) or not 1 <= len(values) <= 3:
            raise ValueError("Qwen image editing requires one to three imageDataUrls")
        paths: list[str] = []
        for index, value in enumerate(values):
            match = _DATA_URL.fullmatch(str(value))
            if match is None:
                raise ValueError("reference images must be PNG, JPEG, or WebP data URLs")
            try:
                content = base64.b64decode(match.group(2), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("reference image base64 is invalid") from exc
            if not content or len(content) > 25 * 1024 * 1024:
                raise ValueError("reference image is empty or too large")
            try:
                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
            except Exception as exc:
                raise ValueError("reference image cannot be decoded") from exc
            path = output_root / f"reference-{index}.{match.group(1)}"
            path.write_bytes(content)
            paths.append(str(path))
        return paths

    async def invoke(self, request: ModelWorkerRequest) -> dict[str, Any]:
        if request.operation not in {"image_generation", "image_edit"}:
            raise ModelWorkerError(
                "Unsupported operation", code="operation_not_supported", status_code=400
            )
        if request.output_root is None:
            raise ModelWorkerError(
                "Runtime output root is missing", code="runtime_protocol_error", status_code=500
            )
        payload = dict(request.payload)
        try:
            kind, package_id, upstream = self._model(payload, request.operation)
            edit = kind == "edit"
            (
                prompt,
                negative_prompt,
                width,
                height,
                steps,
                guidance,
                seed,
                bits,
                output_format,
            ) = self._parameters(payload, edit=edit)
            checkpoint, revision = self._checkpoint(package_id)
            references = self._reference_images(payload, request.output_root) if edit else []
        except ModelWorkerError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise ModelWorkerError(str(exc), code="invalid_request", status_code=400) from exc

        if request.progress is not None:
            await request.progress({"phase": "loading", "current": 0, "total": steps})
        pipeline = await asyncio.to_thread(
            self._load_pipeline,
            kind,
            upstream,
            checkpoint,
            revision=revision,
            bits=bits,
        )

        def generate():
            common = {
                "seed": seed,
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "num_inference_steps": steps,
                "height": height,
                "width": width,
                "guidance": guidance,
            }
            if edit:
                return pipeline.generate_image(**common, image_paths=references)
            return pipeline.generate_image(**common)

        try:
            generated = await asyncio.to_thread(generate)
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
                f"Qwen Image inference failed: {exc}",
                code="generation_failed",
                status_code=500,
            ) from exc
        if request.progress is not None:
            await request.progress({"phase": "complete", "current": steps, "total": steps})
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
        return {
            "created": 0,
            "data": [{"b64_json": encoded}],
            "image": {
                "dataUrl": f"data:{mime};base64,{encoded}",
                "size": f"{width}x{height}",
                "quality": payload.get("quality", "auto"),
                "format": output_format,
            },
            "model": upstream,
            "seed": seed,
            "quantization": "bf16" if bits is None else f"q{bits}",
        }


def create_adapter(context: Any) -> QwenImageAdapter:
    return QwenImageAdapter(context)
