"""Session-owned Decode Burst control for the DeepSeek V4.1 SSD engine."""

from __future__ import annotations

import threading
from typing import Any

BOOST_TO_TOP = {
    "auto": 6,
    "natural": 6,
    "turbo": 4,
    "blast": 2,
}


def normalize_deepseek_v41_boost(mode: str | None) -> str:
    value = str(mode or "natural").strip().lower()
    if value not in BOOST_TO_TOP:
        raise ValueError(
            "DeepSeek V4.1 Engine Boost must be auto, natural, turbo, or blast"
        )
    return value


class DeepseekV41BoostController:
    """Publish lossy Decode policy changes only at request/token boundaries."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.default_mode = "natural"
        self.mode = self.default_mode
        self.session_id: str | None = None
        self.modes: dict[str, str] = {}
        self.pending: dict[str, str] = {}
        self.switches = 0
        self._lock = threading.Lock()

    @staticmethod
    def _effective(mode: str) -> str:
        # DS4.1 has no measured automatic policy. Auto therefore remains exact.
        return "natural" if mode == "auto" else mode

    def _apply(self, session_id: str, requested: str) -> str:
        requested = normalize_deepseek_v41_boost(requested)
        effective = self._effective(requested)
        model = self.owner._model
        if model is None:
            raise RuntimeError("DeepSeek V4.1 engine is not started")
        model.set_boost_mode(effective, BOOST_TO_TOP[effective])
        if effective != self.mode:
            self.switches += 1
        self.mode = effective
        self.session_id = session_id
        self.modes[session_id] = requested
        return effective

    def prepare(self, session_id: str, requested: str | None) -> str:
        with self._lock:
            pending = self.pending.pop(session_id, None)
        selected = normalize_deepseek_v41_boost(
            pending
            if pending is not None
            else requested
            if requested is not None
            else self.modes.get(session_id, self.default_mode)
        )
        self.modes[session_id] = selected
        return self._apply(session_id, selected)

    def apply_pending(self, session_id: str) -> str:
        with self._lock:
            requested = self.pending.pop(session_id, None)
        if requested is None:
            return self.mode
        return self._apply(session_id, requested)

    def request(self, session_id: str, mode: str) -> dict[str, Any]:
        requested = normalize_deepseek_v41_boost(mode)
        active = session_id == self.owner._active_session_id
        self.modes[session_id] = requested
        with self._lock:
            if active:
                self.pending[session_id] = requested
            else:
                self.pending.pop(session_id, None)
        return {
            "accepted": True,
            "queued": active,
            "session_id": session_id,
            "mode": requested,
            "effective_mode": self.mode if active else self._effective(requested),
            "applies": "next_token" if active else "next_request",
            "lossy": self._effective(requested) != "natural",
            "protected_top": BOOST_TO_TOP[self._effective(requested)],
        }

    def stats(self) -> dict[str, Any]:
        result = {
            "available": True,
            "prefill_boost_supported": False,
            "mode": self.mode,
            "requested_mode": (
                self.modes.get(self.session_id, self.default_mode)
                if self.session_id is not None
                else self.default_mode
            ),
            "session_id": self.session_id,
            "switches": self.switches,
            "pending": len(self.pending),
            "lossy": self.mode != "natural",
            "protected_top": BOOST_TO_TOP[self.mode],
        }
        model = self.owner._model
        if model is not None:
            counts = model.boost_counts.tolist()
            cache = model.cache_counters.tolist()
            totals = [sum(int(row[index]) for row in counts) for index in range(4)]
            cache_totals = [sum(int(row[index]) for row in cache) for index in range(3)]
            cache_requests = sum(cache_totals)
            result.update(
                required_misses=totals[0],
                omitted_tail_routes=totals[1],
                executed_routes=totals[2],
                required_routes=totals[3],
                cache_main_hits=cache_totals[0],
                cache_hot_hits=cache_totals[1],
                cache_misses=cache_totals[2],
                cache_hit_rate=(
                    (cache_totals[0] + cache_totals[1]) / cache_requests
                    if cache_requests
                    else None
                ),
            )
        return result


__all__ = [
    "BOOST_TO_TOP",
    "DeepseekV41BoostController",
    "normalize_deepseek_v41_boost",
]
