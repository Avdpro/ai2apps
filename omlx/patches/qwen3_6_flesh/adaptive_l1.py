"""Session-owned adaptive L1 support shared by all Qwen3.6 cache engines."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

import mlx.core as mx

from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.cache.direct_l1 import direct_load_fused_experts, direct_l1_mode
from omlx.patches.deepseek_v4.adaptive_l1 import (
    AdaptiveL1Config,
    AdaptiveL1Manager,
)

from .arena_cache import Qwen36DecodeArena, get_qwen36_decode_arena
from .scope_policy import NUM_EXPERTS
from .tiered_cache import get_qwen36_tiered_cache


class Qwen36AdaptiveBank:
    """Rewrite only changed L1/Tail slots and publish mappings atomically."""

    def __init__(self, model: Any, policy: Any) -> None:
        self.model = model
        self.policy = policy
        self._stores: dict[int, ExpertMajorStore] = {}
        self._staging: dict[int, list[bytearray]] = {}
        self._io_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="qwen36-l1-read"
        )
        self.commits = 0
        self.layers_rewritten = 0
        self.experts_loaded = 0
        self.experts_reused = 0
        self.slots_patched = 0
        self.bytes_loaded = 0
        self.ssd_read_seconds = 0.0
        self.gpu_snapshot_seconds = 0.0
        self.gpu_patch_seconds = 0.0
        self.sync_seconds = 0.0
        self.seconds = 0.0
        self.prefill_swaps = 0
        self.direct_l1_mode = direct_l1_mode()
        self.direct_load_calls = 0
        self.direct_load_bytes = 0
        self.direct_load_seconds = 0.0

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(
                Path(self.policy.store_path) / f"layer-{layer:03d}.moe"
            )
            store.set_no_cache()
            self._stores[layer] = store
        return store

    def prepare(self) -> None:
        for decoder in self.model.language_model.model.layers:
            Qwen36DecodeArena.prepare_switch_backing(decoder.mlp.switch_mlp)

    def _read_raw_records(
        self, layer: int, expert_ids: tuple[int, ...]
    ) -> tuple[ExpertMajorStore, list[tuple[int, Any]], float]:
        """Read missing bytes on a CPU worker without touching MLX."""

        store = self._store(layer)
        staging = self._staging.setdefault(layer, [])
        while len(staging) < len(expert_ids):
            staging.append(store.allocate_staging())
        started = time.perf_counter()
        records: list[tuple[int, Any]] = []
        for expert_id, buffer in zip(
            expert_ids, staging[: len(expert_ids)], strict=True
        ):
            raw = store.read_into(expert_id, buffer)
            records.append((expert_id, raw))
        return store, records, time.perf_counter() - started

    def _snapshot_records(
        self,
        sources: dict[int, tuple[Any, int]], expert_ids: tuple[int, ...]
    ) -> dict[int, dict[str, mx.array]]:
        """Batch resident gathers by bank to avoid tiny Metal operations."""

        records: dict[int, dict[str, mx.array]] = {
            expert: {} for expert in expert_ids
        }
        groups: dict[int, tuple[Any, list[tuple[int, int]]]] = {}
        for expert in expert_ids:
            switch, slot = sources[expert]
            group = groups.setdefault(id(switch), (switch, []))
            group[1].append((expert, slot))

        snapshots: list[mx.array] = []
        for switch, members in groups.values():
            projections = (
                ("gate_up_proj",)
                if getattr(switch, "gate_up_proj", None) is not None
                else ("gate_proj", "up_proj")
            ) + ("down_proj",)
            slots = mx.array([slot for _, slot in members], dtype=mx.int32)
            for projection_name in projections:
                projection = getattr(switch, projection_name)
                for tensor_name in ("weight", "scales", "biases"):
                    value = projection.get(tensor_name)
                    if value is None:
                        continue
                    # Detach the complete gather before overwriting any bank.
                    snapshot = mx.zeros_like(value[slots])
                    snapshot[:] = value[slots]
                    snapshots.append(snapshot)
                    key = f"{projection_name}.{tensor_name}"
                    for index, (expert, _) in enumerate(members):
                        records[expert][key] = snapshot[index]
        if snapshots:
            mx.eval(*snapshots)
        return records

    def _apply_patches(
        self,
        layer: int,
        patches: list[tuple[Any, list[int], tuple[int, ...]]],
        sources: dict[int, tuple[Any, int]],
    ) -> None:
        """Apply a layer transaction, preferring device-resident experts."""

        requested = tuple(
            dict.fromkeys(
                expert_id
                for _, _, expert_ids in patches
                for expert_id in expert_ids
            )
        )
        if not requested:
            return
        resident = tuple(expert for expert in requested if expert in sources)
        missing = tuple(expert for expert in requested if expert not in sources)

        snapshot_started = time.perf_counter()
        records = self._snapshot_records(sources, resident)
        self.gpu_snapshot_seconds += time.perf_counter() - snapshot_started
        self.experts_reused += len(resident)

        direct = False
        if missing:
            store = self._store(layer)
            direct_started = time.perf_counter()
            direct_bytes = 0
            direct_calls = 0
            for switch, slots, expert_ids in patches:
                direct_pairs = [
                    (slot, expert)
                    for slot, expert in zip(slots, expert_ids, strict=True)
                    if expert in missing
                ]
                if not direct_pairs:
                    continue
                loaded = direct_load_fused_experts(
                    store,
                    switch,
                    [slot for slot, _ in direct_pairs],
                    tuple(expert for _, expert in direct_pairs),
                )
                if loaded is None:
                    break
                direct_bytes += loaded
                direct_calls += 1
            else:
                direct = direct_calls > 0
            if direct:
                self.direct_load_calls += direct_calls
                self.direct_load_bytes += direct_bytes
                self.direct_load_seconds += time.perf_counter() - direct_started
            else:
                store, raw_records, read_seconds = self._read_raw_records(
                    layer, missing
                )
                self.ssd_read_seconds += read_seconds
                records.update(
                    {
                        expert: store.mlx_tensor_views(raw, copy_record=True)
                        for expert, raw in raw_records
                    }
                )
            self.experts_loaded += len(missing)
            self.bytes_loaded += len(missing) * store.record_bytes

        patch_started = time.perf_counter()
        arrays: list[mx.array] = []
        checks: list[mx.array] = []
        for switch, slots, expert_ids in patches:
            resident_pairs = [
                (slot, expert)
                for slot, expert in zip(slots, expert_ids, strict=True)
                if not direct or expert in resident
            ]
            if resident_pairs:
                current_arrays, current_checks = Qwen36DecodeArena._patch_switch(
                    switch,
                    [slot for slot, _ in resident_pairs],
                    tuple(expert for _, expert in resident_pairs),
                    records,
                    evaluate=False,
                )
                arrays.extend(current_arrays)
                checks.extend(current_checks)
            self.slots_patched += len(slots)
        mx.eval(*arrays, *checks)
        if checks and not all(bool(value.item()) for value in checks):
            raise RuntimeError("Qwen adaptive slot write validation failed")
        self.gpu_patch_seconds += time.perf_counter() - patch_started

    @staticmethod
    def _lookup(ids: tuple[int, ...]) -> tuple[int, ...]:
        lookup = [-1] * NUM_EXPERTS
        for slot, expert_id in enumerate(ids):
            lookup[expert_id] = slot
        return tuple(lookup)

    @staticmethod
    def _tail(
        desired_l1: tuple[int, ...],
        current_tail: tuple[int, ...],
        old_l1: tuple[int, ...],
        size: int,
    ) -> tuple[int, ...]:
        """Build a slot-stable Tail around the new L1 layout.

        Existing Tail experts that remain outside L1 keep their physical slot.
        Only slots vacated by a promotion are filled.  Besides minimizing I/O,
        this is important for quantized SwitchGLU banks: compacting the Tail
        changes physical execution slots for otherwise untouched experts.
        """

        protected = set(desired_l1)
        result: list[int | None] = [
            None if expert in protected else expert for expert in current_tail
        ]
        retained = {expert for expert in result if expert is not None}
        candidates = (*old_l1, *range(NUM_EXPERTS))
        holes = (slot for slot, expert in enumerate(result) if expert is None)
        for expert in candidates:
            if expert in protected or expert in retained:
                continue
            try:
                slot = next(holes)
            except StopIteration:
                break
            result[slot] = expert
            retained.add(expert)
        if len(result) != size or any(expert is None for expert in result):
            raise RuntimeError("unable to construct a unique Qwen adaptive Tail")
        return tuple(int(expert) for expert in result)

    @staticmethod
    def _initial_tail(
        desired_l1: tuple[int, ...], size: int
    ) -> tuple[int, ...]:
        protected = set(desired_l1)
        return tuple(
            expert for expert in range(NUM_EXPERTS) if expert not in protected
        )[:size]

    def mutable_layout(self) -> list[tuple[int, ...]]:
        """Snapshot the cache-owned physical L0/Tail layout."""

        if self.policy.backend == "flesh":
            return [tuple() for _ in self.model.language_model.model.layers]
        if self.policy.backend == "arena":
            arena = get_qwen36_decode_arena(str(self.policy.store_path))
            return [
                arena.expert_ids(layer)[self.policy.resident_experts :]
                for layer, _ in enumerate(self.model.language_model.model.layers)
            ]
        tiered = get_qwen36_tiered_cache(str(self.policy.store_path))
        return [
            tiered.tail_ids(layer)
            for layer, _ in enumerate(self.model.language_model.model.layers)
        ]

    def activate(
        self,
        layout: list[tuple[int, ...]],
        *,
        reset_mutable: bool = False,
        mutable_layout: list[tuple[int, ...]] | None = None,
    ) -> int:
        started = time.perf_counter()
        changed_layers = 0
        backend = self.policy.backend
        pending = any(
            tuple(layout[layer])
            != tuple(decoder.mlp.scope_protected_expert_ids)
            for layer, decoder in enumerate(self.model.language_model.model.layers)
        )
        pending = pending or (
            backend != "flesh" and (reset_mutable or mutable_layout is not None)
        )
        if pending:
            # GenerationBatch schedules the following token asynchronously.
            # All slot banks are model-global mutable storage, so quiesce once
            # per complete layout commit before overwriting any projection.
            sync_started = time.perf_counter()
            mx.synchronize()
            self.sync_seconds += time.perf_counter() - sync_started
        for layer, decoder in enumerate(self.model.language_model.model.layers):
            block = decoder.mlp
            desired_l1 = tuple(layout[layer])
            old_l1 = tuple(block.scope_protected_expert_ids)
            if len(desired_l1) != self.policy.resident_experts:
                raise RuntimeError("Qwen adaptive L1 layout has the wrong size")

            if backend == "flesh":
                if desired_l1 == old_l1:
                    continue
                desired_primary = desired_l1
                current_primary = tuple(block.scope_expert_ids)
                slots = [
                    slot
                    for slot, (old, new) in enumerate(
                        zip(current_primary, desired_primary, strict=True)
                    )
                    if old != new
                ]
                sources = {
                    expert: (block.switch_mlp, slot)
                    for slot, expert in enumerate(current_primary)
                }
                self._apply_patches(
                    layer,
                    [(
                        block.switch_mlp,
                        slots,
                        tuple(desired_primary[slot] for slot in slots),
                    )],
                    sources,
                )
                block.scope_expert_ids = desired_primary
                block.scope_expert_to_slot_values = self._lookup(desired_primary)
            elif backend == "arena":
                arena = get_qwen36_decode_arena(str(self.policy.store_path))
                # Dynamic misses mutate Arena slots.  The block's ID tuple is
                # only a mirror and may be stale, so plan from the cache-owned
                # physical layout.
                current_primary = arena.expert_ids(layer)
                current_tail = current_primary[self.policy.resident_experts :]
                if mutable_layout is not None:
                    desired_tail = tuple(mutable_layout[layer])
                elif reset_mutable:
                    desired_tail = self._initial_tail(
                        desired_l1, self.policy.arena_tail_slots
                    )
                else:
                    desired_tail = self._tail(
                        desired_l1,
                        current_tail,
                        old_l1,
                        self.policy.arena_tail_slots,
                    )
                desired_primary = desired_l1 + desired_tail
                if desired_primary == current_primary and desired_l1 == old_l1:
                    continue
                slots = [
                    slot
                    for slot, (old, new) in enumerate(
                        zip(current_primary, desired_primary, strict=True)
                    )
                    if old != new
                ]
                sources = {
                    expert: (block.switch_mlp, slot)
                    for slot, expert in enumerate(current_primary)
                }
                self._apply_patches(
                    layer,
                    [(
                        block.switch_mlp,
                        slots,
                        tuple(desired_primary[slot] for slot in slots),
                    )],
                    sources,
                )
                block.scope_expert_ids = desired_primary
                block.scope_tail_expert_ids = desired_tail
                block.scope_expert_to_slot_values = self._lookup(desired_primary)
                arena.replace_layout(
                    layer, desired_primary, self.policy.resident_experts
                )
            elif backend == "tiered":
                tiered = get_qwen36_tiered_cache(str(self.policy.store_path))
                # Tail refills continuously replace physical slots.  Reading
                # the initialization-time block tuple here caused Auto L1 to
                # publish IDs for experts no longer present in those slots.
                current_tail = tiered.tail_ids(layer)
                if mutable_layout is not None:
                    desired_tail = tuple(mutable_layout[layer])
                elif reset_mutable:
                    desired_tail = self._initial_tail(
                        desired_l1, self.policy.arena_tail_slots
                    )
                else:
                    desired_tail = self._tail(
                        desired_l1,
                        current_tail,
                        old_l1,
                        self.policy.arena_tail_slots,
                    )
                if desired_l1 == old_l1 and desired_tail == current_tail:
                    continue
                l1_slots = [
                    slot
                    for slot, (old, new) in enumerate(
                        zip(old_l1, desired_l1, strict=True)
                    )
                    if old != new
                ]
                tail_slots = [
                    slot
                    for slot, (old, new) in enumerate(
                        zip(current_tail, desired_tail, strict=True)
                    )
                    if old != new
                ]
                sources = {
                    expert: (block.switch_mlp, slot)
                    for slot, expert in enumerate(old_l1)
                }
                sources.update(
                    {
                        expert: (block.tail_switch_mlp, slot)
                        for slot, expert in enumerate(current_tail)
                    }
                )
                self._apply_patches(
                    layer,
                    [
                        (
                            block.switch_mlp,
                            l1_slots,
                            tuple(desired_l1[slot] for slot in l1_slots),
                        ),
                        (
                            block.tail_switch_mlp,
                            tail_slots,
                            tuple(desired_tail[slot] for slot in tail_slots),
                        ),
                    ],
                    sources,
                )
                block.scope_expert_ids = desired_l1
                block.scope_tail_expert_ids = desired_tail
                block.scope_expert_to_slot_values = self._lookup(desired_l1)
                block.scope_tail_to_slot_values = self._lookup(desired_tail)
                tiered.replace_layout(layer, desired_l1, desired_tail)
            else:
                raise RuntimeError(f"unsupported Qwen adaptive backend: {backend}")
            block.scope_protected_expert_ids = desired_l1
            self._validate_mapping(layer, block, desired_l1)
            changed_layers += 1

        elapsed = time.perf_counter() - started
        if changed_layers:
            self.commits += 1
            self.layers_rewritten += changed_layers
            self.seconds += elapsed
        return changed_layers

    def _validate_mapping(
        self, layer: int, block: Any, desired_l1: tuple[int, ...]
    ) -> None:
        """Prove ID lists, inverse lookups, and cache metadata agree."""

        primary_ids = tuple(block.scope_expert_ids)
        if len(primary_ids) != len(set(primary_ids)):
            raise RuntimeError(f"Qwen adaptive layer {layer} primary IDs duplicate")
        primary_lookup = tuple(block.scope_expert_to_slot_values)
        if any(primary_lookup[expert] != slot for slot, expert in enumerate(primary_ids)):
            raise RuntimeError(f"Qwen adaptive layer {layer} primary lookup is stale")
        if tuple(block.scope_protected_expert_ids) != desired_l1:
            raise RuntimeError(f"Qwen adaptive layer {layer} protected IDs are stale")

        if self.policy.backend == "arena":
            arena = get_qwen36_decode_arena(str(self.policy.store_path))
            if arena.lookup_values(layer, NUM_EXPERTS) != primary_lookup:
                raise RuntimeError(f"Qwen adaptive layer {layer} arena map differs")
        elif self.policy.backend == "tiered":
            tail_ids = tuple(block.scope_tail_expert_ids)
            if set(primary_ids) & set(tail_ids):
                raise RuntimeError(f"Qwen adaptive layer {layer} L1/Tail overlap")
            tail_lookup = tuple(block.scope_tail_to_slot_values)
            if any(tail_lookup[expert] != slot for slot, expert in enumerate(tail_ids)):
                raise RuntimeError(f"Qwen adaptive layer {layer} Tail lookup is stale")
            tiered = get_qwen36_tiered_cache(str(self.policy.store_path))
            if tiered.lookup_values(layer, NUM_EXPERTS) != tail_lookup:
                raise RuntimeError(f"Qwen adaptive layer {layer} Tiered map differs")

    def stats(self) -> dict[str, int | float | str]:
        return {
            "commits": self.commits,
            "layers_rewritten": self.layers_rewritten,
            "experts_loaded": self.experts_loaded,
            "experts_reused": self.experts_reused,
            "slots_patched": self.slots_patched,
            "bytes_loaded": self.bytes_loaded,
            "ssd_read_seconds": self.ssd_read_seconds,
            "gpu_snapshot_seconds": self.gpu_snapshot_seconds,
            "gpu_patch_seconds": self.gpu_patch_seconds,
            "sync_seconds": self.sync_seconds,
            "seconds": self.seconds,
            "prefill_swaps": self.prefill_swaps,
            "direct_l1_mode": self.direct_l1_mode,
            "direct_load_calls": self.direct_load_calls,
            "direct_load_bytes": self.direct_load_bytes,
            "direct_load_seconds": self.direct_load_seconds,
        }


class Qwen36AdaptiveController:
    """Policy/checkpoint glue for the three serialized Qwen engines."""

    def __init__(self, owner: Any, policy: Any) -> None:
        enabled = os.environ.get("OMLX_QWEN36_ADAPTIVE_L1", "0").lower() in (
            "1", "true", "yes", "on"
        )
        interval = int(os.environ.get("OMLX_QWEN36_ADAPTIVE_L1_INTERVAL", "256"))
        early = int(os.environ.get("OMLX_QWEN36_ADAPTIVE_L1_EARLY", "64"))
        pinned = min(
            int(os.environ.get("OMLX_QWEN36_ADAPTIVE_L1_PINNED", "20")),
            policy.resident_experts - 1,
        )
        max_promotions = min(
            int(
                os.environ.get(
                    "OMLX_QWEN36_ADAPTIVE_L1_MAX_PROMOTIONS",
                    str(min(40, policy.resident_experts - pinned)),
                )
            ),
            policy.resident_experts - pinned,
        )
        if max_promotions < 1:
            raise ValueError("Qwen adaptive L1 promotions must be positive")
        config = AdaptiveL1Config(
            enabled=enabled,
            interval_tokens=interval,
            early_check_tokens=early,
            pinned_slots=pinned,
            max_promotions_per_layer=max_promotions,
            max_layers_per_commit=40,
            min_observations=int(
                os.environ.get("OMLX_QWEN36_ADAPTIVE_L1_MIN_OBSERVATIONS", "2")
            ),
            bank_size=policy.resident_experts,
            layer_start=0,
            layer_count=40,
        )
        self.owner = owner
        self.policy = policy
        self.config = config
        self.manager = (
            AdaptiveL1Manager(policy.catalog, config) if config.enabled else None
        )
        self.bank = Qwen36AdaptiveBank(owner._model, policy)
        self.state: Any | None = None
        self.window_token = 0
        self.last_token = 0
        self.observed_routes = 0
        self.nonresident_routes = 0
        self.checks = 0
        self.triggers = 0
        self.cooldown_checks = 0
        self.idle_manual_rejections = 0
        self.stale_manual_cancellations = 0
        self.min_miss_rate = float(
            os.environ.get("OMLX_QWEN36_ADAPTIVE_L1_MIN_MISS_RATE", "0.10")
        )
        self.base_layout = (
            self.manager._base_layout(policy.scope_name)
            if self.manager is not None
            else self._scope_layout(policy.scope_name)
        )
        self.current_scope = policy.scope_name
        self._static_session_scopes: dict[str, str] = {}
        self._static_active_session_id: str | None = None
        self._in_stable_prefill = False
        self.prefill_backend = os.environ.get(
            "OMLX_QWEN36_PREFILL_BACKEND", "workspace256-direct"
        ).strip().lower()

    def start(self) -> None:
        from .model_patch import set_qwen36_route_observer

        # Engine Boost shares this scheduler-safe boundary. Install it even
        # when adaptive L1 itself is disabled.
        self.owner._engine.engine._between_decode_step_callback = self.between_step
        self.owner._engine.engine.scheduler._prefill_chunk_callback = (
            self.between_prefill_chunk
        )
        self.bank.prepare()
        if self.manager is None:
            set_qwen36_route_observer(None)
            return
        set_qwen36_route_observer(self.observe_routes)
        self.owner._model._qwen36_stable_prefill = self.stable_prefill

    def between_prefill_chunk(
        self,
        request: Any,
        *,
        tokens: int,
        processed_tokens: int,
        remaining_tokens: int,
    ) -> None:
        del request, tokens, processed_tokens
        if remaining_tokens > 0:
            return
        boost = getattr(self.owner, "_qwen_boost", None)
        if boost is not None:
            boost.complete_prefill()

    def stable_prefill(self, call: Callable[[], Any]) -> Any:
        """Run Prefill on the active session's current adaptive L1."""

        return call()

    def session_scope(self, session_id: str) -> str | None:
        """Return the sticky scope already owned by a session."""

        if self.manager is not None:
            return self.manager.session_scope(session_id)
        return self._static_session_scopes.get(session_id)

    def _scope_layout(self, scope_name: str) -> list[tuple[int, ...]]:
        return [
            self.policy.catalog.experts(
                scope_name,
                layer,
                phase="decode",
                limit=self.policy.resident_experts,
            )
            for layer in range(40)
        ]

    async def prepare(
        self, kwargs: dict[str, Any], *, scope_name: str | None = None
    ) -> tuple[str, ...]:
        session_id = str(kwargs.pop("flesh_session_id", "default"))
        raw_mode = str(kwargs.pop("flesh_l1_mode", "auto")).lower()
        trigger = raw_mode == "trigger"
        mode = "auto" if trigger else raw_mode
        if mode not in ("auto", "off"):
            raise ValueError("Qwen adaptive L1 mode must be auto, off, or trigger")
        scope_name = scope_name or self.policy.scope_name
        if scope_name not in self.policy.catalog.scope_ids:
            raise ValueError(f"unknown Qwen scope {scope_name!r}")
        if self.manager is None:
            previous = self._static_session_scopes.get(session_id)
            layout = self._scope_layout(scope_name)
            loop = __import__("asyncio").get_running_loop()
            await loop.run_in_executor(
                self.owner._engine.engine._mlx_executor,
                partial(
                    self.bank.activate,
                    layout,
                    reset_mutable=(
                        self._static_active_session_id != session_id
                        or previous != scope_name
                    ),
                ),
            )
            self._static_session_scopes[session_id] = scope_name
            self._static_active_session_id = session_id
            self.base_layout = layout
            self.current_scope = scope_name
            return ("session", session_id, scope_name)
        # A manual optimization is only valid inside the Decode turn that
        # accepted it. If it arrived after the final safe boundary, do not let
        # it absorb the next turn's Prefill observations or cross a scope
        # change before committing.
        if self.manager.cancel_manual(session_id):
            self.stale_manual_cancellations += 1
        previous_session_id = self.manager.active_session_id
        self.state = self.manager.begin(session_id, scope_name, mode=mode)
        if trigger:
            self.manager.request_manual(session_id)
        loop = __import__("asyncio").get_running_loop()
        await loop.run_in_executor(
            self.owner._engine.engine._mlx_executor,
            partial(
                self.bank.activate,
                self.state.layout,
                reset_mutable=previous_session_id != session_id,
            ),
        )
        self.base_layout = self.manager._base_layout(scope_name)
        self.current_scope = scope_name
        self.window_token = 0
        self.last_token = 0
        self.observed_routes = 0
        self.nonresident_routes = 0
        return ("session", session_id, scope_name)

    def observe_routes(self, layer: int, expert_ids: list[int]) -> None:
        if (
            self.manager is None
            or self.state is None
            or self._in_stable_prefill
        ):
            return
        if self.state.mode == "off" and not self.manager.manual_pending(
            self.state.session_id
        ):
            return
        self.manager.observe_routes(layer, expert_ids)
        resident = set(self.state.layout[layer])
        self.observed_routes += len(expert_ids)
        self.nonresident_routes += sum(
            int(expert not in resident) for expert in expert_ids
        )

    @staticmethod
    def _planned_layout(state: Any, promotions: list[Any]) -> list[tuple[int, ...]]:
        layout = list(state.layout)
        for item in promotions:
            layer = list(layout[item.layer])
            layer[layer.index(item.evict)] = item.promote
            layout[item.layer] = tuple(layer)
        return layout

    def between_step(self, scheduler_output: Any) -> None:
        boost = getattr(self.owner, "_qwen_boost", None)
        if boost is not None:
            boost.between_step()
        if self.manager is None or self.state is None:
            return
        token_count = max(
            (int(value.completion_tokens) for value in scheduler_output.outputs),
            default=0,
        )
        if token_count <= 0:
            return
        self.last_token = max(self.last_token, token_count)
        manual = self.manager.manual_pending(self.state.session_id)
        if self.state.mode == "off" and not manual:
            return
        due = token_count >= self.config.early_check_tokens and (
            self.window_token == 0
            or token_count - self.window_token >= self.config.interval_tokens
        )
        if not manual and not due:
            return
        self.checks += 1
        plan = self.manager.plan(
            self.state,
            min_observations=1 if manual else None,
            max_promotions=(
                self.policy.resident_experts - self.config.pinned_slots
                if manual
                else None
            ),
        )
        miss_rate = self.nonresident_routes / max(self.observed_routes, 1)
        cooling_down = not manual and self.cooldown_checks > 0
        threshold = self.min_miss_rate * (1.5 if cooling_down else 1.0)
        should = bool(plan) and not cooling_down and (
            manual or miss_rate >= threshold
        )
        if cooling_down:
            self.cooldown_checks -= 1
        if should:
            started = time.perf_counter()
            changed = self.bank.activate(self._planned_layout(self.state, plan))
            elapsed = time.perf_counter() - started
            reason = "manual" if manual else "interval"
            self.manager.commit(self.state, plan, reason=reason, seconds=elapsed)
            if manual:
                self.manager.consume_manual(self.state.session_id)
            self.triggers += 1
            self.cooldown_checks = 1
            if changed == 0:
                raise RuntimeError("Qwen adaptive plan changed no physical layers")
        self.window_token = token_count
        self.observed_routes = 0
        self.nonresident_routes = 0

    def request(self, session_id: str) -> dict[str, Any]:
        if self.manager is None:
            return {"accepted": False, "reason": "adaptive_l1_disabled"}
        if not self.owner.has_active_requests():
            self.manager.cancel_manual(session_id)
            self.idle_manual_rejections += 1
            return {"accepted": False, "reason": "no_active_decode"}
        self.manager.request_manual(session_id)
        return {"accepted": True, "queued": True, "session_id": session_id}

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.manager is not None,
            "max_promotions_per_layer": self.config.max_promotions_per_layer,
            "checks": self.checks,
            "triggers": self.triggers,
            "idle_manual_rejections": self.idle_manual_rejections,
            "stale_manual_cancellations": self.stale_manual_cancellations,
            "observed_routes": self.observed_routes,
            "nonresident_routes": self.nonresident_routes,
            "bank": self.bank.stats(),
            "manager": self.manager.stats() if self.manager else None,
            "current_scope": self.current_scope,
        }


__all__ = ["Qwen36AdaptiveBank", "Qwen36AdaptiveController"]
