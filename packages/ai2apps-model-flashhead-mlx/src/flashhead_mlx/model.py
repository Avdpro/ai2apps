"""Single-device MLX port of SoulX-FlashHead's WanModelAudioProject.

Source: Soul-AILab/SoulX-FlashHead, Apache-2.0. BCTHW public latents;
MLX convolution uses BTHWC internally. Distributed training is intentionally absent.
"""

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
    b, length, heads, width = x.shape
    f, h, w = map(int, grid)
    if length != f * h * w or width % 2:
        raise ValueError("RoPE requires an unpadded three-dimensional token grid")
    # Upstream precomputes float64 phases before multiplying complex pairs.
    widths = [width - 2 * (width // 3), width // 3, width // 3]
    phases = []
    for axis, (size, dim) in enumerate(zip((f, h, w), widths)):
        freq = 10000.0 ** (-np.arange(0, dim, 2, dtype=np.float64)[: dim // 2] / dim)
        shape = [1, 1, 1, dim // 2]
        shape[axis] = size
        phase = (np.arange(size)[:, None] * freq).reshape(shape)
        phases.append(np.broadcast_to(phase, (f, h, w, dim // 2)))
    phase = np.concatenate(phases, axis=-1).reshape(1, length, 1, width // 2)
    cos, sin = (
        mx.array(np.cos(phase).astype(np.float32)),
        mx.array(np.sin(phase).astype(np.float32)),
    )
    pairs = x.astype(mx.float32).reshape(b, length, heads, width // 2, 2)
    real, imag = pairs[..., 0], pairs[..., 1]
    return (
        mx.stack([real * cos - imag * sin, real * sin + imag * cos], axis=-1)
        .reshape(x.shape)
        .astype(x.dtype)
    )


def attention(q, k, v, heads):
    b, length, dim = q.shape
    q = q.reshape(b, length, heads, dim // heads).transpose(0, 2, 1, 3)
    k = k.reshape(b, -1, heads, dim // heads).transpose(0, 2, 1, 3)
    v = v.reshape(b, -1, heads, dim // heads).transpose(0, 2, 1, 3)
    value = mx.fast.scaled_dot_product_attention(q, k, v, scale=(dim // heads) ** -0.5)
    return value.transpose(0, 2, 1, 3).reshape(b, length, dim)


class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-6):
        super().__init__()
        self.weight = mx.ones((dim,))
        self.eps = eps

    def __call__(self, x):
        value = x.astype(mx.float32)
        return (
            value * mx.rsqrt(mx.mean(value * value, axis=-1, keepdims=True) + self.eps)
        ).astype(x.dtype) * self.weight


class SelfAttention(nn.Module):
    def __init__(self, dim, num_heads, eps=1e-6):
        super().__init__()
        self.num_heads = num_heads
        self.q, self.k, self.v, self.o = [nn.Linear(dim, dim) for _ in range(4)]
        self.norm_q, self.norm_k = RMSNorm(dim, eps), RMSNorm(dim, eps)

    def __call__(self, x, grid):
        shape = (*x.shape[:2], self.num_heads, x.shape[-1] // self.num_heads)
        q = apply_rope(self.norm_q(self.q(x)).reshape(shape), grid).reshape(x.shape)
        k = apply_rope(self.norm_k(self.k(x)).reshape(shape), grid).reshape(x.shape)
        return self.o(attention(q, k, self.v(x), self.num_heads))


class CrossAttention(nn.Module):
    def __init__(self, dim, num_heads, eps=1e-6, has_image_input=False):
        super().__init__()
        self.num_heads, self.has_image_input = num_heads, has_image_input
        self.q, self.k, self.v, self.o = [nn.Linear(dim, dim) for _ in range(4)]
        self.norm_q, self.norm_k = RMSNorm(dim, eps), RMSNorm(dim, eps)
        if has_image_input:
            self.k_img, self.v_img = nn.Linear(dim, dim), nn.Linear(dim, dim)
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


class DiTAudioBlock(nn.Module):
    def __init__(self, has_image_input, dim, num_heads, ffn_dim, eps=1e-6):
        super().__init__()
        self.self_attn = SelfAttention(dim, num_heads, eps)
        self.cross_attn = CrossAttention(dim, num_heads, eps, has_image_input)
        self.norm1, self.norm2 = [
            nn.LayerNorm(dim, eps=eps, affine=False) for _ in range(2)
        ]
        self.norm3 = nn.LayerNorm(dim, eps=eps)
        self.ffn = nn.Sequential(
            nn.Linear(dim, ffn_dim), nn.GELU(approx="tanh"), nn.Linear(ffn_dim, dim)
        )
        self.modulation = mx.zeros((1, 6, dim))

    def __call__(self, x, context, t_mod, grid):
        e = mx.split(self.modulation.astype(t_mod.dtype) + t_mod, 6, axis=1)
        x = x + self.self_attn(self.norm1(x) * (1 + e[1]) + e[0], grid) * e[2]
        b, frames, tokens, channels = context.shape
        if x.shape[1] % frames:
            raise ValueError("Audio frames must divide video tokens")
        query = self.norm3(x).reshape(b * frames, -1, channels)
        x = x + self.cross_attn(
            query, context.reshape(b * frames, tokens, channels)
        ).reshape(x.shape)
        return x + self.ffn(self.norm2(x) * (1 + e[4]) + e[3]) * e[5]


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
        self.context_tokens, self.output_dim = context_tokens, output_dim
        self.proj1 = nn.Linear(seq_len * blocks * channels, intermediate_dim)
        self.proj1_vf = nn.Linear(seq_len_vf * blocks * channels, intermediate_dim)
        self.proj2 = nn.Linear(intermediate_dim, intermediate_dim)
        self.proj3 = nn.Linear(intermediate_dim, context_tokens * output_dim)
        self.norm = nn.LayerNorm(output_dim) if norm_output_audio else nn.Identity()

    def __call__(self, first, latter):
        b, first_frames = first.shape[:2]
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
    b, length, window, blocks, channels = context.shape
    latter = context[:, 1:].reshape(
        b, (length - 1) // vae_scale, vae_scale, window, blocks, channels
    )
    n = latter.shape[1]
    pieces = [latter[:, :, :1, :3], latter[:, :, 1:-1, 2:3], latter[:, :, -1:, 2:]]
    return context[:, :1], mx.concatenate(
        [part.reshape(b, n, -1, blocks, channels) for part in pieces], axis=2
    )


class Head(nn.Module):
    def __init__(self, dim, out_dim, patch_size, eps):
        super().__init__()
        self.norm = nn.LayerNorm(dim, eps=eps, affine=False)
        self.head = nn.Linear(dim, out_dim * math.prod(patch_size))
        self.modulation = mx.zeros((1, 2, dim))

    def __call__(self, x, timestep):
        b, length, dim = x.shape
        frames = timestep.shape[0] // b
        mod = self.modulation.astype(timestep.dtype)[:, None] + timestep.reshape(
            b, frames, 1, dim
        )
        shift, scale = mx.split(mod, 2, axis=2)
        value = (
            self.norm(x.reshape(b, frames, length // frames, dim)) * (1 + scale) + shift
        )
        return self.head(value).reshape(b, length, -1)


class WanModelAudioProject(nn.Module):
    def __init__(
        self,
        *,
        dim,
        in_dim,
        ffn_dim,
        out_dim,
        text_dim,
        freq_dim,
        eps,
        vae_stride,
        patch_size,
        num_heads,
        num_layers,
        has_image_input,
        **kwargs,
    ):
        super().__init__()
        self.dim, self.freq_dim, self.out_dim = dim, freq_dim, out_dim
        self.patch_size, self.vae_scale = tuple(patch_size), vae_stride[0]
        self.patch_embedding = nn.Conv3d(
            in_dim, dim, kernel_size=self.patch_size, stride=self.patch_size
        )
        self.text_embedding = nn.Sequential(
            nn.Linear(text_dim, dim), nn.GELU(approx="tanh"), nn.Linear(dim, dim)
        )
        self.time_embedding = nn.Sequential(
            nn.Linear(freq_dim, dim), nn.SiLU(), nn.Linear(dim, dim)
        )
        self.time_projection = nn.Sequential(nn.SiLU(), nn.Linear(dim, dim * 6))
        self.blocks = [
            DiTAudioBlock(has_image_input, dim, num_heads, ffn_dim, eps)
            for _ in range(num_layers)
        ]
        self.head = Head(dim, out_dim, self.patch_size, eps)
        self.audio_emb = MLP(768, dim)
        if has_image_input:
            self.img_emb = MLP(1280, dim)
        self.audio_proj = AudioProjModel(
            seq_len_vf=5 + self.vae_scale - 1, output_dim=dim
        )

    def __call__(self, x, timestep, context, y):
        if x.shape[0] != 1 or y.shape != x.shape or timestep.size != 1:
            raise ValueError(
                "FlashHead inference expects one clip, matching reference latents and one timestep"
            )
        value = mx.concatenate([x, y], axis=1).transpose(0, 2, 3, 4, 1)
        value = self.patch_embedding(value)
        grid = value.shape[1:4]
        value = value.reshape(1, -1, self.dim)
        t = self.time_embedding(
            timestep_embedding(self.freq_dim, timestep.astype(value.dtype))
        )
        t_mod = self.time_projection(t).reshape(-1, 6, self.dim)
        first, latter = group_audio(context.astype(value.dtype), self.vae_scale)
        audio = self.audio_proj(first, latter).astype(value.dtype)
        if audio.shape[1] != grid[0]:
            raise ValueError("Audio and latent temporal dimensions differ")
        for block in self.blocks:
            value = block(value, audio, t_mod, grid)
        value = self.head(value, t)
        f, h, w = grid
        pt, ph, pw = self.patch_size
        return (
            value.reshape(1, f, h, w, pt, ph, pw, self.out_dim)
            .transpose(0, 7, 1, 4, 2, 5, 3, 6)
            .reshape(1, self.out_dim, f * pt, h * ph, w * pw)
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
