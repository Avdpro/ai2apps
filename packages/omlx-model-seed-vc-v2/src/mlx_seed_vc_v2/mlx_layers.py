"""Layout-explicit MLX operators for PyTorch checkpoint compatibility."""

from __future__ import annotations

from typing import Any


def linear(values: Any, weight: Any, bias: Any | None = None) -> Any:
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
    import mlx.core as mx

    result = mx.conv1d(
        values.transpose(0, 2, 1),
        weight.transpose(0, 2, 1),
        stride=stride,
        padding=padding,
        dilation=dilation,
        groups=groups,
    )
    if bias is not None:
        result += bias[None, None, :]
    return result.transpose(0, 2, 1)
