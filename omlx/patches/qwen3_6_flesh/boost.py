"""Session-safe lossy Decode policies for Qwen3.6 Cache-MoE engines."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any


BOOST_TO_LOSSY = {
    "natural": "exact",
    "turbo": "tail2",
    "blast": "head2",
    "tail3": "tail3",
    "head3": "head3",
}


@dataclass(frozen=True)
class Qwen36LossyPolicy:
    mode: str
    replace_count: int


def normalize_qwen36_boost(mode: str | None) -> str:
    value = str(mode or "natural").strip().lower()
    if value not in BOOST_TO_LOSSY:
        raise ValueError(
            "Qwen3.6 Engine Boost must be natural, turbo, blast, tail3, or head3"
        )
    return value


def qwen36_lossy_policy(mode: str) -> Qwen36LossyPolicy | None:
    mode = normalize_qwen36_boost(mode)
    if mode == "natural":
        return None
    # Qwen3.6 routes Top-8. Turbo may replace the lowest two routes; Blast
    # protects only the highest two and may replace the remaining six.
    replace_counts = {
        "turbo": 2,
        "blast": 6,
        "tail3": 3,
        # Qwen Top-8 Head3 protects the highest three routes.
        "head3": 5,
    }
    return Qwen36LossyPolicy(
        mode=BOOST_TO_LOSSY[mode], replace_count=replace_counts[mode]
    )


class Qwen36BoostController:
    """Own per-session modes and publish changes at scheduler-safe boundaries."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.default_mode = "natural"
        self.mode = self.default_mode
        self.session_id: str | None = None
        self.modes: dict[str, str] = {}
        self.pending: dict[str, str] = {}
        self.switches = 0
        self._lock = threading.Lock()

    def _apply(self, session_id: str, mode: str) -> bool:
        mode = normalize_qwen36_boost(mode)
        changed = mode != self.mode or session_id != self.session_id
        policy = qwen36_lossy_policy(mode)
        for decoder in self.owner._model.language_model.model.layers:
            decoder.mlp.scope_lossy_policy = policy
        if mode != self.mode:
            self.switches += 1
        self.mode = mode
        self.session_id = session_id
        self.modes[session_id] = mode
        return changed

    async def prepare(self, kwargs: dict[str, Any]) -> tuple[str, str]:
        session_id = str(kwargs.get("flesh_session_id", "default"))
        requested = kwargs.pop("flesh_boost_mode", None)
        mode = normalize_qwen36_boost(
            requested if requested is not None else self.modes.get(
                session_id, self.default_mode
            )
        )
        with self._lock:
            mode = self.pending.pop(session_id, mode)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.owner._engine.engine._mlx_executor,
            self._apply,
            session_id,
            mode,
        )
        return session_id, mode

    def between_step(self) -> None:
        session_id = self.session_id
        if session_id is None:
            return
        with self._lock:
            mode = self.pending.pop(session_id, None)
        if mode is not None:
            self._apply(session_id, mode)

    def request(self, session_id: str, mode: str) -> dict[str, Any]:
        mode = normalize_qwen36_boost(mode)
        active = bool(
            session_id == self.session_id and self.owner.has_active_requests()
        )
        self.modes[session_id] = mode
        if active:
            with self._lock:
                self.pending[session_id] = mode
        else:
            # There is no model execution in flight, so the next request's
            # prepare boundary will publish the policy.
            with self._lock:
                self.pending.pop(session_id, None)
        return {
            "accepted": True,
            "queued": active,
            "session_id": session_id,
            "mode": mode,
            "applies": "next_token" if active else "next_request",
        }

    def stats(self) -> dict[str, Any]:
        replaced = before = after = 0
        layers = 0
        if getattr(self.owner, "_model", None) is not None:
            for decoder in self.owner._model.language_model.model.layers:
                counters = getattr(decoder.mlp, "scope_lossy_stats", None)
                if counters is None:
                    continue
                layers += 1
                replaced += int(counters["routes_replaced"])
                before += int(counters["misses_before"])
                after += int(counters["misses_after"])
        return {
            "available": True,
            "mode": self.mode,
            "lossy_mode": BOOST_TO_LOSSY[self.mode],
            "session_id": self.session_id,
            "switches": self.switches,
            "pending": len(self.pending),
            "layers": layers,
            "routes_replaced": replaced,
            "misses_before": before,
            "misses_after": after,
            "misses_avoided": before - after,
        }


__all__ = [
    "BOOST_TO_LOSSY",
    "Qwen36BoostController",
    "Qwen36LossyPolicy",
    "normalize_qwen36_boost",
    "qwen36_lossy_policy",
]
