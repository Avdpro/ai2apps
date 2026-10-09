"""Cached-AR acoustic midpoint solver; MLX only, matching upstream chunk cuts."""

import math

import mlx.core as mx
import numpy as np

from .model import rope_factors
from .protocol import CODEC_OFFSET, CODEC_SIZE, MUSIC_END, chunk_ranges


class CachedNAR:
    def __init__(self, model, ar_tokens, frames, nar_cond_end=0):
        c = model.config
        if frames < 1 or len(ar_tokens) + frames + 2 > c.max_position_embeddings:
            raise ValueError("Invalid acoustic context")
        self.model = model
        self.frames = frames
        self.length = frames + 2
        self.ar_length = len(ar_tokens)
        self.cache = []
        self.positions = mx.arange(self.ar_length, self.ar_length + self.length)[None]
        x = model.model.embed_tokens(mx.array([ar_tokens]))
        pos = rope_factors(
            mx.arange(len(ar_tokens))[None], c.head_dim, c.rope_theta, x.dtype
        )
        for layer in model.model.layers:
            q, k, v = layer.self_attn.project(layer.input_layernorm(x), pos)
            visible = (
                min(nar_cond_end, len(ar_tokens)) if nar_cond_end else len(ar_tokens)
            )
            self.cache.append((k[:, :, :visible], v[:, :, :visible]))
            x = x + layer.self_attn.o_proj(layer.self_attn.attend(q, k, v, "causal"))
            x = x + layer.mlp(layer.post_attention_layernorm(x))
            mx.eval(x, self.cache[-1])
        del x, q, k, v, layer
        model.activate("nar")
        self.positions = rope_factors(
            self.positions, c.head_dim, c.rope_theta, model.vae2llm.weight.dtype
        )
        self.pos_emb = model.latent_pos_embed.pe[
            mx.minimum(mx.arange(self.length), c.max_latent_frames - 1)
        ][None]
        mx.eval(self.positions, self.pos_emb)

    def velocity(self, state, raw_t):
        m = self.model
        dtype = m.vae2llm.weight.dtype
        x_nar = mx.pad(state.astype(dtype), [(1, 1), (0, 0)])[None]
        t = mx.sigmoid(mx.array(raw_t, dtype))
        s = m.config.timestep_shift
        t = s * t / (1 + (s - 1) * t)
        x = (
            m.vae2llm(x_nar)
            + m.time_embedder(mx.broadcast_to(t, (self.length,)))[None]
            + self.pos_emb
        )
        for layer, (ar_k, ar_v) in zip(m.model.layers, self.cache):
            q, k, v = layer.nar_self_attn.project(
                layer.nar_input_layernorm(x), self.positions
            )
            k = mx.concatenate([ar_k, k], axis=2)
            v = mx.concatenate([ar_v, v], axis=2)
            x = x + layer.nar_self_attn.o_proj(layer.nar_self_attn.attend(q, k, v))
            x = x + layer.nar_mlp(layer.nar_pre_mlp_layernorm(x))
        return m.llm2vae(m.model.norm(x))[0, 1:-1]

    def solve(self, noise, steps=32, cancelled=None, progress=None):
        if type(steps) is not int or steps < 1:
            raise ValueError("steps must be positive")
        state = mx.array(noise).astype(self.model.vae2llm.weight.dtype)
        dt = 1 / steps

        def logit(t):
            return 20.0 if t >= 1 else max(-20.0, min(20.0, math.log(t / (1 - t))))

        for step in range(steps):
            if cancelled and cancelled():
                raise InterruptedError("Cancelled during synthesis")
            t = 1 - step * dt
            first = self.velocity(state, logit(t))
            mid = state - first * (dt / 2)
            mx.async_eval(mid)
            if cancelled and cancelled():
                raise InterruptedError("Cancelled during synthesis")
            state = state - self.velocity(mid, logit(t - dt / 2)) * dt
            mx.eval(state)
            if progress:
                progress(step + 1, steps)
        return state.astype(mx.float32)


def synthesize(
    model, prefix, codec, seed, steps=32, noise=None, cancelled=None, progress=None
):
    if not codec or min(codec) < 0 or max(codec) >= CODEC_SIZE:
        raise ValueError("Invalid semantic tokens")
    # MLX has a different RNG from torch. Explicit noise permits exact-input parity.
    if noise is None:
        noise = mx.random.normal(
            (len(codec), model.config.latent_dim),
            key=mx.array([seed >> 32, seed & 0xFFFFFFFF], dtype=mx.uint32),
        )
    if noise.shape != (len(codec), model.config.latent_dim):
        raise ValueError("Noise shape mismatch")
    if not bool(mx.all(mx.isfinite(mx.array(noise))).item()):
        raise ValueError("Nonfinite noise")
    outputs = []
    ranges = chunk_ranges(len(codec), len(prefix))
    for i, (a, b) in enumerate(ranges):
        if cancelled and cancelled():
            raise InterruptedError("Cancelled before acoustic prefill")
        model.activate("ar")
        engine = CachedNAR(
            model, prefix + [t + CODEC_OFFSET for t in codec[a:b]] + [MUSIC_END], b - a
        )
        callback = (
            (
                lambda done, total, chunk_index=i: progress(
                    chunk_index * total + done, len(ranges) * total
                )
            )
            if progress
            else None
        )
        outputs.append(np.array(engine.solve(noise[a:b], steps, cancelled, callback)))
        del engine
        mx.clear_cache()
    return np.concatenate(outputs)
