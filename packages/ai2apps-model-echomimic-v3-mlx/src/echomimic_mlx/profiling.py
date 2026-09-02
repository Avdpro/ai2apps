"""Phase-level MLX wall-time and unified-memory instrumentation."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from typing import Any

import mlx.core as mx


@dataclass(frozen=True, slots=True)
class PhaseMeasurement:
    """One synchronized MLX phase measurement."""

    label: str
    wall_seconds: float
    eval_count: int
    active_before_bytes: int
    active_after_bytes: int
    cache_before_bytes: int
    cache_after_bytes: int
    peak_bytes: int


class PhaseContext:
    """Evaluation counter exposed inside a profiler phase."""

    def __init__(self) -> None:
        self.eval_count = 0

    def evaluate(self, *values: mx.array) -> None:
        mx.eval(*values)
        self.eval_count += 1


class MLXProfiler:
    """Collect synchronized, reproducible phase measurements."""

    def __init__(self) -> None:
        self.measurements: list[PhaseMeasurement] = []

    @contextmanager
    def phase(self, label: str) -> Iterator[PhaseContext]:
        if not label:
            raise ValueError("profile phase label must not be empty")
        mx.synchronize()
        active_before = mx.get_active_memory()
        cache_before = mx.get_cache_memory()
        mx.reset_peak_memory()
        started = time.perf_counter()
        context = PhaseContext()
        try:
            yield context
        finally:
            mx.synchronize()
            elapsed = time.perf_counter() - started
            self.measurements.append(
                PhaseMeasurement(
                    label=label,
                    wall_seconds=elapsed,
                    eval_count=context.eval_count,
                    active_before_bytes=active_before,
                    active_after_bytes=mx.get_active_memory(),
                    cache_before_bytes=cache_before,
                    cache_after_bytes=mx.get_cache_memory(),
                    peak_bytes=mx.get_peak_memory(),
                )
            )

    def as_dict(self) -> dict[str, Any]:
        return {"phases": [asdict(measurement) for measurement in self.measurements]}
