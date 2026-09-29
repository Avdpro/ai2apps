"""Independent Tail/L1/SSD execution engine for Qwen3.6 Cache-MoE."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from functools import partial
from typing import Any

from .base import GenerationOutput
from .batched import BatchedEngine
from .ssd_telemetry import SsdPressureTelemetry


class Qwen36TieredEngine(BatchedEngine):
    """Serialized exact engine with a small Tail execution bank and L1 backing."""

    supports_kv_continuity = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tiered_lock = asyncio.Lock()
        self._scope_policy: Any | None = None
        self._qwen_adaptive: Any | None = None
        self._qwen_selector: Any | None = None
        self._qwen_last_selection: Any | None = None
        self._ssd_routed_bytes_per_token = 0
        self._ssd_telemetry = SsdPressureTelemetry(self._ssd_storage_totals)
        from ..patches.qwen3_6_flesh.boost import Qwen36BoostController

        self._qwen_boost = Qwen36BoostController(self)

    def _ssd_storage_totals(self) -> tuple[int, int, int]:
        if self._scope_policy is None:
            return 0, 0, 0
        from ..patches.qwen3_6_flesh.scope_cache import (
            get_qwen36_fallback_loader,
        )
        from ..patches.qwen3_6_flesh.tiered_cache import get_qwen36_tiered_cache

        path = str(self._scope_policy.store_path)
        tiered = get_qwen36_tiered_cache(path).stats()
        fallback = get_qwen36_fallback_loader(path).stats()
        return (
            int(tiered.get("ssd_experts_loaded", 0))
            + int(fallback.get("experts_loaded", 0)),
            int(tiered.get("bytes_loaded", 0))
            + int(fallback.get("bytes_loaded", 0)),
            self._ssd_routed_bytes_per_token,
        )

    def _between_decode_step(self, output: Any) -> None:
        self._qwen_adaptive.between_step(output)
        self._ssd_telemetry.record_scheduler_output(output)

    def _between_prefill_chunk(self, request: Any, **kwargs: Any) -> None:
        self._qwen_adaptive.between_prefill_chunk(request, **kwargs)
        if int(kwargs.get("remaining_tokens", -1)) == 0:
            session_id = self._qwen_boost.session_id
            if session_id is not None:
                self._ssd_telemetry.reset(session_id)

    async def start(self) -> None:
        await super().start()
        if self._scope_policy is not None:
            return
        from ..patches.qwen3_6_flesh.scope_policy import load_qwen36_scope_policy

        policy = load_qwen36_scope_policy()
        if policy is None or policy.backend != "tiered":
            raise RuntimeError("Qwen36TieredEngine requires the tiered scope backend")
        from ..patches.qwen3_6_flesh.tiered_cache import get_qwen36_tiered_cache

        cache = get_qwen36_tiered_cache(str(policy.store_path))
        for decoder in self._model.language_model.model.layers:
            cache.prepare_switch_backing(decoder.mlp.tail_switch_mlp)
        self._scope_policy = policy
        from ..patches.qwen3_6_flesh.adaptive_l1 import Qwen36AdaptiveController

        self._qwen_adaptive = Qwen36AdaptiveController(self, policy)
        self._qwen_adaptive.start()
        from ..patches.qwen3_6_flesh.scope_cache import (
            get_qwen36_fallback_loader,
        )

        loader = get_qwen36_fallback_loader(str(policy.store_path))
        self._ssd_routed_bytes_per_token = sum(
            int(loader.expert_record_bytes(int(decoder.mlp.scope_layer)))
            * int(decoder.mlp.top_k)
            for decoder in self._model.language_model.model.layers
            if getattr(decoder.mlp, "scope_policy", None) is not None
        )
        core = self._engine.engine
        core._between_decode_step_callback = self._between_decode_step
        core.scheduler._prefill_chunk_callback = self._between_prefill_chunk
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
        policy = self._scope_policy
        session_id = str(kwargs.get("flesh_session_id", "default"))
        kv_policy = str(kwargs.pop("flesh_kv_policy", "strict")).lower()
        if kv_policy not in {"strict", "session", "persistent"}:
            raise ValueError(f"unsupported Qwen KV continuity policy: {kv_policy}")
        override = kwargs.pop("flesh_scope", None)
        token_ids = (
            list(prompt)
            if isinstance(prompt, list)
            else self._tokenizer.encode(prompt, add_special_tokens=False)
        )
        existing_scope = self._qwen_adaptive.session_scope(session_id)
        if existing_scope is not None:
            scope = existing_scope
            self._qwen_last_selection = None
        elif override is not None:
            scope = str(override)
            self._qwen_last_selection = None
        else:
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
        session_id, boost = await self._qwen_boost.prepare(
            kwargs, context_tokens=len(token_ids)
        )
        self._ssd_telemetry.reset(session_id)
        adaptive_keys = await self._qwen_adaptive.prepare(
            kwargs, scope_name=scope
        )
        if kv_policy == "strict":
            kwargs["cache_extra_keys"] = (
                "qwen3.6-tiered-v1",
                scope,
                f"top{policy.resident_experts}",
                f"tail{policy.arena_tail_slots}",
                f"prefill-boost-{boost}",
                "session",
                session_id,
                *adaptive_keys,
            )
        else:
            kwargs["cache_extra_keys"] = (
                "qwen3.6-tiered-kvc-v1",
                kv_policy,
                session_id,
            )
        kwargs["kv_cache_policy"] = kv_policy

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        async with self._tiered_lock:
            await self.start()
            await self._prepare_request(prompt, kwargs)
            return await super().generate(prompt, *args, **kwargs)

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        async with self._tiered_lock:
            await self.start()
            await self._prepare_request(prompt, kwargs)
            async for output in super().stream_generate(prompt, *args, **kwargs):
                yield output

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._scope_policy is not None:
            from ..patches.qwen3_6_flesh.scope_cache import (
                get_qwen36_fallback_loader,
            )
            from ..patches.qwen3_6_flesh.tiered_cache import (
                get_qwen36_tiered_cache,
            )

            policy = self._scope_policy
            stats["flesh"] = {
                "family": "qwen3.6",
                "scope": self._qwen_adaptive.current_scope,
                "configured_scope": policy.scope_name,
                "active_scope": self._qwen_adaptive.current_scope,
                "selector": {
                    "policy": "session-initial",
                    **self._qwen_selector.stats(),
                },
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
                "tail_experts": policy.arena_tail_slots,
                "phase": "tiered-l0-boost-v1",
                "tiered": get_qwen36_tiered_cache(str(policy.store_path)).stats(),
                "expert_store": get_qwen36_fallback_loader(
                    str(policy.store_path)
                ).stats(),
                "adaptive_l1": self._qwen_adaptive.stats(),
                "engine_boost": self._qwen_boost.stats(),
                **self._ssd_telemetry.stats(),
            }
        return stats

    def get_live_metrics(self, session_id: str | None = None) -> dict[str, Any]:
        return self._ssd_telemetry.live(session_id)

    def request_l1_optimization(self, session_id: str) -> dict[str, Any]:
        if self._qwen_adaptive is None:
            return {"accepted": False, "reason": "engine_not_started"}
        return self._qwen_adaptive.request(session_id)

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        return self._qwen_boost.request(session_id, mode)


__all__ = ["Qwen36TieredEngine"]
