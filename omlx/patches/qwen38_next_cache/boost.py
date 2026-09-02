"""Runtime-selectable Boost policies for Qwen3.8 Flash Next Cached-MoE."""

from __future__ import annotations

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


__all__ = [
    "BOOST_TO_PROTECTED_TOP",
    "Qwen4BoostPolicy",
    "normalize_qwen4_boost",
    "qwen4_boost_policy",
    "set_qwen4_boost_mode",
]
