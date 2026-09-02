"""MLX attention primitives with explicit Wan tensor layouts."""

from __future__ import annotations

import math

import mlx.core as mx


def scaled_dot_product_attention(
    query: mx.array,
    key: mx.array,
    value: mx.array,
    *,
    scale: float | None = None,
    fast: bool = False,
) -> mx.array:
    """Attend over upstream layout ``[batch, sequence, heads, head_dim]``.

    The explicit path is the FP32 operator oracle. ``fast=True`` selects MLX's fused
    production kernel and is evaluated with dtype-appropriate parity bounds.
    """

    if query.ndim != 4 or key.ndim != 4 or value.ndim != 4:
        raise ValueError("attention expects rank-four query, key, and value tensors")
    if query.shape[0] != key.shape[0] or key.shape != value.shape:
        raise ValueError("attention batch/key/value shapes are incompatible")
    if query.shape[2:] != key.shape[2:]:
        raise ValueError("attention head count and head dimension must match")
    query_heads = mx.transpose(query, (0, 2, 1, 3))
    key_heads = mx.transpose(key, (0, 2, 1, 3))
    value_heads = mx.transpose(value, (0, 2, 1, 3))
    attention_scale = scale if scale is not None else 1.0 / math.sqrt(query.shape[-1])
    if fast:
        result = mx.fast.scaled_dot_product_attention(
            query_heads, key_heads, value_heads, scale=attention_scale
        )
    else:
        scores = (
            mx.sum(query_heads[..., :, None, :] * key_heads[..., None, :, :], axis=-1)
            * attention_scale
        )
        probabilities = mx.softmax(scores, axis=-1, precise=True)
        result = mx.sum(probabilities[..., :, :, None] * value_heads[..., None, :, :], axis=-2)
    return mx.transpose(result, (0, 2, 1, 3))
