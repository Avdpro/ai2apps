"""MLX ports of the HTDemucs encoder/decoder building blocks.

The public functions use channels-last MLX tensors and consume a NumPy state
mapping with original PyTorch parameter names.  Layout conversion happens at
the operator boundary so every transform remains explicit and testable.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

State = Mapping[str, np.ndarray]


def _value(mx, state: State, name: str):
    try:
        return mx.array(np.asarray(state[name], dtype=np.float32))
    except KeyError as error:
        raise KeyError(f"Missing Demucs parameter: {name}") from error


def _conv1d(mx, values, state: State, prefix: str, *, stride=1, padding=0, dilation=1):
    # PyTorch OIK -> MLX OKI.
    weight = mx.transpose(_value(mx, state, f"{prefix}.weight"), (0, 2, 1))
    bias = _value(mx, state, f"{prefix}.bias")
    return mx.conv1d(values, weight, stride, padding, dilation) + bias


def _conv2d(mx, values, state: State, prefix: str, *, stride=(1, 1), padding=(0, 0)):
    # PyTorch OIHW -> MLX OHWI.
    weight = mx.transpose(_value(mx, state, f"{prefix}.weight"), (0, 2, 3, 1))
    bias = _value(mx, state, f"{prefix}.bias")
    return mx.conv2d(values, weight, stride, padding) + bias


def _conv_transpose1d(mx, values, state: State, prefix: str, *, stride=1):
    # PyTorch IOK -> MLX OKI.
    weight = mx.transpose(_value(mx, state, f"{prefix}.weight"), (1, 2, 0))
    bias = _value(mx, state, f"{prefix}.bias")
    return mx.conv_transpose1d(values, weight, stride) + bias


def _conv_transpose2d(mx, values, state: State, prefix: str, *, stride=(1, 1)):
    # PyTorch IOHW -> MLX OHWI.
    weight = mx.transpose(_value(mx, state, f"{prefix}.weight"), (1, 2, 3, 0))
    bias = _value(mx, state, f"{prefix}.bias")
    return mx.conv_transpose2d(values, weight, stride) + bias


def _group_norm(mx, values, state: State, prefix: str, *, groups: int = 1, eps=1e-5):
    batch, *spatial, channels = values.shape
    if channels % groups:
        raise ValueError(f"{channels} channels are not divisible by {groups} groups")
    group_size = channels // groups
    grouped = values.reshape((batch, -1, groups, group_size))
    grouped = mx.transpose(grouped, (0, 2, 1, 3)).reshape((batch, groups, -1))
    mean = mx.mean(grouped, axis=-1, keepdims=True)
    variance = mx.var(grouped, axis=-1, keepdims=True)
    normalized = (grouped - mean) * mx.rsqrt(variance + eps)
    normalized = normalized.reshape((batch, groups, -1, group_size))
    normalized = mx.transpose(normalized, (0, 2, 1, 3)).reshape((batch, *spatial, channels))
    weight = _value(mx, state, f"{prefix}.weight")
    bias = _value(mx, state, f"{prefix}.bias")
    return normalized * weight + bias


def _glu(mx, values):
    half = values.shape[-1] // 2
    return values[..., :half] * mx.sigmoid(values[..., half:])


def dconv(values, state: State, prefix: str, *, depth: int = 2):
    """Port the residual DConv used by the released htdemucs checkpoint."""
    import mlx.core as mx
    import mlx.nn as nn

    output = values
    for layer in range(depth):
        root = f"{prefix}.layers.{layer}"
        branch = _conv1d(
            mx,
            output,
            state,
            f"{root}.0",
            padding=2**layer,
            dilation=2**layer,
        )
        branch = _group_norm(mx, branch, state, f"{root}.1")
        branch = nn.gelu(branch)
        branch = _conv1d(mx, branch, state, f"{root}.3")
        branch = _group_norm(mx, branch, state, f"{root}.4")
        branch = _glu(mx, branch)
        scale = _value(mx, state, f"{root}.6.scale")
        output = output + branch * scale
    return output


def henc_time(values, state: State, prefix: str, *, stride: int = 4, padding: int = 2):
    """HTDemucs time-branch HEncLayer in NLC layout."""
    import mlx.core as mx
    import mlx.nn as nn

    length = values.shape[1]
    remainder = length % stride
    if remainder:
        values = mx.pad(values, ((0, 0), (0, stride - remainder), (0, 0)))
    encoded = _conv1d(mx, values, state, f"{prefix}.conv", stride=stride, padding=padding)
    encoded = nn.gelu(encoded)
    encoded = dconv(encoded, state, f"{prefix}.dconv")
    return _glu(mx, _conv1d(mx, encoded, state, f"{prefix}.rewrite"))


def henc_frequency(values, state: State, prefix: str, *, stride: int = 4, padding: int = 2):
    """HTDemucs frequency-branch HEncLayer in NHWC layout."""
    import mlx.core as mx
    import mlx.nn as nn

    encoded = _conv2d(
        mx,
        values,
        state,
        f"{prefix}.conv",
        stride=(stride, 1),
        padding=(padding, 0),
    )
    encoded = nn.gelu(encoded)
    batch, frequencies, frames, channels = encoded.shape
    residual = encoded.reshape((batch * frequencies, frames, channels))
    residual = dconv(residual, state, f"{prefix}.dconv")
    encoded = residual.reshape((batch, frequencies, frames, channels))
    return _glu(mx, _conv2d(mx, encoded, state, f"{prefix}.rewrite"))


def add_frequency_embedding(
    values,
    state: State,
    *,
    prefix: str = "freq_emb.embedding",
    embedding_scale: float = 10.0,
    residual_scale: float = 0.2,
):
    """Add the released checkpoint's learned non-equivariant frequency embedding."""
    import mlx.core as mx

    embedding = _value(mx, state, f"{prefix}.weight")
    if embedding.shape != (values.shape[1], values.shape[-1]):
        raise ValueError(
            f"Frequency embedding shape {embedding.shape} does not match "
            f"{(values.shape[1], values.shape[-1])}"
        )
    return values + (embedding_scale * residual_scale) * embedding[None, :, None, :]


def channel_projection(values, state: State, prefix: str):
    """Apply one of HTDemucs' 1x1 bottom-channel projections."""
    import mlx.core as mx

    return _conv1d(mx, values, state, prefix)


def hdec_time(
    values,
    skip,
    state: State,
    prefix: str,
    *,
    length: int,
    stride: int = 4,
    padding: int = 2,
    last: bool = False,
):
    """HTDemucs time-branch HDecLayer in NLC layout."""
    import mlx.core as mx
    import mlx.nn as nn

    merged = values + skip
    decoded = _glu(mx, _conv1d(mx, merged, state, f"{prefix}.rewrite", padding=1))
    decoded = dconv(decoded, state, f"{prefix}.dconv")
    output = _conv_transpose1d(mx, decoded, state, f"{prefix}.conv_tr", stride=stride)
    output = output[:, padding : padding + length, :]
    return (output if last else nn.gelu(output)), decoded


def hdec_frequency(
    values,
    skip,
    state: State,
    prefix: str,
    *,
    stride: int = 4,
    padding: int = 2,
    last: bool = False,
):
    """HTDemucs frequency-branch HDecLayer in NHWC layout."""
    import mlx.core as mx
    import mlx.nn as nn

    merged = values + skip
    decoded = _glu(
        mx,
        _conv2d(mx, merged, state, f"{prefix}.rewrite", padding=(1, 1)),
    )
    batch, frequencies, frames, channels = decoded.shape
    residual = decoded.reshape((batch * frequencies, frames, channels))
    residual = dconv(residual, state, f"{prefix}.dconv")
    decoded = residual.reshape((batch, frequencies, frames, channels))
    output = _conv_transpose2d(
        mx,
        decoded,
        state,
        f"{prefix}.conv_tr",
        stride=(stride, 1),
    )
    output = output[:, padding:-padding, :, :]
    return (output if last else nn.gelu(output)), decoded
