"""AI2Apps Model Worker adapter for the optimized native MLX Ideogram 4 pipeline."""

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

UPSTREAM_ID = "ideogram-ai/ideogram-4-fp8"
WEIGHTS_ID = "Comfy-Org/Ideogram-4"
PACKAGE_MODEL_ID = "ai2apps.model.ideogram4-mlx/fp8-q4"
WEIGHTS_REVISION = "bbee2ab2b14b2b5223448d12d6e31e5f9cec0546"
QWEN_CONFIG_REVISION = "0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
_DERIVED_FORMAT = "ai2apps.ideogram4-mlx-derived/v1"
_DATA_URL = re.compile(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\s]+)$")
_SOURCE_COMPONENTS = {
    "conditional": "diffusion_models/ideogram4_fp8_scaled.safetensors",
    "unconditional": "diffusion_models/ideogram4_unconditional_fp8_scaled.safetensors",
    "text_encoder": "text_encoders/qwen3vl_8b_fp8_scaled.safetensors",
    "vae": "vae/flux2-vae.safetensors",
}
_DERIVED_COMPONENTS = tuple(f"{name}-q4.safetensors" for name in _SOURCE_COMPONENTS)
_LOG = logging.getLogger(__name__)


def _derived_complete(root: Path) -> bool:
    return all((root / name).is_file() for name in _DERIVED_COMPONENTS)


def _source_complete(root: Path) -> bool:
    return all((root / name).is_file() for name in _SOURCE_COMPONENTS.values())


def _cache_key(source: Path, revision: str) -> str:
    identity = (
        f"{source.resolve()}\0{revision}\0q4\0g64\0{QWEN_CONFIG_REVISION}\0optimized-v1"
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]


class Ideogram4Adapter:
    def __init__(
        self,
        context: Any,
        *,
        pipeline_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.context = context
        self._pipeline_factory = pipeline_factory
        self._pipeline: Any | None = None
        self._pipeline_key: tuple[str, bool] | None = None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        self._pipeline = None
        self._pipeline_key = None
        try:
            import mlx.core as mx

            mx.synchronize()
            mx.clear_cache()
        except (ImportError, IndexError, RuntimeError):
            pass

    @staticmethod
    def _model(payload: dict[str, Any]) -> str:
        model = str(payload.get("model") or "")
        if model not in {UPSTREAM_ID, WEIGHTS_ID, PACKAGE_MODEL_ID}:
            raise ModelWorkerError(
                "Unsupported Ideogram 4 model",
                code="model_not_found",
                status_code=404,
            )
        return PACKAGE_MODEL_ID

    def _checkpoint(self, package_id: str) -> tuple[Path, str]:
        checkpoint = self.context.checkpoint_for(package_id)
        if checkpoint is None:
            checkpoint = self.context.checkpoint_for(WEIGHTS_ID)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "The pinned Ideogram 4 checkpoint is not installed",
                code="model_unavailable",
                status_code=503,
            )
        root = checkpoint.path.resolve()
        if not (_source_complete(root) or _derived_complete(root)):
            raise ModelWorkerError(
                "Ideogram 4 checkpoint is incomplete",
                code="invalid_checkpoint",
                status_code=503,
            )
        return root, str(getattr(checkpoint, "revision", WEIGHTS_REVISION))

    def _cache_target(self, source: Path, revision: str) -> Path:
        return (
            Path(self.context.data_root)
            / "derived-models"
            / "ideogram4"
            / f"q4-{_cache_key(source, revision)}"
        )

    def _materialize_q4(self, source: Path, revision: str) -> Path:
        if _derived_complete(source):
            return source
        target = self._cache_target(source, revision)
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_suffix(".lock")
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if _derived_complete(target):
                return target
            source_bytes = sum(
                (source / name).stat().st_size for name in _SOURCE_COMPONENTS.values()
            )
            required = max(18 << 30, int(source_bytes * 0.65))
            if shutil.disk_usage(target.parent).free < required:
                raise ModelWorkerError(
                    "Insufficient disk space for the Ideogram 4 Q4 cache",
                    code="insufficient_storage",
                    status_code=507,
                )
            staging = Path(
                tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent)
            )
            try:
                from convert_fp8_to_mlx import convert_component

                reports = []
                for component, relative in _SOURCE_COMPONENTS.items():
                    reports.append(
                        convert_component(
                            source / relative,
                            staging / f"{component}-q4.safetensors",
                            bits=4,
                            group_size=64,
                        )
                    )
                receipt = {
                    "format": _DERIVED_FORMAT,
                    "source": str(source),
                    "source_revision": revision,
                    "qwen_config_revision": QWEN_CONFIG_REVISION,
                    "quantization_bits": 4,
                    "quantization_group_size": 64,
                    "components": reports,
                }
                (staging / "conversion.json").write_text(
                    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                if not _derived_complete(staging):
                    raise RuntimeError("Ideogram 4 conversion is incomplete")
                if target.exists():
                    stale = target.with_name(f".{target.name}.stale-{os.getpid()}")
                    os.replace(target, stale)
                    shutil.rmtree(stale, ignore_errors=True)
                os.replace(staging, target)
                return target
            except ModelWorkerError:
                raise
            except (OSError, RuntimeError, TypeError, ValueError) as exc:
                _LOG.exception("Ideogram 4 Q4 conversion failed")
                raise ModelWorkerError(
                    f"Ideogram 4 Q4 conversion failed: {exc}",
                    code="model_preparation_failed",
                    status_code=503,
                ) from exc
            finally:
                if staging.exists():
                    shutil.rmtree(staging, ignore_errors=True)

    def _load_pipeline(
        self,
        checkpoint: Path,
        *,
        revision: str,
        compile_denoisers: bool,
    ) -> Any:
        derived = self._materialize_q4(checkpoint, revision)
        key = (str(derived), compile_denoisers)
        if self._pipeline is not None and self._pipeline_key == key:
            return self._pipeline
        self._pipeline = None
        try:
            if self._pipeline_factory is not None:
                pipeline = self._pipeline_factory(
                    derived_root=derived,
                    qwen_config_root=self._qwen_config_root(),
                    compile_denoisers=compile_denoisers,
                )
            else:
                import mlx.core as mx
                from pipeline import Ideogram4MLXPipeline, PipelinePaths

                mx.synchronize()
                mx.clear_cache()
                pipeline = Ideogram4MLXPipeline(
                    PipelinePaths(derived, self._qwen_config_root()),
                    bits=4,
                    group_size=64,
                    staged=True,
                    compile_denoisers=compile_denoisers,
                )
            self._pipeline = pipeline
            self._pipeline_key = key
            return pipeline
        except ModelWorkerError:
            raise
        except (ImportError, OSError, RuntimeError, TypeError, ValueError) as exc:
            raise ModelWorkerError(
                f"Ideogram 4 loading failed: {exc}",
                code="model_load_failed",
                status_code=503,
            ) from exc

    def _qwen_config_root(self) -> Path:
        root = Path(self.context.package_root) / "assets" / "qwen3-vl-8b-config"
        required = ("config.json", "tokenizer.json", "tokenizer_config.json")
        if not all((root / name).is_file() for name in required):
            raise ModelWorkerError(
                "Bundled Qwen tokenizer/config is incomplete",
                code="package_corrupt",
                status_code=500,
            )
        return root

    @staticmethod
    def _parameters(
        payload: dict[str, Any], *, edit: bool
    ) -> tuple[str, int, int, int, int, str, bool]:
        prompt = str(payload.get("prompt") or "").strip()
        if not prompt or len(prompt) > 32768:
            raise ValueError("prompt must contain 1-32768 characters")
        size = str(payload.get("size") or "1024x1024").lower()
        try:
            width, height = (int(value) for value in size.split("x", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError("size must be WIDTHxHEIGHT") from exc
        if not (
            256 <= width <= 2048
            and 256 <= height <= 2048
            and width % 16 == 0
            and height % 16 == 0
        ):
            raise ValueError("dimensions must be 256-2048 pixels and divisible by 16")
        default_steps = 12
        steps = int(
            payload.get("num_inference_steps", payload.get("steps", default_steps))
        )
        seed = int(payload.get("seed", 0))
        if not 1 <= steps <= 48 or not 0 <= seed < 2**32:
            raise ValueError("steps must be 1-48 and seed must be uint32")
        quantization = str(payload.get("quantization", "q4")).strip().lower()
        if quantization not in {"4", "q4"}:
            raise ValueError("the Ideogram 4 MVP currently supports q4 only")
        output_format = str(
            payload.get("outputFormat", payload.get("output_format", "png"))
        ).lower()
        if output_format not in {"png", "jpeg", "webp"}:
            raise ValueError("output format must be png, jpeg, or webp")
        compiled = payload.get(
            "compileDenoisers", payload.get("compile_denoisers", False)
        )
        if not isinstance(compiled, bool):
            raise ValueError("compileDenoisers must be boolean")
        if edit and steps < 2:
            raise ValueError("image editing requires at least two configured steps")
        return prompt, width, height, steps, seed, output_format, compiled

    @staticmethod
    def _reference_image(
        payload: dict[str, Any], output_root: Path
    ) -> tuple[Path, float]:
        values = payload.get("imageDataUrls", payload.get("image_data_urls", []))
        if not isinstance(values, list) or len(values) != 1:
            raise ValueError("Ideogram 4 editing requires exactly one imageDataUrl")
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
        path = output_root / f"reference-0.{match.group(1).lower()}"
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
        edit = request.operation == "image_edit"
        try:
            package_id = self._model(payload)
            prompt, width, height, steps, seed, output_format, compiled = (
                self._parameters(payload, edit=edit)
            )
            checkpoint, revision = self._checkpoint(package_id)
            reference = (
                self._reference_image(payload, request.output_root) if edit else None
            )
        except ModelWorkerError:
            raise
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
            compile_denoisers=compiled,
        )
        source_image = None
        strength = None
        if reference is not None:
            strength = reference[1]
            with Image.open(reference[0]) as opened:
                opened.load()
                source_image = opened.copy()
        try:
            image, report = await asyncio.to_thread(
                pipeline.generate,
                prompt,
                height=height,
                width=width,
                seed=seed,
                steps=steps,
                image=source_image,
                strength=strength,
            )
            if output_format == "jpeg" and image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            buffer = io.BytesIO()
            image.save(
                buffer,
                format={"png": "PNG", "jpeg": "JPEG", "webp": "WEBP"}[output_format],
            )
        except Exception as exc:
            raise ModelWorkerError(
                f"Ideogram 4 inference failed: {exc}",
                code="generation_failed",
                status_code=500,
            ) from exc
        if request.progress is not None:
            await request.progress(
                {
                    "phase": "complete",
                    "current": int(report["effective_steps"]),
                    "total": int(report["effective_steps"]),
                }
            )
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        mime = "image/jpeg" if output_format == "jpeg" else f"image/{output_format}"
        return {
            "created": 0,
            "data": [{"b64_json": encoded}],
            "image": {
                "dataUrl": f"data:{mime};base64,{encoded}",
                "size": f"{width}x{height}",
                "quality": payload.get("quality", "quality"),
                "format": output_format,
            },
            "model": payload.get("model"),
            "seed": seed,
            "operation": request.operation,
            "imageStrength": strength,
            "quantization": "q4",
            "optimization": {
                "native_mlx": True,
                "staged_model_lifecycle": report["staged_model_lifecycle"],
                "bf16_mlp": True,
                "bf16_sdpa": True,
                "fused_qk_rms_mrope": True,
                "compiled_denoisers": report["compiled_denoisers"],
                "effective_steps": report["effective_steps"],
                "denoise_seconds": report["denoise_seconds"],
                "decode_seconds": report["decode_seconds"],
                "encode_image_seconds": report["stage_seconds"].get(
                    "encode_image", 0.0
                ),
                "peak_memory_bytes": report["peak_memory_bytes"],
            },
        }


def create_adapter(context: Any) -> Ideogram4Adapter:
    return Ideogram4Adapter(context)
