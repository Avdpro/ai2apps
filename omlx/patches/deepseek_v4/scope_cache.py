"""Runtime helpers for exact DeepSeek V4 scope-cache fallback."""

from __future__ import annotations

import copy
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import mlx.core as mx

from omlx.cache.direct_l1 import direct_l1_mode, use_direct_l1
from omlx.cache.moe_expert_store import ExpertMajorStore
from omlx.custom_kernels.glm_moe_dsa import fast as glm_fast

from .switch_layers import SwitchGLU


@dataclass
class _HotBank:
    ids: tuple[int, ...]
    recency: list[int]
    switch: SwitchGLU


@dataclass
class _PreparedTransientRecords:
    layer: int
    ids: tuple[int, ...]
    buffers: dict[int, bytearray]
    record_bytes: int
    read_seconds: float


@dataclass(frozen=True)
class _PreparedDirectRequest:
    layer: int
    ids: tuple[int, ...]


class ScopeFallbackLoader:
    """Load exact L3 experts and assemble a temporary compact SwitchGLU."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._stores: dict[int, ExpertMajorStore] = {}
        self._staging_buffers: list[bytearray] = []
        self._hot: dict[int, _HotBank] = {}
        self._lock = threading.Lock()
        self._decode_miss_observer: Callable[[int, list[int]], None] | None = None
        self._route_telemetry_enabled = False
        self._prefill_route_telemetry_enabled = False
        self._route_histograms: dict[int, mx.array] = {}
        self._route_miss_events: dict[int, mx.array] = {}
        self.route_telemetry_records = 0
        self.route_telemetry_drains = 0
        self.route_telemetry_bytes_read = 0
        self.no_cache = os.environ.get(
            "OMLX_DEEPSEEK_V4_SCOPE_NOCACHE", ""
        ).strip().lower() in ("1", "true", "yes", "on")
        self.hot_slots = int(os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS", "8"))
        if not 0 <= self.hot_slots <= 32:
            raise ValueError("OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS must be 0..32")
        self.io_workers = int(os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_IO_WORKERS", "4"))
        if not 1 <= self.io_workers <= 16:
            raise ValueError("OMLX_DEEPSEEK_V4_SCOPE_IO_WORKERS must be 1..16")
        self._io_pool = (
            ThreadPoolExecutor(
                max_workers=self.io_workers,
                thread_name_prefix="omlx-moe-read",
            )
            if self.io_workers > 1
            else None
        )
        # This single coordinator may wait on the ordinary read pool while
        # Metal evaluates the current bank. It never creates MLX arrays: GPU
        # publication remains on the inference thread and its active stream.
        self._prefetch_pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="omlx-moe-prefetch",
        )
        self.experts_loaded = 0
        self.bytes_loaded = 0
        self.load_seconds = 0.0
        self.fallback_calls = 0
        self.hot_only_calls = 0
        self.transient_calls = 0
        self.transient_experts_loaded = 0
        self.decode_experts_loaded = 0
        self.max_request_experts = 0
        self.lossy_routes_replaced = 0
        self.lossy_l3_misses_avoided = 0
        self.lossy_l3_layers_avoided = 0
        self.l1_rebuilds = 0
        self.l1_rebuild_experts_loaded = 0
        self.l1_rebuild_bytes = 0
        self.l1_rebuild_seconds = 0.0
        self.l1_patch_calls = 0
        self.l1_patch_slots = 0
        self.l1_patch_bytes = 0
        self.l1_patch_seconds = 0.0
        self.l1_patch_prepare_layers = 0
        self.l1_patch_prepare_seconds = 0.0
        self.prefetch_submits = 0
        self.prefetch_hits = 0
        self.prefetch_wait_seconds = 0.0
        self.prefetch_read_seconds = 0.0
        self.direct_l1_mode = direct_l1_mode()
        self.direct_load_calls = 0
        self.direct_load_experts = 0
        self.direct_load_bytes = 0
        self.direct_load_seconds = 0.0
        self.direct_prefill = os.environ.get(
            "OMLX_DEEPSEEK_V4_DIRECT_PREFILL", ""
        ).strip().lower() in ("1", "true", "yes", "on")

    def set_decode_miss_observer(
        self, observer: Callable[[int, list[int]], None] | None
    ) -> None:
        """Install a serialized Decode observer at the existing host boundary."""

        self._decode_miss_observer = observer

    def reset_route_telemetry(
        self, *, enabled: bool, prefill_enabled: bool = False
    ) -> None:
        """Start a new device-resident route telemetry window."""

        self._route_telemetry_enabled = enabled
        self._prefill_route_telemetry_enabled = prefill_enabled
        self._route_histograms = {}
        self._route_miss_events = {}

    def enable_route_telemetry(self) -> None:
        """Enable collection without discarding an in-flight window."""

        self._route_telemetry_enabled = True

    def route_telemetry_enabled(self, *, prefill: bool) -> bool:
        return (
            self._prefill_route_telemetry_enabled
            if prefill
            else self._route_telemetry_enabled
        )

    def record_routes(
        self,
        layer: int,
        expert_ids: mx.array,
        expert_to_slot: mx.array,
        *,
        prefill: bool,
    ) -> None:
        """Accumulate route frequency without synchronizing the host."""

        if not self.route_telemetry_enabled(prefill=prefill):
            return
        self.record_decode_routes(layer, expert_ids, expert_to_slot, _force=True)

    def record_decode_routes(
        self,
        layer: int,
        expert_ids: mx.array,
        expert_to_slot: mx.array,
        *,
        _force: bool = False,
    ) -> None:
        """Accumulate route frequency and L1-miss events without a host wait."""

        if (not _force and not self._route_telemetry_enabled) or not 3 <= layer < 43:
            return
        flat = expert_ids.reshape(-1)
        universe = mx.arange(256, dtype=flat.dtype)
        counts = mx.sum(flat[:, None] == universe[None, :], axis=0).astype(mx.int32)
        miss_event = mx.any(expert_to_slot[flat] < 0).astype(mx.int32)
        histogram = self._route_histograms.get(layer)
        misses = self._route_miss_events.get(layer)
        histogram = counts if histogram is None else histogram + counts
        misses = miss_event if misses is None else misses + miss_event
        self._route_histograms[layer] = histogram
        self._route_miss_events[layer] = misses
        # Submit the tiny counter kernels on the inference stream, but do not
        # wait for them on the host. The review boundary performs the only read.
        mx.async_eval(histogram, misses)
        self.route_telemetry_records += 1

    def drain_route_telemetry(self) -> dict[str, Any]:
        """Read one device window and immediately reset its counters."""

        layers = sorted(self._route_histograms)
        arrays = [self._route_histograms[layer] for layer in layers]
        arrays += [self._route_miss_events[layer] for layer in layers]
        if arrays:
            mx.eval(*arrays)
        histograms = {
            layer: [int(value) for value in self._route_histograms[layer].tolist()]
            for layer in layers
        }
        miss_events = {
            layer: int(self._route_miss_events[layer].item()) for layer in layers
        }
        self._route_histograms = {}
        self._route_miss_events = {}
        self.route_telemetry_drains += 1
        self.route_telemetry_bytes_read += len(layers) * (256 + 1) * 4
        return {
            "histograms": histograms,
            "miss_events": miss_events,
            "miss_layer_steps": sum(miss_events.values()),
            "layers": len(layers),
        }

    def hot_ids(self, layer: int) -> tuple[int, ...]:
        """Return the current Hot8 IDs without evaluating any MLX arrays."""

        with self._lock:
            state = self._hot.get(layer)
            return state.ids if state is not None else ()

    def expert_record_bytes(self, layer: int) -> int:
        """Return the on-disk bytes for one routed expert in ``layer``."""

        return int(self._store(layer).record_bytes)

    def record_lossy(
        self,
        routes_replaced: int,
        l3_misses_before: int,
        l3_misses_after: int,
    ) -> None:
        """Record counters at the existing miss-detection sync boundary."""

        self.lossy_routes_replaced += routes_replaced
        avoided = max(0, l3_misses_before - l3_misses_after)
        self.lossy_l3_misses_avoided += avoided
        if l3_misses_before and not l3_misses_after:
            self.lossy_l3_layers_avoided += 1

    def set_io_workers(self, workers: int) -> None:
        """Reconfigure read parallelism between quiescent benchmark runs."""

        if not 1 <= workers <= 16:
            raise ValueError("I/O workers must be 1..16")
        with self._lock:
            if workers == self.io_workers:
                return
            old_pool = self._io_pool
            self.io_workers = workers
            self._io_pool = (
                ThreadPoolExecutor(
                    max_workers=workers,
                    thread_name_prefix="omlx-moe-read",
                )
                if workers > 1
                else None
            )
            if old_pool is not None:
                old_pool.shutdown(wait=True)

    def clear_hot(self) -> None:
        """Drop rolling banks without touching immutable Top60 weights."""

        with self._lock:
            self._hot.clear()

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(self.directory / f"layer-{layer:03d}.moe")
            if self.no_cache:
                store.set_no_cache()
            self._stores[layer] = store
        return store

    @staticmethod
    def _make_switch(
        resident: SwitchGLU,
        ids: tuple[int, ...],
        tensors: dict[str, mx.array],
    ) -> SwitchGLU:
        fallback = copy.copy(resident)
        fallback.global_num_experts = len(ids)
        for projection_name in ("gate_proj", "down_proj", "up_proj"):
            projection = copy.copy(getattr(resident, projection_name))
            projection.weight = tensors[f"{projection_name}.weight"]
            scales = tensors[f"{projection_name}.scales"]
            if scales.dtype != projection.scales.dtype:
                scales = scales.astype(projection.scales.dtype)
            projection.scales = scales
            biases = tensors.get(f"{projection_name}.biases")
            if biases is not None:
                resident_biases = projection.get("biases")
                if (
                    resident_biases is not None
                    and biases.dtype != resident_biases.dtype
                ):
                    biases = biases.astype(resident_biases.dtype)
                projection.biases = biases
            setattr(fallback, projection_name, projection)
        return fallback

    @staticmethod
    def _direct_store_compatible(store: ExpertMajorStore) -> bool:
        return tuple(tensor.name for tensor in store.tensors) == (
            "gate_proj.weight",
            "gate_proj.scales",
            "down_proj.weight",
            "down_proj.scales",
            "up_proj.weight",
            "up_proj.scales",
        )

    def _direct_enabled(self) -> bool:
        return use_direct_l1(
            native_available=("preadv_fused_experts" in glm_fast.native_symbols())
        )

    def _make_fixed_hot_switch(
        self,
        resident: SwitchGLU,
        ids: tuple[int, ...],
        records: dict[int, dict[str, Any]] | None = None,
        source: SwitchGLU | None = None,
        source_ids: tuple[int, ...] = (),
    ) -> SwitchGLU:
        """Allocate Hot8's final capacity once, optionally seeding loaded IDs."""

        tensors: dict[str, mx.array] = {}
        arrays: list[mx.array] = []
        for projection_name in ("gate_proj", "down_proj", "up_proj"):
            projection = getattr(resident, projection_name)
            for tensor_name in ("weight", "scales"):
                current = projection.get(tensor_name)
                value = mx.zeros(
                    (self.hot_slots, *current.shape[1:]), dtype=current.dtype
                )
                if records is not None:
                    for slot, expert_id in enumerate(ids):
                        selected = records[expert_id][
                            f"{projection_name}.{tensor_name}"
                        ]
                        if selected.dtype != value.dtype:
                            selected = selected.astype(value.dtype)
                        value[slot] = selected
                elif source is not None:
                    source_slots = {
                        expert_id: slot for slot, expert_id in enumerate(source_ids)
                    }
                    source_projection = getattr(source, projection_name)
                    source_tensor = source_projection.get(tensor_name)
                    for slot, expert_id in enumerate(ids):
                        selected = source_tensor[source_slots[expert_id]]
                        if selected.dtype != value.dtype:
                            selected = selected.astype(value.dtype)
                        value[slot] = selected
                tensors[f"{projection_name}.{tensor_name}"] = value
                arrays.append(value)
        mx.eval(*arrays)
        switch = self._make_switch(resident, ids, tensors)
        switch._omlx_direct_hot_capacity = self.hot_slots
        return switch

    def _make_empty_direct_switch(
        self,
        resident: SwitchGLU,
        ids: tuple[int, ...],
    ) -> SwitchGLU:
        tensors: dict[str, mx.array] = {}
        arrays: list[mx.array] = []
        for projection_name in ("gate_proj", "down_proj", "up_proj"):
            projection = getattr(resident, projection_name)
            for tensor_name in ("weight", "scales"):
                current = projection.get(tensor_name)
                value = mx.zeros((len(ids), *current.shape[1:]), dtype=current.dtype)
                tensors[f"{projection_name}.{tensor_name}"] = value
                arrays.append(value)
        mx.eval(*arrays)
        return self._make_switch(resident, ids, tensors)

    def _read_records(
        self,
        layer: int,
        expert_ids: list[int],
    ) -> tuple[dict[int, dict[str, Any]], int]:
        store = self._store(layer)
        while len(self._staging_buffers) < len(expert_ids):
            self._staging_buffers.append(store.allocate_staging())

        # Quantized DeepSeek checkpoints may use different bit widths across
        # layers, so one expert record is not necessarily a model-wide
        # constant. Reuse staging storage only when its exact byte size matches
        # the current layer's store.
        for index in range(len(expert_ids)):
            if len(self._staging_buffers[index]) != store.record_bytes:
                self._staging_buffers[index] = store.allocate_staging()

        buffers = self._staging_buffers[: len(expert_ids)]
        if self._io_pool is not None and len(expert_ids) > 1:
            futures = [
                self._io_pool.submit(store.read_into, expert_id, staging)
                for expert_id, staging in zip(expert_ids, buffers, strict=True)
            ]
            raw_records = [future.result() for future in futures]
        else:
            raw_records = [
                store.read_into(expert_id, staging)
                for expert_id, staging in zip(expert_ids, buffers, strict=True)
            ]

        records = {}
        for expert_id, record in zip(expert_ids, raw_records, strict=True):
            records[expert_id] = store.mlx_tensor_views(record, copy_record=True)
        return records, store.record_bytes

    def _read_transient_records_detached(
        self,
        layer: int,
        expert_ids: tuple[int, ...],
    ) -> _PreparedTransientRecords:
        """Read one future bank into private CPU buffers only."""

        started = time.perf_counter()
        store = self._store(layer)
        buffers = {expert_id: store.allocate_staging() for expert_id in expert_ids}
        if self._io_pool is not None and len(expert_ids) > 1:
            futures = [
                self._io_pool.submit(store.read_into, expert_id, buffers[expert_id])
                for expert_id in expert_ids
            ]
            for future in futures:
                future.result()
        else:
            for expert_id in expert_ids:
                store.read_into(expert_id, buffers[expert_id])
        elapsed = time.perf_counter() - started
        return _PreparedTransientRecords(
            layer=layer,
            ids=expert_ids,
            buffers=buffers,
            record_bytes=store.record_bytes,
            read_seconds=elapsed,
        )

    def prefetch_transient_records(
        self,
        layer: int,
        expert_ids: list[int],
    ) -> Future[_PreparedTransientRecords | _PreparedDirectRequest]:
        """Start pure CPU/SSD preparation for the next Prefill bank."""

        ids = tuple(expert_ids)
        if not ids:
            raise ValueError("cannot prefetch an empty fallback expert bank")
        self.prefetch_submits += 1
        if self.direct_prefill and self._direct_enabled():
            future: Future[_PreparedTransientRecords | _PreparedDirectRequest] = (
                Future()
            )
            future.set_result(_PreparedDirectRequest(layer=layer, ids=ids))
            return future
        return self._prefetch_pool.submit(
            self._read_transient_records_detached,
            layer,
            ids,
        )

    @staticmethod
    def _stack_records(
        ids: tuple[int, ...], records: dict[int, dict[str, Any]]
    ) -> dict[str, mx.array]:
        return {
            name: mx.stack([records[expert_id][name] for expert_id in ids])
            for name in records[ids[0]]
        }

    def build_transient_switch(
        self,
        layer: int,
        expert_ids: list[int],
        resident: SwitchGLU,
        seed_ids: list[int] | None = None,
        prepared: Future[_PreparedTransientRecords | _PreparedDirectRequest]
        | None = None,
    ) -> tuple[SwitchGLU, tuple[int, ...]]:
        """Build a Prefill-only tail bank and seed Decode's rolling Top8."""

        if not expert_ids:
            raise ValueError("cannot build an empty fallback expert bank")
        started = time.perf_counter()
        with self._lock:
            ids = tuple(expert_ids)
            prefetched = prepared.result() if prepared is not None else None
            direct = (
                self.direct_prefill
                and self._direct_enabled()
                and self._direct_store_compatible(self._store(layer))
                and (
                    prefetched is None or isinstance(prefetched, _PreparedDirectRequest)
                )
            )
            records = None
            if direct:
                if isinstance(prefetched, _PreparedDirectRequest) and (
                    prefetched.layer != layer or prefetched.ids != ids
                ):
                    raise ValueError("prefetched direct bank does not match request")
                store = self._store(layer)
                fallback = self._make_empty_direct_switch(resident, ids)
                if not self._direct_load_slots(
                    store,
                    fallback,
                    list(range(len(ids))),
                    list(ids),
                ):
                    raise RuntimeError("direct Prefill unexpectedly fell back")
                record_bytes = store.record_bytes
            elif prefetched is None:
                records, record_bytes = self._read_records(layer, expert_ids)
            else:
                wait_started = time.perf_counter()
                self.prefetch_wait_seconds += time.perf_counter() - wait_started
                if isinstance(prefetched, _PreparedDirectRequest):
                    raise RuntimeError("direct Prefill marker reached legacy path")
                if prefetched.layer != layer or prefetched.ids != ids:
                    raise ValueError("prefetched expert bank does not match request")
                store = self._store(layer)
                records = {
                    expert_id: store.mlx_tensor_views(
                        prefetched.buffers[expert_id], copy_record=True
                    )
                    for expert_id in ids
                }
                record_bytes = prefetched.record_bytes
                self.prefetch_hits += 1
                self.prefetch_read_seconds += prefetched.read_seconds
            if not direct:
                assert records is not None
                stacked = self._stack_records(ids, records)
                mx.eval(*stacked.values())
                fallback = self._make_switch(resident, ids, stacked)

            seeds = (
                tuple(dict.fromkeys(seed_ids or ()))[-self.hot_slots :]
                if self.hot_slots
                else ()
            )
            if seeds:
                store = self._store(layer)
                if self._direct_enabled() and self._direct_store_compatible(store):
                    hot_switch = (
                        self._make_fixed_hot_switch(
                            resident,
                            seeds,
                            source=fallback,
                            source_ids=ids,
                        )
                        if direct
                        else self._make_fixed_hot_switch(resident, seeds, records)
                    )
                else:
                    hot_tensors = {
                        name: mx.stack(
                            [records[expert_id][name] for expert_id in seeds]
                        )
                        for name in records[seeds[0]]
                    }
                    hot_switch = self._make_switch(resident, seeds, hot_tensors)
                self._hot[layer] = _HotBank(seeds, list(seeds), hot_switch)

        elapsed = time.perf_counter() - started
        self.experts_loaded += len(expert_ids)
        self.bytes_loaded += len(expert_ids) * record_bytes
        self.load_seconds += elapsed
        self.fallback_calls += 1
        self.transient_calls += 1
        self.transient_experts_loaded += len(expert_ids)
        self.max_request_experts = max(self.max_request_experts, len(expert_ids))
        return fallback, ids

    def rebuild_resident_switch(
        self,
        layer: int,
        expert_ids: list[int],
        resident: SwitchGLU,
    ) -> tuple[SwitchGLU, tuple[int, ...]]:
        """Prepare one replacement L1 layer without mutating the live mapping."""

        expected = int(resident.up_proj.num_experts)
        if len(expert_ids) != expected or len(set(expert_ids)) != expected:
            raise ValueError(
                f"adaptive L1 layer must contain {expected} unique experts"
            )
        started = time.perf_counter()
        with self._lock:
            ids = tuple(expert_ids)
            records, record_bytes = self._read_records(layer, expert_ids)
            stacked = self._stack_records(ids, records)
            mx.eval(*stacked.values())
            replacement = self._make_switch(resident, ids, stacked)
        elapsed = time.perf_counter() - started
        loaded_bytes = len(ids) * record_bytes
        self.experts_loaded += len(ids)
        self.bytes_loaded += loaded_bytes
        self.load_seconds += elapsed
        self.l1_rebuilds += 1
        self.l1_rebuild_experts_loaded += len(ids)
        self.l1_rebuild_bytes += loaded_bytes
        self.l1_rebuild_seconds += elapsed
        return replacement, ids

    def _prepare_mutable_switch(self, resident: SwitchGLU) -> None:
        """Detach one resident bank from checkpoint/concat graphs for slot writes."""

        if getattr(resident, "_ai2apps_mutable_backing", False):
            return
        started = time.perf_counter()
        replacements: list[tuple[Any, str, mx.array]] = []
        arrays: list[mx.array] = []
        for projection_name in ("gate_proj", "down_proj", "up_proj"):
            projection = getattr(resident, projection_name)
            for tensor_name in ("weight", "scales", "biases"):
                value = projection.get(tensor_name)
                if value is None:
                    continue
                backing = mx.zeros_like(value)
                backing[:] = value
                replacements.append((projection, tensor_name, backing))
                arrays.append(backing)
        if arrays:
            mx.eval(*arrays)
        for projection, tensor_name, backing in replacements:
            setattr(projection, tensor_name, backing)
        resident._ai2apps_mutable_backing = True
        self.l1_patch_prepare_layers += 1
        self.l1_patch_prepare_seconds += time.perf_counter() - started

    def _direct_load_slots(
        self,
        store: ExpertMajorStore,
        switch: SwitchGLU,
        slots: list[int],
        expert_ids: list[int],
    ) -> bool:
        """Read DSV4F's six disk-ready segments into final Metal-visible slots."""

        if not self._direct_enabled():
            return False
        if not self._direct_store_compatible(store):
            if self.direct_l1_mode == "on":
                raise ValueError(
                    "direct DSV4F loading requires compute-ready six-segment records"
                )
            return False
        arrays = (
            switch.gate_proj.weight,
            switch.gate_proj.scales,
            switch.down_proj.weight,
            switch.down_proj.scales,
            switch.up_proj.weight,
            switch.up_proj.scales,
        )
        # The native writer mutates unified-memory backing directly. Drain all
        # prior Metal consumers before exposing those slots to POSIX preadv.
        mx.synchronize()
        started = time.perf_counter()
        loaded = glm_fast.preadv_expert_segments(
            store.fileno(),
            store.data_offset,
            store.record_bytes,
            expert_ids,
            slots,
            *arrays,
            io_workers=self.io_workers,
        )
        elapsed = time.perf_counter() - started
        expected_bytes = len(expert_ids) * store.record_bytes
        if loaded != expected_bytes:
            raise RuntimeError(
                f"native DSV4F loader reported {loaded} bytes, "
                f"expected {expected_bytes}"
            )
        self.direct_load_calls += 1
        self.direct_load_experts += len(expert_ids)
        self.direct_load_bytes += loaded
        self.direct_load_seconds += elapsed
        return True

    def patch_resident_switch(
        self,
        layer: int,
        slots: list[int],
        expert_ids: list[int],
        resident: SwitchGLU,
    ) -> tuple[SwitchGLU, tuple[int, ...]]:
        """Overwrite only changed physical L1 slots in one quiescent layer."""

        if not slots or len(slots) != len(expert_ids):
            raise ValueError("adaptive L1 slot patch has mismatched inputs")
        expected = int(resident.up_proj.num_experts)
        if len(set(slots)) != len(slots) or min(slots) < 0 or max(slots) >= expected:
            raise ValueError("adaptive L1 slot patch contains invalid slots")
        num_experts = self._store(layer).num_experts
        if (
            len(set(expert_ids)) != len(expert_ids)
            or min(expert_ids) < 0
            or max(expert_ids) >= num_experts
        ):
            raise ValueError("adaptive L1 slot patch contains invalid expert IDs")
        started = time.perf_counter()
        with self._lock:
            self._prepare_mutable_switch(resident)
            ids = tuple(expert_ids)
            store = self._store(layer)
            direct = self._direct_load_slots(store, resident, slots, expert_ids)
            record_bytes = store.record_bytes
            if not direct:
                records, record_bytes = self._read_records(layer, expert_ids)
                stacked = self._stack_records(ids, records)
                slot_array = mx.array(slots, dtype=mx.int32)
                arrays: list[mx.array] = []
                checks: list[mx.array] = []
                validate = os.environ.get(
                    "OMLX_DEEPSEEK_V4_L1_PATCH_VALIDATE", ""
                ).strip().lower() in ("1", "true", "yes", "on")
                for projection_name in ("gate_proj", "down_proj", "up_proj"):
                    projection = getattr(resident, projection_name)
                    for tensor_name in ("weight", "scales", "biases"):
                        current = projection.get(tensor_name)
                        replacement = stacked.get(f"{projection_name}.{tensor_name}")
                        if current is None or replacement is None:
                            continue
                        if replacement.dtype != current.dtype:
                            replacement = replacement.astype(current.dtype)
                        current[slot_array] = replacement
                        arrays.append(current)
                        if validate:
                            checks.append(mx.all(current[slot_array] == replacement))
                mx.eval(*arrays, *checks)
                if checks and not all(bool(value.item()) for value in checks):
                    raise RuntimeError("DeepSeek adaptive L1 slot validation failed")
        elapsed = time.perf_counter() - started
        loaded_bytes = len(ids) * record_bytes
        self.experts_loaded += len(ids)
        self.bytes_loaded += loaded_bytes
        self.load_seconds += elapsed
        self.l1_rebuilds += 1
        self.l1_rebuild_experts_loaded += len(ids)
        self.l1_rebuild_bytes += loaded_bytes
        self.l1_rebuild_seconds += elapsed
        self.l1_patch_calls += 1
        self.l1_patch_slots += len(slots)
        self.l1_patch_bytes += loaded_bytes
        self.l1_patch_seconds += elapsed
        return resident, ids

    def resolve_hot_switch(
        self,
        layer: int,
        expert_ids: list[int],
        resident: SwitchGLU,
    ) -> tuple[SwitchGLU, tuple[int, ...]]:
        """Resolve Decode misses through a persistent per-layer rolling Top8."""

        if not expert_ids:
            raise ValueError("cannot resolve an empty fallback expert bank")
        requested = list(dict.fromkeys(expert_ids))
        observer = self._decode_miss_observer
        if observer is not None:
            observer(layer, requested)
        if self.hot_slots == 0 or len(requested) > self.hot_slots:
            # A batched Decode can select more IDs than the rolling bank can
            # represent.  Preserve exactness with a transient bank and retain
            # only the most recent eight for the following step.
            return self.build_transient_switch(
                layer,
                requested,
                resident,
                seed_ids=requested[-self.hot_slots :] if self.hot_slots else None,
            )
        started = time.perf_counter()
        loaded = 0
        record_bytes = 0
        with self._lock:
            state = self._hot.get(layer)
            if state is None and self._direct_enabled():
                store = self._store(layer)
                if self._direct_store_compatible(store):
                    state = _HotBank(
                        ids=(),
                        recency=[],
                        switch=self._make_fixed_hot_switch(resident, ()),
                    )
                    self._hot[layer] = state
            old_ids = state.ids if state is not None else ()
            old_slots = {expert_id: slot for slot, expert_id in enumerate(old_ids)}
            new_ids = [
                expert_id for expert_id in requested if expert_id not in old_slots
            ]

            recency = list(state.recency) if state is not None else []
            for expert_id in requested:
                if expert_id in recency:
                    recency.remove(expert_id)
                recency.append(expert_id)

            if not new_ids:
                assert state is not None
                state.recency = recency[-self.hot_slots :]
                self.hot_only_calls += 1
                self.fallback_calls += 1
                self.max_request_experts = max(self.max_request_experts, len(requested))
                return state.switch, state.ids

            # A direct bank has its final Hot8 capacity from creation onward.
            # Fill empty slots first, then replace only LRU victims; neither
            # case reconstructs or reorders the six backing arrays.
            direct_hot = (
                state is not None
                and getattr(state.switch, "_omlx_direct_hot_capacity", 0)
                == self.hot_slots
                and self._direct_enabled()
            )
            if direct_hot:
                desired_recency = recency[-self.hot_slots :]
                desired = set(desired_recency)
                victims = [
                    expert_id for expert_id in old_ids if expert_id not in desired
                ]
                slots = [old_slots[expert_id] for expert_id in victims]
                slots.extend(range(len(old_ids), self.hot_slots))
                slots = slots[: len(new_ids)]
                if len(slots) != len(new_ids):
                    raise RuntimeError("rolling Hot8 could not select enough slots")
                store = self._store(layer)
                if self._direct_load_slots(store, state.switch, slots, new_ids):
                    physical_ids = list(old_ids) + [-1] * (
                        self.hot_slots - len(old_ids)
                    )
                    for slot, expert_id in zip(slots, new_ids, strict=True):
                        physical_ids[slot] = expert_id
                    state.ids = tuple(
                        expert_id for expert_id in physical_ids if expert_id >= 0
                    )
                    # Preserve the legacy rebuild path's exact LRU ordering,
                    # including requests that interleave hits and new IDs.
                    state.recency = desired_recency
                    loaded = len(new_ids)
                    record_bytes = store.record_bytes
                    bank_ids = state.ids
                    switch = state.switch
                else:
                    direct_hot = False

            if not direct_hot:
                new_records, record_bytes = self._read_records(layer, new_ids)
                loaded = len(new_ids)
                bank_ids = tuple(recency[-self.hot_slots :])
                tensors: dict[str, mx.array] = {}
                sample = next(iter(new_records.values()))
                for name in sample:
                    projection_name, tensor_name = name.split(".", 1)
                    old_tensor = (
                        getattr(getattr(state.switch, projection_name), tensor_name)
                        if state is not None
                        else None
                    )
                    values = []
                    for expert_id in bank_ids:
                        if expert_id in new_records:
                            values.append(new_records[expert_id][name])
                        else:
                            values.append(old_tensor[old_slots[expert_id]])
                    tensors[name] = mx.stack(values)
                mx.eval(*tensors.values())
                switch = self._make_switch(resident, bank_ids, tensors)
                self._hot[layer] = _HotBank(bank_ids, list(bank_ids), switch)

        elapsed = time.perf_counter() - started
        self.experts_loaded += loaded
        self.decode_experts_loaded += loaded
        self.bytes_loaded += loaded * record_bytes
        self.load_seconds += elapsed
        self.fallback_calls += 1
        self.max_request_experts = max(self.max_request_experts, len(expert_ids))
        return switch, bank_ids

    def stats(self) -> dict[str, float | int | str]:
        return {
            "fallback_calls": self.fallback_calls,
            "hot_only_calls": self.hot_only_calls,
            "transient_calls": self.transient_calls,
            "transient_experts_loaded": self.transient_experts_loaded,
            "decode_experts_loaded": self.decode_experts_loaded,
            "experts_loaded": self.experts_loaded,
            "bytes_loaded": self.bytes_loaded,
            "load_seconds": self.load_seconds,
            "max_request_experts": self.max_request_experts,
            "lossy_routes_replaced": self.lossy_routes_replaced,
            "lossy_l3_misses_avoided": self.lossy_l3_misses_avoided,
            "lossy_l3_layers_avoided": self.lossy_l3_layers_avoided,
            "l1_rebuilds": self.l1_rebuilds,
            "l1_rebuild_experts_loaded": self.l1_rebuild_experts_loaded,
            "l1_rebuild_bytes": self.l1_rebuild_bytes,
            "l1_rebuild_seconds": self.l1_rebuild_seconds,
            "l1_patch_calls": self.l1_patch_calls,
            "l1_patch_slots": self.l1_patch_slots,
            "l1_patch_bytes": self.l1_patch_bytes,
            "l1_patch_seconds": self.l1_patch_seconds,
            "l1_patch_prepare_layers": self.l1_patch_prepare_layers,
            "l1_patch_prepare_seconds": self.l1_patch_prepare_seconds,
            "route_telemetry_records": self.route_telemetry_records,
            "route_telemetry_drains": self.route_telemetry_drains,
            "route_telemetry_bytes_read": self.route_telemetry_bytes_read,
            "hot_layers": len(self._hot),
            "hot_slots": self.hot_slots,
            "io_workers": self.io_workers,
            "direct_l1_mode": self.direct_l1_mode,
            "direct_prefill": int(self.direct_prefill),
            "direct_load_calls": self.direct_load_calls,
            "direct_load_experts": self.direct_load_experts,
            "direct_load_bytes": self.direct_load_bytes,
            "direct_load_seconds": self.direct_load_seconds,
            "prefetch_submits": self.prefetch_submits,
            "prefetch_hits": self.prefetch_hits,
            "prefetch_wait_seconds": self.prefetch_wait_seconds,
            "prefetch_read_seconds": self.prefetch_read_seconds,
        }


@cache
def get_scope_fallback_loader(directory: str) -> ScopeFallbackLoader:
    return ScopeFallbackLoader(Path(directory).expanduser().resolve())
