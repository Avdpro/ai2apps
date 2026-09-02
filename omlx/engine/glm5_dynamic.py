"""Serialized, session-aware VLM engine for GLM-5 dynamic Cache-MoE."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from .base import GenerationOutput
from .vlm import VLMBatchedEngine


class Glm5DynamicVLMEngine(VLMBatchedEngine):
    """Bind Engine Boost and prefix-KV identity to the system session."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._glm5_lock = asyncio.Lock()
        self._glm5_boost = None
        self._glm5_sessions = None

    async def start(self) -> None:
        await super().start()
        integrated_mtp = getattr(self._vlm_model.language_model, "mtp", None)
        if integrated_mtp is not None and self.vlm_mtp_drafter is None:
            from ..speculative.vlm_mtp import VLMMTPDrafter

            if (
                self._model_settings is not None
                and getattr(
                    self._model_settings, "vlm_mtp_draft_block_size", None
                )
                is None
            ):
                # Block=2 keeps every target verifier token inside Hot16 and
                # was faster than block=3 on the GLM Cache-MoE path. Explicit
                # user/model settings still take precedence.
                self._model_settings.vlm_mtp_draft_block_size = 2
            self.set_vlm_mtp_drafter(
                VLMMTPDrafter(integrated_mtp, "mtp", "integrated-layer-45")
            )
        if self._glm5_boost is None:
            from ..patches.glm5_next_cache.boost import Glm5BoostController
            from ..patches.glm5_next_cache.session_cache import (
                Glm5SessionCacheController,
            )

            self._glm5_boost = Glm5BoostController(self)
            self._glm5_sessions = Glm5SessionCacheController(self)
            core = self._engine.engine
            core._between_decode_step_callback = (
                self._glm5_boost.on_scheduler_step
            )
            core.scheduler._prefill_chunk_callback = (
                self._glm5_boost.between_prefill_chunk
            )

    async def _prepare_glm5(
        self, prompt: str | list[int], kwargs: dict[str, Any]
    ) -> None:
        token_count = (
            len(prompt)
            if isinstance(prompt, list)
            else len(self._tokenizer.encode(prompt, add_special_tokens=False))
        )
        session_id, prefill_mode = await self._glm5_boost.prepare(
            kwargs, context_tokens=token_count
        )
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self._engine.engine._mlx_executor,
            self._glm5_sessions.prepare,
            session_id,
        )
        kv_policy = str(kwargs.pop("flesh_kv_policy", "session")).lower()
        if kv_policy not in {"strict", "session", "persistent"}:
            raise ValueError(f"unsupported GLM-5 KV continuity policy: {kv_policy}")
        existing = tuple(kwargs.get("cache_extra_keys") or ())
        kwargs["cache_extra_keys"] = (
            *existing,
            "glm5-dynamic-v1",
            f"boost-{prefill_mode}",
            "session",
            session_id,
        )
        kwargs["kv_cache_policy"] = kv_policy

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        async with self._glm5_lock:
            await self.start()
            await self._prepare_glm5(prompt, kwargs)
            session_id = str(kwargs.get("flesh_session_id", "default"))
            try:
                return await super().generate(prompt, *args, **kwargs)
            finally:
                self._glm5_sessions.finish(session_id)

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        async with self._glm5_lock:
            await self.start()
            await self._prepare_glm5(prompt, kwargs)
            session_id = str(kwargs.get("flesh_session_id", "default"))
            try:
                async for output in super().stream_generate(prompt, *args, **kwargs):
                    yield output
            finally:
                self._glm5_sessions.finish(session_id)

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        if self._glm5_boost is None:
            return {"accepted": False, "reason": "engine_not_started"}
        return self._glm5_boost.request(session_id, mode)

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._glm5_boost is not None:
            stats["engine_boost"] = self._glm5_boost.stats()
        if self._glm5_sessions is not None:
            stats["session_l1"] = self._glm5_sessions.stats()
        return stats


__all__ = ["Glm5DynamicVLMEngine"]
