"""Real-valued Wan 3D rotary position embedding for MLX."""

from __future__ import annotations

from dataclasses import dataclass

import mlx.core as mx
import numpy as np


@dataclass(frozen=True, slots=True)
class RopeTable:
    """Cosine/sine tables split across temporal, height, and width axes."""

    temporal_cos: mx.array
    temporal_sin: mx.array
    height_cos: mx.array
    height_sin: mx.array
    width_cos: mx.array
    width_sin: mx.array


def _axis_table(max_length: int, complex_dim: int, theta: float) -> tuple[mx.array, mx.array]:
    if complex_dim == 0:
        empty = mx.zeros((max_length, 0), dtype=mx.float32)
        return empty, empty
    real_dim = complex_dim * 2
    positions = np.arange(max_length, dtype=np.float64)
    inverse = 1.0 / np.power(theta, np.arange(0, real_dim, 2, dtype=np.float64) / real_dim)
    phase = np.outer(positions, inverse)
    return mx.array(np.cos(phase).astype(np.float32)), mx.array(np.sin(phase).astype(np.float32))


def build_rope_table(max_length: int, head_dim: int, *, theta: float = 10_000.0) -> RopeTable:
    """Build the axis split used by the pinned Wan implementation."""

    if max_length <= 0 or head_dim <= 0 or head_dim % 2:
        raise ValueError("max_length must be positive and head_dim must be positive and even")
    complex_dim = head_dim // 2
    spatial = complex_dim // 3
    temporal = complex_dim - 2 * spatial
    temporal_cos, temporal_sin = _axis_table(max_length, temporal, theta)
    height_cos, height_sin = _axis_table(max_length, spatial, theta)
    width_cos, width_sin = _axis_table(max_length, spatial, theta)
    return RopeTable(
        temporal_cos,
        temporal_sin,
        height_cos,
        height_sin,
        width_cos,
        width_sin,
    )


def _apply_pairs(x: mx.array, cos: mx.array, sin: mx.array) -> mx.array:
    pairs = mx.reshape(x.astype(mx.float32), (*x.shape[:-1], x.shape[-1] // 2, 2))
    even = pairs[..., 0]
    odd = pairs[..., 1]
    rotated = mx.stack([even * cos - odd * sin, even * sin + odd * cos], axis=-1)
    return mx.reshape(rotated, x.shape)


def _grid_multipliers(
    frames: int, height: int, width: int, table: RopeTable
) -> tuple[mx.array, mx.array]:
    if frames <= 0 or height <= 0 or width <= 0:
        raise ValueError("RoPE grid extents must be positive")
    if (
        frames > table.temporal_cos.shape[0]
        or height > table.height_cos.shape[0]
        or width > table.width_cos.shape[0]
    ):
        raise ValueError("RoPE grid exceeds the precomputed table")
    temporal_cos = mx.broadcast_to(
        table.temporal_cos[:frames, None, None, :],
        (frames, height, width, table.temporal_cos.shape[1]),
    )
    temporal_sin = mx.broadcast_to(
        table.temporal_sin[:frames, None, None, :],
        (frames, height, width, table.temporal_sin.shape[1]),
    )
    height_cos = mx.broadcast_to(
        table.height_cos[None, :height, None, :],
        (frames, height, width, table.height_cos.shape[1]),
    )
    height_sin = mx.broadcast_to(
        table.height_sin[None, :height, None, :],
        (frames, height, width, table.height_sin.shape[1]),
    )
    width_cos = mx.broadcast_to(
        table.width_cos[None, None, :width, :],
        (frames, height, width, table.width_cos.shape[1]),
    )
    width_sin = mx.broadcast_to(
        table.width_sin[None, None, :width, :],
        (frames, height, width, table.width_sin.shape[1]),
    )
    cos = mx.concatenate([temporal_cos, height_cos, width_cos], axis=-1)
    sin = mx.concatenate([temporal_sin, height_sin, width_sin], axis=-1)
    return mx.reshape(cos, (-1, 1, cos.shape[-1])), mx.reshape(sin, (-1, 1, sin.shape[-1]))


def apply_3d_rope(
    x: mx.array, grid_sizes: list[tuple[int, int, int]], table: RopeTable
) -> mx.array:
    """Apply Wan RoPE to ``[batch, sequence, heads, head_dim]`` tensors."""

    if x.ndim != 4 or x.shape[-1] % 2:
        raise ValueError("3D RoPE expects [batch, sequence, heads, even head_dim]")
    if len(grid_sizes) != x.shape[0]:
        raise ValueError("one RoPE grid is required for each batch item")
    output: list[mx.array] = []
    for batch, (frames, height, width) in enumerate(grid_sizes):
        sequence = frames * height * width
        if sequence > x.shape[1]:
            raise ValueError("RoPE grid contains more tokens than the input sequence")
        cos, sin = _grid_multipliers(frames, height, width, table)
        rotated = _apply_pairs(x[batch, :sequence], cos, sin)
        if sequence < x.shape[1]:
            rotated = mx.concatenate([rotated, x[batch, sequence:].astype(mx.float32)], axis=0)
        output.append(rotated)
    return mx.stack(output).astype(mx.float32)
