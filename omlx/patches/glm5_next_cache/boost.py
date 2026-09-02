"""Device-side Engine Boost policies for GLM-5 Cache-MoE."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any

import mlx.core as mx

BOOST_TO_LOSSY = {
    "natural": "exact",
    "turbo": "head5",
    "blast": "head3",
    "tail3": "tail3",
    "head3": "head3",
}


@dataclass(frozen=True)
class Glm5LossyPolicy:
    mode: str
    replace_count: int


def normalize_glm5_boost(mode: str | None) -> str:
    value = str(mode or "natural").strip().lower()
    if value not in BOOST_TO_LOSSY:
        raise ValueError(
            "GLM-5 Engine Boost must be natural, turbo, blast, tail3, or head3"
        )
    return value


def glm5_lossy_policy(mode: str | None) -> Glm5LossyPolicy | None:
    value = normalize_glm5_boost(mode)
    if value == "natural":
        return None
    # GLM-5 routes Top-8. Its smaller experts make a less aggressive product
    # policy worthwhile: Turbo protects Top-5 and Blast protects Top-3.
    counts = {"turbo": 3, "blast": 5, "tail3": 3, "head3": 5}
    return Glm5LossyPolicy(BOOST_TO_LOSSY[value], counts[value])


def available_experts(
    l1_lookup: mx.array,
    hot_lookup: mx.array,
) -> mx.array:
    """Return the union of fixed L1 and Hot-bank expert IDs on device."""

    return (l1_lookup >= 0) | (hot_lookup >= 0)


def replace_missed_routes(
    inds: mx.array,
    scores: mx.array,
    router_choice_scores: mx.array,
    available: mx.array,
    policy: Glm5LossyPolicy,
) -> tuple[mx.array, tuple[mx.array, mx.array, mx.array]]:
    """Replace eligible misses with the best resident experts on device.

    Original routing weights are retained. Candidates use the router's
    bias-corrected choice score and exclude every expert in the original
    Top-K. No route IDs are copied to the host.
    """

    top_k = int(inds.shape[-1])
    count = min(policy.replace_count, top_k)
    all_ids = mx.arange(available.shape[0], dtype=inds.dtype)
    selected = mx.any(all_ids[None, None, None, :] == inds[..., None], axis=-2)
    candidates = available[None, None, :] & ~selected
    masked_scores = mx.where(candidates, router_choice_scores, -mx.inf)
    candidate_ids = mx.argpartition(-masked_scores, kth=count - 1, axis=-1)[..., :count]
    candidate_values = mx.take_along_axis(masked_scores, candidate_ids, axis=-1)
    candidate_ids = mx.take_along_axis(
        candidate_ids, mx.argsort(-candidate_values, axis=-1), axis=-1
    )

    positions = mx.argsort(scores, axis=-1)[..., :count]
    route_ids = mx.take_along_axis(inds, positions, axis=-1)
    eligible = ~available[route_ids]
    rank_positions = mx.arange(count, dtype=mx.int32)
    higher_weight = rank_positions[None, :] > rank_positions[:, None]
    candidate_rank = mx.sum(
        eligible[..., None, :] & higher_weight,
        axis=-1,
    ).astype(mx.int32)
    replacements = mx.take_along_axis(candidate_ids, candidate_rank, axis=-1)
    candidate_count = mx.sum(mx.isfinite(candidate_values), axis=-1)
    replacement_valid = candidate_rank < candidate_count[..., None]

    output = inds
    replaced_mask = mx.zeros(inds.shape, dtype=mx.bool_)
    top_positions = mx.arange(top_k, dtype=positions.dtype)
    for offset in range(count):
        apply = (
            (top_positions == positions[..., offset, None])
            & eligible[..., offset, None]
            & replacement_valid[..., offset, None]
        )
        output = mx.where(apply, replacements[..., offset, None], output)
        replaced_mask = replaced_mask | apply

    before = mx.sum((~available[inds]).astype(mx.int32))
    after = mx.sum((~available[output]).astype(mx.int32))
    replaced = mx.sum(replaced_mask.astype(mx.int32))
    return output, (replaced, before, after)


class Glm5BoostController:
    """Keep GLM Boost preferences isolated by the AI2Apps session ID."""

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

    def _blocks(self):
        return self.owner._vlm_model.language_model.model.layers

    def _apply(self, session_id: str, mode: str) -> bool:
        mode = normalize_glm5_boost(mode)
        changed = mode != self.mode or session_id != self.session_id
        policy = glm5_lossy_policy(mode)
        for decoder in self._blocks():
            block = decoder.mlp
            if hasattr(block, "boost_policy"):
                block.boost_policy = policy
        if mode != self.mode:
            self.switches += 1
        self.mode = mode
        self.session_id = session_id
        self.modes[session_id] = mode
        return changed

    async def prepare(
        self, kwargs: dict[str, Any], *, context_tokens: int = 0
    ) -> tuple[str, str]:
        del context_tokens  # Reserved for a future measured Prefill Auto policy.
        session_id = str(kwargs.get("flesh_session_id", "default"))
        legacy = kwargs.pop("flesh_boost_mode", None)
        prefill_requested = kwargs.pop("flesh_prefill_boost_mode", legacy)
        decode_requested = kwargs.pop("flesh_decode_boost_mode", legacy)
        prefill_mode = normalize_glm5_boost(
            prefill_requested
            if prefill_requested is not None
            else self.modes.get(session_id, self.default_mode)
        )
        decode_mode = normalize_glm5_boost(
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

    def _apply_pending(self, session_id: str) -> bool:
        with self._lock:
            mode = self.decode_pending.pop(session_id, None)
            if mode is None:
                mode = self.pending.pop(session_id, None)
        return False if mode is None else self._apply(session_id, mode)

    def on_scheduler_step(self, scheduler_output: Any) -> None:
        """Publish pending changes between Decode steps on the MLX thread."""

        session_id = self.session_id
        if session_id is None:
            return
        has_decode_output = any(
            int(getattr(output, "completion_tokens", 0)) > 0
            for output in getattr(scheduler_output, "outputs", ())
        )
        if has_decode_output:
            self._apply_pending(session_id)

    def between_prefill_chunk(
        self,
        request: Any,
        *,
        tokens: int,
        processed_tokens: int,
        remaining_tokens: int,
    ) -> None:
        """Switch a split Prefill/Decode policy after the final prompt chunk."""

        del request, tokens, processed_tokens
        if remaining_tokens == 0 and self.session_id is not None:
            self._apply_pending(self.session_id)

    def request(self, session_id: str, mode: str) -> dict[str, Any]:
        mode = normalize_glm5_boost(mode)
        active = bool(
            session_id == self.session_id and self.owner.has_active_requests()
        )
        self.modes[session_id] = mode
        with self._lock:
            if active:
                self.pending[session_id] = mode
            else:
                self.pending.pop(session_id, None)
        return {
            "accepted": True,
            "queued": active,
            "session_id": session_id,
            "mode": mode,
            "applies": "next_token" if active else "next_request",
        }

    def stats(self) -> dict[str, Any]:
        replaced = before = after = layers = 0
        if getattr(self.owner, "_vlm_model", None) is not None:
            for decoder in self._blocks():
                counters = getattr(decoder.mlp, "boost_stats", None)
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
    "Glm5LossyPolicy",
    "Glm5BoostController",
    "available_experts",
    "glm5_lossy_policy",
    "normalize_glm5_boost",
    "replace_missed_routes",
]
