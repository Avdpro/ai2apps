"""Session-aware Boost wrapper for Qwen3.6-family Cached-MoE VLMs."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .base import GenerationOutput
from .ssd_telemetry import SsdPressureTelemetry
from .vlm import VLMBatchedEngine


class Qwen36DynamicVLMEngine(VLMBatchedEngine):
    """Apply Qwen3.6 Boost to multimodal Cached-MoE scheduler boundaries."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._qwen36_lock = asyncio.Lock()
        self._qwen_boost = None
        self._ssd_routed_bytes_per_token = 0
        self._ssd_telemetry = SsdPressureTelemetry(self._ssd_storage_totals)

    def _moe_blocks(self) -> list[Any]:
        model = getattr(self, "_vlm_model", None)
        if model is None:
            return []
        inner = getattr(model.language_model, "model", model.language_model)
        return [
            decoder.mlp
            for decoder in getattr(inner, "layers", ())
            if getattr(decoder.mlp, "scope_policy", None) is not None
        ]

    def _ssd_storage_totals(self) -> tuple[int, int, int]:
        blocks = self._moe_blocks()
        if not blocks:
            return 0, 0, 0
        policy = blocks[0].scope_policy
        from ..patches.qwen3_6_flesh.scope_cache import (
            get_qwen36_fallback_loader,
        )
        from ..patches.qwen3_6_flesh.tiered_cache import get_qwen36_tiered_cache

        tiered = get_qwen36_tiered_cache(str(policy.store_path)).stats()
        fallback = get_qwen36_fallback_loader(str(policy.store_path)).stats()
        return (
            int(tiered.get("ssd_experts_loaded", 0))
            + int(fallback.get("experts_loaded", 0)),
            int(tiered.get("bytes_loaded", 0))
            + int(fallback.get("bytes_loaded", 0)),
            self._ssd_routed_bytes_per_token,
        )

    def _between_decode_step(self, output: Any) -> None:
        self._qwen_boost.between_step()
        self._ssd_telemetry.record_scheduler_output(output)

    async def start(self) -> None:
        await super().start()
        if self._qwen_boost is not None:
            return
        from ..patches.qwen3_6_flesh.boost import Qwen36BoostController

        self._qwen_boost = Qwen36BoostController(self)
        blocks = self._moe_blocks()
        if blocks:
            from ..patches.qwen3_6_flesh.scope_cache import (
                get_qwen36_fallback_loader,
            )

            policy = blocks[0].scope_policy
            loader = get_qwen36_fallback_loader(str(policy.store_path))
            self._ssd_routed_bytes_per_token = sum(
                int(loader.expert_record_bytes(int(block.scope_layer)))
                * int(block.top_k)
                for block in blocks
            )
        core = self._engine.engine
        core._between_decode_step_callback = self._between_decode_step
        core.scheduler._prefill_chunk_callback = self._between_prefill_chunk

    def _between_prefill_chunk(
        self,
        request: Any,
        *,
        tokens: int,
        processed_tokens: int,
        remaining_tokens: int,
    ) -> None:
        del request, tokens, processed_tokens
        if remaining_tokens == 0:
            self._qwen_boost.complete_prefill()
            if self._qwen_boost.session_id is not None:
                self._ssd_telemetry.reset(self._qwen_boost.session_id)

    async def _prepare_qwen36(
        self, prompt: str | list[int], kwargs: dict[str, Any]
    ) -> None:
        token_count = (
            len(prompt)
            if isinstance(prompt, list)
            else len(self._tokenizer.encode(prompt, add_special_tokens=False))
        )
        session_id, prefill_mode = await self._qwen_boost.prepare(
            kwargs, context_tokens=token_count
        )
        self._ssd_telemetry.reset(session_id)
        existing = tuple(kwargs.get("cache_extra_keys") or ())
        kwargs["cache_extra_keys"] = (
            *existing,
            "qwen3.6-vlm-boost-v1",
            f"prefill-boost-{prefill_mode}",
            "session",
            session_id,
        )

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        async with self._qwen36_lock:
            await self.start()
            await self._prepare_qwen36(prompt, kwargs)
            return await super().generate(prompt, *args, **kwargs)

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        async with self._qwen36_lock:
            await self.start()
            await self._prepare_qwen36(prompt, kwargs)
            async for output in super().stream_generate(prompt, *args, **kwargs):
                yield output

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        if self._qwen_boost is None:
            return {"accepted": False, "reason": "engine_not_started"}
        return self._qwen_boost.request(session_id, mode)

    def get_live_metrics(self, session_id: str | None = None) -> dict[str, Any]:
        return self._ssd_telemetry.live(session_id)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._qwen_boost is not None:
            stats["engine_boost"] = self._qwen_boost.stats()
        stats["flesh"] = {"family": "qwen3.6", **self._ssd_telemetry.stats()}
        return stats


__all__ = ["Qwen36DynamicVLMEngine"]
