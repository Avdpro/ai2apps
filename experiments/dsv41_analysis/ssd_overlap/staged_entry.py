"""Measure staged auxiliary expert reads during an unchanged decode forward."""

import concurrent.futures
import fcntl
import json
import os
import random
import time
from pathlib import Path

import mlx.core as mx

import run
from metal_bank import native


Base = run.Model
TRIGGERS = (0, 5, 15, 25)
TARGETS = ((3, 10), (10, 20), (20, 30), (30, 40))


class StagedOverlap(Base):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.counts = tuple(json.loads(os.environ["STAGED_COUNTS"]))
        assert len(self.counts) == 4 and sum(self.counts) <= 72
        self.events = []
        self.step = 0
        self.pending = []
        self.info = json.loads((self.expert_store / "layer-0.bin.json").read_text())
        # Every case reserves the same 72-slot scratch bank so memory allocation
        # cannot explain the 64/72 comparison. Scratch is never consumed.
        self.scratch = tuple(mx.zeros((72, *shape), dtype=mx.uint8) for shape in self.info["shapes"])
        mx.eval(*self.scratch)
        mx.synchronize()
        self.fds = []
        for layer in range(40):
            fd = os.open(self.expert_store / f"layer-{layer}.bin", os.O_RDONLY)
            fcntl.fcntl(fd, 48, 1)  # Darwin F_NOCACHE.
            self.fds.append(fd)
        # One worker models the existing bounded native prefetch queue. A larger
        # pool would hide queue pressure by increasing SSD concurrency.
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def read_stage(self, step, stage, count, slot_offset):
        begin = time.perf_counter()
        rng = random.Random(41041 + step * 101 + stage)
        total = 0
        requests = []
        lo, hi = TARGETS[stage]
        for offset in range(0, count, 4):
            size = min(4, count - offset)
            layer = rng.randrange(lo, hi)
            experts = rng.sample(range(384), size)
            slots = list(range(slot_offset + offset, slot_offset + offset + size))
            total += native.preadv_fused_experts(
                self.fds[layer],
                0,
                self.info["record_bytes"],
                experts,
                slots,
                *self.scratch,
                4,
            )
            requests.append([layer, experts])
        assert total == count * self.info["record_bytes"]
        return {
            "stage": stage,
            "trigger": TRIGGERS[stage],
            "count": count,
            "begin": begin,
            "end": time.perf_counter(),
            "bytes": total,
            "requests": requests,
        }

    def moe(self, layer, x, start):
        if start and layer in TRIGGERS:
            stage = TRIGGERS.index(layer)
            count = self.counts[stage]
            if count:
                slot_offset = sum(self.counts[:stage])
                future = self.pool.submit(self.read_stage, self.step, stage, count, slot_offset)
                self.pending.append(future)
        return super().moe(layer, x, start)

    def __call__(self, ids, start=0):
        if not start:
            return super().__call__(ids, start)
        self.step += 1
        self.pending = []
        begin = time.perf_counter()
        output = super().__call__(ids, start)
        mx.eval(output, self.cache_counters, *self.ages.values())
        compute_end = time.perf_counter()
        reads = [future.result() for future in self.pending]
        end = time.perf_counter()
        self.events.append(
            {
                "step": self.step,
                "begin": begin,
                "compute_end": compute_end,
                "end": end,
                "reads": reads,
            }
        )
        return output

    def close(self):
        self.pool.shutdown(wait=True)
        for fd in self.fds:
            os.close(fd)
        Path(os.environ["STAGED_OUTPUT"], "staged-overlap.json").write_text(
            json.dumps(
                {
                    "counts": self.counts,
                    "record_bytes": self.info["record_bytes"],
                    "scratch_bytes": sum(array.nbytes for array in self.scratch),
                    "events": self.events,
                },
                indent=2,
            )
        )
        super().close()


run.Model = StagedOverlap
run.main()
