"""Small layout-explicit MLX operators shared by the RVC model port."""

from __future__ import annotations

from typing import Any

import numpy as np


def weight_norm(
    weight_g: np.ndarray, weight_v: np.ndarray, *, dim: int = 0
) -> np.ndarray:
    """Materialize PyTorch legacy ``weight_norm(..., dim=dim)`` in float32."""

    gain = np.asarray(weight_g, dtype=np.float32)
    direction = np.asarray(weight_v, dtype=np.float32)
    if direction.ndim < 1 or not 0 <= dim < direction.ndim:
        raise ValueError("weight norm dimension is invalid")
    reduction_axes = tuple(axis for axis in range(direction.ndim) if axis != dim)
    norm = np.sqrt(np.sum(np.square(direction), axis=reduction_axes, keepdims=True))
    if gain.shape != norm.shape:
        try:
            gain = np.broadcast_to(gain, norm.shape)
        except ValueError as error:
            raise ValueError(
                "weight_g is not broadcastable to the weight norm"
            ) from error
    return direction * (gain / np.maximum(norm, np.finfo(np.float32).tiny))


def linear(values: Any, weight: Any, bias: Any | None = None) -> Any:
    """Apply a PyTorch-layout linear layer to an MLX array."""

    result = values @ weight.T
    return result if bias is None else result + bias


def conv1d_nct(
    values: Any,
    weight: Any,
    bias: Any | None = None,
    *,
    stride: int = 1,
    padding: int = 0,
    dilation: int = 1,
    groups: int = 1,
) -> Any:
    """Conv1d with PyTorch NCT input and OIK weight layouts."""

    import mlx.core as mx

    nlc = mx.transpose(values, (0, 2, 1))
    oki = mx.transpose(weight, (0, 2, 1))
    result = mx.conv1d(
        nlc,
        oki,
        stride=stride,
        padding=padding,
        dilation=dilation,
        groups=groups,
    )
    if bias is not None:
        result += bias[None, None, :]
    return mx.transpose(result, (0, 2, 1))


def conv_transpose1d_nct(
    values: Any,
    weight: Any,
    bias: Any | None = None,
    *,
    stride: int = 1,
    padding: int = 0,
    dilation: int = 1,
    output_padding: int = 0,
    groups: int = 1,
) -> Any:
    """ConvTranspose1d with PyTorch NCT input and IOk weight layouts."""

    import mlx.core as mx

    nlc = mx.transpose(values, (0, 2, 1))
    oki = mx.transpose(weight, (1, 2, 0))
    result = mx.conv_transpose1d(
        nlc,
        oki,
        stride=stride,
        padding=padding,
        dilation=dilation,
        output_padding=output_padding,
        groups=groups,
    )
    if bias is not None:
        result += bias[None, None, :]
    return mx.transpose(result, (0, 2, 1))
