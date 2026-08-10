"""Runtime helpers for exact DeepSeek V4 scope-cache fallback."""

from __future__ import annotations

import copy
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Callable

import mlx.core as mx

from omlx.cache.moe_expert_store import ExpertMajorStore

from .switch_layers import SwitchGLU


@dataclass
class _HotBank:
    ids: tuple[int, ...]
    recency: list[int]
    switch: SwitchGLU


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
        self._route_histograms: dict[int, mx.array] = {}
        self._route_miss_events: dict[int, mx.array] = {}
        self.route_telemetry_records = 0
        self.route_telemetry_drains = 0
        self.route_telemetry_bytes_read = 0
        self.no_cache = os.environ.get(
            "OMLX_DEEPSEEK_V4_SCOPE_NOCACHE", ""
        ).strip().lower() in ("1", "true", "yes", "on")
        self.hot_slots = int(
            os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS", "8")
        )
        if not 0 <= self.hot_slots <= 32:
            raise ValueError("OMLX_DEEPSEEK_V4_SCOPE_HOT_SLOTS must be 0..32")
        self.io_workers = int(
            os.environ.get("OMLX_DEEPSEEK_V4_SCOPE_IO_WORKERS", "4")
        )
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

    def set_decode_miss_observer(
        self, observer: Callable[[int, list[int]], None] | None
    ) -> None:
        """Install a serialized Decode observer at the existing host boundary."""

        self._decode_miss_observer = observer

    def reset_route_telemetry(self, *, enabled: bool) -> None:
        """Start a new device-resident Decode telemetry window."""

        self._route_telemetry_enabled = enabled
        self._route_histograms = {}
        self._route_miss_events = {}

    def enable_route_telemetry(self) -> None:
        """Enable collection without discarding an in-flight window."""

        self._route_telemetry_enabled = True

    def record_decode_routes(
        self,
        layer: int,
        expert_ids: mx.array,
        expert_to_slot: mx.array,
    ) -> None:
        """Accumulate route frequency and L1-miss events without a host wait."""

        if not self._route_telemetry_enabled or not 3 <= layer < 43:
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
    ) -> tuple[SwitchGLU, tuple[int, ...]]:
        """Build a Prefill-only tail bank and seed Decode's rolling Top8."""

        if not expert_ids:
            raise ValueError("cannot build an empty fallback expert bank")
        started = time.perf_counter()
        with self._lock:
            ids = tuple(expert_ids)
            records, record_bytes = self._read_records(layer, expert_ids)
            stacked = self._stack_records(ids, records)
            mx.eval(*stacked.values())
            fallback = self._make_switch(resident, ids, stacked)

            seeds = (
                tuple(dict.fromkeys(seed_ids or ()))[-self.hot_slots :]
                if self.hot_slots
                else ()
            )
            if seeds:
                hot_tensors = {
                    name: mx.stack(
                        [records[expert_id][name] for expert_id in seeds]
                    )
                    for name in records[seeds[0]]
                }
                self._hot[layer] = _HotBank(
                    seeds,
                    list(seeds),
                    self._make_switch(resident, seeds, hot_tensors),
                )

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
        if (
            len(set(slots)) != len(slots)
            or min(slots) < 0
            or max(slots) >= expected
        ):
            raise ValueError("adaptive L1 slot patch contains invalid slots")
        if (
            len(set(expert_ids)) != len(expert_ids)
            or min(expert_ids) < 0
            or max(expert_ids) >= 256
        ):
            raise ValueError("adaptive L1 slot patch contains invalid expert IDs")
        started = time.perf_counter()
        with self._lock:
            self._prepare_mutable_switch(resident)
            ids = tuple(expert_ids)
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
                    replacement = stacked.get(
                        f"{projection_name}.{tensor_name}"
                    )
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
            old_ids = state.ids if state is not None else ()
            old_slots = {expert_id: slot for slot, expert_id in enumerate(old_ids)}
            new_ids = [expert_id for expert_id in requested if expert_id not in old_slots]

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
                self.max_request_experts = max(
                    self.max_request_experts, len(requested)
                )
                return state.switch, state.ids

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

    def stats(self) -> dict[str, float | int]:
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
        }


@cache
def get_scope_fallback_loader(directory: str) -> ScopeFallbackLoader:
    return ScopeFallbackLoader(Path(directory).expanduser().resolve())
