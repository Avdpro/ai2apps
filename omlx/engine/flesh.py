"""DeepSeek V4 Flesh backend for the standard oMLX/DynaMoe serving surface."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from .base import GenerationOutput
from .batched import BatchedEngine

logger = logging.getLogger(__name__)

_BOOST_TO_LOSSY = {
    "natural": "exact",
    "turbo": "tail2",
    "blast": "head2",
}
_LOSSY_TO_BOOST = {
    "": "natural",
    "exact": "natural",
    "off": "natural",
    "0": "natural",
    "tail2": "turbo",
    "aggressive-2": "turbo",
    "aggressive2": "turbo",
    "head2": "blast",
    "protect2": "blast",
}

# Model-normalized thresholds. For DeepSeek V4 (40 routed layers × Top-6),
# these are equivalent to about 400 and 600 same-size experts per 10 tokens.
_SSD_ELEVATED_PRESSURE = 1.0 / 6.0
_SSD_CRITICAL_PRESSURE = 0.25


class DeepseekV4FleshEngine(BatchedEngine):
    """Scope-selecting DeepSeek V4 engine with session-safe KV namespaces.

    Requests are deliberately serialized across scope selection, bank
    activation, and generation. The physical expert residency is mutable
    model-wide state; one active inference makes current Top60 banks safe and
    also leaves room for future access-driven L1 promotion/eviction. The outer
    oMLX EnginePool can still serve other model types concurrently.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._flesh_lock = asyncio.Lock()
        self._scope_selector: Any | None = None
        self._scope_bank: Any | None = None
        self._last_scope_selection: Any | None = None
        self._adaptive_l1: Any | None = None
        self._adaptive_state: Any | None = None
        self._adaptive_window_started = 0.0
        self._adaptive_window_token = 0
        self._adaptive_window_stats: dict[str, Any] | None = None
        self._adaptive_early_checked = False
        self._adaptive_last_token = 0
        self._adaptive_turn_started = 0.0
        self._adaptive_turn_stats: dict[str, Any] | None = None
        self._adaptive_turn_miss_steps = 0
        self._adaptive_turn_scored_steps = 0
        self._adaptive_turn_miss_routes = 0
        self._adaptive_turn_routes = 0
        self._maintenance_tasks: set[asyncio.Task[Any]] = set()
        self._last_decode_tail: dict[str, Any] | None = None
        # The product default is always exact. Legacy lossy environment flags
        # remain useful to low-level benchmark scripts, but must not silently
        # put an API/WebUI session into an approximate mode.
        self._default_boost_mode = "natural"
        self._engine_boost_mode = self._default_boost_mode
        self._engine_boost_session_id: str | None = None
        self._engine_boost_modes: dict[str, str] = {}
        self._pending_engine_boost: dict[str, str] = {}
        self._session_owned_kv: set[str] = set()
        self._engine_boost_lock = threading.Lock()
        self._engine_boost_switches = 0
        self._routed_expert_bytes_per_token = 0
        self._ssd_window_samples: deque[tuple[int, int, int]] = deque(maxlen=32)
        self._ssd_recent_10_tokens = {
            "tokens": 0,
            "expert_loads": 0,
            "bytes_loaded": 0,
            "pressure": 0.0,
            "pressure_percent": 0.0,
            "severity": "healthy",
        }
        self._ssd_window_session_id: str | None = None
        self._ssd_recent_by_session: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        await super().start()
        if self._scope_selector is not None:
            return

        from ..patches.deepseek_v4.scope_cache import get_scope_fallback_loader
        from ..patches.deepseek_v4.scope_policy import (
            load_scope_policy_from_env,
            load_scope_probe_depth_from_env,
        )
        from ..patches.deepseek_v4.scope_runtime import (
            DeepseekV4ScopeBank,
            DeepseekV4ScopeSelector,
            ScopeCatalog,
        )
        from ..patches.deepseek_v4.adaptive_l1 import (
            AdaptiveL1Config,
            AdaptiveL1Manager,
        )

        policy = load_scope_policy_from_env()
        if policy is None:
            raise RuntimeError(
                "DeepseekV4FleshEngine requires scope profile, name, and store"
            )
        raw_max = os.environ.get(
            "OMLX_DEEPSEEK_V4_SCOPE_PROBE_MAX_TOKENS", "1024"
        ).strip()
        try:
            max_tokens = int(raw_max)
        except ValueError as exc:
            raise ValueError(
                "OMLX_DEEPSEEK_V4_SCOPE_PROBE_MAX_TOKENS must be an integer"
            ) from exc
        if not 8 <= max_tokens <= 4096:
            raise ValueError(
                "OMLX_DEEPSEEK_V4_SCOPE_PROBE_MAX_TOKENS must be 8..4096"
            )

        core = self._engine.engine
        stream = core.scheduler._stream
        catalog = ScopeCatalog.load(
            policy.profile_path, resident_experts=policy.resident_experts
        )
        loader = get_scope_fallback_loader(str(policy.store_path))

        def initialize() -> tuple[Any, Any, int]:
            selector = DeepseekV4ScopeSelector(
                self._model,
                catalog,
                depth=load_scope_probe_depth_from_env(),
                max_tokens=max_tokens,
                stream=stream,
            )
            bank = DeepseekV4ScopeBank(
                self._model,
                catalog,
                loader,
                policy.scope_name,
            )
            target = getattr(self._model, "model", self._model)
            routed_bytes = 0
            for layer, block in enumerate(target.layers):
                ffn = getattr(block, "ffn", None)
                gate = getattr(ffn, "gate", None)
                top_k = int(getattr(gate, "top_k", 0))
                if layer >= 3 and top_k > 0 and hasattr(ffn, "scope_expert_ids"):
                    routed_bytes += loader.expert_record_bytes(layer) * top_k
            return selector, bank, routed_bytes

        loop = asyncio.get_running_loop()
        (
            self._scope_selector,
            self._scope_bank,
            self._routed_expert_bytes_per_token,
        ) = await loop.run_in_executor(
            core._mlx_executor, initialize
        )
        adaptive_config = AdaptiveL1Config.from_env()
        if adaptive_config.enabled:
            self._adaptive_l1 = AdaptiveL1Manager(catalog, adaptive_config)
            # Route utility is accumulated asynchronously on device and read
            # only at policy checkpoints. The legacy host miss observer would
            # double-count non-resident experts, so leave it disconnected.
            loader.set_decode_miss_observer(None)
        # Engine Boost uses the same scheduler-safe boundary even when
        # adaptive L1 itself is disabled.
        core._between_decode_step_callback = self._between_decode_step
        logger.info(
            "DeepSeek V4 Flesh ready: scopes=%d initial=%s probe_depth=%d",
            len(catalog.scope_ids),
            policy.scope_name,
            self._scope_selector.depth,
        )

    async def _prepare_scope(
        self,
        prompt: str | list[int],
        override: str | None = None,
        session_id: str = "default",
        l1_mode: str = "auto",
        boost_mode: str | None = None,
    ) -> str:
        await self.start()
        token_ids = (
            list(prompt)
            if isinstance(prompt, list)
            else self._tokenizer.encode(prompt, add_special_tokens=False)
        )
        core = self._engine.engine
        loop = asyncio.get_running_loop()
        if override is None:
            selection = await loop.run_in_executor(
                core._mlx_executor, self._scope_selector.select, token_ids
            )
            scope = selection.scope
            self._last_scope_selection = selection
        else:
            scope = override
            self._last_scope_selection = None
        if self._adaptive_l1 is None:
            await loop.run_in_executor(
                core._mlx_executor, self._scope_bank.activate, scope
            )
        else:
            self._adaptive_state = self._adaptive_l1.begin(
                session_id, scope, mode=l1_mode
            )
            await loop.run_in_executor(
                core._mlx_executor,
                self._scope_bank.activate_layout,
                scope,
                self._adaptive_state.layout,
            )
            self._adaptive_window_started = time.perf_counter()
            self._adaptive_window_token = 0
            self._adaptive_window_stats = self._scope_bank.loader.stats()
            self._adaptive_early_checked = False
            self._adaptive_last_token = 0
            self._adaptive_turn_started = time.perf_counter()
            self._adaptive_turn_stats = self._scope_bank.loader.stats()
            self._adaptive_turn_miss_steps = 0
            self._adaptive_turn_scored_steps = 0
            self._adaptive_turn_miss_routes = 0
            self._adaptive_turn_routes = 0
            self._scope_bank.loader.reset_route_telemetry(
                enabled=(
                    self._adaptive_state.mode == "auto"
                    or self._adaptive_l1.manual_pending(session_id)
                )
            )
        boost_mode = self._normalize_boost_mode(
            boost_mode or self._engine_boost_modes.get(
                session_id, self._default_boost_mode
            )
        )
        with self._engine_boost_lock:
            boost_mode = self._pending_engine_boost.pop(session_id, boost_mode)
        await loop.run_in_executor(
            core._mlx_executor, self._apply_engine_boost, session_id, boost_mode
        )
        self._reset_ssd_window(session_id)
        return scope

    @staticmethod
    def _cache_namespace(
        scope: str,
        fingerprint: str | None = None,
        boost_mode: str | None = None,
        session_id: str | None = None,
        session_owned: bool = False,
    ) -> tuple[str, ...]:
        if session_owned:
            if not session_id:
                raise ValueError("session_id is required for session-owned KV")
            # A conversation may legitimately contain KV produced before and
            # after a live policy/L1 change. Keep that lineage reusable inside
            # the owning Session without exposing it to unrelated prompts.
            return ("deepseek-v4-flesh-v1", scope, "session", session_id)
        if boost_mode is None:
            raw_lossy = os.environ.get(
                "OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE", "exact"
            ).strip().lower().replace("_", "-")
            boost_mode = _LOSSY_TO_BOOST.get(raw_lossy, "natural")
        lossy = _BOOST_TO_LOSSY[boost_mode]
        namespace: tuple[str, ...] = (
            "deepseek-v4-flesh-v1", scope, lossy or "exact"
        )
        # Exact fallback is invariant to physical residency. Lossy replacement
        # is not, so only approximate KV needs the adaptive bank fingerprint.
        if fingerprint and lossy not in ("", "exact", "off", "0"):
            namespace += (fingerprint,)
        return namespace

    @staticmethod
    def _normalize_boost_mode(mode: str) -> str:
        normalized = str(mode).strip().lower()
        if normalized not in _BOOST_TO_LOSSY:
            raise ValueError("Engine Boost must be natural, turbo, or blast")
        return normalized

    def _apply_engine_boost(self, session_id: str, mode: str) -> bool:
        """Publish a policy-only change on the MLX executor boundary."""

        from ..patches.deepseek_v4.scope_policy import (
            scope_lossy_policy_for_mode,
        )

        mode = self._normalize_boost_mode(mode)
        changed = mode != self._engine_boost_mode
        policy = scope_lossy_policy_for_mode(_BOOST_TO_LOSSY[mode])
        target = getattr(self._model, "model", self._model)
        for layer, block in enumerate(target.layers):
            if layer >= 3 and hasattr(block.ffn, "scope_lossy_policy"):
                block.ffn.scope_lossy_policy = policy
        self._engine_boost_mode = mode
        self._engine_boost_session_id = session_id
        self._engine_boost_modes[session_id] = mode
        if changed:
            self._engine_boost_switches += 1
            logger.info(
                "Engine Boost switched: session=%s mode=%s lossy=%s",
                session_id,
                mode,
                _BOOST_TO_LOSSY[mode],
            )
        return changed

    def request_engine_boost(self, session_id: str, mode: str) -> dict[str, Any]:
        """Queue a live-mode switch for the next scheduler-safe token boundary."""

        mode = self._normalize_boost_mode(mode)
        previous = self._engine_boost_modes.get(
            session_id, self._default_boost_mode
        )
        active = self._flesh_lock.locked() or (
            session_id == self._engine_boost_session_id
            and self.has_active_requests()
        )
        if mode != previous:
            self._session_owned_kv.add(session_id)
        self._engine_boost_modes[session_id] = mode
        if active:
            with self._engine_boost_lock:
                self._pending_engine_boost[session_id] = mode
        return {
            "accepted": True,
            "queued": active,
            "session_id": session_id,
            "mode": mode,
            "applies": "next_token" if active else "next_request",
        }

    def _session_cache_namespace(self, session_id: str) -> tuple[str, ...]:
        state = self._adaptive_state
        scope = (
            state.scope
            if state is not None and state.session_id == session_id
            else self._scope_bank.current_scope
        )
        return self._cache_namespace(
            scope, session_id=session_id, session_owned=True
        )

    def _promote_request_to_session_kv(
        self, request: Any | None, session_id: str
    ) -> None:
        """Keep mixed-policy KV reusable, but only by its owning Session."""

        self._session_owned_kv.add(session_id)
        if request is not None:
            request.cache_extra_keys = self._session_cache_namespace(session_id)

    def _reset_ssd_window(self, session_id: str) -> None:
        # Seed after scope activation; chunked-Prefill callbacks keep this
        # baseline fresh until Decode begins. ``experts_loaded`` then captures
        # transient (>Hot8) reads and adaptive-L1 rebuilds as well.
        stats = self._scope_bank.loader.stats()
        loads = int(stats["experts_loaded"])
        loaded_bytes = int(stats["bytes_loaded"])
        self._ssd_window_samples.clear()
        self._ssd_window_samples.append((0, loads, loaded_bytes))
        self._ssd_window_session_id = session_id
        self._ssd_recent_10_tokens = {
            "tokens": 0,
            "expert_loads": 0,
            "bytes_loaded": 0,
            "pressure": 0.0,
            "pressure_percent": 0.0,
            "severity": "healthy",
        }
        self._ssd_recent_by_session[session_id] = dict(
            self._ssd_recent_10_tokens
        )

    def _record_ssd_window(self, token_count: int) -> None:
        stats = self._scope_bank.loader.stats()
        loads = int(stats["experts_loaded"])
        loaded_bytes = int(stats["bytes_loaded"])
        if self._ssd_window_samples and self._ssd_window_samples[-1][0] == token_count:
            self._ssd_window_samples[-1] = (token_count, loads, loaded_bytes)
        else:
            self._ssd_window_samples.append((token_count, loads, loaded_bytes))
        cutoff = max(token_count - 10, 0)
        baseline_token, baseline_loads, baseline_bytes = self._ssd_window_samples[0]
        for sample_token, sample_loads, sample_bytes in self._ssd_window_samples:
            if sample_token > cutoff:
                break
            baseline_token, baseline_loads, baseline_bytes = (
                sample_token, sample_loads, sample_bytes
            )
        window_tokens = min(max(token_count - baseline_token, 0), 10)
        recent_loads = max(loads - baseline_loads, 0)
        recent_bytes = max(loaded_bytes - baseline_bytes, 0)
        routed_bytes = window_tokens * self._routed_expert_bytes_per_token
        pressure = recent_bytes / routed_bytes if routed_bytes > 0 else 0.0
        severity = (
            "critical" if pressure >= _SSD_CRITICAL_PRESSURE
            else "elevated" if pressure > _SSD_ELEVATED_PRESSURE
            else "healthy"
        )
        self._ssd_recent_10_tokens = {
            "tokens": window_tokens,
            "expert_loads": recent_loads,
            "bytes_loaded": recent_bytes,
            "pressure": pressure,
            "pressure_percent": pressure * 100.0,
            "severity": severity,
        }
        if self._ssd_window_session_id is not None:
            self._ssd_recent_by_session[self._ssd_window_session_id] = dict(
                self._ssd_recent_10_tokens
            )

    def _refresh_ssd_prefill_baseline(self) -> None:
        """Exclude chunked-Prefill reads before the first Decode token."""

        if not self._ssd_window_samples or self._ssd_window_samples[-1][0] != 0:
            return
        stats = self._scope_bank.loader.stats()
        self._ssd_window_samples[-1] = (
            0,
            int(stats["experts_loaded"]),
            int(stats["bytes_loaded"]),
        )

    @staticmethod
    def _stats_delta(after: dict[str, Any], before: dict[str, Any], key: str) -> int:
        return int(after.get(key, 0)) - int(before.get(key, 0))

    @staticmethod
    def _planned_layout(
        state: Any, promotions: list[Any]
    ) -> list[tuple[int, ...]]:
        layout = list(state.layout)
        for item in promotions:
            layer = list(layout[item.layer])
            layer[layer.index(item.evict)] = item.promote
            layout[item.layer] = tuple(layer)
        return layout

    def _apply_adaptive_l1(
        self,
        reason: str,
        *,
        state: Any | None = None,
        promotions: list[Any] | None = None,
    ) -> dict[str, Any]:
        state = state or self._adaptive_state
        if self._adaptive_l1 is None or state is None:
            return {"applied": False, "reason": "disabled"}
        if promotions is None:
            promotions = self._adaptive_l1.plan(state)
        started = time.perf_counter()
        rebuilt = 0
        if promotions:
            rebuilt = self._scope_bank.activate_layout(
                state.scope,
                self._planned_layout(state, promotions),
                adaptive=True,
            )
        elapsed = time.perf_counter() - started
        self._adaptive_l1.commit(
            state, promotions, reason=reason, seconds=elapsed
        )
        if promotions:
            logger.info(
                "Adaptive L1 commit: session=%s reason=%s promotions=%d "
                "layers=%d seconds=%.3f",
                state.session_id,
                reason,
                len(promotions),
                rebuilt,
                elapsed,
            )
        self._adaptive_window_started = time.perf_counter()
        self._adaptive_window_stats = self._scope_bank.loader.stats()
        return {
            "applied": bool(promotions),
            "reason": reason,
            "promotions": len(promotions),
            "layers_rebuilt": rebuilt,
            "seconds": elapsed,
        }

    def _drain_route_window(self, state: Any, tokens: int) -> dict[str, int]:
        window = self._scope_bank.loader.drain_route_telemetry()
        route_count = 0
        miss_routes = 0
        for layer, histogram in window["histograms"].items():
            resident = set(state.layout[layer])
            for expert, count in enumerate(histogram):
                route_count += count
                if expert not in resident:
                    miss_routes += count
        self._adaptive_l1.observe_route_window(state, window["histograms"])
        miss_steps = int(window["miss_layer_steps"])
        self._adaptive_turn_miss_steps += miss_steps
        self._adaptive_turn_scored_steps += max(tokens, 0) * 40
        self._adaptive_turn_miss_routes += miss_routes
        self._adaptive_turn_routes += route_count
        return {
            "miss_steps": miss_steps,
            "scored_steps": max(tokens, 0) * 40,
            "miss_routes": miss_routes,
            "routes": route_count,
        }

    def _switch_cost(self, promotions: list[Any]) -> tuple[int, float]:
        changed_layers = len({item.layer for item in promotions})
        prior_layers = max(self._scope_bank.adaptive_layers_rebuilt, 1)
        per_layer = (
            self._scope_bank.adaptive_seconds / prior_layers
            if self._scope_bank.adaptive_seconds > 0
            else 0.10
        )
        return changed_layers, per_layer * max(changed_layers, 1)

    @staticmethod
    def _update_tps_baseline(state: Any, tps: float) -> None:
        if state.baseline_tps is None:
            state.baseline_tps = tps
        else:
            state.baseline_tps = max(state.baseline_tps * 0.9 + tps * 0.1, tps)

    def _between_decode_step(self, scheduler_output: Any) -> None:
        """Drain GPU telemetry and commit only at safe token boundaries."""

        token_count = 0
        request_id = None
        for output in getattr(scheduler_output, "outputs", ()):
            token_count = max(token_count, int(output.completion_tokens))
            request_id = getattr(output, "request_id", request_id)
        if token_count <= 0:
            self._refresh_ssd_prefill_baseline()
            return
        self._record_ssd_window(token_count)
        core = self._engine.engine
        request = core.scheduler.running.get(request_id) if request_id else None
        boost_session_id = self._engine_boost_session_id
        pending_boost = None
        if boost_session_id is not None:
            with self._engine_boost_lock:
                pending_boost = self._pending_engine_boost.pop(
                    boost_session_id, None
                )
        if pending_boost is not None:
            self._apply_engine_boost(boost_session_id, pending_boost)
            # Preserve the mixed lineage for the next turn, but isolate it from
            # global exact/Tail2/Head2 prefix namespaces.
            self._promote_request_to_session_kv(request, boost_session_id)

        state = self._adaptive_state
        if self._adaptive_l1 is None or state is None:
            return
        self._adaptive_last_token = max(self._adaptive_last_token, token_count)
        session_id = state.session_id
        manual = self._adaptive_l1.manual_pending(session_id)
        if state.mode == "off" and not manual:
            return
        early = (
            not self._adaptive_early_checked
            and token_count >= self._adaptive_l1.config.early_check_tokens
        )
        interval = early or (
            token_count - self._adaptive_window_token
            >= self._adaptive_l1.config.interval_tokens
        )
        if not manual and not interval:
            return
        if early:
            self._adaptive_early_checked = True

        now = time.perf_counter()
        before = self._adaptive_window_stats or self._scope_bank.loader.stats()
        after = self._scope_bank.loader.stats()
        tokens = max(token_count - self._adaptive_window_token, 1)
        route_window = self._drain_route_window(state, tokens)
        miss_steps = route_window["miss_steps"]
        miss_route_rate = route_window["miss_routes"] / max(
            route_window["routes"], 1
        )
        equivalent_miss_steps = miss_route_rate * tokens * 40
        seconds = max(now - self._adaptive_window_started, 1e-9)
        tps = tokens / seconds
        remaining_tokens = max(
            int(getattr(request, "max_tokens", token_count)) - token_count, 0
        )
        plan = self._adaptive_l1.plan(
            state, min_observations=1 if manual else None
        )
        decode_loaded = max(
            self._stats_delta(after, before, "decode_experts_loaded"), 1
        )
        per_expert_seconds = max(
            float(after.get("load_seconds", 0.0))
            - float(before.get("load_seconds", 0.0)),
            0.0,
        ) / decode_loaded
        predicted_savings = (
            sum(item.observations for item in plan)
            / tokens * remaining_tokens * per_expert_seconds
        )
        changed_layers, switch_cost = self._switch_cost(plan)

        cooldown = not manual and state.auto_cooldown_checks > 0
        strict = not manual and state.auto_strict_checks > 0
        if cooldown:
            state.auto_cooldown_checks -= 1
        should = manual or (
            not cooldown
            and self._adaptive_l1.should_interval_optimize(
                tokens=tokens,
                seconds=seconds,
                ssd_publish_calls=equivalent_miss_steps,
                baseline_tps=state.baseline_tps,
                predicted_savings_seconds=predicted_savings,
                switch_cost_seconds=switch_cost,
                remaining_tokens=remaining_tokens,
                allow_without_tps=early,
                min_ssd_layer_rate=(
                    self._adaptive_l1.config.early_min_ssd_layer_rate
                    if early else None
                ),
                strict=strict,
            )
        )
        if strict and not cooldown:
            state.auto_strict_checks -= 1
        logger.info(
            "Adaptive L1 GPU review: session=%s reason=%s tokens=%d "
            "l1_miss_route_rate=%.3f l1_miss_layer_rate=%.3f "
            "candidates=%d layers=%d "
            "predicted_savings=%.3fs switch_cost=%.3fs cooldown=%s "
            "strict=%s trigger=%s",
            session_id,
            "manual" if manual else ("early" if early else "interval"),
            tokens,
            miss_route_rate,
            miss_steps / max(tokens * 40, 1),
            len(plan),
            changed_layers,
            predicted_savings,
            switch_cost,
            cooldown,
            strict,
            should,
        )
        self._update_tps_baseline(state, tps)
        if should and plan:
            if manual:
                self._adaptive_l1.consume_manual(session_id)
            if self._engine_boost_mode != "natural":
                self._promote_request_to_session_kv(request, session_id)
            self._apply_adaptive_l1(
                "manual" if manual else ("early" if early else "interval"),
                state=state,
                promotions=plan,
            )
        self._adaptive_window_token = token_count
        self._adaptive_window_started = time.perf_counter()
        self._adaptive_window_stats = self._scope_bank.loader.stats()
        self._scope_bank.loader.reset_route_telemetry(enabled=state.mode == "auto")

    def _review_turn_end(self, state: Any) -> dict[str, Any]:
        """Review a completed turn after its response has been delivered."""

        tokens = max(self._adaptive_last_token - self._adaptive_window_token, 0)
        if state.mode == "off":
            self._scope_bank.loader.reset_route_telemetry(enabled=False)
            self._adaptive_l1.record_turn(state)
            return {"applied": False, "reason": "off"}
        if tokens:
            self._drain_route_window(state, tokens)
        else:
            self._scope_bank.loader.drain_route_telemetry()
        total_tokens = max(self._adaptive_last_token, 1)
        seconds = max(time.perf_counter() - self._adaptive_turn_started, 1e-9)
        tps = total_tokens / seconds
        plan = self._adaptive_l1.plan(state)
        after = self._scope_bank.loader.stats()
        before = self._adaptive_turn_stats or after
        decode_loaded = max(
            self._stats_delta(after, before, "decode_experts_loaded"), 1
        )
        per_expert_seconds = max(
            float(after.get("load_seconds", 0.0))
            - float(before.get("load_seconds", 0.0)),
            0.0,
        ) / decode_loaded
        projected_tokens = max(total_tokens, self._adaptive_l1.config.interval_tokens)
        predicted_savings = (
            sum(item.observations for item in plan)
            / total_tokens * projected_tokens * per_expert_seconds
        )
        changed_layers, switch_cost = self._switch_cost(plan)
        miss_steps = self._adaptive_turn_miss_steps
        scored_steps = max(self._adaptive_turn_scored_steps, 1)
        miss_route_rate = self._adaptive_turn_miss_routes / max(
            self._adaptive_turn_routes, 1
        )
        equivalent_miss_steps = miss_route_rate * total_tokens * 40
        gross = (
            miss_route_rate
            >= self._adaptive_l1.config.early_min_ssd_layer_rate
        )
        cooldown = state.auto_cooldown_checks > 0
        strict = state.auto_strict_checks > 0
        if cooldown:
            state.auto_cooldown_checks -= 1
        should = (
            bool(plan)
            and not cooldown
            and self._adaptive_l1.should_interval_optimize(
                tokens=total_tokens,
                seconds=seconds,
                ssd_publish_calls=equivalent_miss_steps,
                baseline_tps=state.baseline_tps,
                predicted_savings_seconds=predicted_savings,
                switch_cost_seconds=switch_cost,
                remaining_tokens=projected_tokens,
                allow_without_tps=gross,
                strict=strict,
            )
        )
        if strict and not cooldown:
            state.auto_strict_checks -= 1
        logger.info(
            "Adaptive L1 turn-end review: session=%s tps=%.2f "
            "l1_miss_route_rate=%.3f l1_miss_layer_rate=%.3f "
            "candidates=%d layers=%d "
            "predicted_savings=%.3fs switch_cost=%.3fs trigger=%s",
            state.session_id,
            tps,
            miss_route_rate,
            miss_steps / scored_steps,
            len(plan),
            changed_layers,
            predicted_savings,
            switch_cost,
            should,
        )
        self._update_tps_baseline(state, tps)
        if should:
            result = self._apply_adaptive_l1(
                "turn_end_auto", state=state, promotions=plan
            )
        else:
            self._adaptive_l1.record_turn(state)
            result = {"applied": False, "reason": "not_beneficial"}
        self._scope_bank.loader.reset_route_telemetry(enabled=False)
        return result

    async def _schedule_turn_maintenance(self, state: Any) -> None:
        if self._adaptive_l1 is None:
            return
        core = self._engine.engine
        loop = asyncio.get_running_loop()

        async def run() -> None:
            async with self._flesh_lock:
                await loop.run_in_executor(
                    core._mlx_executor, self._review_turn_end, state
                )

        task = asyncio.create_task(run())
        self._maintenance_tasks.add(task)
        task.add_done_callback(self._maintenance_tasks.discard)
        # Queue maintenance on the lock before a subsequent request can enter.
        await asyncio.sleep(0)

    def request_l1_optimization(self, session_id: str) -> dict[str, Any]:
        if self._adaptive_l1 is None:
            return {"accepted": False, "reason": "adaptive_l1_disabled"}
        self._adaptive_l1.request_manual(session_id)
        if (
            self._adaptive_state is not None
            and self._adaptive_state.session_id == session_id
        ):
            self._scope_bank.loader.enable_route_telemetry()
        return {
            "accepted": True,
            "queued": True,
            "session_id": session_id,
            "active": (
                self._adaptive_state is not None
                and self._adaptive_state.session_id == session_id
            ),
        }

    async def generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> GenerationOutput:
        state = None
        async with self._flesh_lock:
            override = kwargs.pop("flesh_scope", None)
            session_id = str(kwargs.pop("flesh_session_id", "default"))
            l1_mode = str(kwargs.pop("flesh_l1_mode", "auto"))
            boost_override = kwargs.pop("flesh_boost_mode", None)
            previous_boost = self._engine_boost_modes.get(session_id)
            boost_mode = self._normalize_boost_mode(
                boost_override
                or self._engine_boost_modes.get(
                    session_id, self._default_boost_mode
                )
            )
            if previous_boost is not None and previous_boost != boost_mode:
                self._session_owned_kv.add(session_id)
            if boost_mode != "natural":
                self._session_owned_kv.add(session_id)
            scope = await self._prepare_scope(
                prompt, override, session_id, l1_mode, boost_mode
            )
            # A live control request may arrive while scope preparation is
            # awaiting the MLX executor. Use the policy that was actually
            # published, not the value sampled before that await.
            boost_mode = self._engine_boost_modes.get(session_id, boost_mode)
            state = self._adaptive_state
            fingerprint = (
                self._adaptive_state.fingerprint()
                if self._adaptive_state is not None else None
            )
            kwargs["cache_extra_keys"] = self._cache_namespace(
                scope,
                fingerprint,
                boost_mode,
                session_id,
                session_id in self._session_owned_kv,
            )
            output = await super().generate(prompt, *args, **kwargs)
            if state is not None and state.mode != "off":
                await self._schedule_turn_maintenance(state)
        return output

    async def stream_generate(
        self, prompt: str | list[int], *args: Any, **kwargs: Any
    ) -> AsyncIterator[GenerationOutput]:
        state = None
        tail_window = 128
        # Burst decode may advance completion_tokens by more than one per
        # Python yield. Keep enough cumulative samples to locate the exact
        # N-token boundary instead of assuming one yield equals one token.
        token_times: deque[tuple[int, float]] = deque(maxlen=4097)
        async with self._flesh_lock:
            override = kwargs.pop("flesh_scope", None)
            session_id = str(kwargs.pop("flesh_session_id", "default"))
            l1_mode = str(kwargs.pop("flesh_l1_mode", "auto"))
            boost_override = kwargs.pop("flesh_boost_mode", None)
            previous_boost = self._engine_boost_modes.get(session_id)
            boost_mode = self._normalize_boost_mode(
                boost_override
                or self._engine_boost_modes.get(
                    session_id, self._default_boost_mode
                )
            )
            if previous_boost is not None and previous_boost != boost_mode:
                self._session_owned_kv.add(session_id)
            if boost_mode != "natural":
                self._session_owned_kv.add(session_id)
            scope = await self._prepare_scope(
                prompt, override, session_id, l1_mode, boost_mode
            )
            boost_mode = self._engine_boost_modes.get(session_id, boost_mode)
            state = self._adaptive_state
            fingerprint = (
                self._adaptive_state.fingerprint()
                if self._adaptive_state is not None else None
            )
            kwargs["cache_extra_keys"] = self._cache_namespace(
                scope,
                fingerprint,
                boost_mode,
                session_id,
                session_id in self._session_owned_kv,
            )
            finished = False
            try:
                async for output in super().stream_generate(prompt, *args, **kwargs):
                    finished = finished or output.finished
                    generated_at = output.generated_until or output.generated_at
                    if generated_at is not None and output.completion_tokens > 0:
                        token_times.append((output.completion_tokens, generated_at))
                    yield output
            finally:
                if finished and len(token_times) >= 2:
                    last_count, last_at = token_times[-1]
                    target_count = max(last_count - tail_window, 0)
                    samples = list(token_times)
                    anchor_count, anchor_at = samples[0]
                    for index, (count, at) in enumerate(samples):
                        if count == target_count:
                            anchor_count, anchor_at = count, at
                            break
                        if count > target_count:
                            if index > 0:
                                low_count, low_at = samples[index - 1]
                                span = count - low_count
                                fraction = (
                                    (target_count - low_count) / span if span else 0.0
                                )
                                anchor_count = target_count
                                anchor_at = low_at + (at - low_at) * fraction
                            break
                        anchor_count, anchor_at = count, at
                    measured_tokens = last_count - anchor_count
                    elapsed = last_at - anchor_at
                    self._last_decode_tail = {
                        "session_id": session_id,
                        "mode": l1_mode,
                        "completion_tokens": last_count,
                        "window_tokens": measured_tokens,
                        "seconds": elapsed,
                        "tokens_per_second": (
                            measured_tokens / elapsed if elapsed > 0 else None
                        ),
                    }
                    logger.info(
                        "DynaMoe decode tail: session=%s mode=%s "
                        "completion=%d window=%d seconds=%.3f tps=%.3f",
                        session_id,
                        l1_mode,
                        last_count,
                        measured_tokens,
                        elapsed,
                        measured_tokens / elapsed if elapsed > 0 else 0.0,
                    )
                if finished and state is not None and state.mode != "off":
                    await self._schedule_turn_maintenance(state)

    async def stop(self) -> None:
        if self._maintenance_tasks:
            await asyncio.gather(*tuple(self._maintenance_tasks), return_exceptions=True)
        if self._scope_bank is not None:
            self._scope_bank.loader.set_decode_miss_observer(None)
        if self._engine is not None and self._engine.engine is not None:
            self._engine.engine._between_decode_step_callback = None
        await super().stop()
        self._scope_selector = None
        self._scope_bank = None
        self._last_scope_selection = None
        self._adaptive_l1 = None
        self._adaptive_state = None

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
        if self._scope_selector is not None and self._scope_bank is not None:
            stats["flesh"] = {
                "selector": self._scope_selector.stats(),
                "bank": self._scope_bank.stats(),
                "expert_store": self._scope_bank.loader.stats(),
                "last_selection": (
                    {
                        "scope": self._last_scope_selection.scope,
                        "margin": self._last_scope_selection.margin,
                        "top3": list(self._last_scope_selection.top3),
                    }
                    if self._last_scope_selection is not None
                    else None
                ),
                "adaptive_l1": (
                    self._adaptive_l1.stats()
                    if self._adaptive_l1 is not None else {"enabled": False}
                ),
                "engine_boost": {
                    "mode": self._engine_boost_mode,
                    "lossy_mode": _BOOST_TO_LOSSY[self._engine_boost_mode],
                    "session_id": self._engine_boost_session_id,
                    "switches": self._engine_boost_switches,
                    "pending": len(self._pending_engine_boost),
                },
                "ssd_recent_10_tokens": dict(self._ssd_recent_10_tokens),
                "ssd_health_thresholds": {
                    "elevated_above_percent": _SSD_ELEVATED_PRESSURE * 100.0,
                    "critical_at_percent": _SSD_CRITICAL_PRESSURE * 100.0,
                    "routed_expert_bytes_per_token": (
                        self._routed_expert_bytes_per_token
                    ),
                },
                "ssd_recent_by_session": {
                    session_id: dict(window)
                    for session_id, window in self._ssd_recent_by_session.items()
                },
                "last_decode_tail": self._last_decode_tail,
            }
        return stats
