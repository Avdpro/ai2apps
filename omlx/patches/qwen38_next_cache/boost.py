"""Runtime-selectable Boost policies for Qwen3.8 Flash Next Cached-MoE."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any

BOOST_TO_PROTECTED_TOP = {
    "natural": 10,
    "turbo": 5,
    "blast": 3,
    "top7": 7,
    "top6": 6,
    "top5": 5,
    "top4": 4,
    "top3": 3,
}


@dataclass(frozen=True)
class Qwen4BoostPolicy:
    """Protect the highest weighted routes and replace eligible tail misses."""

    mode: str
    protected_top: int
    replace_count: int


def normalize_qwen4_boost(mode: str | None) -> str:
    value = str(mode or "natural").strip().lower()
    if value not in BOOST_TO_PROTECTED_TOP:
        choices = ", ".join(BOOST_TO_PROTECTED_TOP)
        raise ValueError(f"Qwen4 Boost must be one of: {choices}")
    return value


def qwen4_boost_policy(mode: str | None) -> Qwen4BoostPolicy | None:
    value = normalize_qwen4_boost(mode)
    protected_top = BOOST_TO_PROTECTED_TOP[value]
    if protected_top == 10:
        return None
    return Qwen4BoostPolicy(
        mode=f"head{protected_top}",
        protected_top=protected_top,
        replace_count=10 - protected_top,
    )


def set_qwen4_boost_mode(model: Any, mode: str | None) -> int:
    """Publish a Boost change between scheduler steps or requests.

    AI2Apps can call this on its MLX executor at the same safe next-token
    boundary used by the GLM/Qwen3.6 controllers.  The standalone benchmark
    also uses it after model construction.
    """

    value = normalize_qwen4_boost(mode)
    policy = qwen4_boost_policy(value)
    language_model = getattr(model, "language_model", model)
    inner = getattr(language_model, "model", language_model)
    layers = getattr(inner, "layers", ())
    changed = 0
    for decoder in layers:
        block = getattr(decoder, "mlp", None)
        if hasattr(block, "boost_policy"):
            block.boost_mode = value
            block.boost_policy = policy
            changed += 1
    return changed


class Qwen4BoostController:
    """Keep Qwen4 Boost modes session-owned and scheduler-boundary safe."""

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
        mode = normalize_qwen4_boost(mode)
        changed = mode != self.mode or session_id != self.session_id
        count = set_qwen4_boost_mode(self.owner._vlm_model, mode)
        if count <= 0:
            raise RuntimeError("Qwen4 Cached-MoE Boost blocks are not installed")
        if mode != self.mode:
            self.switches += 1
        self.mode = mode
        self.session_id = session_id
        self.modes[session_id] = mode
        return changed

    async def prepare(
        self, kwargs: dict[str, Any], *, context_tokens: int = 0
    ) -> tuple[str, str]:
        del context_tokens
        session_id = str(kwargs.get("flesh_session_id", "default"))
        legacy = kwargs.pop("flesh_boost_mode", None)
        prefill_requested = kwargs.pop("flesh_prefill_boost_mode", legacy)
        decode_requested = kwargs.pop("flesh_decode_boost_mode", legacy)
        prefill_mode = normalize_qwen4_boost(
            prefill_requested
            if prefill_requested is not None
            else self.modes.get(session_id, self.default_mode)
        )
        decode_mode = normalize_qwen4_boost(
            decode_requested
            if decode_requested is not None
            else self.modes.get(session_id, self.default_mode)
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
        self.modes[session_id] = decode_mode
        return session_id, prefill_mode

    def _apply_pending(self) -> bool:
        session_id = self.session_id
        if session_id is None:
            return False
        with self._lock:
            mode = self.decode_pending.pop(session_id, None)
            if mode is None:
                mode = self.pending.pop(session_id, None)
        return False if mode is None else self._apply(session_id, mode)

    def on_scheduler_step(self, scheduler_output: Any) -> None:
        if any(
            int(getattr(output, "completion_tokens", 0)) > 0
            for output in getattr(scheduler_output, "outputs", ())
        ):
            self._apply_pending()

    def between_prefill_chunk(
        self,
        request: Any,
        *,
        tokens: int,
        processed_tokens: int,
        remaining_tokens: int,
    ) -> None:
        del request, tokens, processed_tokens
        if remaining_tokens == 0:
            self._apply_pending()

    def request(self, session_id: str, mode: str) -> dict[str, Any]:
        mode = normalize_qwen4_boost(mode)
        active = bool(
            session_id == self.session_id and self.owner.has_active_requests()
        )
        self.modes[session_id] = mode
        with self._lock:
            if active:
                self.pending[session_id] = mode
            else:
                self.pending.pop(session_id, None)
        policy = qwen4_boost_policy(mode)
        return {
            "accepted": True,
            "queued": active,
            "session_id": session_id,
            "mode": mode,
            "effective_mode": self.mode if active else mode,
            "applies": "next_token" if active else "next_request",
            "lossy": policy is not None,
            "protected_top": 10 if policy is None else policy.protected_top,
        }

    def stats(self) -> dict[str, Any]:
        replaced = before = after = layers = 0
        model = getattr(self.owner, "_vlm_model", None)
        if model is not None:
            inner = getattr(model.language_model, "model", model.language_model)
            for decoder in getattr(inner, "layers", ()):
                counters = getattr(getattr(decoder, "mlp", None), "boost_stats", None)
                if counters is None:
                    continue
                layers += 1
                replaced += int(counters["routes_replaced"])
                before += int(counters["misses_before"])
                after += int(counters["misses_after"])
        policy = qwen4_boost_policy(self.mode)
        return {
            "available": True,
            "prefill_boost_supported": True,
            "mode": self.mode,
            "session_id": self.session_id,
            "switches": self.switches,
            "pending": len(self.pending),
            "layers": layers,
            "lossy": policy is not None,
            "protected_top": 10 if policy is None else policy.protected_top,
            "routes_replaced": replaced,
            "misses_before": before,
            "misses_after": after,
            "misses_avoided": before - after,
        }


__all__ = [
    "BOOST_TO_PROTECTED_TOP",
    "Qwen4BoostPolicy",
    "Qwen4BoostController",
    "normalize_qwen4_boost",
    "qwen4_boost_policy",
    "set_qwen4_boost_mode",
]
