"""Synchronization-free rolling SSD pressure telemetry for Cached-MoE engines."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from typing import Any

_SSD_ELEVATED_PRESSURE = 1.0 / 6.0
_SSD_CRITICAL_PRESSURE = 0.25


def _empty_window() -> dict[str, Any]:
    return {
        "tokens": 0,
        "expert_loads": 0,
        "bytes_loaded": 0,
        "pressure": 0.0,
        "pressure_percent": 0.0,
        "severity": "healthy",
    }


class SsdPressureTelemetry:
    """Turn-local view over already-materialized cumulative SSD counters.

    ``sample`` must return ``(expert_loads, bytes_loaded,
    routed_expert_bytes_per_token)`` without evaluating MLX arrays. Engines call
    :meth:`reset` after Prefill and :meth:`record` at their existing Decode
    scheduler boundary, so observability cannot add a GPU/CPU synchronization.
    """

    def __init__(self, sample: Callable[[], tuple[int, int, int]]) -> None:
        self._sample = sample
        self._samples: deque[tuple[int, int, int]] = deque(maxlen=32)
        self._recent = _empty_window()
        self._session_id: str | None = None
        self._recent_by_session: dict[str, dict[str, Any]] = {}
        self._turn_baseline: tuple[int, int] | None = None
        self._turn_by_session: dict[str, dict[str, Any]] = {}
        self._routed_bytes_per_token = 0

    @staticmethod
    def _window(
        tokens: int,
        loads: int,
        loaded_bytes: int,
        routed_bytes_per_token: int,
    ) -> dict[str, Any]:
        routed_bytes = max(0, int(tokens)) * max(0, int(routed_bytes_per_token))
        pressure = loaded_bytes / routed_bytes if routed_bytes > 0 else 0.0
        severity = (
            "critical"
            if pressure >= _SSD_CRITICAL_PRESSURE
            else "elevated"
            if pressure > _SSD_ELEVATED_PRESSURE
            else "healthy"
        )
        return {
            "tokens": max(0, int(tokens)),
            "expert_loads": max(0, int(loads)),
            "bytes_loaded": max(0, int(loaded_bytes)),
            "pressure": pressure,
            "pressure_percent": pressure * 100.0,
            "severity": severity,
        }

    def reset(self, session_id: str) -> None:
        loads, loaded_bytes, routed_bytes = self._sample()
        self._routed_bytes_per_token = max(0, int(routed_bytes))
        self._samples.clear()
        self._samples.append((0, int(loads), int(loaded_bytes)))
        self._session_id = str(session_id)
        self._turn_baseline = (int(loads), int(loaded_bytes))
        self._recent = _empty_window()
        self._recent_by_session[self._session_id] = dict(self._recent)
        self._turn_by_session[self._session_id] = dict(self._recent)

    def record(self, token_count: int) -> None:
        if self._session_id is None:
            return
        loads, loaded_bytes, routed_bytes = self._sample()
        if routed_bytes > 0:
            self._routed_bytes_per_token = int(routed_bytes)
        token_count = max(0, int(token_count))
        sample = (token_count, int(loads), int(loaded_bytes))
        if self._samples and self._samples[-1][0] == token_count:
            self._samples[-1] = sample
        else:
            self._samples.append(sample)

        cutoff = max(token_count - 10, 0)
        baseline_token, baseline_loads, baseline_bytes = self._samples[0]
        for current_token, current_loads, current_bytes in self._samples:
            if current_token > cutoff:
                break
            baseline_token, baseline_loads, baseline_bytes = (
                current_token,
                current_loads,
                current_bytes,
            )
        window_tokens = min(max(token_count - baseline_token, 0), 10)
        self._recent = self._window(
            window_tokens,
            int(loads) - baseline_loads,
            int(loaded_bytes) - baseline_bytes,
            self._routed_bytes_per_token,
        )
        self._recent_by_session[self._session_id] = dict(self._recent)

        turn_loads, turn_bytes = self._turn_baseline or (int(loads), int(loaded_bytes))
        self._turn_by_session[self._session_id] = self._window(
            token_count,
            int(loads) - turn_loads,
            int(loaded_bytes) - turn_bytes,
            self._routed_bytes_per_token,
        )

    def record_scheduler_output(self, scheduler_output: Any) -> None:
        completion_tokens = max(
            (
                int(getattr(output, "completion_tokens", 0) or 0)
                for output in getattr(scheduler_output, "outputs", ())
            ),
            default=0,
        )
        if completion_tokens == 1 and self._session_id is not None:
            # The first sampled token is produced by Prefill logits. This is
            # also the universal non-chunked Prefill-complete boundary.
            self.reset(self._session_id)
            return
        # Token 1 is sampled from Prefill logits. Only completed one-token
        # forwards belong in the Decode pressure denominator.
        self.record(max(completion_tokens - 1, 0))

    def live(self, session_id: str | None = None) -> dict[str, Any]:
        resolved = str(session_id) if session_id is not None else self._session_id
        recent = self._recent_by_session.get(resolved) if resolved else None
        turn = self._turn_by_session.get(resolved) if resolved else None
        return {
            "ssd_recent_10_tokens": dict(recent or self._recent),
            "ssd_turn_average": dict(turn) if turn is not None else {},
        }

    def stats(self) -> dict[str, Any]:
        return {
            "ssd_recent_10_tokens": dict(self._recent),
            "ssd_health_thresholds": {
                "elevated_above_percent": _SSD_ELEVATED_PRESSURE * 100.0,
                "critical_at_percent": _SSD_CRITICAL_PRESSURE * 100.0,
                "routed_expert_bytes_per_token": self._routed_bytes_per_token,
            },
            "ssd_recent_by_session": {
                session_id: dict(window)
                for session_id, window in self._recent_by_session.items()
            },
            "ssd_turn_by_session": {
                session_id: dict(window)
                for session_id, window in self._turn_by_session.items()
            },
        }


__all__ = ["SsdPressureTelemetry"]
