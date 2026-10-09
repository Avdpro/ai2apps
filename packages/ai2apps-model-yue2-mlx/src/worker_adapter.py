"""Text-to-music/effects adapter: only Host-granted checkpoints and output files."""

from __future__ import annotations

import asyncio
import os

os.environ["MLX_ENABLE_TF32"] = "0"
import inspect
import threading
from contextlib import suppress

from ai2apps.model_worker import ModelWorkerArtifact, ModelWorkerError
from ai2apps.model_worker.audio_generation import validate_audio_generation


class AudioAdapter:
    def __init__(self, context, *, engine=None):
        self.context = context
        self.engine = engine
        self.tokens = {}
        self.early_cancel = set()
        self.stopping = False
        self.lock = asyncio.Lock()

    async def start(self):
        self.stopping = False

    async def stop(self):
        self.stopping = True
        for token in self.tokens.values():
            token.set()
        async with self.lock:
            self.early_cancel.clear()

    def cancel(self, request_id):
        if request_id in self.tokens:
            self.tokens[request_id].set()
        else:
            self.early_cancel.add(request_id)

    async def invoke(self, request):
        if request.operation != "audio_generate":
            raise ModelWorkerError(
                "Unsupported operation", code="operation_not_supported", status_code=400
            )
        p = validate_audio_generation(request.payload, has_parts=bool(request.parts))
        model = next(
            (
                m
                for m in self.context.models
                if p["model"] in (m["id"], m.get("upstream_id"))
            ),
            None,
        )
        if model is None:
            raise ModelWorkerError(
                "Unknown model", code="model_not_found", status_code=404
            )
        if model.get("metadata", {}).get("internal"):
            raise ModelWorkerError("Internal checkpoint is not callable", code="operation_not_supported", status_code=400)
        config = model["metadata"]["audio_generation"]
        g = p.get("generation", {})
        if (model["id"] != "ai2apps.model.yue2-mlx/default"
            or p.get("schema") != "ai2apps.audio-generation/v2"
            or p.get("duration_mode") != "auto" or p["task"] != "music"
            or g.get("planning_mode", "full") not in config["planning_modes"]
            or type(g.get("max_semantic_tokens")) is not int
            or not 1 <= g["max_semantic_tokens"] <= 3000):
            raise ModelWorkerError("Unsupported song workflow", code="invalid_audio_generation", status_code=400)
        checkpoint = self.context.checkpoint_for(model["id"])
        if (
            checkpoint is None
            or checkpoint.path is None
            or not checkpoint.path.is_dir()
        ):
            raise ModelWorkerError(
                "Prepare the declared checkpoint first",
                code="checkpoint_not_ready",
                status_code=409,
            )
        vae = self.context.checkpoint_for("ai2apps.model.yue2-mlx/vae")
        if vae is None or vae.path is None or not vae.path.is_dir():
            raise ModelWorkerError("Prepare the required VAE checkpoint", code="checkpoint_not_ready", status_code=409)
        if request.output_root is None:
            raise ModelWorkerError(
                "Missing controlled output root",
                code="runtime_protocol_error",
                status_code=500,
            )
        token = threading.Event()
        self.tokens[request.request_id] = token
        if request.request_id in self.early_cancel:
            self.early_cancel.remove(request.request_id)
            token.set()

        def check():
            if token.is_set() or self.stopping:
                raise ModelWorkerError(
                    "Generation cancelled", code="generation_cancelled", status_code=499
                )

        async def progress(phase, current=0, total=1):
            if request.progress:
                r = request.progress(
                    {"phase": phase, "current": current, "total": total}
                )
                if inspect.isawaitable(r):
                    await r

        loop = asyncio.get_running_loop()

        def report(phase, current=0, total=1):
            check()
            asyncio.run_coroutine_threadsafe(
                progress(phase, current, total), loop
            ).result(timeout=10)

        output = request.output_root / "audio.wav"
        try:
            async with self.lock:
                check()
                await progress("loading")
                if self.engine is None:
                    from engine import generate

                    engine = generate
                else:
                    engine = self.engine
                job = asyncio.create_task(
                    asyncio.to_thread(
                        engine, (checkpoint.path, vae.path), config, p, output, check, report
                    )
                )
                try:
                    await asyncio.shield(job)
                except asyncio.CancelledError:
                    token.set()
                    with suppress(BaseException):
                        await asyncio.shield(job)
                    raise
                check()
                await progress("complete", 1, 1)
                return ModelWorkerArtifact(output, "audio/wav", "audio.wav")
        finally:
            self.tokens.pop(request.request_id, None)
            self.early_cancel.discard(request.request_id)


def create_adapter(context):
    return AudioAdapter(context)
