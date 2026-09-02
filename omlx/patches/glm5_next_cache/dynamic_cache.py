"""Exact fixed-slot GLM-5 expert cache and grouped prefill executor."""

from __future__ import annotations

import copy
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import mlx.core as mx

from omlx.cache.direct_l1 import direct_l1_mode, use_direct_l1
from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast

from .policy import EMPTY, PROTECTED, DynamicL1Policy, LayerState


@dataclass
class _RawBatch:
    layer: int
    ids: tuple[int, ...]
    store: ExpertMajorStore
    buffers: list[bytearray]
    seconds: float


class Glm5DynamicCache:
    """Own per-layer tags and mutate one fixed-capacity SwitchGLU per layer."""

    def __init__(
        self,
        directory: str | os.PathLike[str],
        *,
        capacity: int = 80,
        tail_slots: int = 0,
        l1_promotions_per_layer: int = 0,
        num_experts: int = 288,
        io_workers: int = 4,
    ) -> None:
        if not 1 <= io_workers <= 16:
            raise ValueError("GLM5 dynamic cache I/O workers must be 1..16")
        self.directory = Path(directory).expanduser().resolve()
        self.capacity = capacity
        self.tail_slots = tail_slots
        if not 0 <= l1_promotions_per_layer <= 8:
            raise ValueError("GLM5 L1 promotions per layer must be in [0, 8]")
        self.l1_promotions_per_layer = l1_promotions_per_layer
        self.num_experts = num_experts
        self.policy = DynamicL1Policy(
            capacity=capacity,
            num_experts=num_experts,
        )
        self.tail_policy = (
            DynamicL1Policy(capacity=tail_slots, num_experts=num_experts)
            if tail_slots
            else None
        )
        self._stores: dict[int, ExpertMajorStore] = {}
        self._lock = threading.RLock()
        self._read_pool = ThreadPoolExecutor(
            max_workers=io_workers,
            thread_name_prefix="glm5-expert-read",
        )
        self._prefetch_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="glm5-expert-prefetch",
        )
        self.io_workers = io_workers
        self.calls = 0
        self.hit_calls = 0
        self.miss_calls = 0
        self.prefill_calls = 0
        self.experts_loaded = 0
        self.bytes_loaded = 0
        self.read_seconds = 0.0
        self.materialize_seconds = 0.0
        self.patch_seconds = 0.0
        self.direct_load_calls = 0
        self.direct_load_bytes = 0
        self.direct_l1_mode = direct_l1_mode()
        self.sync_seconds = 0.0
        self.overlap_calls = 0
        self.overlap_hit_routes = 0
        self.overlap_miss_routes = 0
        self.promote_seconds = 0.0
        self._decode_scratch: Any | None = None
        self._tail_switches: dict[int, Any] = {}
        self._switches: dict[int, Any] = {}
        self._pending_l1_promotions: dict[int, tuple[int, ...]] = {}
        self.tail_hit_routes = 0
        self.tail_miss_routes = 0
        self.l1_promotions = 0
        self.l1_promotion_bytes = 0
        self.l1_promotion_seconds = 0.0
        configured_prefill_slots = os.environ.get("OMLX_GLM5_PREFILL_BANK_SLOTS")
        self.prefill_bank_slots = (
            int(configured_prefill_slots)
            if configured_prefill_slots is not None
            else min(208, num_experts)
        )
        if not 1 <= self.prefill_bank_slots <= num_experts:
            raise ValueError("GLM5 prefill bank slots must be in [1, num_experts]")
        self._prefill_scratch: list[Any | None] = [None, None]
        self._prefill_scratch_slots = [0, 0]
        self.prefill_workspaces_released = 0
        self.prefill_release_seconds = 0.0
        self.prefill_direct_calls = 0
        self.prefill_direct_groups = 0
        self.prefill_compute_seconds = 0.0
        self.prefill_main_routes = 0
        self.prefill_tail_routes = 0
        self.prefill_miss_routes = 0
        self.prefill_unique_misses = 0
        self.prefill_experts_avoided = 0
        self._route_observer: Callable[[int, Any, Any, str], None] | None = None
        # Some routers are sensitive enough that changing the Top-K BF16
        # reduction tree can flip a later token.  Architecture adapters may
        # request strict original-route ordering; GLM keeps its validated
        # resident/tail partial reduction by default.
        self.preserve_route_order = False

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(self.directory / f"layer-{layer:03d}.moe")
            if store.num_experts != self.num_experts:
                raise ValueError(
                    f"GLM5 layer {layer} store has {store.num_experts} experts; "
                    f"expected {self.num_experts}"
                )
            expected = {
                f"{projection}.{component}"
                for projection in ("gate_up_proj", "down_proj")
                for component in ("weight", "scales", "biases")
            }
            actual = {tensor.name for tensor in store.tensors}
            if actual != expected:
                raise ValueError(
                    f"GLM5 layer {layer} store is not compute-ready fused-v2; "
                    "re-run scripts/convert_glm5_expert_store.py"
                )
            store.set_no_cache()
            self._stores[layer] = store
        return store

    def _read_raw(self, layer: int, ids: tuple[int, ...]) -> _RawBatch:
        started = time.perf_counter()
        store = self._store(layer)
        buffers = [store.allocate_staging() for _ in ids]
        futures = [
            self._read_pool.submit(store.read_into, expert, buffer)
            for expert, buffer in zip(ids, buffers, strict=True)
        ]
        for future in futures:
            future.result()
        return _RawBatch(
            layer=layer,
            ids=ids,
            store=store,
            buffers=buffers,
            seconds=time.perf_counter() - started,
        )

    @staticmethod
    def _materialize(raw: _RawBatch) -> dict[int, dict[str, mx.array]]:
        return {
            expert: raw.store.mlx_tensor_views(buffer, copy_record=True)
            for expert, buffer in zip(raw.ids, raw.buffers, strict=True)
        }

    def _direct_load(
        self,
        store: ExpertMajorStore,
        switch: Any,
        slots: tuple[int, ...] | list[int],
        ids: tuple[int, ...],
    ) -> bool:
        """preadv fused records into their final MLX/Metal L1 slots."""

        if not use_direct_l1(
            native_available=("preadv_fused_experts" in glm_fast.native_symbols())
        ):
            return False
        gate_up = getattr(switch, "gate_up_proj", None)
        if gate_up is None:
            return False
        arrays = tuple(
            projection.get(component)
            for projection in (gate_up, switch.down_proj)
            for component in ("weight", "scales", "biases")
        )
        if any(value is None for value in arrays):
            return False
        loaded = glm_fast.preadv_fused_experts(
            store.fileno(),
            store.data_offset,
            store.record_bytes,
            list(ids),
            list(slots),
            *arrays,
            io_workers=self.io_workers,
        )
        expected = len(ids) * store.record_bytes
        if loaded != expected:
            raise RuntimeError(
                f"native GLM5 loader reported {loaded} bytes, expected {expected}"
            )
        self.direct_load_calls += 1
        self.direct_load_bytes += loaded
        return True

    def direct_enabled(self) -> bool:
        """Whether the native SSD-to-unified-memory path is usable."""

        return use_direct_l1(
            native_available=("preadv_fused_experts" in glm_fast.native_symbols())
        )

    def _prepare_switch(self, layer: int, switch: Any) -> None:
        self._switches[layer] = switch
        if getattr(switch, "_omlx_glm5_mutable", False):
            return
        empty = all(expert < 0 for expert in self.policy.state(layer).expert_ids)
        arrays: list[mx.array] = []
        replacements: list[tuple[Any, str, mx.array]] = []
        projections = (
            ("gate_up_proj",)
            if getattr(switch, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            projection = getattr(switch, projection_name)
            for tensor_name in ("weight", "scales", "biases"):
                value = projection.get(tensor_name)
                if value is None:
                    continue
                backing = mx.zeros_like(value)
                if not empty:
                    backing[:] = value
                arrays.append(backing)
                replacements.append((projection, tensor_name, backing))
        if arrays:
            mx.eval(*arrays)
        for projection, tensor_name, backing in replacements:
            setattr(projection, tensor_name, backing)
        switch._omlx_glm5_mutable = True

    @staticmethod
    def _make_fixed_switch(template: Any, slots: int) -> Any:
        """Allocate one compute-ready fixed-shape bank outside the model tree."""

        scratch = copy.copy(template)
        scratch.global_num_experts = slots
        arrays: list[mx.array] = []
        projections = (
            ("gate_up_proj",)
            if getattr(template, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            source = getattr(template, projection_name)
            projection = copy.copy(source)
            for tensor_name in ("weight", "scales", "biases"):
                value = source.get(tensor_name)
                if value is None:
                    continue
                backing = mx.zeros((slots, *value.shape[1:]), dtype=value.dtype)
                setattr(projection, tensor_name, backing)
                arrays.append(backing)
            setattr(scratch, projection_name, projection)
        mx.eval(*arrays)
        scratch._omlx_glm5_mutable = True
        return scratch

    def _decode_scratch_switch(self, template: Any) -> Any:
        if self._decode_scratch is None:
            self._decode_scratch = self._make_fixed_switch(template, 8)
        return self._decode_scratch

    def _prefill_scratch_switch(
        self, template: Any, index: int, slots: int | None = None
    ) -> Any:
        minimum_slots = slots or self.prefill_bank_slots
        requested_slots = (
            32
            if minimum_slots <= 32
            else 96
            if minimum_slots <= 96
            else 208
            if minimum_slots <= 208
            else self.num_experts
        )
        scratch = self._prefill_scratch[index]
        if scratch is None or self._prefill_scratch_slots[index] < requested_slots:
            scratch = self._make_fixed_switch(template, requested_slots)
            self._prefill_scratch[index] = scratch
            self._prefill_scratch_slots[index] = requested_slots
        return scratch

    def release_prefill_workspaces(self) -> None:
        """Drop the decode-unused double buffer before allocating per-layer L0."""

        if all(scratch is None for scratch in self._prefill_scratch):
            return
        started = time.perf_counter()
        self._prefill_scratch = [None, None]
        self._prefill_scratch_slots = [0, 0]
        mx.clear_cache()
        self.prefill_workspaces_released += 1
        self.prefill_release_seconds += time.perf_counter() - started

    def _tail_switch(self, layer: int, template: Any) -> Any:
        tail = self._tail_switches.get(layer)
        if tail is None:
            if not self.tail_slots:
                raise RuntimeError("GLM5 persistent Tail is disabled")
            tail = self._make_fixed_switch(template, self.tail_slots)
            self._tail_switches[layer] = tail
        return tail

    @staticmethod
    def _copy_switch_slots(
        source: Any,
        source_slots: tuple[int, ...],
        target: Any,
        target_slots: tuple[int, ...],
        *,
        evaluate: bool = True,
    ) -> list[mx.array]:
        """Promote already-loaded unified-memory records without SSD rereads."""

        if not source_slots:
            return []
        source_index = mx.array(source_slots, dtype=mx.int32)
        target_index = mx.array(target_slots, dtype=mx.int32)
        arrays: list[mx.array] = []
        projections = (
            ("gate_up_proj",)
            if getattr(source, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            source_projection = getattr(source, projection_name)
            target_projection = getattr(target, projection_name)
            for tensor_name in ("weight", "scales", "biases"):
                source_value = source_projection.get(tensor_name)
                target_value = target_projection.get(tensor_name)
                if source_value is None or target_value is None:
                    continue
                target_value[target_index] = source_value[source_index]
                arrays.append(target_value)
        if evaluate:
            mx.eval(*arrays)
        return arrays

    @staticmethod
    def _patch_records(
        switch: Any,
        slots: tuple[int, ...] | list[int],
        ids: tuple[int, ...],
        records: dict[int, dict[str, mx.array]],
    ) -> None:
        if not slots:
            return
        slot_array = mx.array(slots, dtype=mx.int32)
        arrays: list[mx.array] = []
        projections = (
            ("gate_up_proj",)
            if getattr(switch, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        for projection_name in projections:
            projection = getattr(switch, projection_name)
            for tensor_name in ("weight", "scales", "biases"):
                current = projection.get(tensor_name)
                if current is None:
                    continue
                name = f"{projection_name}.{tensor_name}"
                replacement = mx.stack([records[expert][name] for expert in ids])
                if replacement.dtype != current.dtype:
                    replacement = replacement.astype(current.dtype)
                current[slot_array] = replacement
                arrays.append(current)
        if arrays:
            mx.eval(*arrays)

    def resolve(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
    ) -> tuple[int, ...]:
        """Ensure one decode Top-K set is resident and return global lookup."""

        self.calls += 1
        with self._lock:
            self._prepare_switch(layer, switch)
            plan = self.policy.plan(layer, requested)
            if not plan.missing:
                self.policy.publish(layer, plan)
                self.hit_calls += 1
                return self.policy.lookup(layer)

            sync_started = time.perf_counter()
            mx.synchronize()
            self.sync_seconds += time.perf_counter() - sync_started
            store = self._store(layer)
            read_started = time.perf_counter()
            direct = self._direct_load(store, switch, plan.slots, plan.missing)
            if direct:
                self.read_seconds += time.perf_counter() - read_started
            else:
                raw = self._read_raw(layer, plan.missing)
                self.read_seconds += raw.seconds
                materialize_started = time.perf_counter()
                records = self._materialize(raw)
                self.materialize_seconds += time.perf_counter() - materialize_started
                patch_started = time.perf_counter()
                self._patch_records(switch, plan.slots, plan.missing, records)
                self.patch_seconds += time.perf_counter() - patch_started
            # Publish tags only after every physical write has completed.
            self.policy.publish(layer, plan)
            self.miss_calls += 1
            self.experts_loaded += len(plan.missing)
            self.bytes_loaded += len(plan.missing) * store.record_bytes
            return self.policy.lookup(layer)

    def resolve_split(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        mapped: mx.array,
        overlap_dependency: mx.array | None = None,
    ) -> tuple[mx.array, tuple[int, ...]]:
        """Compute resident routes while direct-loading misses into Hot8.

        The main L1 is never mutated while its hit kernel is running. Misses
        land in a separate fixed eight-slot bank, are evaluated there, then
        are promoted to their reserved L1 slots through unified-memory Metal
        copies. This mirrors the DSV4F hit/SSD overlap without exposing a
        partially written bank to a QMM.
        """

        self.calls += 1
        with self._lock:
            self._prepare_switch(layer, switch)
            plan = self.policy.plan(layer, requested)
            if not plan.missing:
                self.policy.publish(layer, plan)
                self.hit_calls += 1
                routes = switch(x, mapped)
                output = (
                    routes * scores[..., None].astype(routes.dtype)
                ).sum(axis=-2)
                return output, self.policy.lookup(layer)

            flat_ids = [int(value) for value in inds.reshape(-1).tolist()]
            missing_set = set(plan.missing)
            hit_positions = tuple(
                position
                for position, expert in enumerate(flat_ids)
                if expert not in missing_set
            )
            miss_positions = tuple(
                position
                for position, expert in enumerate(flat_ids)
                if expert in missing_set
            )
            if not hit_positions:
                # No useful Metal work exists to hide the SSD read behind.
                lookup = self.resolve(layer, requested, switch)
                local = mx.array(lookup, dtype=mx.int32)[inds]
                routes = switch(x, local)
                output = (
                    routes * scores[..., None].astype(routes.dtype)
                ).sum(axis=-2)
                return output, lookup

            sync_started = time.perf_counter()
            mx.synchronize()
            self.sync_seconds += time.perf_counter() - sync_started
            scratch = self._decode_scratch_switch(switch)

            top_k = int(inds.shape[-1])
            hidden = int(x.shape[-1])
            route_x = mx.broadcast_to(
                x.reshape(-1, hidden)[:, None, :],
                (x.shape[0] * x.shape[1], top_k, hidden),
            ).reshape(-1, hidden)
            flat_scores = scores.reshape(-1)
            flat_mapped = mapped.reshape(-1)
            hit_index = mx.array(hit_positions, dtype=mx.int32)
            hit_routes = switch(
                route_x[hit_index][None],
                flat_mapped[hit_index].reshape(1, -1, 1),
            ).reshape(len(hit_positions), hidden)
            hit_output = (
                hit_routes
                * flat_scores[hit_index, None].astype(hit_routes.dtype)
            ).sum(axis=0)
            if overlap_dependency is None:
                mx.async_eval(hit_output)
            else:
                mx.async_eval(hit_output, overlap_dependency)

            store = self._store(layer)
            scratch_slots = tuple(range(len(plan.missing)))
            read_started = time.perf_counter()
            direct = self._direct_load(
                store, scratch, scratch_slots, plan.missing
            )
            if not direct:
                raise RuntimeError(
                    "GLM5 split decode requires the native direct loader"
                )
            self.read_seconds += time.perf_counter() - read_started

            scratch_lookup = {
                expert: slot for slot, expert in enumerate(plan.missing)
            }
            miss_index = mx.array(miss_positions, dtype=mx.int32)
            miss_slots = mx.array(
                [scratch_lookup[flat_ids[position]] for position in miss_positions],
                dtype=mx.int32,
            )
            miss_routes = scratch(
                route_x[miss_index][None], miss_slots.reshape(1, -1, 1)
            ).reshape(len(miss_positions), hidden)
            miss_output = (
                miss_routes
                * flat_scores[miss_index, None].astype(miss_routes.dtype)
            ).sum(axis=0)

            promote_started = time.perf_counter()
            self._copy_switch_slots(scratch, scratch_slots, switch, plan.slots)
            self.promote_seconds += time.perf_counter() - promote_started
            self.policy.publish(layer, plan)
            self.miss_calls += 1
            self.overlap_calls += 1
            self.overlap_hit_routes += len(hit_positions)
            self.overlap_miss_routes += len(miss_positions)
            self.experts_loaded += len(plan.missing)
            self.bytes_loaded += len(plan.missing) * store.record_bytes
            output = (hit_output + miss_output).reshape(
                x.shape[0], x.shape[1], hidden
            )
            return output, self.policy.lookup(layer)

    def decode_tiered(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        main_mapped: mx.array,
        overlap_dependency: mx.array | None = None,
        promotion_limit: int | None = None,
    ) -> tuple[mx.array, tuple[int, ...], tuple[int, ...]]:
        """Run main-L1 hits while filling a persistent per-layer Tail bank."""

        if self.tail_policy is None:
            raise RuntimeError("GLM5 tiered decode requires persistent Tail slots")
        if promotion_limit is None:
            promotion_limit = self.l1_promotions_per_layer
        if not 0 <= promotion_limit <= 8:
            raise ValueError("tiered L1 promotion limit must be in [0, 8]")
        self.calls += 1
        with self._lock:
            self._prepare_switch(layer, switch)
            tail = self._tail_switch(layer, switch)
            host_ids = [int(value) for value in inds.reshape(-1).tolist()]
            pending = self._pending_l1_promotions.pop(layer, ())
            if pending:
                tail_lookup_before = self.tail_policy.lookup(layer)
                main_lookup_before = self.policy.lookup(layer)
                promotable = tuple(
                    expert
                    for expert in pending
                    if tail_lookup_before[expert] >= 0
                    and main_lookup_before[expert] < 0
                )
                if promotable:
                    pinned_main = tuple(
                        dict.fromkeys(
                            expert
                            for expert in host_ids
                            if main_lookup_before[expert] >= 0
                        )
                    )
                    promotion = self.policy.plan(
                        layer, (*pinned_main, *promotable)
                    )
                    started = time.perf_counter()
                    self._copy_switch_slots(
                        tail,
                        tuple(tail_lookup_before[expert] for expert in promotable),
                        switch,
                        promotion.slots,
                    )
                    self.l1_promotion_seconds += time.perf_counter() - started
                    self.l1_promotions += len(promotable)
                    self.l1_promotion_bytes += len(promotable) * self._store(
                        layer
                    ).record_bytes
                    self.policy.publish(layer, promotion)
            main_lookup = self.policy.lookup(layer)
            main_mapped = mx.array(main_lookup, dtype=mx.int32)[inds]
            tail_requested = tuple(
                dict.fromkeys(expert for expert in host_ids if main_lookup[expert] < 0)
            )
            if not tail_requested:
                self.hit_calls += 1
                output = (
                    switch(x, main_mapped)
                    * scores[..., None].astype(x.dtype)
                ).sum(axis=-2)
                return output, main_lookup, self.tail_policy.lookup(layer)
            plan = self.tail_policy.plan(layer, tail_requested)

            hidden = int(x.shape[-1])
            top_k = int(inds.shape[-1])
            token_count = int(x.shape[0] * x.shape[1])
            route_x = mx.broadcast_to(
                x.reshape(-1, hidden)[:, None, :],
                (x.shape[0] * x.shape[1], top_k, hidden),
            ).reshape(-1, hidden)
            flat_scores = scores.reshape(-1)
            flat_main = main_mapped.reshape(-1)
            main_positions = tuple(
                position
                for position, expert in enumerate(host_ids)
                if main_lookup[expert] >= 0
            )
            tail_positions = tuple(
                position
                for position, expert in enumerate(host_ids)
                if main_lookup[expert] < 0
            )
            main_output = mx.zeros((token_count, hidden), dtype=x.dtype)
            main_values = None
            main_index = None

            if plan.missing:
                sync_started = time.perf_counter()
                mx.synchronize()
                self.sync_seconds += time.perf_counter() - sync_started
                if main_positions:
                    main_index = mx.array(main_positions, dtype=mx.int32)
                    main_routes = switch(
                        route_x[main_index][None],
                        flat_main[main_index].reshape(1, -1, 1),
                    ).reshape(len(main_positions), hidden)
                    main_values = (
                        main_routes
                        * flat_scores[main_index, None].astype(main_routes.dtype)
                    )
                    main_tokens = main_index // top_k
                    main_output = main_output.at[main_tokens].add(main_values)
                    if overlap_dependency is None:
                        mx.async_eval(main_output)
                    else:
                        mx.async_eval(main_output, overlap_dependency)

                store = self._store(layer)
                read_started = time.perf_counter()
                if not self._direct_load(store, tail, plan.slots, plan.missing):
                    raise RuntimeError(
                        "GLM5 persistent Tail requires the native direct loader"
                    )
                self.read_seconds += time.perf_counter() - read_started
                self.experts_loaded += len(plan.missing)
                self.bytes_loaded += len(plan.missing) * store.record_bytes
                self.miss_calls += 1
                if main_positions:
                    self.overlap_calls += 1
                    self.overlap_hit_routes += len(main_positions)
                    self.overlap_miss_routes += len(tail_positions)
            else:
                self.hit_calls += 1

            self.tail_policy.publish(layer, plan)
            tail_lookup = self.tail_policy.lookup(layer)
            tail_index = mx.array(tail_positions, dtype=mx.int32)
            tail_slots = mx.array(
                [tail_lookup[host_ids[position]] for position in tail_positions],
                dtype=mx.int32,
            ).reshape(1, -1, 1)
            tail_routes = tail(route_x[tail_index][None], tail_slots).reshape(
                len(tail_positions), hidden
            )
            tail_values = (
                tail_routes
                * flat_scores[tail_index, None].astype(tail_routes.dtype)
            )
            tail_tokens = tail_index // top_k
            tail_output = mx.zeros((token_count, hidden), dtype=x.dtype).at[
                tail_tokens
            ].add(tail_values)

            if main_positions and not plan.missing:
                main_index = mx.array(main_positions, dtype=mx.int32)
                main_routes = switch(
                    route_x[main_index][None],
                    flat_main[main_index].reshape(1, -1, 1),
                ).reshape(len(main_positions), hidden)
                main_values = (
                    main_routes
                    * flat_scores[main_index, None].astype(main_routes.dtype)
                )
                main_tokens = main_index // top_k
                main_output = main_output.at[main_tokens].add(main_values)
            self.tail_hit_routes += len(tail_positions) - len(plan.missing)
            self.tail_miss_routes += len(plan.missing)
            if promotion_limit:
                protected = tuple(
                    expert
                    for expert in tail_requested
                    if plan.next_state.segments[
                        plan.next_state.expert_ids.index(expert)
                    ]
                    == PROTECTED
                )
                if protected:
                    self._pending_l1_promotions[layer] = protected[
                        :promotion_limit
                    ]
            if self.preserve_route_order:
                ordered = mx.zeros((len(host_ids), hidden), dtype=x.dtype)
                if main_index is not None and main_values is not None:
                    ordered = ordered.at[main_index].add(main_values)
                ordered = ordered.at[tail_index].add(tail_values)
                output = ordered.reshape(token_count, top_k, hidden).sum(axis=-2)
                output = output.reshape(x.shape[0], x.shape[1], hidden)
            else:
                output = (main_output + tail_output).reshape(
                    x.shape[0], x.shape[1], hidden
                )
            return output, main_lookup, tail_lookup

    def observe_slot_counts(self, layer: int, counts: tuple[int, ...]) -> None:
        """Drain device-side all-hit telemetry at an existing miss boundary."""

        with self._lock:
            self.policy.observe_slot_counts(layer, counts)

    def record_all_hit(self) -> None:
        """Account for a decode layer invocation handled on the device fast path."""

        self.calls += 1
        self.hit_calls += 1

    def set_route_observer(
        self,
        observer: Callable[[int, Any, Any, str], None] | None,
    ) -> None:
        """Install an experiment-only router observer without changing routing."""

        self._route_observer = observer

    def observe_routes(
        self,
        layer: int,
        inds: Any,
        scores: Any,
        phase: str,
    ) -> None:
        observer = self._route_observer
        if observer is not None:
            observer(layer, inds, scores, phase)

    def prefill(
        self,
        layer: int,
        switch: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
    ) -> mx.array:
        """Execute every routed prefill contribution in capacity-sized groups.

        Route values are copied to the host once at the existing expert-I/O
        boundary.  Expert arithmetic stays in the original route order: group
        outputs are evaluated before the mutable bank is overwritten, sorted
        back by flat route position, reshaped, and only then reduced over Top-K.
        """

        self.prefill_calls += 1
        mx.eval(inds)
        host_ids = [int(value) for value in inds.reshape(-1).tolist()]
        top_k = int(inds.shape[-1])
        route_batches = [
            tuple(host_ids[offset : offset + top_k])
            for offset in range(0, len(host_ids), top_k)
        ]
        simulation = DynamicL1Policy(
            capacity=self.capacity,
            num_experts=self.num_experts,
        )
        simulation.install(layer, self.policy.state(layer))
        retain_l1 = getattr(
            self,
            "prefill_retain_l1",
            os.environ.get("OMLX_GLM5_PREFILL_RETAIN_L1", "0") == "1",
        )
        current_state = self.policy.state(layer)
        if retain_l1 and any(expert >= 0 for expert in current_state.expert_ids):
            target_state = current_state
        else:
            target_state = simulation.replay(layer, route_batches)
        target_ids = {expert for expert in target_state.expert_ids if expert >= 0}

        unique = tuple(sorted(set(host_ids)))
        groups = [
            unique[offset : offset + self.capacity]
            for offset in range(0, len(unique), self.capacity)
        ]
        if not groups:
            raise RuntimeError("GLM5 prefill produced no routed experts")

        with self._lock:
            self._prepare_switch(layer, switch)
            sync_started = time.perf_counter()
            mx.synchronize()
            self.sync_seconds += time.perf_counter() - sync_started

            if self.direct_enabled():
                return self._prefill_direct_locked(
                    layer=layer,
                    switch=switch,
                    x=x,
                    inds=inds,
                    scores=scores,
                    host_ids=host_ids,
                    target_state=target_state,
                )

            contributions: list[mx.array] = []
            contribution_positions: list[mx.array] = []
            retained: dict[int, dict[str, mx.array]] = {}
            future: Future[_RawBatch] = self._prefetch_pool.submit(
                self._read_raw, layer, groups[0]
            )
            flat_x = x.reshape(-1, x.shape[-1])
            flat_scores = scores.reshape(-1)
            hidden = int(x.shape[-1])

            for index, group in enumerate(groups):
                raw = future.result()
                self.read_seconds += raw.seconds
                if index + 1 < len(groups):
                    future = self._prefetch_pool.submit(
                        self._read_raw, layer, groups[index + 1]
                    )
                materialize_started = time.perf_counter()
                records = self._materialize(raw)
                self.materialize_seconds += time.perf_counter() - materialize_started
                for expert in group:
                    if expert in target_ids:
                        retained[expert] = records[expert]

                patch_started = time.perf_counter()
                slots = tuple(range(len(group)))
                self._patch_records(switch, slots, group, records)
                self.patch_seconds += time.perf_counter() - patch_started

                local = {expert: slot for slot, expert in enumerate(group)}
                positions = [
                    route for route, expert in enumerate(host_ids) if expert in local
                ]
                token_positions = [route // top_k for route in positions]
                local_ids = [local[host_ids[route]] for route in positions]
                pos_array = mx.array(positions, dtype=mx.int32)
                token_array = mx.array(token_positions, dtype=mx.int32)
                local_array = mx.array(local_ids, dtype=mx.int32).reshape(1, -1, 1)
                routed = switch(flat_x[token_array][None], local_array).reshape(
                    -1, hidden
                )
                weighted = routed * flat_scores[pos_array, None].astype(routed.dtype)
                # The next group overwrites the same physical weights.
                mx.eval(weighted)
                contributions.append(weighted)
                contribution_positions.append(pos_array)
                self.experts_loaded += len(group)
                self.bytes_loaded += len(group) * raw.store.record_bytes

            all_positions = mx.concatenate(contribution_positions)
            all_values = mx.concatenate(contributions, axis=0)
            order = mx.argsort(all_positions)
            routes = all_values[order].reshape(*inds.shape, hidden)
            output = routes.sum(axis=-2)
            mx.eval(output)

            final_slots = tuple(
                slot
                for slot, expert in enumerate(target_state.expert_ids)
                if expert >= 0
            )
            final_ids = tuple(target_state.expert_ids[slot] for slot in final_slots)
            if set(final_ids) != set(retained):
                raise RuntimeError("GLM5 prefill did not retain its final L1 records")
            patch_started = time.perf_counter()
            self._patch_records(switch, final_slots, final_ids, retained)
            self.patch_seconds += time.perf_counter() - patch_started
            self.policy.install(layer, target_state)
            return output

    def _prefill_direct_locked(
        self,
        *,
        layer: int,
        switch: Any,
        x: mx.array,
        inds: mx.array,
        scores: mx.array,
        host_ids: list[int],
        target_state: Any,
    ) -> mx.array:
        """Exact resident-first prefill with SSD-direct miss workspaces."""

        main_lookup = self.policy.lookup(layer)
        target_state = self._keep_resident_slots_stable(
            self.policy.state(layer), target_state
        )
        tail_lookup = (
            self.tail_policy.lookup(layer)
            if self.tail_policy is not None
            else (-1,) * self.num_experts
        )
        main_positions = tuple(
            position
            for position, expert in enumerate(host_ids)
            if main_lookup[expert] >= 0
        )
        tail_positions = tuple(
            position
            for position, expert in enumerate(host_ids)
            if main_lookup[expert] < 0 and tail_lookup[expert] >= 0
        )
        miss_positions = tuple(
            position
            for position, expert in enumerate(host_ids)
            if main_lookup[expert] < 0 and tail_lookup[expert] < 0
        )
        unique = tuple(sorted({host_ids[position] for position in miss_positions}))
        all_unique = tuple(sorted(set(host_ids)))
        resident_kernels = int(bool(main_positions)) + int(bool(tail_positions))
        resident_plan_kernels = resident_kernels + (
            (len(unique) + self.prefill_bank_slots - 1)
            // self.prefill_bank_slots
        )
        direct_plan_kernels = (
            len(all_unique) + self.prefill_bank_slots - 1
        ) // self.prefill_bank_slots
        resident_first = getattr(
            self,
            "prefill_resident_first",
            os.environ.get("OMLX_GLM5_PREFILL_RESIDENT_FIRST", "1") == "1",
        )
        canonical_reuse = bool(
            getattr(self, "prefill_canonical_reuse", False)
            and not resident_first
        )
        if not resident_first or resident_plan_kernels > direct_plan_kernels:
            # Saving bytes is counterproductive when it adds an MoE kernel.
            # Fall back to the old exact grouped path for this layer/chunk.
            main_positions = ()
            tail_positions = ()
            miss_positions = tuple(range(len(host_ids)))
            unique = all_unique
        groups = [
            unique[offset : offset + self.prefill_bank_slots]
            for offset in range(0, len(unique), self.prefill_bank_slots)
        ]
        store = self._store(layer) if groups else None
        top_k = int(inds.shape[-1])
        hidden = int(x.shape[-1])
        flat_x = x.reshape(-1, hidden)
        flat_scores = scores.reshape(-1)
        target_slots = {
            expert: slot
            for slot, expert in enumerate(target_state.expert_ids)
            if expert >= 0
        }
        contributions: list[mx.array] = []
        contribution_positions: list[mx.array] = []
        resident_values: list[mx.array] = []

        def compute_resident(
            resident_switch: Any,
            positions: tuple[int, ...],
            lookup: tuple[int, ...],
        ) -> None:
            if not positions:
                return
            position_array = mx.array(positions, dtype=mx.int32)
            token_positions = mx.array(
                [position // top_k for position in positions], dtype=mx.int32
            )
            slots = mx.array(
                [lookup[host_ids[position]] for position in positions],
                dtype=mx.int32,
            ).reshape(1, -1, 1)
            routed = resident_switch(flat_x[token_positions][None], slots).reshape(
                len(positions), hidden
            )
            weighted = routed * flat_scores[position_array, None].astype(
                routed.dtype
            )
            contributions.append(weighted)
            contribution_positions.append(position_array)
            resident_values.append(weighted)

        compute_started = time.perf_counter()
        compute_resident(switch, main_positions, main_lookup)
        tail = None
        if tail_positions:
            tail = self._tail_switch(layer, switch)
            compute_resident(tail, tail_positions, tail_lookup)
        self.prefill_compute_seconds += time.perf_counter() - compute_started
        if resident_values:
            # Let resident Metal work overlap the first SSD-direct miss load.
            mx.async_eval(*resident_values)

        bank_slots = max((len(group) for group in groups), default=0)
        bank_count = min(2, len(groups))
        banks = tuple(
            self._prefill_scratch_switch(switch, index, bank_slots)
            for index in range(bank_count)
        )
        pending: list[tuple[mx.array, list[mx.array]] | None] = [None] * bank_count

        ssd_unique_count = 0

        def load_group(bank: Any, group: tuple[int, ...]) -> None:
            """Fill one canonical bank from SSD plus existing resident slots."""

            nonlocal ssd_unique_count
            if not canonical_reuse:
                read_started = time.perf_counter()
                if not self._direct_load(
                    store, bank, tuple(range(len(group))), group
                ):
                    raise RuntimeError("GLM5 direct prefill lost its native loader")
                self.read_seconds += time.perf_counter() - read_started
                ssd_unique_count += len(group)
                return

            local = {expert: slot for slot, expert in enumerate(group)}
            from_main = tuple(
                expert for expert in group if main_lookup[expert] >= 0
            )
            from_tail = tuple(
                expert
                for expert in group
                if main_lookup[expert] < 0 and tail_lookup[expert] >= 0
            )
            from_ssd = tuple(
                expert
                for expert in group
                if main_lookup[expert] < 0 and tail_lookup[expert] < 0
            )
            if from_ssd:
                read_started = time.perf_counter()
                if not self._direct_load(
                    store,
                    bank,
                    tuple(local[expert] for expert in from_ssd),
                    from_ssd,
                ):
                    raise RuntimeError("GLM5 direct prefill lost its native loader")
                self.read_seconds += time.perf_counter() - read_started
                ssd_unique_count += len(from_ssd)
            if from_main:
                self._copy_switch_slots(
                    switch,
                    tuple(main_lookup[expert] for expert in from_main),
                    bank,
                    tuple(local[expert] for expert in from_main),
                )
            if from_tail:
                source_tail = tail or self._tail_switch(layer, switch)
                self._copy_switch_slots(
                    source_tail,
                    tuple(tail_lookup[expert] for expert in from_tail),
                    bank,
                    tuple(local[expert] for expert in from_tail),
                )

        if groups:
            load_group(banks[0], groups[0])

        for index, group in enumerate(groups):
            bank_index = index % bank_count
            bank = banks[bank_index]
            local = {expert: slot for slot, expert in enumerate(group)}
            positions = tuple(
                route for route, expert in enumerate(host_ids) if expert in local
            )
            token_positions = mx.array(
                [position // top_k for position in positions], dtype=mx.int32
            )
            position_array = mx.array(positions, dtype=mx.int32)
            local_ids = mx.array(
                [local[host_ids[position]] for position in positions],
                dtype=mx.int32,
            ).reshape(1, -1, 1)

            compute_started = time.perf_counter()
            routed = bank(flat_x[token_positions][None], local_ids).reshape(
                len(positions), hidden
            )
            weighted = (
                routed
                * flat_scores[position_array, None].astype(routed.dtype)
            )
            self.prefill_compute_seconds += time.perf_counter() - compute_started
            contributions.append(weighted)
            contribution_positions.append(position_array)

            retained = tuple(expert for expert in group if expert in target_slots)
            if resident_values and retained:
                # Target slots may evict experts whose outputs are still pending.
                mx.eval(*resident_values)
                resident_values.clear()
            promotion_arrays = self._copy_switch_slots(
                bank,
                tuple(local[expert] for expert in retained),
                switch,
                tuple(target_slots[expert] for expert in retained),
                evaluate=False,
            )
            mx.async_eval(weighted, *promotion_arrays)
            pending[bank_index] = (weighted, promotion_arrays)

            if index + 1 < len(groups):
                next_bank_index = (index + 1) % bank_count
                previous = pending[next_bank_index]
                if previous is not None:
                    mx.eval(previous[0], *previous[1])
                    pending[next_bank_index] = None
                next_group = groups[index + 1]
                load_group(banks[next_bank_index], next_group)

        for item in pending:
            if item is not None:
                mx.eval(item[0], *item[1])

        tail_promotions = tuple(
            expert
            for expert in target_slots
            if main_lookup[expert] < 0 and tail_lookup[expert] >= 0
        )
        if tail_promotions:
            if resident_values:
                mx.eval(*resident_values)
                resident_values.clear()
            if tail is None:
                tail = self._tail_switch(layer, switch)
            self._copy_switch_slots(
                tail,
                tuple(tail_lookup[expert] for expert in tail_promotions),
                switch,
                tuple(target_slots[expert] for expert in tail_promotions),
            )

        if resident_values:
            mx.eval(*resident_values)

        all_positions = mx.concatenate(contribution_positions)
        all_values = mx.concatenate(contributions, axis=0)
        order = mx.argsort(all_positions)
        routes = all_values[order].reshape(*inds.shape, hidden)
        output = routes.sum(axis=-2)
        mx.eval(output)
        self.policy.install(layer, target_state)
        self.experts_loaded += ssd_unique_count
        if store is not None:
            self.bytes_loaded += ssd_unique_count * store.record_bytes
        self.prefill_direct_calls += 1
        self.prefill_direct_groups += len(groups)
        self.prefill_main_routes += len(main_positions)
        self.prefill_tail_routes += len(tail_positions)
        self.prefill_miss_routes += len(miss_positions)
        self.prefill_unique_misses += ssd_unique_count
        self.prefill_experts_avoided += len(set(host_ids)) - ssd_unique_count
        return output

    @staticmethod
    def _keep_resident_slots_stable(
        current: LayerState,
        target: LayerState,
    ) -> LayerState:
        """Keep surviving residents in their already materialized slots.

        Policy replay can evict an expert and later admit it into a different
        slot during the same prefill.  The direct planner classifies routes
        against the pre-prefill lookup, so blindly installing that replayed
        tag state would associate the moved expert with weights that were
        never copied.  Preserve slots for the intersection and place only
        genuinely new residents into the remaining slots.
        """

        capacity = len(target.expert_ids)
        stable = LayerState(
            expert_ids=[-1] * capacity,
            segments=[EMPTY] * capacity,
            last_used=[0] * capacity,
            clock=target.clock,
        )
        current_slots = {
            expert: slot
            for slot, expert in enumerate(current.expert_ids)
            if expert >= 0
        }
        target_meta = {
            expert: (target.segments[slot], target.last_used[slot], slot)
            for slot, expert in enumerate(target.expert_ids)
            if expert >= 0
        }

        placed: set[int] = set()
        for expert, current_slot in current_slots.items():
            meta = target_meta.get(expert)
            if meta is None:
                continue
            segment, last_used, _ = meta
            stable.expert_ids[current_slot] = expert
            stable.segments[current_slot] = segment
            stable.last_used[current_slot] = last_used
            placed.add(expert)

        free = [slot for slot, expert in enumerate(stable.expert_ids) if expert < 0]
        for expert, (segment, last_used, preferred) in target_meta.items():
            if expert in placed:
                continue
            slot = preferred if stable.expert_ids[preferred] < 0 else free[0]
            stable.expert_ids[slot] = expert
            stable.segments[slot] = segment
            stable.last_used[slot] = last_used
            free.remove(slot)
        return stable

    def lookup(self, layer: int) -> tuple[int, ...]:
        return self.policy.lookup(layer)

    def tail_lookup(self, layer: int) -> tuple[int, ...]:
        if self.tail_policy is None:
            return (-1,) * self.num_experts
        return self.tail_policy.lookup(layer)

    def session_snapshot(self) -> dict[str, dict[int, tuple[int, ...]]]:
        """Capture resident expert identities for a serialized chat session."""

        with self._lock:
            layers = tuple(sorted(self._switches))
            main = {
                layer: tuple(
                    expert
                    for expert in self.policy.state(layer).expert_ids
                    if expert >= 0
                )
                for layer in layers
            }
            tail = (
                {
                    layer: tuple(
                        expert
                        for expert in self.tail_policy.state(layer).expert_ids
                        if expert >= 0
                    )
                    for layer in layers
                }
                if self.tail_policy is not None
                else {}
            )
            return {"main": main, "tail": tail}

    def restore_session(
        self, snapshot: dict[str, dict[int, tuple[int, ...]]]
    ) -> dict[str, int | float]:
        """Restore a session's L1/Hot identities at a request boundary."""

        started = time.perf_counter()
        loaded = 0
        loaded_bytes = 0
        with self._lock:
            plans: list[tuple[int, Any, Any, Any]] = []
            for tier, policy in (("main", self.policy), ("tail", self.tail_policy)):
                if policy is None:
                    continue
                for layer, requested in snapshot.get(tier, {}).items():
                    switch = self._switches.get(layer)
                    if switch is None or not requested:
                        continue
                    target = switch if tier == "main" else self._tail_switch(layer, switch)
                    plan = policy.plan(layer, requested)
                    if plan.missing:
                        plans.append((layer, target, policy, plan))

            if plans:
                mx.synchronize()
            for layer, target, policy, plan in plans:
                store = self._store(layer)
                read_started = time.perf_counter()
                if not self._direct_load(store, target, plan.slots, plan.missing):
                    raise RuntimeError(
                        "GLM5 session L1 restore requires the native direct loader"
                    )
                self.read_seconds += time.perf_counter() - read_started
                policy.publish(layer, plan)
                count = len(plan.missing)
                loaded += count
                loaded_bytes += count * store.record_bytes
            self.experts_loaded += loaded
            self.bytes_loaded += loaded_bytes
        return {
            "experts_loaded": loaded,
            "bytes_loaded": loaded_bytes,
            "seconds": time.perf_counter() - started,
        }

    def stats(self) -> dict[str, int | float | str]:
        return {
            "directory": str(self.directory),
            "capacity": self.capacity,
            "tail_slots": self.tail_slots,
            "layers": len(self._stores),
            "calls": self.calls,
            "hit_calls": self.hit_calls,
            "miss_calls": self.miss_calls,
            "prefill_calls": self.prefill_calls,
            "experts_loaded": self.experts_loaded,
            "bytes_loaded": self.bytes_loaded,
            "read_seconds": self.read_seconds,
            "materialize_seconds": self.materialize_seconds,
            "patch_seconds": self.patch_seconds,
            "ssd_to_ready_seconds": (
                self.read_seconds + self.materialize_seconds + self.patch_seconds
            ),
            "sync_seconds": self.sync_seconds,
            "overlap_calls": self.overlap_calls,
            "overlap_hit_routes": self.overlap_hit_routes,
            "overlap_miss_routes": self.overlap_miss_routes,
            "promote_seconds": self.promote_seconds,
            "tail_hit_routes": self.tail_hit_routes,
            "tail_miss_routes": self.tail_miss_routes,
            "l1_promotions_per_layer": self.l1_promotions_per_layer,
            "l1_promotions": self.l1_promotions,
            "l1_promotion_bytes": self.l1_promotion_bytes,
            "l1_promotion_seconds": self.l1_promotion_seconds,
            "prefill_bank_slots": self.prefill_bank_slots,
            "prefill_direct_calls": self.prefill_direct_calls,
            "prefill_direct_groups": self.prefill_direct_groups,
            "prefill_compute_seconds": self.prefill_compute_seconds,
            "prefill_main_routes": self.prefill_main_routes,
            "prefill_tail_routes": self.prefill_tail_routes,
            "prefill_miss_routes": self.prefill_miss_routes,
            "prefill_unique_misses": self.prefill_unique_misses,
            "prefill_experts_avoided": self.prefill_experts_avoided,
            "prefill_workspaces_released": self.prefill_workspaces_released,
            "prefill_release_seconds": self.prefill_release_seconds,
            "io_workers": self.io_workers,
            "direct_load_calls": self.direct_load_calls,
            "direct_load_bytes": self.direct_load_bytes,
            "direct_l1_mode": self.direct_l1_mode,
        }


__all__ = ["Glm5DynamicCache"]
