"""MLX cross-domain Transformer used by the released HTDemucs checkpoint."""

from __future__ import annotations

import math

from .mlx_layers import State, _group_norm, _value


def _layer_norm(mx, values, state: State, prefix: str, *, eps: float = 1e-5):
    mean = mx.mean(values, axis=-1, keepdims=True)
    variance = mx.var(values, axis=-1, keepdims=True)
    normalized = (values - mean) * mx.rsqrt(variance + eps)
    return (
        normalized * _value(mx, state, f"{prefix}.weight")
        + _value(mx, state, f"{prefix}.bias")
    )


def _linear(mx, values, state: State, prefix: str):
    weight = _value(mx, state, f"{prefix}.weight")
    bias = _value(mx, state, f"{prefix}.bias")
    return values @ mx.transpose(weight) + bias


def _attention(mx, query, key, state: State, prefix: str, *, heads: int):
    dimensions = query.shape[-1]
    if dimensions % heads:
        raise ValueError(f"{dimensions} dimensions are not divisible by {heads} heads")
    weight = _value(mx, state, f"{prefix}.in_proj_weight")
    bias = _value(mx, state, f"{prefix}.in_proj_bias")
    q = query @ mx.transpose(weight[:dimensions]) + bias[:dimensions]
    k = key @ mx.transpose(weight[dimensions : 2 * dimensions]) + bias[
        dimensions : 2 * dimensions
    ]
    v = key @ mx.transpose(weight[2 * dimensions :]) + bias[2 * dimensions :]
    head_size = dimensions // heads

    def split_heads(values):
        batch, length, _ = values.shape
        return mx.transpose(values.reshape((batch, length, heads, head_size)), (0, 2, 1, 3))

    q = split_heads(q)
    k = split_heads(k)
    v = split_heads(v)
    attended = mx.fast.scaled_dot_product_attention(
        q,
        k,
        v,
        scale=head_size**-0.5,
    )
    attended = mx.transpose(attended, (0, 2, 1, 3)).reshape(query.shape)
    return _linear(mx, attended, state, f"{prefix}.out_proj")


def _feed_forward(mx, values, state: State, prefix: str):
    import mlx.nn as nn

    hidden = nn.gelu(_linear(mx, values, state, f"{prefix}.linear1"))
    return _linear(mx, hidden, state, f"{prefix}.linear2")


def _transformer_layer(
    values,
    context,
    state: State,
    prefix: str,
    *,
    heads: int,
    self_attention: bool,
):
    """Apply a norm-first self- or cross-attention layer with LayerScale."""
    import mlx.core as mx

    normalized_query = _layer_norm(mx, values, state, f"{prefix}.norm1")
    if self_attention:
        normalized_context = normalized_query
        attention_prefix = f"{prefix}.self_attn"
    else:
        normalized_context = _layer_norm(mx, context, state, f"{prefix}.norm2")
        attention_prefix = f"{prefix}.cross_attn"
    attention = _attention(
        mx,
        normalized_query,
        normalized_context,
        state,
        attention_prefix,
        heads=heads,
    )
    values = values + attention * _value(mx, state, f"{prefix}.gamma_1.scale")
    ff_norm_name = "norm2" if self_attention else "norm3"
    feed_forward = _feed_forward(
        mx,
        _layer_norm(mx, values, state, f"{prefix}.{ff_norm_name}"),
        state,
        prefix,
    )
    values = values + feed_forward * _value(mx, state, f"{prefix}.gamma_2.scale")
    return _group_norm(mx, values, state, f"{prefix}.norm_out")


def sin_embedding(length: int, dimensions: int, *, max_period: float = 10000.0):
    """Return the deterministic 1D Demucs sinusoidal embedding as ``[1,T,C]``."""
    import mlx.core as mx

    if dimensions % 2:
        raise ValueError("Sinusoidal embedding dimensions must be even")
    half = dimensions // 2
    positions = mx.arange(length, dtype=mx.float32)[:, None]
    dimensions_index = mx.arange(half, dtype=mx.float32)[None, :]
    phase = positions / (max_period ** (dimensions_index / (half - 1)))
    return mx.concatenate([mx.cos(phase), mx.sin(phase)], axis=-1)[None, :, :]


def sin_embedding_2d(
    height: int,
    width: int,
    dimensions: int,
    *,
    max_period: float = 10000.0,
):
    """Return Demucs' 2D embedding as channels-last ``[1,H,W,C]``."""
    import mlx.core as mx

    if dimensions % 4:
        raise ValueError("2D sinusoidal embedding dimensions must be divisible by four")
    half = dimensions // 2
    divisor = mx.exp(
        mx.arange(0, half, 2, dtype=mx.float32) * (-math.log(max_period) / half)
    )
    width_phase = mx.arange(width, dtype=mx.float32)[:, None] * divisor[None, :]
    height_phase = mx.arange(height, dtype=mx.float32)[:, None] * divisor[None, :]
    width_values = mx.stack([mx.sin(width_phase), mx.cos(width_phase)], axis=-1).reshape(
        (width, half)
    )
    height_values = mx.stack(
        [mx.sin(height_phase), mx.cos(height_phase)], axis=-1
    ).reshape((height, half))
    width_values = mx.broadcast_to(width_values[None, :, :], (height, width, half))
    height_values = mx.broadcast_to(height_values[:, None, :], (height, width, half))
    return mx.concatenate([width_values, height_values], axis=-1)[None, :, :, :]


def cross_transformer(
    frequency,
    time,
    state: State,
    prefix: str,
    *,
    heads: int = 8,
    layers: int = 5,
    max_period: float = 10000.0,
):
    """Run the released five-layer alternating cross/self Transformer.

    ``frequency`` is ``[B,F,T,C]`` and ``time`` is ``[B,L,C]``.
    """
    import mlx.core as mx

    batch, frequencies, frames, dimensions = frequency.shape
    frequency_tokens = mx.transpose(frequency, (0, 2, 1, 3)).reshape(
        (batch, frames * frequencies, dimensions)
    )
    position_2d = mx.transpose(
        sin_embedding_2d(frequencies, frames, dimensions, max_period=max_period),
        (0, 2, 1, 3),
    ).reshape((1, frames * frequencies, dimensions))
    frequency_tokens = _layer_norm(mx, frequency_tokens, state, f"{prefix}.norm_in")
    frequency_tokens = frequency_tokens + position_2d

    time_tokens = _layer_norm(mx, time, state, f"{prefix}.norm_in_t")
    time_tokens = time_tokens + sin_embedding(
        time.shape[1], dimensions, max_period=max_period
    )

    # The released model uses cross_first=False: even layers are independent
    # self attention and odd layers are cross attention.
    for index in range(layers):
        if not index % 2:
            frequency_tokens = _transformer_layer(
                frequency_tokens,
                frequency_tokens,
                state,
                f"{prefix}.layers.{index}",
                heads=heads,
                self_attention=True,
            )
            time_tokens = _transformer_layer(
                time_tokens,
                time_tokens,
                state,
                f"{prefix}.layers_t.{index}",
                heads=heads,
                self_attention=True,
            )
        else:
            previous_frequency = frequency_tokens
            frequency_tokens = _transformer_layer(
                frequency_tokens,
                time_tokens,
                state,
                f"{prefix}.layers.{index}",
                heads=heads,
                self_attention=False,
            )
            time_tokens = _transformer_layer(
                time_tokens,
                previous_frequency,
                state,
                f"{prefix}.layers_t.{index}",
                heads=heads,
                self_attention=False,
            )

    frequency = frequency_tokens.reshape((batch, frames, frequencies, dimensions))
    return mx.transpose(frequency, (0, 2, 1, 3)), time_tokens
