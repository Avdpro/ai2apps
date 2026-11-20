"""Native, exact-attention InfiniteTalk DiT; single-device, one video batch.

Based on the pinned MeiGen-AI/InfiniteTalk implementation. Supports one or two
speakers. No distributed execution, TeaCache or approximate attention.
"""

import math

import mlx.core as mx
import mlx.nn as nn
import numpy as np

from .primitives import (
    MLP,
    AudioProjModel,
    RMSNorm,
    attention,
    group_audio,
    timestep_embedding,
)
from .primitives import (
    convert_weights as convert_weights,
)


def rope(x, grid):
    b, n, h, d = x.shape
    if n != math.prod(grid) or d % 2:
        raise ValueError("Invalid video token grid")
    widths = (d - 4 * (d // 6), 2 * (d // 6), 2 * (d // 6))
    phases = []
    for axis, (size, width) in enumerate(zip(grid, widths)):
        freq = 10000.0 ** (-np.arange(0, width, 2, dtype=np.float64) / width)
        shape = [1, 1, 1, width // 2]
        shape[axis] = size
        phases.append(
            np.broadcast_to(
                (np.arange(size)[:, None] * freq).reshape(shape), (*grid, width // 2)
            )
        )
    phase = np.concatenate(phases, axis=-1).reshape(1, n, 1, d // 2)
    c, s = (
        mx.array(np.cos(phase).astype("float32")),
        mx.array(np.sin(phase).astype("float32")),
    )
    z = x.astype(mx.float32).reshape(b, n, h, d // 2, 2)
    return (
        mx.stack(
            [z[..., 0] * c - z[..., 1] * s, z[..., 0] * s + z[..., 1] * c], axis=-1
        )
        .reshape(x.shape)
        .astype(x.dtype)
    )


def rope1d(x, positions):
    d = x.shape[-1]
    phase = (
        positions.astype(mx.float32)[:, None]
        * mx.exp(-math.log(10000) * mx.arange(0, d, 2) / d)[None]
    )
    c, s = mx.cos(phase)[None, None], mx.sin(phase)[None, None]
    z = x.astype(mx.float32).reshape(*x.shape[:-1], d // 2, 2)
    return (
        mx.stack(
            [z[..., 0] * c - z[..., 1] * s, z[..., 0] * s + z[..., 1] * c], axis=-1
        )
        .reshape(x.shape)
        .astype(x.dtype)
    )


def reference_attention(q, k, grid, masks):
    if masks.ndim != 2 or masks.shape[1] != grid[1] * grid[2]:
        raise ValueError("Expected token-space reference masks")
    if bool(mx.any(mx.sum(masks, axis=1) == 0).item()):
        raise ValueError("Reference masks must be nonempty")
    # Process one head at a time to bound the reference map allocation.
    k = k[:, : grid[1] * grid[2]]
    result = mx.zeros((masks.shape[0], q.shape[1]), dtype=q.dtype)
    for head in range(q.shape[2]):
        scores = mx.softmax(
            (q[:, :, head] * q.shape[-1] ** -0.5) @ k[:, :, head].transpose(0, 2, 1),
            axis=-1,
        )
        result = result + (scores[0] @ masks.T / mx.sum(masks, axis=1)[None]).T
    return result / q.shape[2]


class SelfAttention(nn.Module):
    def __init__(self, dim, num_heads, qk_norm=True, eps=1e-6):
        super().__init__()
        self.heads = num_heads
        self.q, self.k, self.v, self.o = [nn.Linear(dim, dim) for _ in range(4)]
        self.norm_q = RMSNorm(dim, eps) if qk_norm else nn.Identity()
        self.norm_k = RMSNorm(dim, eps) if qk_norm else nn.Identity()

    def __call__(self, x, grid, masks=None):
        shape = (*x.shape[:2], self.heads, x.shape[-1] // self.heads)
        q = rope(self.norm_q(self.q(x)).reshape(shape), grid)
        k = rope(self.norm_k(self.k(x)).reshape(shape), grid)
        out = self.o(
            attention(q.reshape(x.shape), k.reshape(x.shape), self.v(x), self.heads)
        )
        return out, reference_attention(
            q, k, grid, masks
        ) if masks is not None else None


class CrossAttention(nn.Module):
    def __init__(self, dim, num_heads, qk_norm=True, eps=1e-6):
        super().__init__()
        self.heads = num_heads
        self.q, self.k, self.v, self.o, self.k_img, self.v_img = [
            nn.Linear(dim, dim) for _ in range(6)
        ]
        self.norm_q = RMSNorm(dim, eps) if qk_norm else nn.Identity()
        self.norm_k = RMSNorm(dim, eps) if qk_norm else nn.Identity()
        self.norm_k_img = RMSNorm(dim, eps) if qk_norm else nn.Identity()

    def __call__(self, x, context):
        image, text = context[:, :257], context[:, 257:]
        q = self.norm_q(self.q(x))
        return self.o(
            attention(q, self.norm_k(self.k(text)), self.v(text), self.heads)
            + attention(
                q, self.norm_k_img(self.k_img(image)), self.v_img(image), self.heads
            )
        )


class AudioAttention(nn.Module):
    def __init__(self, dim, audio_dim, num_heads):
        super().__init__()
        self.heads = num_heads
        self.q_linear = nn.Linear(dim, dim)
        self.kv_linear = nn.Linear(audio_dim, dim * 2)
        self.proj = nn.Linear(dim, dim)

    def __call__(self, x, audio, grid, ref_map=None, speakers=1):
        frames = grid[0]
        b, n, c = x.shape
        spatial = n // frames
        d = c // self.heads
        q = (
            self.q_linear(x)
            .reshape(b, frames, spatial, self.heads, d)
            .transpose(0, 1, 3, 2, 4)
            .reshape(b * frames, self.heads, spatial, d)
        )
        kv = (
            self.kv_linear(audio)
            .reshape(b * frames, audio.shape[2], 2, self.heads, d)
            .transpose(2, 0, 3, 1, 4)
        )
        k, v = kv[0], kv[1]
        if speakers == 2:
            if ref_map is None or ref_map.shape[0] != 3:
                raise ValueError(
                    "Two-speaker inference requires two person masks and a background mask"
                )
            pos = []
            for i, start in [(0, 0), (1, 20)]:
                a = ref_map[i]
                pos.append((a - mx.min(a)) / (mx.max(a) - mx.min(a) + 1e-8) * 4 + start)
            pos = mx.stack([*pos, mx.full((n,), 12, dtype=ref_map.dtype)], axis=-1)
            selected = mx.take_along_axis(
                pos, mx.argmax(ref_map, axis=0)[:, None], axis=1
            )[:, 0]
            q = rope1d(
                q.reshape(b, frames, self.heads, spatial, d)
                .transpose(0, 2, 1, 3, 4)
                .reshape(b, self.heads, n, d),
                selected,
            )
            q = (
                q.reshape(b, self.heads, frames, spatial, d)
                .transpose(0, 2, 1, 3, 4)
                .reshape(b * frames, self.heads, spatial, d)
            )
            tokens = k.shape[2]
            keypos = mx.tile(
                mx.concatenate(
                    [mx.full((tokens // 2,), 2), mx.full((tokens // 2,), 22)]
                ),
                frames,
            )
            k = rope1d(
                k.reshape(b, frames, self.heads, tokens, d)
                .transpose(0, 2, 1, 3, 4)
                .reshape(b, self.heads, frames * tokens, d),
                keypos,
            )
            k = (
                k.reshape(b, self.heads, frames, tokens, d)
                .transpose(0, 2, 1, 3, 4)
                .reshape(b * frames, self.heads, tokens, d)
            )
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=d**-0.5)
        return self.proj(out.transpose(0, 2, 1, 3).reshape(b, n, c))


class Block(nn.Module):
    def __init__(
        self,
        dim,
        ffn_dim,
        heads,
        output_dim,
        eps,
        qk_norm,
        cross_attn_norm,
        norm_input_visual,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim, eps=eps, affine=False)
        self.norm2 = nn.LayerNorm(dim, eps=eps, affine=False)
        self.norm3 = nn.LayerNorm(dim, eps=eps) if cross_attn_norm else nn.Identity()
        self.norm_x = nn.LayerNorm(dim, eps=eps) if norm_input_visual else nn.Identity()
        self.self_attn = SelfAttention(dim, heads, qk_norm, eps)
        self.cross_attn = CrossAttention(dim, heads, qk_norm, eps)
        self.audio_cross_attn = AudioAttention(dim, output_dim, heads)
        self.ffn = nn.Sequential(
            nn.Linear(dim, ffn_dim), nn.GELU(approx="tanh"), nn.Linear(ffn_dim, dim)
        )
        self.modulation = mx.zeros((1, 6, dim))

    def __call__(self, x, e, grid, context, audio, masks, speakers):
        dtype = x.dtype
        e = mx.split(
            self.modulation.astype(mx.float32) + e.astype(mx.float32), 6, axis=1
        )
        y, ref = self.self_attn(
            (self.norm1(x).astype(mx.float32) * (1 + e[1]) + e[0]).astype(dtype),
            grid,
            masks,
        )
        x = (x + y * e[2]).astype(dtype)
        x = x + self.cross_attn(self.norm3(x), context)
        x = x + self.audio_cross_attn(self.norm_x(x), audio, grid, ref, speakers)
        y = self.ffn(
            (self.norm2(x).astype(mx.float32) * (1 + e[4]) + e[3]).astype(dtype)
        )
        return (x + y * e[5]).astype(dtype)


class Head(nn.Module):
    def __init__(self, dim, out_dim, patch_size, eps):
        super().__init__()
        self.norm = nn.LayerNorm(dim, eps=eps, affine=False)
        self.head = nn.Linear(dim, out_dim * math.prod(patch_size))
        self.modulation = mx.zeros((1, 2, dim))

    def __call__(self, x, e):
        shift, scale = mx.split(self.modulation + e[:, None], 2, axis=1)
        return self.head(self.norm(x) * (1 + scale) + shift)


class WanModel(nn.Module):
    def __init__(
        self,
        model_type="i2v",
        patch_size=(1, 2, 2),
        text_len=512,
        in_dim=36,
        dim=5120,
        ffn_dim=13824,
        freq_dim=256,
        text_dim=4096,
        out_dim=16,
        num_heads=40,
        num_layers=40,
        window_size=(-1, -1),
        qk_norm=True,
        cross_attn_norm=True,
        eps=1e-6,
        audio_window=5,
        intermediate_dim=512,
        output_dim=768,
        context_tokens=32,
        vae_scale=4,
        norm_input_visual=True,
        norm_output_audio=True,
        **kwargs,
    ):
        super().__init__()
        if model_type != "i2v" or tuple(window_size) != (-1, -1) or audio_window != 5:
            raise ValueError("Unsupported InfiniteTalk configuration")
        self.patch_size = tuple(patch_size)
        self.text_len = text_len
        self.dim = dim
        self.freq_dim = freq_dim
        self.out_dim = out_dim
        self.vae_scale = vae_scale
        self.patch_embedding = nn.Conv3d(
            in_dim, dim, kernel_size=patch_size, stride=patch_size
        )
        self.text_embedding = nn.Sequential(
            nn.Linear(text_dim, dim), nn.GELU(approx="tanh"), nn.Linear(dim, dim)
        )
        self.time_embedding = nn.Sequential(
            nn.Linear(freq_dim, dim), nn.SiLU(), nn.Linear(dim, dim)
        )
        self.time_projection = nn.Sequential(nn.SiLU(), nn.Linear(dim, dim * 6))
        self.blocks = [
            Block(
                dim,
                ffn_dim,
                num_heads,
                output_dim,
                eps,
                qk_norm,
                cross_attn_norm,
                norm_input_visual,
            )
            for _ in range(num_layers)
        ]
        self.head = Head(dim, out_dim, patch_size, eps)
        self.img_emb = MLP(1280, dim)
        self.audio_proj = AudioProjModel(
            seq_len_vf=audio_window + vae_scale - 1,
            intermediate_dim=intermediate_dim,
            output_dim=output_dim,
            context_tokens=context_tokens,
            norm_output_audio=norm_output_audio,
        )

    def __call__(self, x, t, context, clip_fea, y, audio, ref_target_masks=None):
        if x.shape[0] != 1 or audio.shape[0] not in (1, 2):
            raise ValueError("Expected one video and one or two audio tracks")
        if context.shape[1] > self.text_len:
            raise ValueError("Text context exceeds configured length")
        value = self.patch_embedding(
            mx.concatenate([x, y], axis=1)
            .astype(context.dtype)
            .transpose(0, 2, 3, 4, 1)
        )
        grid = value.shape[1:4]
        value = value.reshape(1, -1, self.dim)
        e = self.time_embedding(timestep_embedding(self.freq_dim, t.astype(mx.float32)))
        e0 = self.time_projection(e).reshape(1, 6, self.dim)
        context = mx.pad(
            context, [(0, 0), (0, self.text_len - context.shape[1]), (0, 0)]
        )
        context = mx.concatenate(
            [self.img_emb(clip_fea), self.text_embedding(context)], axis=1
        ).astype(value.dtype)
        projected = self.audio_proj(*group_audio(audio, self.vae_scale))
        speakers = audio.shape[0]
        projected = mx.concatenate(
            [projected[i : i + 1] for i in range(speakers)], axis=2
        ).astype(value.dtype)
        if projected.shape[1] != grid[0]:
            raise ValueError("Audio/latent frame mismatch")
        if speakers == 2 and ref_target_masks is None:
            raise ValueError("Two-speaker inference requires reference masks")
        for block in self.blocks:
            value = block(
                value, e0, grid, context, projected, ref_target_masks, speakers
            )
        value = self.head(value, e)
        f, h, w = grid
        pt, ph, pw = self.patch_size
        return (
            value.reshape(1, f, h, w, pt, ph, pw, self.out_dim)
            .transpose(0, 7, 1, 4, 2, 5, 3, 6)
            .reshape(1, self.out_dim, f * pt, h * ph, w * pw)
        )
