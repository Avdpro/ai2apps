"""Experiment-only control for direct SSD-to-MLX expert slot loading."""

from __future__ import annotations

import os
from typing import Any

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def direct_l1_mode() -> str:
    """Return ``auto``, ``on``, or ``off`` for the local A/B experiment."""

    value = os.environ.get("OMLX_MOE_DIRECT_L1", "auto").strip().lower()
    if value in ("", "auto"):
        return "auto"
    if value in _TRUE:
        return "on"
    if value in _FALSE:
        return "off"
    raise ValueError("OMLX_MOE_DIRECT_L1 must be auto, 0/off, or 1/on")


def use_direct_l1(*, native_available: bool) -> bool:
    """Resolve the A/B mode, failing loudly when forced native is unavailable."""

    mode = direct_l1_mode()
    if mode == "off":
        return False
    if native_available:
        return True
    if mode == "on":
        raise RuntimeError(
            "OMLX_MOE_DIRECT_L1=1 requires the native direct expert loader"
        )
    return False


def direct_load_fused_experts(
    store: Any,
    switch: Any,
    slots: tuple[int, ...] | list[int],
    expert_ids: tuple[int, ...],
    *,
    io_workers: int = 4,
) -> int | None:
    """Load compute-ready fused records into final unified-memory slots.

    The native primitive is deliberately model agnostic.  It consumes the
    shared expert-major ABI used by DeepSeek, GLM, and Qwen and writes each
    record directly into the six affine-Q4 arrays owned by ``SwitchGLU``.
    ``None`` means that the portable staging path must be used instead.
    """

    # Import lazily so ordinary CPU-only tooling can inspect/convert stores
    # without importing the native MLX extension.
    from omlx.custom_kernels.glm_moe_dsa import fast as native_fast

    available = "preadv_fused_experts" in native_fast.native_symbols()
    if not use_direct_l1(native_available=available):
        return None

    gate_up = getattr(switch, "gate_up_proj", None)
    if gate_up is None:
        if direct_l1_mode() == "on":
            raise RuntimeError(
                "OMLX_MOE_DIRECT_L1=1 requires a fused gate_up_proj SwitchGLU"
            )
        return None
    arrays = tuple(
        projection.get(component)
        for projection in (gate_up, switch.down_proj)
        for component in ("weight", "scales", "biases")
    )
    if any(value is None for value in arrays):
        if direct_l1_mode() == "on":
            raise RuntimeError(
                "OMLX_MOE_DIRECT_L1=1 requires affine weight/scales/biases"
            )
        return None

    loaded = native_fast.preadv_expert_segments(
        store.fileno(),
        store.data_offset,
        store.record_bytes,
        list(expert_ids),
        list(slots),
        *arrays,
        io_workers=io_workers,
    )
    expected = len(expert_ids) * store.record_bytes
    if loaded != expected:
        raise RuntimeError(
            f"native expert loader reported {loaded} bytes, expected {expected}"
        )
    return loaded


__all__ = [
    "direct_l1_mode",
    "direct_load_fused_experts",
    "use_direct_l1",
]
