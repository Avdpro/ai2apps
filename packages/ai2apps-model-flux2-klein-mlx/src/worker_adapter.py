"""AI2Apps Model Worker adapter for optimized FLUX.2 Klein MLX inference."""

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
from pathlib import Path
from typing import Any, Callable

from ai2apps.model_worker import ModelWorkerError, ModelWorkerRequest

MODEL_IDS = {
    "black-forest-labs/FLUX.2-klein-4B": ("4b", "ai2apps.model.flux2-klein-mlx/4b"),
    "black-forest-labs/FLUX.2-klein-9B": ("9b", "ai2apps.model.flux2-klein-mlx/9b"),
}
_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
_DERIVED_FORMAT = "ai2apps.flux2-mlx-quantized/v1"
_LOG = logging.getLogger(__name__)


def _checkpoint_quantization(root: Path) -> int | None:
    """Return the stored mflux quantization level, if this is a saved MLX tree."""
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


def _derived_cache_key(checkpoint: Path, revision: str, variant: str, bits: int) -> str:
    identity = f"{checkpoint.resolve()}\0{revision}\0{variant}\0q{bits}\0mflux-0.19.0\0v1"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class Flux2KleinAdapter:
    def __init__(self, context: Any, *, pipeline_factory: Callable[..., Any] | None = None) -> None:
        self.context = context
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any | None = None
        self._pipeline_key: tuple[str, int | None, bool] | None = None

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
    def _model(payload: dict[str, Any]) -> tuple[str, str, Path]:
        upstream = str(payload.get("model") or "")
        selected = MODEL_IDS.get(upstream)
        if selected is None:
            raise ModelWorkerError("Unsupported FLUX.2 Klein model", code="model_not_found", status_code=404)
        variant, package_id = selected
        return variant, package_id, Path()

    def _checkpoint(self, package_id: str) -> tuple[Path, str]:
        checkpoint = self.context.checkpoint_for(package_id)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned FLUX.2 checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = checkpoint.path.resolve()
        required = (root / "model_index.json", root / "transformer", root / "text_encoder", root / "vae")
        if not all(item.exists() for item in required):
            raise ModelWorkerError("FLUX.2 checkpoint is incomplete", code="invalid_checkpoint", status_code=503)
        return root, str(getattr(checkpoint, "revision", "unknown"))

    def _cache_target(self, checkpoint: Path, revision: str, variant: str, bits: int) -> Path:
        key = _derived_cache_key(checkpoint, revision, variant, bits)
        return Path(self.context.data_root) / "derived-models" / "flux2-klein" / f"{variant}-q{bits}-{key}"

    @staticmethod
    def _required_cache_bytes(checkpoint: Path, bits: int) -> int:
        source_bytes = sum(path.stat().st_size for path in checkpoint.rglob("*.safetensors"))
        # Saved MLX weights are approximately bits/16 of a BF16 tree. Keep 20%
        # headroom for shards, tokenizer files, and atomic staging.
        return max(2 << 30, int(source_bytes * (bits / 16) * 1.2))

    def _materialize_quantized_checkpoint(
        self,
        *,
        pipeline: Any,
        source: Path,
        revision: str,
        variant: str,
        bits: int,
    ) -> Path | None:
        """Persist a process-safe, revision-keyed MLX checkpoint.

        Conversion is an optimization only: insufficient disk or a save failure
        falls back to the already-loaded online-quantized pipeline.
        """
        target = self._cache_target(source, revision, variant, bits)
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_suffix(".lock")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _derived_checkpoint_complete(target, bits):
                return target
            required = self._required_cache_bytes(source, bits)
            if shutil.disk_usage(target.parent).free < required:
                _LOG.warning(
                    "Skipping FLUX.2 Q%s derived cache: need %s bytes of free disk",
                    bits,
                    required,
                )
                return None
            staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent))
            try:
                pipeline.save_model(str(staging))
                receipt = {
                    "format": _DERIVED_FORMAT,
                    "source": str(source),
                    "source_revision": revision,
                    "variant": variant,
                    "quantization_bits": bits,
                    "mflux_version": "0.19.0",
                }
                (staging / ".ai2apps-derived.json").write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )
                if not _derived_checkpoint_complete(staging, bits):
                    raise RuntimeError("mflux produced an incomplete derived checkpoint")
                if target.exists():
                    stale = target.with_name(f".{target.name}.stale-{os.getpid()}")
                    os.replace(target, stale)
                    shutil.rmtree(stale, ignore_errors=True)
                os.replace(staging, target)
                return target
            except (OSError, RuntimeError, ValueError) as exc:
                _LOG.warning("FLUX.2 derived checkpoint creation failed: %s", exc)
                return None
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)

    def _load_pipeline(
        self,
        variant: str,
        checkpoint: Path,
        *,
        revision: str,
        bits: int | None,
        edit: bool,
    ) -> Any:
        key = (variant, bits, edit)
        if self._pipeline is not None and self._pipeline_key == key:
            return self._pipeline
        self._pipeline = None
        try:
            if self._pipeline_factory is not None:
                pipeline = self._pipeline_factory(variant=variant, checkpoint=checkpoint, bits=bits, edit=edit)
            else:
                import mlx.core as mx

                mx.clear_cache()
                from mflux.models.common.config.model_config import ModelConfig
                from optimized_pipeline import OptimizedFlux2Klein, OptimizedFlux2KleinEdit

                config = ModelConfig.flux2_klein_4b() if variant == "4b" else ModelConfig.flux2_klein_9b()
                pipeline_type = OptimizedFlux2KleinEdit if edit else OptimizedFlux2Klein
                load_path = checkpoint
                if bits is not None:
                    cached = self._cache_target(checkpoint, revision, variant, bits)
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
                        variant=variant,
                        bits=bits,
                    )
                    if cached is not None:
                        # Release source tensors and reload the smaller native tree.
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
                f"FLUX.2 model loading failed: {exc}", code="model_load_failed", status_code=503
            ) from exc

    @staticmethod
    def _parameters(payload: dict[str, Any]) -> tuple[str, int, int, int, float, int | None, str]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt or len(prompt) > 8192:
            raise ValueError("prompt must contain 1-8192 characters")
        size = str(payload.get("size") or "1024x1024").lower()
        try:
            width, height = (int(item) for item in size.split("x", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("size must be WIDTHxHEIGHT") from exc
        if not (256 <= width <= 2048 and 256 <= height <= 2048 and width % 32 == height % 32 == 0):
            raise ValueError("dimensions must be 256-2048 pixels and divisible by 32")
        steps = int(payload.get("num_inference_steps", payload.get("steps", 4)))
        guidance = float(payload.get("guidance", payload.get("guidance_scale", 1.0)))
        seed = int(payload.get("seed", 0))
        if not 1 <= steps <= 50 or not 0.0 <= guidance <= 20.0 or not 0 <= seed < 2**32:
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
        output_format = str(payload.get("outputFormat", payload.get("output_format", "png"))).lower()
        if output_format not in {"png", "jpeg", "webp"}:
            raise ValueError("output format must be png, jpeg, or webp")
        return prompt, width, height, steps, guidance, bits, output_format

    @staticmethod
    def _reference_images(payload: dict[str, Any], output_root: Path) -> list[Path]:
        values = payload.get("imageDataUrls", payload.get("image_data_urls", []))
        if not isinstance(values, list) or not 1 <= len(values) <= 4:
            raise ValueError("image editing requires one to four imageDataUrls")
        paths: list[Path] = []
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
            path = output_root / f"reference-{index}.{match.group(1)}"
            path.write_bytes(content)
            paths.append(path)
        return paths

    async def invoke(self, request: ModelWorkerRequest) -> dict[str, Any]:
        if request.operation not in {"image_generation", "image_edit"}:
            raise ModelWorkerError("Unsupported operation", code="operation_not_supported", status_code=400)
        if request.output_root is None:
            raise ModelWorkerError("Runtime output root is missing", code="runtime_protocol_error", status_code=500)
        payload = dict(request.payload)
        try:
            variant, package_id, _ = self._model(payload)
            prompt, width, height, steps, guidance, bits, output_format = self._parameters(payload)
            checkpoint, revision = self._checkpoint(package_id)
            edit = request.operation == "image_edit"
            references = self._reference_images(payload, request.output_root) if edit else []
        except (OSError, TypeError, ValueError) as exc:
            raise ModelWorkerError(str(exc), code="invalid_request", status_code=400) from exc

        if request.progress is not None:
            await request.progress({"phase": "loading", "current": 0, "total": steps})
        pipeline = await asyncio.to_thread(
            self._load_pipeline,
            variant,
            checkpoint,
            revision=revision,
            bits=bits,
            edit=edit,
        )

        def generate():
            common = dict(
                seed=int(payload.get("seed", 0)), prompt=prompt,
                num_inference_steps=steps, height=height, width=width, guidance=guidance,
            )
            if edit:
                return pipeline.generate_image(
                    **common, image_paths=references,
                    use_kv_cache=payload.get("use_kv_cache", True) is not False,
                )
            return pipeline.generate_image(**common)

        try:
            generated = await asyncio.to_thread(generate)
            image = generated.image
            if output_format == "jpeg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format={"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[output_format])
        except Exception as exc:
            raise ModelWorkerError(
                f"FLUX.2 generation failed: {exc}", code="generation_failed", status_code=500
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
            "model": payload.get("model"),
            "seed": int(payload.get("seed", 0)),
            "quantization": "bf16" if bits is None else f"q{bits}",
        }


def create_adapter(context: Any) -> Flux2KleinAdapter:
    return Flux2KleinAdapter(context)
