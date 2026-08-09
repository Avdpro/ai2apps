"""Two-level execution cache for the independent Qwen3.6 tiered engine."""

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

from omlx.cache.moe_expert_store import ExpertMajorStore

from .arena_cache import Qwen36DecodeArena


@dataclass
class _TieredLayer:
    l1_ids: tuple[int, ...]
    tail_ids: list[int]
    frequency: dict[int, int]
    last_used: dict[int, int]
    clock: int
    observations: int


class Qwen36TieredCache:
    """Keep execution in Tail while using the scope bank as an L1 source."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._stores: dict[int, ExpertMajorStore] = {}
        self._layers: dict[int, _TieredLayer] = {}
        self._staging: list[bytearray] = []
        self._lock = threading.RLock()
        self.io_workers = int(os.environ.get("OMLX_QWEN36_IO_WORKERS", "4"))
        self._io_pool = ThreadPoolExecutor(
            max_workers=self.io_workers,
            thread_name_prefix="qwen36-tiered-read",
        )
        self.calls = 0
        self.hit_calls = 0
        self.refill_calls = 0
        self.l1_bypass_routes = 0
        self.tail_hit_routes = 0
        self.tail_evictions = 0
        self.ssd_experts_loaded = 0
        self.ssd_refill_calls = 0
        self.bytes_loaded = 0
        self.read_seconds = 0.0
        self.patch_seconds = 0.0
        self.lfu_decay_interval = int(
            os.environ.get("OMLX_QWEN36_TIERED_LFU_DECAY", "64")
        )
        self.lfu_decays = 0

    @staticmethod
    def prepare_switch_backing(switch: Any) -> None:
        Qwen36DecodeArena.prepare_switch_backing(switch)

    def _store(self, layer: int) -> ExpertMajorStore:
        store = self._stores.get(layer)
        if store is None:
            store = ExpertMajorStore(self.directory / f"layer-{layer:03d}.moe")
            self._stores[layer] = store
        return store

    def initialize_layer(
        self,
        layer: int,
        l1_ids: tuple[int, ...],
        tail_ids: tuple[int, ...],
    ) -> None:
        if not tail_ids or len(tail_ids) != len(set(tail_ids)):
            raise ValueError("Qwen tiered Tail must contain unique experts")
        self._layers[layer] = _TieredLayer(
            l1_ids=l1_ids,
            tail_ids=list(tail_ids),
            frequency={expert_id: 0 for expert_id in tail_ids},
            last_used={expert_id: slot for slot, expert_id in enumerate(tail_ids)},
            clock=len(tail_ids),
            observations=0,
        )

    def lookup_values(self, layer: int, expert_count: int) -> tuple[int, ...]:
        state = self._layers[layer]
        self._assert_state(layer, state)
        lookup = [-1] * expert_count
        for slot, expert_id in enumerate(state.tail_ids):
            lookup[expert_id] = slot
        return tuple(lookup)

    def tail_ids(self, layer: int) -> tuple[int, ...]:
        """Return the physical Tail layout, which changes after every refill."""

        with self._lock:
            state = self._layers[layer]
            self._assert_state(layer, state)
            return tuple(state.tail_ids)

    def replace_layout(
        self,
        layer: int,
        l1_ids: tuple[int, ...],
        tail_ids: tuple[int, ...],
    ) -> None:
        """Publish metadata after adaptive L1/Tail banks are rewritten."""

        with self._lock:
            self.initialize_layer(layer, l1_ids, tail_ids)

    def advance(self, layer: int) -> None:
        """Advance LFU aging without materializing any route IDs."""

        with self._lock:
            self._advance_state(self._layers[layer])

    def _advance_state(self, state: _TieredLayer) -> None:
        state.observations += 1
        if (
            self.lfu_decay_interval > 0
            and state.observations % self.lfu_decay_interval == 0
        ):
            for expert_id in state.tail_ids:
                state.frequency[expert_id] //= 2
            self.lfu_decays += 1

    @staticmethod
    def _assert_state(layer: int, state: _TieredLayer) -> None:
        if len(state.tail_ids) != len(set(state.tail_ids)):
            raise RuntimeError(f"Qwen tiered layer {layer} contains duplicate Tail IDs")
        tail = set(state.tail_ids)
        if set(state.frequency) != tail or set(state.last_used) != tail:
            raise RuntimeError(f"Qwen tiered layer {layer} LFU state differs from Tail")

    def resolve(
        self,
        layer: int,
        requested: tuple[int, ...],
        tail_switch: Any,
        *,
        expert_count: int,
    ) -> tuple[int, ...]:
        """Load only L1 misses into Tail and return the updated Tail map."""

        self.calls += 1
        with self._lock:
            state = self._layers[layer]
            self._advance_state(state)
            resident = set(state.tail_ids)
            l1_resident = set(state.l1_ids)
            for expert_id in requested:
                if expert_id in l1_resident:
                    # A duplicate Tail copy adds no coverage value. Route it
                    # through L1 and leave its LFU count cold so overflow
                    # experts can reclaim the slot.
                    self.l1_bypass_routes += 1
                elif expert_id in resident:
                    state.clock += 1
                    state.frequency[expert_id] += 1
                    state.last_used[expert_id] = state.clock
                    self.tail_hit_routes += 1
            missing = tuple(
                expert
                for expert in requested
                if expert not in resident and expert not in l1_resident
            )
            if not missing:
                self.hit_calls += 1
                return self.lookup_values(layer, expert_count)
            if len(missing) > len(state.tail_ids):
                raise RuntimeError("decode request exceeds Qwen tiered Tail capacity")

            pinned = set(requested)
            victims = sorted(
                (expert for expert in state.tail_ids if expert not in pinned),
                key=lambda expert: (
                    state.frequency[expert],
                    state.last_used[expert],
                ),
            )
            if len(victims) < len(missing):
                raise RuntimeError("Qwen tiered Tail has no unpinned victims")
            slots = [state.tail_ids.index(expert) for expert in victims[: len(missing)]]

            patch_started = time.perf_counter()
            self.ssd_refill_calls += 1
            store = self._store(layer)
            read_started = time.perf_counter()
            records = self._read_records(store, missing)
            self.read_seconds += time.perf_counter() - read_started
            Qwen36DecodeArena._patch_switch(
                tail_switch,
                slots,
                missing,
                records,
            )
            self.ssd_experts_loaded += len(missing)
            self.bytes_loaded += len(missing) * store.record_bytes
            self.patch_seconds += time.perf_counter() - patch_started

            for slot, old, new in zip(
                slots, victims[: len(missing)], missing, strict=True
            ):
                state.tail_ids[slot] = new
                del state.frequency[old]
                del state.last_used[old]
                state.clock += 1
                state.frequency[new] = 1
                state.last_used[new] = state.clock
                self.tail_evictions += 1
            self._assert_state(layer, state)
            if any(expert not in state.tail_ids for expert in missing):
                raise RuntimeError(f"Qwen tiered layer {layer} failed to cover a route")
            self.refill_calls += 1
            return self.lookup_values(layer, expert_count)

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

    def stats(self) -> dict[str, float | int]:
        return {
            "layers": len(self._layers),
            "calls": self.calls,
            "hit_calls": self.hit_calls,
            "refill_calls": self.refill_calls,
            "l1_bypass_routes": self.l1_bypass_routes,
            "tail_hit_routes": self.tail_hit_routes,
            "tail_evictions": self.tail_evictions,
            "ssd_experts_loaded": self.ssd_experts_loaded,
            "ssd_refill_calls": self.ssd_refill_calls,
            "bytes_loaded": self.bytes_loaded,
            "read_seconds": self.read_seconds,
            "patch_seconds": self.patch_seconds,
            "io_workers": self.io_workers,
            "lfu_decay_interval": self.lfu_decay_interval,
            "lfu_decays": self.lfu_decays,
        }


@cache
def get_qwen36_tiered_cache(directory: str) -> Qwen36TieredCache:
    return Qwen36TieredCache(Path(directory).expanduser().resolve())


__all__ = ["Qwen36TieredCache", "get_qwen36_tiered_cache"]
