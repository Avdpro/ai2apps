"""Pure scheduling helpers for optional H3 acceleration recipes."""

from __future__ import annotations


def attention_broadcast_refresh(index: int, steps: int, period: int = 2) -> bool:
    """PAB refresh schedule with warmup/tail gates scaled from H3's 30-step recipe."""
    if period <= 1:
        return True

    def scaled_gate(at_30: int) -> int:
        return max(1, min(at_30, steps * at_30 // 30))

    warmup, tail = scaled_gate(4), scaled_gate(2)
    if index < warmup or index + tail >= steps:
        return True
    return (index - warmup) % period == 0


def step_cache_warmup(steps: int) -> int:
    """Number of initial steps before TeaCache-style velocity reuse may begin."""
    return max(1, min(2, steps * 2 // 30))
