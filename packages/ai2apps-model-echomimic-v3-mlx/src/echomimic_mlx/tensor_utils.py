"""Close-reference MLX tensor operators used by the Wan transformer."""

from __future__ import annotations

import math

import mlx.core as mx


def wan_rms_norm(x: mx.array, weight: mx.array | None = None, *, eps: float = 1e-6) -> mx.array:
    """Match upstream WanRMSNorm's FP32 normalization and output cast."""

    dtype = x.dtype
    values = x.astype(mx.float32)
    normalized = values * mx.rsqrt(mx.mean(mx.square(values), axis=-1, keepdims=True) + eps)
    result = normalized.astype(dtype)
    return result if weight is None else result * weight


def wan_layer_norm(
    x: mx.array,
    weight: mx.array | None = None,
    bias: mx.array | None = None,
    *,
    eps: float = 1e-6,
) -> mx.array:
    """Match upstream WanLayerNorm's biased FP32 variance calculation."""

    dtype = x.dtype
    values = x.astype(mx.float32)
    mean = mx.mean(values, axis=-1, keepdims=True)
    centered = values - mean
    variance = mx.mean(mx.square(centered), axis=-1, keepdims=True)
    result = (centered * mx.rsqrt(variance + eps)).astype(dtype)
    if weight is not None:
        result = result * weight
    if bias is not None:
        result = result + bias
    return result


def gelu_tanh(x: mx.array) -> mx.array:
    """PyTorch-compatible GELU with ``approximate='tanh'``."""

    coefficient = math.sqrt(2.0 / math.pi)
    return 0.5 * x * (1.0 + mx.tanh(coefficient * (x + 0.044715 * mx.power(x, 3))))


def linear(x: mx.array, weight: mx.array, bias: mx.array | None = None) -> mx.array:
    """Apply a PyTorch-layout Linear weight shaped ``[out, in]``."""

    if weight.ndim != 2 or x.shape[-1] != weight.shape[1]:
        raise ValueError(
            f"linear shape mismatch: input {x.shape}, weight {weight.shape}; expected [..., in]"
        )
    result = mx.matmul(x, mx.transpose(weight))
    return result if bias is None else result + bias
