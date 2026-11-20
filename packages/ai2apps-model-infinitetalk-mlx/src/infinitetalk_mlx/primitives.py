"""Wan MLX primitives derived from the validated FlashHead port."""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn


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


class AudioProjModel(nn.Module):
    def __init__(
        self,
        seq_len=5,
        seq_len_vf=8,
        blocks=12,
        channels=768,
        intermediate_dim=512,
        output_dim=1536,
        context_tokens=32,
        norm_output_audio=True,
    ):
        super().__init__()
        (self.context_tokens, self.output_dim) = (context_tokens, output_dim)
        self.proj1 = nn.Linear(seq_len * blocks * channels, intermediate_dim)
        self.proj1_vf = nn.Linear(seq_len_vf * blocks * channels, intermediate_dim)
        self.proj2 = nn.Linear(intermediate_dim, intermediate_dim)
        self.proj3 = nn.Linear(intermediate_dim, context_tokens * output_dim)
        self.norm = nn.LayerNorm(output_dim) if norm_output_audio else nn.Identity()

    def __call__(self, first, latter):
        (b, first_frames) = first.shape[:2]
        latter_frames = latter.shape[1]
        a = nn.relu(self.proj1(first.reshape(b * first_frames, -1))).reshape(
            b, first_frames, -1
        )
        z = nn.relu(self.proj1_vf(latter.reshape(b * latter_frames, -1))).reshape(
            b, latter_frames, -1
        )
        value = mx.concatenate([a, z], axis=1)
        value = self.proj3(nn.relu(self.proj2(value)))
        return self.norm(
            value.reshape(
                b, first_frames + latter_frames, self.context_tokens, self.output_dim
            )
        )


def group_audio(context, vae_scale):
    if context.ndim != 5 or context.shape[2] != 5 or (context.shape[1] - 1) % vae_scale:
        raise ValueError("Expected B,(1+N*vae_scale),5,blocks,channels audio")
    (b, length, window, blocks, channels) = context.shape
    latter = context[:, 1:].reshape(
        b, (length - 1) // vae_scale, vae_scale, window, blocks, channels
    )
    n = latter.shape[1]
    pieces = [latter[:, :, :1, :3], latter[:, :, 1:-1, 2:3], latter[:, :, -1:, 2:]]
    return (
        context[:, :1],
        mx.concatenate(
            [part.reshape(b, n, -1, blocks, channels) for part in pieces], axis=2
        ),
    )


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
