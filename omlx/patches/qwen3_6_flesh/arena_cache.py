"""Fixed-slot decode arena for the independent Qwen3.6 arena engine."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import mlx.core as mx

from omlx.cache.direct_l1 import direct_load_fused_experts, direct_l1_mode
from omlx.cache.moe_expert_store import ExpertMajorStore


@dataclass
class _ArenaLayer:
    expert_ids: list[int]
    protected_slots: int
    recency: list[int]


class Qwen36DecodeArena:
    """Patch a small mutable tail region without rebuilding SwitchGLU."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._stores: dict[int, ExpertMajorStore] = {}
        self._layers: dict[int, _ArenaLayer] = {}
        self._staging: list[bytearray] = []
        self._lock = threading.RLock()
        self.io_workers = int(os.environ.get("OMLX_QWEN36_IO_WORKERS", "4"))
        self._io_pool = ThreadPoolExecutor(
            max_workers=self.io_workers,
            thread_name_prefix="qwen36-arena-read",
        )
        self.calls = 0
        self.hit_calls = 0
        self.patch_calls = 0
        self.experts_loaded = 0
        self.bytes_loaded = 0
        self.load_seconds = 0.0
        self.patch_seconds = 0.0
        self.direct_l1_mode = direct_l1_mode()
        self.direct_load_calls = 0
        self.direct_load_bytes = 0
        self.direct_load_seconds = 0.0

    @staticmethod
    def prepare_switch_backing(switch: Any) -> None:
        """Detach arena parameters from post-load concat/checkpoint graphs."""

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
                backing[:] = value
                mx.eval(backing)
                setattr(projection, tensor_name, backing)

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(self.directory / f"layer-{layer:03d}.moe")
            store.set_no_cache()
            self._stores[layer] = store
        return store

    def initialize_layer(
        self,
        layer: int,
        expert_ids: tuple[int, ...],
        protected_slots: int,
    ) -> None:
        if not 0 < protected_slots < len(expert_ids):
            raise ValueError("arena requires protected and mutable slots")
        self._layers[layer] = _ArenaLayer(
            expert_ids=list(expert_ids),
            protected_slots=protected_slots,
            recency=list(expert_ids[protected_slots:]),
        )

    def lookup_values(self, layer: int, expert_count: int) -> tuple[int, ...]:
        state = self._layers[layer]
        self._assert_state(layer, state)
        lookup = [-1] * expert_count
        for slot, expert_id in enumerate(state.expert_ids):
            lookup[expert_id] = slot
        return tuple(lookup)

    def expert_ids(self, layer: int) -> tuple[int, ...]:
        """Return the physical slot layout, which is the mapping truth source."""

        with self._lock:
            state = self._layers[layer]
            self._assert_state(layer, state)
            return tuple(state.expert_ids)

    def replace_layout(
        self, layer: int, expert_ids: tuple[int, ...], protected_slots: int
    ) -> None:
        """Publish metadata after an external adaptive-L1 slot rewrite."""

        with self._lock:
            self.initialize_layer(layer, expert_ids, protected_slots)

    @staticmethod
    def _assert_state(layer: int, state: _ArenaLayer) -> None:
        if len(state.expert_ids) != len(set(state.expert_ids)):
            raise RuntimeError(f"Qwen arena layer {layer} contains duplicate experts")
        tail = state.expert_ids[state.protected_slots :]
        if len(state.recency) != len(tail) or set(state.recency) != set(tail):
            raise RuntimeError(f"Qwen arena layer {layer} LRU differs from tail slots")

    def resolve(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
        *,
        expert_count: int,
    ) -> tuple[int, ...]:
        """Ensure every requested expert is resident and return device lookup."""

        self.calls += 1
        with self._lock:
            state = self._layers[layer]
            resident = set(state.expert_ids)
            for expert_id in requested:
                if expert_id in state.recency:
                    state.recency.remove(expert_id)
                    state.recency.append(expert_id)
            missing = tuple(expert for expert in requested if expert not in resident)
            if not missing:
                self.hit_calls += 1
                return self.lookup_values(layer, expert_count)
            tail_slots = len(state.expert_ids) - state.protected_slots
            if len(missing) > tail_slots:
                raise RuntimeError("decode request exceeds Qwen arena tail capacity")

            pinned = set(requested)
            victims = [expert for expert in state.recency if expert not in pinned]
            if len(victims) < len(missing):
                raise RuntimeError("Qwen arena has no unpinned tail victims")
            victim_slots = [state.expert_ids.index(expert) for expert in victims[: len(missing)]]

            store = self._store(layer)
            load_started = time.perf_counter()
            if os.environ.get("OMLX_QWEN36_ARENA_SYNC_OVERWRITE", "0") == "1":
                mx.synchronize()
            direct_bytes = direct_load_fused_experts(
                store,
                switch,
                victim_slots,
                missing,
                io_workers=self.io_workers,
            )
            elapsed = time.perf_counter() - load_started
            if direct_bytes is None:
                records = self._read_records(store, missing)
                self.load_seconds += time.perf_counter() - load_started
                patch_started = time.perf_counter()
                self._patch_switch(switch, victim_slots, missing, records)
                self.patch_seconds += time.perf_counter() - patch_started
            else:
                self.direct_load_calls += 1
                self.direct_load_bytes += direct_bytes
                self.direct_load_seconds += elapsed

            for slot, old, new in zip(
                victim_slots, victims[: len(missing)], missing, strict=True
            ):
                state.expert_ids[slot] = new
                state.recency.remove(old)
                state.recency.append(new)
            self._assert_state(layer, state)
            if any(expert not in state.expert_ids for expert in requested):
                raise RuntimeError(f"Qwen arena layer {layer} failed to cover a route")
            if os.environ.get("OMLX_QWEN36_ARENA_VALIDATE_REQUESTED", "0") == "1":
                self._validate_requested(layer, requested, switch, store)
            self.patch_calls += 1
            self.experts_loaded += len(missing)
            self.bytes_loaded += len(missing) * store.record_bytes
            return self.lookup_values(layer, expert_count)

    def _validate_requested(
        self,
        layer: int,
        requested: tuple[int, ...],
        switch: Any,
        store: ExpertMajorStore,
    ) -> None:
        """Prove that every requested ID maps to its exact stored tensors."""

        state = self._layers[layer]
        records = self._read_records(store, requested)
        projections = (
            ("gate_up_proj",)
            if getattr(switch, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        checks: list[tuple[int, int, str, mx.array]] = []
        for expert_id in requested:
            slot = state.expert_ids.index(expert_id)
            for projection_name in projections:
                projection = getattr(switch, projection_name)
                for tensor_name in ("weight", "scales", "biases"):
                    current = projection.get(tensor_name)
                    if current is None:
                        continue
                    expected = records[expert_id].get(
                        f"{projection_name}.{tensor_name}"
                    )
                    if expected is None and projection_name == "gate_up_proj":
                        expected = mx.concatenate(
                            (
                                records[expert_id][f"gate_proj.{tensor_name}"],
                                records[expert_id][f"up_proj.{tensor_name}"],
                            ),
                            axis=1,
                        )
                    if expected.dtype != current.dtype:
                        expected = expected.astype(current.dtype)
                    checks.append(
                        (
                            expert_id,
                            slot,
                            f"{projection_name}.{tensor_name}",
                            mx.all(current[slot] == expected),
                        )
                    )
        mx.eval(*(check for _, _, _, check in checks))
        for expert_id, slot, name, check in checks:
            if not bool(check.item()):
                raise RuntimeError(
                    f"Qwen arena tensor mismatch at layer {layer}, expert "
                    f"{expert_id}, slot {slot}, tensor {name}"
                )

    def _read_records(
        self, store: ExpertMajorStore, ids: tuple[int, ...]
    ) -> dict[int, dict[str, mx.array]]:
        while len(self._staging) < len(ids):
            self._staging.append(store.allocate_staging())
        pairs = list(zip(ids, self._staging, strict=False))
        futures = [
            self._io_pool.submit(store.read_into, expert_id, staging)
            for expert_id, staging in pairs
        ]
        raw = [future.result() for future in futures]
        return {
            expert_id: store.mlx_tensor_views(record, copy_record=True)
            for (expert_id, _), record in zip(pairs, raw, strict=True)
        }

    @staticmethod
    def _patch_switch(
        switch: Any,
        slots: list[int],
        expert_ids: tuple[int, ...],
        records: dict[int, dict[str, mx.array]],
        *,
        evaluate: bool = True,
    ) -> tuple[list[mx.array], list[mx.array]]:
        slot_array = mx.array(slots, dtype=mx.int32)
        projections = (
            ("gate_up_proj",)
            if getattr(switch, "gate_up_proj", None) is not None
            else ("gate_proj", "up_proj")
        ) + ("down_proj",)
        arrays = []
        checks = []
        validate = os.environ.get("OMLX_QWEN36_ARENA_VALIDATE", "0") == "1"
        for projection_name in projections:
            projection = getattr(switch, projection_name)
            for tensor_name in ("weight", "scales", "biases"):
                current = projection.get(tensor_name)
                if current is None:
                    continue
                values = []
                for expert_id in expert_ids:
                    value = records[expert_id].get(
                        f"{projection_name}.{tensor_name}"
                    )
                    if value is None and projection_name == "gate_up_proj":
                        gate = records[expert_id][f"gate_proj.{tensor_name}"]
                        up = records[expert_id][f"up_proj.{tensor_name}"]
                        value = mx.concatenate((gate, up), axis=1)
                    if value.dtype != current.dtype:
                        value = value.astype(current.dtype)
                    values.append(value)
                replacement = mx.stack(values)
                current[slot_array] = replacement
                arrays.append(current)
                if validate:
                    checks.append(mx.all(current[slot_array] == replacement))
        if evaluate:
            mx.eval(*arrays, *checks)
            if checks and not all(bool(value.item()) for value in checks):
                raise RuntimeError("Qwen arena slot write validation failed")
        return arrays, checks

    def stats(self) -> dict[str, float | int]:
        return {
            "layers": len(self._layers),
            "calls": self.calls,
            "hit_calls": self.hit_calls,
            "patch_calls": self.patch_calls,
            "experts_loaded": self.experts_loaded,
            "bytes_loaded": self.bytes_loaded,
            "read_seconds": self.load_seconds,
            "patch_seconds": self.patch_seconds,
            "io_workers": self.io_workers,
            "direct_l1_mode": self.direct_l1_mode,
            "direct_load_calls": self.direct_load_calls,
            "direct_load_bytes": self.direct_load_bytes,
            "direct_load_seconds": self.direct_load_seconds,
        }


@cache
def get_qwen36_decode_arena(directory: str) -> Qwen36DecodeArena:
    return Qwen36DecodeArena(Path(directory).expanduser().resolve())


__all__ = ["Qwen36DecodeArena", "get_qwen36_decode_arena"]
