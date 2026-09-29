"""Session-aware Boost wrapper for Qwen4-Exp Cached-MoE VLMs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .base import GenerationOutput
from .ssd_telemetry import SsdPressureTelemetry
from .vlm import VLMBatchedEngine


class Qwen4DynamicVLMEngine(VLMBatchedEngine):
    """Bind Qwen3.8 Next Boost policy to request and Decode boundaries."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._qwen4_lock = asyncio.Lock()
        self._qwen4_boost = None
        self._ssd_telemetry = SsdPressureTelemetry(self._ssd_storage_totals)

    def _moe_blocks(self) -> list[Any]:
        model = getattr(self, "_vlm_model", None)
        if model is None:
            return []
        inner = getattr(model.language_model, "model", model.language_model)
        return [
            decoder.mlp
            for decoder in getattr(inner, "layers", ())
            if getattr(decoder.mlp, "dynamic_cache", None) is not None
        ]

    def _ssd_storage_totals(self) -> tuple[int, int, int]:
        blocks = self._moe_blocks()
        if not blocks:
            return 0, 0, 0
        cache = blocks[0].dynamic_cache
        cache_stats = cache.stats()
        routed_bytes = 0
        for block in blocks:
            store = cache._stores.get(int(block.dynamic_layer))
            if store is not None:
                routed_bytes += int(store.record_bytes) * int(block.top_k)
        return (
            int(cache_stats.get("experts_loaded", 0)),
            int(cache_stats.get("bytes_loaded", 0)),
            routed_bytes,
        )

    def _between_decode_step(self, output: Any) -> None:
        self._qwen4_boost.on_scheduler_step(output)
        self._ssd_telemetry.record_scheduler_output(output)

    def _between_prefill_chunk(self, request: Any, **kwargs: Any) -> None:
        self._qwen4_boost.between_prefill_chunk(request, **kwargs)
        if int(kwargs.get("remaining_tokens", -1)) == 0:
            session_id = self._qwen4_boost.session_id
            if session_id is not None:
                self._ssd_telemetry.reset(session_id)

    async def start(self) -> None:
        await super().start()
        if self._qwen4_boost is not None:
            return
        from ..patches.qwen38_next_cache.boost import Qwen4BoostController

        self._qwen4_boost = Qwen4BoostController(self)
        core = self._engine.engine
        core._between_decode_step_callback = self._between_decode_step
        core.scheduler._prefill_chunk_callback = self._between_prefill_chunk

    async def _prepare_qwen4(
        self, prompt: str | list[int], kwargs: dict[str, Any]
    ) -> None:
        token_count = (
            len(prompt)
            if isinstance(prompt, list)
            else len(self._tokenizer.encode(prompt, add_special_tokens=False))
        )
        session_id, prefill_mode = await self._qwen4_boost.prepare(
            kwargs, context_tokens=token_count
        )
        self._ssd_telemetry.reset(session_id)
        existing = tuple(kwargs.get("cache_extra_keys") or ())
        kwargs["cache_extra_keys"] = (
            *existing,
            "qwen4-dynamic-boost-v1",
            f"prefill-boost-{prefill_mode}",
            "session",
            session_id,
        )

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        async with self._qwen4_lock:
            await self.start()
            await self._prepare_qwen4(prompt, kwargs)
            return await super().generate(prompt, *args, **kwargs)

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        async with self._qwen4_lock:
            await self.start()
            await self._prepare_qwen4(prompt, kwargs)
            async for output in super().stream_generate(prompt, *args, **kwargs):
                yield output

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        if self._qwen4_boost is None:
            return {"accepted": False, "reason": "engine_not_started"}
        return self._qwen4_boost.request(session_id, mode)

    def get_live_metrics(self, session_id: str | None = None) -> dict[str, Any]:
        return self._ssd_telemetry.live(session_id)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._qwen4_boost is not None:
            stats["engine_boost"] = self._qwen4_boost.stats()
        stats["flesh"] = {"family": "qwen4-exp", **self._ssd_telemetry.stats()}
        return stats


__all__ = ["Qwen4DynamicVLMEngine"]
