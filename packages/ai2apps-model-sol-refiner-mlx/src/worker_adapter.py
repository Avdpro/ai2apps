"""Pure Python adapter for the dedicated video_upscaling operation."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import threading
from pathlib import Path

from prompt_context import DEFAULT_PROMPT, fixed_context

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError

MODEL_ID = "ai2apps.model.sol-refiner-mlx/ltx23-one-step"
UPSTREAM_ID = "ai2apps-sol-refiner-default"
CUSTOM_MODEL_ID = "ai2apps.model.sol-refiner-mlx/ltx23-custom-prompt"
CUSTOM_UPSTREAM_ID = "ai2apps-sol-refiner-custom"


class SoLRefinerAdapter:
    def __init__(self, context, *, engine=None, image_engine=None):
        self.context = context
        self.engine = engine
        self.image_engine = image_engine
        self._tokens = {}
        self._cancelled_before_start = set()
        self._stopping = False
        self._lock = asyncio.Lock()

    async def start(self):
        self._stopping = False

    def cancel(self, request_id):
        token = self._tokens.get(request_id)
        if token is not None:
            token.set()
        else:
            self._cancelled_before_start.add(request_id)

    async def stop(self):
        self._stopping = True
        for token in tuple(self._tokens.values()):
            token.set()
        async with self._lock:
            self._cancelled_before_start.clear()

    @staticmethod
    def parameters(payload):
        if payload.get("model") not in (
            MODEL_ID,
            UPSTREAM_ID,
            CUSTOM_MODEL_ID,
            CUSTOM_UPSTREAM_ID,
        ):
            raise ModelWorkerError(
                "Select the SoL-Refiner upscaling model",
                code="model_not_found",
                status_code=404,
            )
        p = payload.get("parameters", payload)
        if isinstance(p, str):
            p = json.loads(p)
        if not isinstance(p, dict):
            raise ValueError("parameters must be an object")
        scale = p.get("scale", 2)
        if scale == "2":
            scale = 2
        if type(scale) is not int or scale != 2:
            raise ValueError("This checkpoint supports 2x upscaling")
        seed = p.get("seed", 0)
        if isinstance(seed, str) and seed.isdecimal():
            seed = int(seed)
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise ValueError("seed must be an integer from 0 to 4294967295")
        prompt = p.get("prompt", DEFAULT_PROMPT)
        if not isinstance(prompt, str) or len(prompt) > 2048:
            raise ValueError("prompt must be text of at most 2048 characters")
        return prompt.strip() or DEFAULT_PROMPT, seed

    async def invoke(self, request):
        if request.operation not in {"video_upscaling", "image_upscaling"}:
            raise ModelWorkerError(
                "Unsupported operation", code="operation_not_supported"
            )
        if request.output_root is None:
            raise ModelWorkerError(
                "Missing controlled output root",
                code="runtime_protocol_error",
                status_code=500,
            )
        is_image = request.operation == "image_upscaling"
        part_name = "image" if is_image else "video"
        try:
            prompt, seed = self.parameters(request.payload)
            source = request.part(part_name)
            if not (
                source.media_type.startswith("image/" if is_image else "video/")
                or source.media_type == "application/octet-stream"
            ):
                raise ValueError(f"{part_name} part has an unsupported media type")
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ModelWorkerError(str(exc), code="invalid_request") from exc
        selected_model = (
            CUSTOM_MODEL_ID
            if request.payload.get("model") in (CUSTOM_MODEL_ID, CUSTOM_UPSTREAM_ID)
            else MODEL_ID
        )
        checkpoint = self.context.checkpoint_for(selected_model)
        if checkpoint is None or checkpoint.path is None:
            raise ModelWorkerError(
                "Install the pinned SoL-Refiner checkpoint first",
                code="model_unavailable",
                status_code=503,
            )
        root = Path(checkpoint.path)
        if not (root / "model_index.json").is_file():
            raise ModelWorkerError(
                "Checkpoint is incomplete",
                code="checkpoint_incomplete",
                status_code=503,
            )
        try:
            fixed_context(root, prompt)
        except ValueError as exc:
            raise ModelWorkerError(
                str(exc), code="prompt_configuration_required", status_code=400
            ) from exc
        from upscale_engine import UpscaleCancelled, upscale

        if is_image:
            from image_upscale_engine import upscale_image

            engine = self.image_engine or upscale_image
        else:
            engine = self.engine or upscale
        output = request.output_root / (
            "upscaled-"
            + hashlib.sha256(request.request_id.encode()).hexdigest()[:20]
            + (".png" if is_image else ".mp4")
        )
        token = threading.Event()
        loop = asyncio.get_running_loop()

        async def report(data):
            if request.progress:
                result = request.progress(data)
                if inspect.isawaitable(result):
                    await result

        def progress(data):
            asyncio.run_coroutine_threadsafe(report(data), loop).result(timeout=30)

        def check():
            if token.is_set():
                raise UpscaleCancelled()

        async with self._lock:
            if self._stopping or request.request_id in self._cancelled_before_start:
                self._cancelled_before_start.discard(request.request_id)
                raise ModelWorkerError(
                    "Upscaling cancelled before execution",
                    code="generation_cancelled",
                    status_code=499,
                )
            self._tokens[request.request_id] = token
            self.context.data_root.mkdir(parents=True, exist_ok=True)
            task = asyncio.create_task(
                asyncio.to_thread(
                    engine,
                    source.path,
                    output,
                    root,
                    prompt,
                    seed,
                    self.context.data_root,
                    check,
                    progress,
                )
            )
            try:
                metadata = await asyncio.shield(task)
            except asyncio.CancelledError:
                token.set()
                try:
                    await asyncio.shield(task)
                except (Exception, asyncio.CancelledError):
                    pass
                output.unlink(missing_ok=True)
                raise
            except UpscaleCancelled as exc:
                output.unlink(missing_ok=True)
                raise ModelWorkerError(
                    "Upscaling cancelled",
                    code="generation_cancelled",
                    status_code=499,
                ) from exc
            except MemoryError as exc:
                output.unlink(missing_ok=True)
                raise ModelWorkerError(
                    str(exc), code="resource_exhausted", status_code=503
                ) from exc
            except (ValueError, OSError) as exc:
                output.unlink(missing_ok=True)
                raise ModelWorkerError(
                    str(exc), code="invalid_image" if is_image else "invalid_video"
                ) from exc
            except Exception:
                output.unlink(missing_ok=True)
                raise
            finally:
                self._tokens.pop(request.request_id, None)
        return ModelWorkerArtifact(
            path=output,
            media_type="image/png" if is_image else "video/mp4",
            filename="upscaled.png" if is_image else "upscaled.mp4",
            metadata=metadata,
        )


def create_adapter(context):
    return SoLRefinerAdapter(context)
