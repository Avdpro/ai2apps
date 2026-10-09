"""YuE2 AR/NAR MLX port of upstream 3d21f8f (Apache-2.0).

Checkpoint names and BF16 rounding boundaries match the released architecture.
Single-request inference, unpadded sequences; KV state is caller-owned.
"""

import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import mlx.core as mx
import mlx.nn as nn


def silu_kernel(x):
    f = x.astype(mx.float32)
    return (f * mx.sigmoid(f)).astype(x.dtype)


def norm_kernel(x, weight, eps):
    return (
        x
        * mx.rsqrt(
            mx.mean(x.astype(mx.float32) ** 2, axis=-1, keepdims=True) + eps
        ).astype(x.dtype)
        * weight
    )


def rotary_kernel(x, c, s):
    half = x.shape[-1] // 2
    a, b = x[..., :half], x[..., half:]
    return mx.concatenate([a * c - b * s, b * c + a * s], axis=-1)


# Opt-in: fusion passes FP32 parity but can change BF16 rounding and samples.
# The default preserves the baseline's arithmetic boundaries.
KERNEL_MODE = os.environ.get("YUE2_KERNEL_MODE", "exact")
if KERNEL_MODE not in {"exact", "compiled"}:
    raise ValueError("YUE2_KERNEL_MODE must be exact or compiled")
if KERNEL_MODE == "compiled":
    silu_kernel = mx.compile(silu_kernel)
    norm_kernel = mx.compile(norm_kernel)
    rotary_kernel = mx.compile(rotary_kernel)


class SiLU(nn.Module):
    def __call__(self, x):
        return silu_kernel(x)


class RMSNorm(nn.Module):
    def __init__(self, dim, eps):
        super().__init__()
        self.weight = mx.ones(dim)
        self.eps = eps

    def __call__(self, x):
        return norm_kernel(x, self.weight, self.eps)


class KVCache:
    def __init__(self):
        self.keys = self.values = None
        self.offset = 0

    def update(self, k, v):
        end = self.offset + k.shape[2]
        if self.keys is None or end > self.keys.shape[2]:
            size = ((end + 255) // 256) * 256
            shape = (*k.shape[:2], size, k.shape[3])
            keys = mx.zeros(shape, k.dtype)
            values = mx.zeros(shape, v.dtype)
            if self.offset:
                keys[:, :, : self.offset] = self.keys[:, :, : self.offset]
                values[:, :, : self.offset] = self.values[:, :, : self.offset]
            self.keys, self.values = keys, values
        self.keys[:, :, self.offset : end] = k
        self.values[:, :, self.offset : end] = v
        self.offset = end
        return self.keys[:, :, :end], self.values[:, :, :end]


def rope_factors(positions, dim, theta, dtype):
    inv = 1 / (theta ** (mx.arange(dim // 2, dtype=mx.float32) * 2 / dim))
    angles = positions.astype(mx.float32)[..., None] * inv
    return mx.cos(angles)[:, :, None, :].astype(dtype), mx.sin(angles)[
        :, :, None, :
    ].astype(dtype)


def rotary(x, positions, theta):
    c, s = (
        positions
        if isinstance(positions, tuple)
        else rope_factors(positions, x.shape[-1], theta, x.dtype)
    )
    return rotary_kernel(x, c, s)


class Attention(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.heads = c.num_attention_heads
        self.kv_heads = c.num_key_value_heads
        self.dim = c.head_dim
        self.theta = c.rope_theta
        self.q_proj = nn.Linear(c.hidden_size, self.heads * self.dim, bias=False)
        self.k_proj = nn.Linear(c.hidden_size, self.kv_heads * self.dim, bias=False)
        self.v_proj = nn.Linear(c.hidden_size, self.kv_heads * self.dim, bias=False)
        self.o_proj = nn.Linear(self.heads * self.dim, c.hidden_size, bias=False)
        self.q_norm = RMSNorm(self.dim, c.rms_norm_eps)
        self.k_norm = RMSNorm(self.dim, c.rms_norm_eps)

    def project(self, x, positions):
        b, t, _ = x.shape
        q = self.q_norm(self.q_proj(x).reshape(b, t, self.heads, self.dim))
        k = self.k_norm(self.k_proj(x).reshape(b, t, self.kv_heads, self.dim))
        v = self.v_proj(x).reshape(b, t, self.kv_heads, self.dim)
        return (
            rotary(q, positions, self.theta).transpose(0, 2, 1, 3),
            rotary(k, positions, self.theta).transpose(0, 2, 1, 3),
            v.transpose(0, 2, 1, 3),
        )

    def attend(self, q, k, v, mask=None):
        out = mx.fast.scaled_dot_product_attention(
            q, k, v, scale=self.dim**-0.5, mask=mask
        )
        return out.transpose(0, 2, 1, 3).reshape(q.shape[0], q.shape[2], -1)


class MLP(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.gate_proj = nn.Linear(c.hidden_size, c.intermediate_size, bias=False)
        self.up_proj = nn.Linear(c.hidden_size, c.intermediate_size, bias=False)
        self.down_proj = nn.Linear(c.intermediate_size, c.hidden_size, bias=False)

    def __call__(self, x):
        return self.down_proj(SiLU()(self.gate_proj(x)) * self.up_proj(x))


class Layer(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.input_layernorm = RMSNorm(c.hidden_size, c.rms_norm_eps)
        self.post_attention_layernorm = RMSNorm(c.hidden_size, c.rms_norm_eps)
        self.nar_input_layernorm = RMSNorm(c.hidden_size, c.rms_norm_eps)
        self.nar_pre_mlp_layernorm = RMSNorm(c.hidden_size, c.rms_norm_eps)
        self.self_attn = Attention(c)
        self.nar_self_attn = Attention(c)
        self.mlp = MLP(c)
        self.nar_mlp = MLP(c)

    def ar(self, x, positions, cache=None):
        q, k, v = self.self_attn.project(self.input_layernorm(x), positions)
        offset = cache.offset if cache else 0
        if cache:
            k, v = cache.update(k, v)
        mask = None
        if x.shape[1] > 1:
            mask = (
                "causal"
                if offset == 0
                else mx.arange(k.shape[2])[None, :]
                <= (mx.arange(x.shape[1]) + offset)[:, None]
            )
        x = x + self.self_attn.o_proj(self.self_attn.attend(q, k, v, mask))
        return x + self.mlp(self.post_attention_layernorm(x))


class Backbone(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.embed_tokens = nn.Embedding(c.vocab_size, c.hidden_size)
        self.layers = [Layer(c) for _ in range(c.num_hidden_layers)]
        self.norm = RMSNorm(c.hidden_size, c.rms_norm_eps)


class TimeEmbedder(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.mlp = [
            nn.Linear(256, c.hidden_size),
            SiLU(),
            nn.Linear(c.hidden_size, c.hidden_size),
        ]

    def __call__(self, t):
        args = t.astype(mx.float32)[..., None] * mx.exp(
            -math.log(10000) * mx.arange(128, dtype=mx.float32) / 128
        )
        x = mx.concatenate([mx.cos(args), mx.sin(args)], axis=-1).astype(
            self.mlp[0].weight.dtype
        )
        for f in self.mlp:
            x = f(x)
        return x


class PositionEmbedding(nn.Module):
    def __init__(self, c):
        super().__init__()
        angle = mx.arange(c.max_latent_frames, dtype=mx.float32)[:, None] * mx.exp(
            mx.arange(0, c.hidden_size, 2, dtype=mx.float32)
            * (-math.log(10000) / c.hidden_size)
        )
        self.pe = mx.stack([mx.sin(angle), mx.cos(angle)], axis=-1).reshape(
            c.max_latent_frames, c.hidden_size
        )


class Model(nn.Module):
    def __init__(self, config):
        super().__init__()
        c = SimpleNamespace(**config)
        self.config = c
        self._phase = "all"
        self._path = None
        self._dtype = None
        self.model = Backbone(c)
        self.lm_head = nn.Linear(c.hidden_size, c.vocab_size, bias=False)
        self.vae2llm = nn.Linear(c.latent_dim, c.hidden_size)
        self.llm2vae = nn.Linear(c.hidden_size, c.latent_dim)
        self.time_embedder = TimeEmbedder(c)
        self.latent_pos_embed = PositionEmbedding(c)

    def cache(self):
        return [KVCache() for _ in self.model.layers]

    def __call__(self, ids, cache=None, last_only=True, output_range=None):
        offset = cache[0].offset if cache else 0
        pos = mx.arange(offset, offset + ids.shape[1])[None]
        x = self.model.embed_tokens(ids)
        pos = rope_factors(pos, self.config.head_dim, self.config.rope_theta, x.dtype)
        for i, layer in enumerate(self.model.layers):
            x = layer.ar(x, pos, cache[i] if cache else None)
        x = self.model.norm(x)
        x = x[:, -1:] if last_only else x
        if output_range is not None:
            start, end = output_range
            return x @ self.lm_head.weight[start:end].T
        return self.lm_head(x)

    def _prune(self, phase):
        if phase not in {"all", "ar", "nar"}:
            raise ValueError("Unknown weight phase")
        if phase == "ar":
            for name in ("vae2llm", "llm2vae", "time_embedder", "latent_pos_embed"):
                if name in self:
                    del self[name]
            for layer in self.model.layers:
                for name in (
                    "nar_input_layernorm",
                    "nar_pre_mlp_layernorm",
                    "nar_self_attn",
                    "nar_mlp",
                ):
                    if name in layer:
                        del layer[name]
        elif phase == "nar":
            if "lm_head" in self:
                del self["lm_head"]
            if "embed_tokens" in self.model:
                del self.model["embed_tokens"]
            for layer in self.model.layers:
                for name in (
                    "input_layernorm",
                    "post_attention_layernorm",
                    "self_attn",
                    "mlp",
                ):
                    if name in layer:
                        del layer[name]
        self._phase = phase

    def _read_weights(self):
        from mlx.utils import tree_flatten

        expected = {k for k, _ in tree_flatten(self.parameters())}
        weights = {}
        for file in sorted(self._path.glob("*.safetensors")):
            for key, value in mx.load(str(file)).items():
                if key not in expected:
                    if self._phase == "all":
                        raise ValueError("Unexpected tensor " + key)
                    continue
                if key in weights:
                    raise ValueError("Duplicate tensor " + key)
                weights[key] = value.astype(self._dtype)
        self.load_weights(list(weights.items()), strict=True)
        mx.eval(self.parameters())

    def activate(self, phase):
        """Replace phase weights in-place so no caller retains the inactive bank.

        The evaluated AR prefix KV survives the transition. All weights are read
        unchanged from the pinned local safetensors; no offload conversion/cache.
        """
        if self._phase in {"all", phase}:
            return
        if self._path is None:
            raise RuntimeError("Phase switching needs a pinned checkpoint")
        self._prune(phase)  # Release inactive weights BEFORE allocating replacements.
        mx.clear_cache()
        c = self.config
        if phase == "ar":
            self.model.embed_tokens = nn.Embedding(c.vocab_size, c.hidden_size)
            self.lm_head = nn.Linear(c.hidden_size, c.vocab_size, bias=False)
            names = ("input_layernorm", "post_attention_layernorm", "self_attn", "mlp")
        else:
            self.vae2llm = nn.Linear(c.latent_dim, c.hidden_size)
            self.llm2vae = nn.Linear(c.hidden_size, c.latent_dim)
            self.time_embedder = TimeEmbedder(c)
            self.latent_pos_embed = PositionEmbedding(c)
            names = (
                "nar_input_layernorm",
                "nar_pre_mlp_layernorm",
                "nar_self_attn",
                "nar_mlp",
            )
        for layer in self.model.layers:
            fresh = Layer(c)
            for name in names:
                layer[name] = fresh[name]
        self._read_weights()
        mx.clear_cache()

    @classmethod
    def load(cls, path, dtype=mx.bfloat16, phase="all"):
        path = Path(path)
        config = json.loads((path / "config.json").read_text())
        model = cls(config)
        model._path, model._dtype = path, dtype
        model._prune(phase)
        model._read_weights()
        return model
