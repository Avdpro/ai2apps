"""Native MLX Ex-Omni teacher DiT and Qwen speech-token conditioning.

Only the published offline teacher path is implemented here. Causal streaming
and the language/speech generation stages have separate acceptance gates.
"""

import math

import mlx.core as mx
import mlx.nn as nn

from .primitives import (
    MLP,
    CrossAttention,
    Head,
    SelfAttention,
    timestep_embedding,
)
from .primitives import (
    convert_weights as _convert,
)


class AudioPack(nn.Module):
    def __init__(self, in_channels, patch_size, dim, layernorm=False):
        super().__init__()
        self.patch_size = (
            (patch_size,) * 3 if isinstance(patch_size, int) else tuple(patch_size)
        )
        self.proj = nn.Linear(in_channels * math.prod(self.patch_size), dim)
        self.norm_out = nn.LayerNorm(dim) if layernorm else nn.Identity()

    def __call__(self, x):
        b, c, f, h, w = x.shape
        t, p, q = self.patch_size
        if f % t or h % p or w % q:
            raise ValueError("AudioPack dimensions must divide patch size")
        x = (
            x.reshape(b, c, f // t, t, h // p, p, w // q, q)
            .transpose(0, 2, 4, 6, 3, 5, 7, 1)
            .reshape(b, f // t, h // p, w // q, -1)
        )
        return self.norm_out(self.proj(x))


def embed_speech_tokens(tokens, codebooks):
    count = codebooks.shape[0]
    if tokens.ndim == 1:
        tokens = tokens[:, None]
    if tokens.ndim != 2:
        raise ValueError("Speech tokens must have two dimensions")
    if tokens.shape[0] == count and tokens.shape[1] != count:
        tokens = tokens.T
    if tokens.shape[1] < count:
        raise ValueError("Insufficient speech codebooks")
    tokens = mx.clip(tokens[:, :count].astype(mx.int32), 0, codebooks.shape[1] - 1)
    return mx.sum(mx.stack([codebooks[i, tokens[:, i]] for i in range(count)]), axis=0)


def prepare_audio_condition(audio, pack, projections):
    if audio is None:
        return None
    audio = audio.transpose(0, 2, 1)[:, :, :, None, None]
    audio = mx.concatenate([mx.repeat(audio[:, :, :1], 3, axis=2), audio], axis=2)
    audio = pack(audio)
    return mx.stack([proj(audio) for proj in projections], axis=1)


class Block(nn.Module):
    def __init__(self, has_image_input, dim, heads, ffn_dim, eps):
        super().__init__()
        self.self_attn = SelfAttention(dim, heads, eps)
        self.cross_attn = CrossAttention(dim, heads, eps, has_image_input)
        self.norm1 = nn.LayerNorm(dim, eps=eps, affine=False)
        self.norm2 = nn.LayerNorm(dim, eps=eps, affine=False)
        self.norm3 = nn.LayerNorm(dim, eps=eps)
        self.ffn = nn.Sequential(
            nn.Linear(dim, ffn_dim), nn.GELU(approx="tanh"), nn.Linear(ffn_dim, dim)
        )
        self.modulation = mx.zeros((1, 6, dim))

    def __call__(self, x, context, t_mod, grid):
        a, b, c, d, e, f = mx.split(
            self.modulation.astype(t_mod.dtype) + t_mod, 6, axis=1
        )
        x = x + self.self_attn(self.norm1(x) * (1 + b) + a, grid) * c
        x = x + self.cross_attn(self.norm3(x), context)
        return x + self.ffn(self.norm2(x) * (1 + e) + d) * f


class WanModel(nn.Module):
    def __init__(
        self,
        dim,
        in_dim,
        ffn_dim,
        out_dim,
        text_dim,
        freq_dim,
        eps,
        patch_size,
        num_heads,
        num_layers,
        has_image_input,
        audio_hidden_size=32,
        use_audio=True,
        audio_input_dim=10752,
        speech_embedding_dim=None,
    ):
        super().__init__()
        self.dim = dim
        self.out_dim = out_dim
        self.freq_dim = freq_dim
        self.patch_size = tuple(patch_size)
        self.use_audio = use_audio
        if use_audio and self.patch_size != (1, 2, 2):
            raise ValueError("Teacher audio injection expects spatial 2x2 patches")
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
            Block(has_image_input, dim, num_heads, ffn_dim, eps)
            for _ in range(num_layers)
        ]
        self.head = Head(dim, out_dim, patch_size, eps)
        if has_image_input:
            self.img_emb = MLP(1280, dim)
        if use_audio:
            if num_layers < 4:
                raise ValueError("Audio-conditioned teacher needs at least four layers")
            self.audio_proj = AudioPack(
                audio_input_dim, (4, 1, 1), audio_hidden_size, True
            )
            self.audio_cond_projs = [
                nn.Linear(audio_hidden_size, dim) for _ in range(num_layers // 2 - 1)
            ]
        if speech_embedding_dim is not None:
            self.speech_token_adapter = nn.Sequential(
                nn.LayerNorm(speech_embedding_dim),
                nn.Linear(speech_embedding_dim, audio_input_dim),
            )

    def __call__(
        self, x, timestep, context, y, *, audio_emb=None, prepared_audio_condition=None
    ):
        t = self.time_embedding(timestep_embedding(self.freq_dim, timestep))
        mod = self.time_projection(t).reshape(-1, 6, self.dim)
        context = self.text_embedding(context)
        if self.use_audio:
            audio = (
                prepared_audio_condition
                if prepared_audio_condition is not None
                else prepare_audio_condition(
                    audio_emb, self.audio_proj, self.audio_cond_projs
                )
            )
        else:
            audio = None
        value = self.patch_embedding(
            mx.concatenate([x, y], axis=1).transpose(0, 2, 3, 4, 1)
        )
        grid = value.shape[1:4]
        b = value.shape[0]
        value = value.reshape(b, -1, self.dim)
        for i, block in enumerate(self.blocks):
            if audio is not None and 1 < i <= len(self.blocks) // 2:
                cond = audio[:, i - 2]
                if cond.shape[1] != grid[0]:
                    raise ValueError("Speech/video frame mismatch")
                value = value + mx.broadcast_to(cond, (b, *grid, self.dim)).reshape(
                    b, -1, self.dim
                )
            value = block(value, context, mod, grid)
        value = self.head(value, t)
        f, h, w = grid
        pt, ph, pw = self.patch_size
        return (
            value.reshape(b, f, h, w, pt, ph, pw, self.out_dim)
            .transpose(0, 7, 1, 4, 2, 5, 3, 6)
            .reshape(b, self.out_dim, f * pt, h * ph, w * pw)
        )


def convert_weights(state):
    state = {
        k.replace("speech_token_adapter.", "speech_token_adapter.layers."): v
        for k, v in state.items()
    }
    return _convert(state)
