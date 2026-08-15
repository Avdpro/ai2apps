"""Session-safe lossy Prefill and Decode policies for Qwen3.6 Cache-MoE."""

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
PREFILL_AUTO_TURBO_TOKENS = 2048
PREFILL_AUTO_BLAST_TOKENS = 10 * 1024


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


def resolve_qwen36_prefill_boost(mode: str | None, context_tokens: int) -> str:
    """Resolve Prefill Auto using the shared AI2Apps context bands."""

    value = str(mode or "natural").strip().lower()
    if value != "auto":
        return normalize_qwen36_boost(value)
    if context_tokens > PREFILL_AUTO_BLAST_TOKENS:
        return "blast"
    if context_tokens > PREFILL_AUTO_TURBO_TOKENS:
        return "turbo"
    return "natural"


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
        self.decode_pending: dict[str, str] = {}
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

    async def prepare(
        self, kwargs: dict[str, Any], *, context_tokens: int = 0
    ) -> tuple[str, str]:
        session_id = str(kwargs.get("flesh_session_id", "default"))
        legacy_requested = kwargs.pop("flesh_boost_mode", None)
        prefill_requested = kwargs.pop(
            "flesh_prefill_boost_mode", legacy_requested
        )
        decode_requested = kwargs.pop(
            "flesh_decode_boost_mode", legacy_requested
        )
        prefill_mode = resolve_qwen36_prefill_boost(
            prefill_requested if prefill_requested is not None else self.modes.get(
                session_id, self.default_mode
            ),
            context_tokens,
        )
        decode_mode = normalize_qwen36_boost(
            decode_requested if decode_requested is not None else self.modes.get(
                session_id, self.default_mode
            )
        )
        with self._lock:
            decode_mode = self.pending.pop(session_id, decode_mode)
            if prefill_mode != decode_mode:
                self.decode_pending[session_id] = decode_mode
            else:
                self.decode_pending.pop(session_id, None)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            self.owner._engine.engine._mlx_executor,
            self._apply,
            session_id,
            prefill_mode,
        )
        # _apply records the active phase; keep the session preference pointed
        # at Decode so the next request inherits the durable policy.
        self.modes[session_id] = decode_mode
        return session_id, prefill_mode

    def complete_prefill(self) -> None:
        session_id = self.session_id
        if session_id is None:
            return
        with self._lock:
            mode = self.decode_pending.pop(session_id, None)
        if mode is not None:
            self._apply(session_id, mode)

    def between_step(self) -> None:
        self.complete_prefill()
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
            "prefill_boost_supported": True,
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
    "resolve_qwen36_prefill_boost",
]
