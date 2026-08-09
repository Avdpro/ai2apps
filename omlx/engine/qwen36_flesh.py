"""Dedicated Qwen3.6 Flesh serving engine."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from functools import partial
from typing import Any

from .base import GenerationOutput
from .batched import BatchedEngine


class Qwen36FleshEngine(BatchedEngine):
    """Serialized Qwen3.6 Cache-MoE engine with session-owned Engine Boost."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._qwen_flesh_lock = asyncio.Lock()
        self._qwen_scope_policy: Any | None = None
        self._qwen_adaptive: Any | None = None
        self._qwen_selector: Any | None = None
        self._qwen_last_selection: Any | None = None
        from ..patches.qwen3_6_flesh.boost import Qwen36BoostController

        self._qwen_boost = Qwen36BoostController(self)

    async def start(self) -> None:
        await super().start()
        if self._qwen_scope_policy is not None:
            return
        from ..patches.qwen3_6_flesh.scope_policy import load_qwen36_scope_policy

        policy = load_qwen36_scope_policy()
        if policy is None:
            raise RuntimeError("Qwen36FleshEngine requires a Qwen Scope Pack")
        self._qwen_scope_policy = policy
        from ..patches.qwen3_6_flesh.adaptive_l1 import Qwen36AdaptiveController

        self._qwen_adaptive = Qwen36AdaptiveController(self, policy)
        self._qwen_adaptive.start()
        from ..patches.qwen3_6_flesh.scope_runtime import Qwen36ScopeSelector

        self._qwen_selector = Qwen36ScopeSelector(
            self._model,
            policy.catalog,
            resident_experts=policy.resident_experts,
            depth=int(os.environ.get("OMLX_QWEN36_SCOPE_PROBE_DEPTH", "8")),
            max_tokens=int(
                os.environ.get("OMLX_QWEN36_SCOPE_PROBE_MAX_TOKENS", "1024")
            ),
            stream=self._engine.engine.scheduler._stream,
        )

    async def _prepare_request(
        self, prompt: str | list[int], kwargs: dict[str, Any]
    ) -> None:
        policy = self._qwen_scope_policy
        override = kwargs.pop("flesh_scope", None)
        if override is None:
            token_ids = (
                list(prompt)
                if isinstance(prompt, list)
                else self._tokenizer.encode(prompt, add_special_tokens=False)
            )
            threshold = float(
                os.environ.get("OMLX_QWEN36_SCOPE_PROBE_MARGIN", "0.010")
            )
            loop = asyncio.get_running_loop()
            selection = await loop.run_in_executor(
                self._engine.engine._mlx_executor,
                partial(
                    self._qwen_selector.select_cascade,
                    token_ids,
                    margin_threshold=threshold,
                ),
            )
            scope = selection.scope
            self._qwen_last_selection = selection
        else:
            scope = str(override)
            self._qwen_last_selection = None
        session_id, boost = await self._qwen_boost.prepare(kwargs)
        adaptive_keys = await self._qwen_adaptive.prepare(
            kwargs, scope_name=scope
        )
        kwargs["cache_extra_keys"] = (
            "qwen3.6-flesh-v1",
            scope,
            f"top{policy.resident_experts}",
            "session",
            session_id,
            *adaptive_keys,
        )

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        async with self._qwen_flesh_lock:
            await self.start()
            await self._prepare_request(prompt, kwargs)
            return await super().generate(prompt, *args, **kwargs)

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        async with self._qwen_flesh_lock:
            await self.start()
            await self._prepare_request(prompt, kwargs)
            async for output in super().stream_generate(prompt, *args, **kwargs):
                yield output

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._qwen_scope_policy is not None:
            from ..patches.qwen3_6_flesh.scope_cache import (
                get_qwen36_fallback_loader,
            )

            policy = self._qwen_scope_policy
            loader = get_qwen36_fallback_loader(str(policy.store_path))
            stats["flesh"] = {
                "family": "qwen3.6",
                "scope": self._qwen_adaptive.current_scope,
                "configured_scope": policy.scope_name,
                "active_scope": self._qwen_adaptive.current_scope,
                "selector": self._qwen_selector.stats(),
                "last_selection": (
                    {
                        "scope": self._qwen_last_selection.scope,
                        "margin": self._qwen_last_selection.margin,
                        "top3": list(self._qwen_last_selection.top3),
                        "method": self._qwen_last_selection.method,
                        "shared_margin": self._qwen_last_selection.shared_margin,
                        "seconds": self._qwen_last_selection.seconds,
                    }
                    if self._qwen_last_selection is not None
                    else None
                ),
                "resident_experts": policy.resident_experts,
                "phase": "scope-cache-boost-v1",
                "expert_store": loader.stats(),
                "adaptive_l1": self._qwen_adaptive.stats(),
                "engine_boost": self._qwen_boost.stats(),
            }
        return stats

    def request_l1_optimization(self, session_id: str) -> dict[str, Any]:
        if self._qwen_adaptive is None:
            return {"accepted": False, "reason": "engine_not_started"}
        return self._qwen_adaptive.request(session_id)

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        return self._qwen_boost.request(session_id, mode)


__all__ = ["Qwen36FleshEngine"]
