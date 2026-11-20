"""Wan MLX primitives derived from the validated FlashHead port."""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn
import numpy as np


def timestep_embedding(dim, timestep):
    angles = (
        timestep.astype(mx.float32)[:, None]
        * mx.exp(-math.log(10000) * mx.arange(dim // 2, dtype=mx.float32) / (dim // 2))[
            None
        ]
    )
    return mx.concatenate([mx.cos(angles), mx.sin(angles)], axis=-1).astype(
        timestep.dtype
    )


def apply_rope(x, grid):
    (b, length, heads, width) = x.shape
    (f, h, w) = map(int, grid)
    if length != f * h * w or width % 2:
        raise ValueError("RoPE requires an unpadded three-dimensional token grid")
    widths = [width - 2 * (width // 3), width // 3, width // 3]
    phases = []
    for axis, (size, dim) in enumerate(zip((f, h, w), widths)):
        freq = 10000.0 ** (-np.arange(0, dim, 2, dtype=np.float64)[: dim // 2] / dim)
        shape = [1, 1, 1, dim // 2]
        shape[axis] = size
        phase = (np.arange(size)[:, None] * freq).reshape(shape)
        phases.append(np.broadcast_to(phase, (f, h, w, dim // 2)))
    phase = np.concatenate(phases, axis=-1).reshape(1, length, 1, width // 2)
    (cos, sin) = (
        mx.array(np.cos(phase).astype(np.float32)),
        mx.array(np.sin(phase).astype(np.float32)),
    )
    pairs = x.astype(mx.float32).reshape(b, length, heads, width // 2, 2)
    (real, imag) = (pairs[..., 0], pairs[..., 1])
    return (
        mx.stack([real * cos - imag * sin, real * sin + imag * cos], axis=-1)
        .reshape(x.shape)
        .astype(x.dtype)
    )


def attention(q, k, v, heads):
    (b, length, dim) = q.shape
    q = q.reshape(b, length, heads, dim // heads).transpose(0, 2, 1, 3)
    k = k.reshape(b, -1, heads, dim // heads).transpose(0, 2, 1, 3)
    v = v.reshape(b, -1, heads, dim // heads).transpose(0, 2, 1, 3)
    value = mx.fast.scaled_dot_product_attention(
        q, k, v, scale=(dim // heads) ** (-0.5)
    )
    return value.transpose(0, 2, 1, 3).reshape(b, length, dim)


class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-06):
        super().__init__()
        self.weight = mx.ones((dim,))
        self.eps = eps

    def __call__(self, x):
        value = x.astype(mx.float32)
        return (
            value * mx.rsqrt(mx.mean(value * value, axis=-1, keepdims=True) + self.eps)
        ).astype(x.dtype) * self.weight


class SelfAttention(nn.Module):
    def __init__(self, dim, num_heads, eps=1e-06):
        super().__init__()
        self.num_heads = num_heads
        (self.q, self.k, self.v, self.o) = [nn.Linear(dim, dim) for _ in range(4)]
        (self.norm_q, self.norm_k) = (RMSNorm(dim, eps), RMSNorm(dim, eps))

    def __call__(self, x, grid):
        shape = (*x.shape[:2], self.num_heads, x.shape[-1] // self.num_heads)
        q = apply_rope(self.norm_q(self.q(x)).reshape(shape), grid).reshape(x.shape)
        k = apply_rope(self.norm_k(self.k(x)).reshape(shape), grid).reshape(x.shape)
        return self.o(attention(q, k, self.v(x), self.num_heads))


class CrossAttention(nn.Module):
    def __init__(self, dim, num_heads, eps=1e-06, has_image_input=False):
        super().__init__()
        (self.num_heads, self.has_image_input) = (num_heads, has_image_input)
        (self.q, self.k, self.v, self.o) = [nn.Linear(dim, dim) for _ in range(4)]
        (self.norm_q, self.norm_k) = (RMSNorm(dim, eps), RMSNorm(dim, eps))
        if has_image_input:
            (self.k_img, self.v_img) = (nn.Linear(dim, dim), nn.Linear(dim, dim))
            self.norm_k_img = RMSNorm(dim, eps)

    def __call__(self, x, context):
        text = context[:, 257:] if self.has_image_input else context
        q = self.norm_q(self.q(x))
        out = attention(q, self.norm_k(self.k(text)), self.v(text), self.num_heads)
        if self.has_image_input:
            image = context[:, :257]
            out = out + attention(
                q, self.norm_k_img(self.k_img(image)), self.v_img(image), self.num_heads
            )
        return self.o(out)


class MLP(nn.Module):
    def __init__(self, in_dim, out_dim):
        super().__init__()
        self.proj = nn.Sequential(
            nn.LayerNorm(in_dim),
            nn.Linear(in_dim, in_dim),
            nn.GELU(),
            nn.Linear(in_dim, out_dim),
            nn.LayerNorm(out_dim),
        )

    def __call__(self, x):
        return self.proj(x)


class Head(nn.Module):
    def __init__(self, dim, out_dim, patch_size, eps):
        super().__init__()
        self.norm = nn.LayerNorm(dim, eps=eps, affine=False)
        self.head = nn.Linear(dim, out_dim * math.prod(patch_size))
        self.modulation = mx.zeros((1, 2, dim))

    def __call__(self, x, timestep):
        (b, length, dim) = x.shape
        frames = timestep.shape[0] // b
        mod = self.modulation.astype(timestep.dtype)[:, None] + timestep.reshape(
            b, frames, 1, dim
        )
        (shift, scale) = mx.split(mod, 2, axis=2)
        value = (
            self.norm(x.reshape(b, frames, length // frames, dim)) * (1 + scale) + shift
        )
        return self.head(value).reshape(b, length, -1)


def convert_weights(state):
    """Convert numeric arrays from the upstream state dict; loading remains strict."""
    sequential = ("text_embedding", "time_embedding", "time_projection", "ffn", "proj")
    out = {}
    for key, value in state.items():
        parts = key.split(".")
        mapped = []
        for i, part in enumerate(parts):
            mapped.append(part)
            if part in sequential and i + 1 < len(parts) and parts[i + 1].isdigit():
                mapped.append("layers")
        if key == "patch_embedding.weight":
            value = value.transpose(0, 2, 3, 4, 1)
        out[".".join(mapped)] = (
            value if isinstance(value, mx.array) else mx.array(value)
        )
    return out
