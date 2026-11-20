"""MeanFlow head: one audio latent from one LM hidden state.

The head predicts the mean velocity ``u(z, t, h | c, w)`` of the flow from
noise (``t = 0``) to data (``t = 1``) over an interval ``h``; sampling is
``z += h * u``. The guidance scale ``w`` is an input of the network, so a
single forward pass of a small MLP produces a guided latent.

Every layer modulates its input with projections of the same conditioning
vector; they are stacked into one matrix (``ada``) and evaluated once. The
time, interval and guidance embeddings do not depend on the hidden state and
are computed once per ``(steps, guidance)``, together with a compiled sampler.
"""

from __future__ import annotations

import math
from typing import Callable

import mlx.core as mx
import mlx.nn as nn

from ..config import HeadConfig

_FREQUENCY_DIM = 256


def _rms_norm(x: mx.array, eps: float) -> mx.array:
    return mx.fast.rms_norm(x.astype(mx.float32), None, eps).astype(x.dtype)


class ScalarEmbed(nn.Module):
    """Sinusoidal features of a scalar, then a two-layer MLP."""

    def __init__(self, hidden: int):
        super().__init__()
        self.fc1 = nn.Linear(_FREQUENCY_DIM, hidden, bias=False)
        self.fc2 = nn.Linear(hidden, hidden, bias=False)

    def __call__(self, value: float, dtype: mx.Dtype) -> mx.array:
        """A scalar -> ``[1, hidden]``. The scalar is rounded to ``dtype`` first."""
        half = _FREQUENCY_DIM // 2
        freqs = mx.exp(-math.log(10000.0) * mx.arange(half, dtype=mx.float32) / half)
        args = mx.array([value], dtype=dtype).astype(mx.float32)[:, None] * freqs
        features = mx.concatenate([mx.cos(args), mx.sin(args)], axis=-1).astype(dtype)
        return self.fc2(nn.silu(self.fc1(features)))


class FeedForward(nn.Module):
    def __init__(self, hidden: int, ffn: int):
        super().__init__()
        self.gate_proj = nn.Linear(hidden, ffn, bias=False)
        self.up_proj = nn.Linear(hidden, ffn, bias=False)
        self.down_proj = nn.Linear(ffn, hidden, bias=False)

    def __call__(self, x: mx.array) -> mx.array:
        return self.down_proj(nn.silu(self.gate_proj(x)) * self.up_proj(x))


class _Gain(nn.Module):
    def __init__(self, dims: int):
        super().__init__()
        self.weight = mx.ones((dims,))


class HeadLayer(nn.Module):
    def __init__(self, hidden: int, ffn: int, eps: float):
        super().__init__()
        self.norm = _Gain(hidden)
        self.ffn = FeedForward(hidden, ffn)
        self.eps = eps

    def __call__(self, x: mx.array, modulation: mx.array) -> mx.array:
        shift, scale, gate = mx.split(modulation, 3, axis=-1)
        h = _rms_norm(x, self.eps) * self.norm.weight
        return x + gate * self.ffn(h * (1 + scale) + shift)


class FinalLayer(nn.Module):
    def __init__(self, hidden: int, out: int, eps: float):
        super().__init__()
        self.proj = nn.Linear(hidden, out, bias=False)
        self.eps = eps

    def __call__(self, x: mx.array, modulation: mx.array) -> mx.array:
        shift, scale = mx.split(modulation, 2, axis=-1)
        return self.proj(_rms_norm(x, self.eps) * (1 + scale) + shift)


class _Samplers:
    """Compiled samplers by ``(steps, guidance, dtype)``."""

    def __init__(self) -> None:
        self.by_key: dict[tuple[int, float, mx.Dtype], Callable[[mx.array, mx.array], mx.array]] = {}


class MeanFlowHead(nn.Module):
    def __init__(self, config: HeadConfig):
        super().__init__()
        self.config = config
        hidden = config.hidden_size
        self.latent_proj = nn.Linear(config.latent_dim, hidden, bias=False)
        self.cond_proj = nn.Linear(hidden, hidden, bias=False)
        self.t_embed = ScalarEmbed(hidden)
        self.dt_embed = ScalarEmbed(hidden)
        self.h_embed = ScalarEmbed(hidden)
        self.omega_embed = ScalarEmbed(hidden)
        # Rows: (shift, scale, gate) of every layer, then (shift, scale) of the final layer.
        self.ada = nn.Linear(hidden, (3 * config.num_layers + 2) * hidden, bias=False)
        ffn = int(hidden * config.ffn_ratio)
        self.layers = [HeadLayer(hidden, ffn, config.norm_eps) for _ in range(config.num_layers)]
        self.final = FinalLayer(hidden, config.latent_dim, config.norm_eps)
        self._samplers = _Samplers()

    def velocity(self, z: mx.array, c: mx.array) -> mx.array:
        """``z [B, D]`` and the summed conditioning ``c [B, H]`` -> mean velocity ``[B, D]``."""
        hidden = self.config.hidden_size
        modulations = mx.split(
            self.ada(nn.silu(c)), [3 * hidden * (i + 1) for i in range(len(self.layers))], axis=-1
        )
        x = self.latent_proj(z)
        for layer, modulation in zip(self.layers, modulations):
            x = layer(x, modulation)
        return self.final(x, modulations[-1])

    def _build_sampler(self, steps: int, guidance: float, dtype: mx.Dtype):
        h = 1.0 / steps
        times = [self.t_embed(i * h, dtype) for i in range(steps)]
        interval = self.dt_embed(self.config.interval_embed, dtype)
        step = self.h_embed(h, dtype)
        omega = self.omega_embed(1.0 - 1.0 / guidance, dtype)
        mx.eval(times, interval, step, omega)

        def sample(hidden: mx.array, noise: mx.array) -> mx.array:
            cond = self.cond_proj(hidden.astype(dtype))
            z = noise
            for time in times:
                # Each sum rounds in the working dtype, so the order is part of the result.
                c = cond + time
                c = c + interval
                c = c + step
                c = c + omega
                z = z + h * self.velocity(z, c)
            return z

        return mx.compile(sample)

    def sample(
        self,
        hidden: mx.array,
        noise: mx.array,
        guidance: float | None = None,
        steps: int | None = None,
    ) -> mx.array:
        """LM hidden states ``[B, H]`` and noise ``[B, D]`` -> normalized latents ``[B, D]``."""
        steps = steps or self.config.num_steps
        guidance = float(self.config.guidance_scale if guidance is None else guidance)
        key = (steps, guidance, noise.dtype)
        sampler = self._samplers.by_key.get(key)
        if sampler is None:
            sampler = self._samplers.by_key[key] = self._build_sampler(steps, guidance, noise.dtype)
        return sampler(hidden, noise)

    def clear_samplers(self) -> None:
        """Drop the compiled samplers (they capture the weights they were built with)."""
        self._samplers.by_key.clear()
