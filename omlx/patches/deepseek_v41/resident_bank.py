"""L1/L0 expert banks backed by the Runtime's native Direct-L1 loader."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import mlx.core as mx

from omlx.custom_kernels.glm_moe_dsa import fast as native


class MetalBank:
    def __init__(
        self,
        path,
        l1_ids,
        l0_slots=8,
        io_workers=4,
        no_cache=False,
    ):
        required = {"preadv_fused_experts", "copy_expert_slots"}
        missing = sorted(required - set(native.native_symbols()))
        if missing:
            raise RuntimeError(
                "DeepSeek V4.1 native expert loader is incomplete: "
                + ", ".join(missing)
            )
        self.info = json.loads(Path(str(path) + ".json").read_text())
        self.fd = os.open(path, os.O_RDONLY)
        if no_cache:
            import fcntl

            try:
                fcntl.fcntl(self.fd, 48, 1)
            except BaseException:
                os.close(self.fd)
                raise
        self.records = {
            int(key): value for key, value in self.info["expert_to_record"].items()
        }
        if len(l1_ids) != len(set(l1_ids)):
            raise ValueError("duplicate L1 ids")
        self.main = {expert: slot for slot, expert in enumerate(l1_ids)}
        self.hot = {}
        self.l0_slots = l0_slots
        self.workers = io_workers
        self.pending = []
        self.loads = self.bytes = 0
        self.io_seconds = 0.0
        self.fence_calls = 0
        self.copy_bytes = self.copy_experts = 0
        self.copy_seconds = 0.0
        self.capacity = len(l1_ids) + l0_slots
        self.arrays = tuple(
            mx.zeros((self.capacity, *shape), dtype=mx.uint8)
            for shape in self.info["shapes"]
        )
        mx.eval(*self.arrays)
        mx.synchronize()
        self._load(l1_ids, list(range(len(l1_ids))))

    def _fence(self):
        self.fence_calls += 1
        if self.pending:
            mx.eval(*self.pending)
        mx.synchronize()
        self.pending.clear()

    def _read_ready(self, ids, slots):
        if not ids:
            return
        started = time.perf_counter()
        count = native.preadv_fused_experts(
            self.fd,
            0,
            self.info["record_bytes"],
            [self.records[expert] for expert in ids],
            slots,
            *self.arrays,
            self.workers,
        )
        self.io_seconds += time.perf_counter() - started
        if count != len(ids) * self.info["record_bytes"]:
            raise IOError("native byte count mismatch")
        self.loads += 1
        self.bytes += count

    def _load(self, ids, slots):
        if not ids:
            return
        if len(set(slots)) != len(slots):
            raise ValueError("duplicate native destinations")
        self._fence()
        self._read_ready(ids, slots)

    def _copy_ready(self, sources, slots):
        if not sources:
            return
        started = time.perf_counter()
        count = native.copy_expert_slots(sources, slots, list(self.arrays))
        self.copy_seconds += time.perf_counter() - started
        if count != len(sources) * self.info["record_bytes"]:
            raise RuntimeError("promotion copy byte mismatch")
        self.copy_bytes += count
        self.copy_experts += len(sources)

    def load_promotions(self, ids, slots):
        if (
            len(ids) != len(slots)
            or len(set(ids)) != len(ids)
            or len(set(slots)) != len(slots)
        ):
            raise ValueError("invalid promotion list")
        if any(expert not in self.records or expert in self.main for expert in ids):
            raise ValueError("invalid promotion expert")
        if any(slot < 0 or slot >= len(self.main) for slot in slots):
            raise ValueError("promotion destination must be Main")
        resident = [
            (self.hot[expert], slot)
            for expert, slot in zip(ids, slots)
            if expert in self.hot
        ]
        disk = [
            (expert, slot)
            for expert, slot in zip(ids, slots)
            if expert not in self.hot
        ]
        if not ids:
            return {"copied": 0, "ssd": 0}
        self._fence()
        self._read_ready([expert for expert, _ in disk], [slot for _, slot in disk])
        self._copy_ready(
            [source for source, _ in resident], [slot for _, slot in resident]
        )
        return {"copied": len(resident), "ssd": len(disk)}

    def track(self, value):
        self.pending.append(value)

    def close(self):
        if self.pending:
            mx.eval(*self.pending)
        mx.synchronize()
        os.close(self.fd)


class LRUMetalBank(MetalBank):
    def __init__(self, path, l1_ids, l0_slots=8, io_workers=4, no_cache=False):
        super().__init__(path, l1_ids, l0_slots, io_workers, no_cache=no_cache)
        self.hits = self.misses = self.evictions = 0
        self.slot_swaps = 0
        self.dynamic_roles = False
        self.last_eviction_promotions = []

    def prepare(self, ids, promotion_scores=None, slot_swap=False):
        ids = list(dict.fromkeys(ids))
        if any(expert not in self.records for expert in ids):
            raise KeyError("unknown expert")
        requested = set(ids)
        if len(requested - self.main.keys()) > self.l0_slots:
            raise ValueError("route exceeds L0 capacity")
        missing = [
            expert
            for expert in ids
            if expert not in self.main and expert not in self.hot
        ]
        self.hits += len(ids) - len(missing)
        self.misses += len(missing)
        occupied = set(self.hot.values())
        free = [
            slot
            for slot in range(self.capacity)
            if slot not in occupied and slot not in self.main.values()
        ]
        victims = [
            (expert, slot)
            for expert, slot in self.hot.items()
            if expert not in requested
        ]
        slots = free[: len(missing)]
        evicted = victims[: len(missing) - len(slots)]
        self.last_eviction_promotions = []
        if promotion_scores is not None and missing:
            candidates = sorted(
                evicted, key=lambda item: (-promotion_scores[item[0]], item[0])
            )
            old = sorted(
                (expert for expert in self.main if expert not in requested),
                key=lambda expert: (promotion_scores[expert], expert),
            )
            pairs = [
                (expert, victim, self.main[victim], source)
                for (expert, source), victim in zip(candidates[:4], old[:4])
                if promotion_scores[expert] >= 3
                and promotion_scores[expert] > promotion_scores[victim] + 2
            ]
            slots.extend(slot for _, slot in evicted)
            if slot_swap:
                redirects = {source: destination for _, _, destination, source in pairs}
                slots = [redirects.get(slot, slot) for slot in slots]
            self._fence()
            if pairs and not slot_swap:
                self._copy_ready(
                    [pair[3] for pair in pairs], [pair[2] for pair in pairs]
                )
            self._read_ready(missing, slots)
            for expert, victim, destination, source in pairs:
                del self.main[victim]
                self.main[expert] = source if slot_swap else destination
            for expert, _ in evicted:
                del self.hot[expert]
            self.evictions += len(evicted)
            self.hot.update(zip(missing, slots))
            for expert in ids:
                if expert in self.hot:
                    self.hot[expert] = self.hot.pop(expert)
            self.last_eviction_promotions = [pair[:3] for pair in pairs]
            if slot_swap:
                self.dynamic_roles = True
                self.slot_swaps += len(pairs)
            return mx.array(
                [self.main[e] if e in self.main else self.hot[e] for e in ids],
                dtype=mx.int32,
            )
        for expert, slot in evicted:
            del self.hot[expert]
            slots.append(slot)
            self.evictions += 1
        self._load(missing, slots)
        self.hot.update(zip(missing, slots))
        for expert in ids:
            if expert in self.hot:
                self.hot[expert] = self.hot.pop(expert)
        return mx.array(
            [self.main[e] if e in self.main else self.hot[e] for e in ids],
            dtype=mx.int32,
        )
