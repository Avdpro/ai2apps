"""Qwen3.5 text backbone, laid out for one position per 133 ms frame.

Three of every four layers are Gated DeltaNet layers (a causal convolution and
a fast-weight recurrence, constant state), the fourth is full attention with a
growing key/value cache.

A live session runs a single position per frame, where a layer is a few
matrix-vector products and many small elementwise operations, so:

- projections that read the same input are one stacked matrix (see
  :mod:`haru_mlx.weights`): larger products run closer to memory bandwidth;
- the single-position step of a Gated DeltaNet layer is one compiled function
  with the recurrent state as explicit input and output. Attention layers
  compile everything around the growing cache.

Longer inputs (the prompt) take the same weights through the uncompiled path.
"""

from __future__ import annotations

from dataclasses import dataclass

import mlx.core as mx
import mlx.nn as nn

from ..lm_config import LINEAR, TextConfig
from .gated_delta import gated_delta_rule


class RMSNorm(nn.Module):
    """RMS norm computed in float32 with a float32 gain.

    The gain is stored as ``1 + w`` of the checkpoint's zero-centred ``w``;
    bfloat16 only resolves 1/128 near 1.
    """

    def __init__(self, dims: int, eps: float):
        super().__init__()
        self.weight = mx.ones((dims,), dtype=mx.float32)
        self.eps = eps

    def __call__(self, x: mx.array) -> mx.array:
        return mx.fast.rms_norm(x.astype(mx.float32), self.weight, self.eps).astype(x.dtype)


class MLP(nn.Module):
    """SwiGLU feed-forward; ``gate_up`` stacks the gate and up projections."""

    def __init__(self, hidden: int, intermediate: int):
        super().__init__()
        self.gate_up = nn.Linear(hidden, 2 * intermediate, bias=False)
        self.down_proj = nn.Linear(intermediate, hidden, bias=False)

    def __call__(self, x: mx.array) -> mx.array:
        gate, up = mx.split(self.gate_up(x), 2, axis=-1)
        return self.down_proj(nn.silu(gate) * up)


class GatedNorm(nn.Module):
    """RMS norm of the recurrence output, gated by ``silu(z)`` in float32."""

    def __init__(self, dims: int, eps: float):
        super().__init__()
        self.weight = mx.ones((dims,))
        self.eps = eps

    def __call__(self, y: mx.array, z: mx.array) -> mx.array:
        normed = mx.fast.rms_norm(y, self.weight, self.eps).astype(mx.float32)
        return (nn.silu(z.astype(mx.float32)) * normed).astype(y.dtype)


@dataclass
class DeltaState:
    """State of one Gated DeltaNet layer."""

    conv: mx.array  # [B, kernel - 1, conv_dim]: left context of the convolution
    memory: mx.array  # [B, Hv, Dv, Dk] float32: fast weights of the recurrence

    def arrays(self) -> list[mx.array]:
        return [self.conv, self.memory]


class KVCache:
    """Keys and values of one attention layer, grown in blocks of ``STEP`` positions."""

    STEP = 256

    def __init__(self) -> None:
        self.keys: mx.array | None = None
        self.values: mx.array | None = None
        self.offset = 0

    def update_and_fetch(self, keys: mx.array, values: mx.array) -> tuple[mx.array, mx.array]:
        """Append ``[B, heads, T, D]`` and return everything stored so far."""
        start, end = self.offset, self.offset + keys.shape[2]
        capacity = 0 if self.keys is None else self.keys.shape[2]
        if end > capacity:
            extra = -(-(end - capacity) // self.STEP) * self.STEP
            self.keys = self._extend(self.keys, keys, extra)
            self.values = self._extend(self.values, values, extra)
        self.keys[..., start:end, :] = keys
        self.values[..., start:end, :] = values
        self.offset = end
        return self.keys[..., :end, :], self.values[..., :end, :]

    @staticmethod
    def _extend(buffer: mx.array | None, like: mx.array, extra: int) -> mx.array:
        batch, heads, _, dims = like.shape
        block = mx.zeros((batch, heads, extra, dims), dtype=like.dtype)
        return block if buffer is None else mx.concatenate([buffer, block], axis=2)

    def arrays(self) -> list[mx.array]:
        return [] if self.keys is None else [self.keys, self.values]


LayerCache = DeltaState | KVCache


class GatedDeltaNet(nn.Module):
    def __init__(self, config: TextConfig):
        super().__init__()
        self.key_heads, self.value_heads = config.linear_num_key_heads, config.linear_num_value_heads
        self.key_head_dim, self.value_head_dim = config.linear_key_head_dim, config.linear_value_head_dim
        self.key_dim, self.value_dim, self.conv_dim = config.key_dim, config.value_dim, config.conv_dim
        self.kernel = config.linear_conv_kernel_dim
        # Rows: queries/keys/values (conv_dim), gate z (value_dim), write strength b and decay a (one per head).
        self.in_proj = nn.Linear(
            config.hidden_size, self.conv_dim + self.value_dim + 2 * self.value_heads, bias=False
        )
        self.conv1d = nn.Conv1d(self.conv_dim, self.conv_dim, self.kernel, groups=self.conv_dim, bias=False)
        self.A_log = mx.zeros((self.value_heads,))
        self.dt_bias = mx.zeros((self.value_heads,))
        self.norm = GatedNorm(self.value_head_dim, config.rms_norm_eps)
        self.out_proj = nn.Linear(self.value_dim, config.hidden_size, bias=False)

    def init_state(self, batch: int, dtype: mx.Dtype) -> DeltaState:
        return DeltaState(
            conv=mx.zeros((batch, self.kernel - 1, self.conv_dim), dtype=dtype),
            memory=mx.zeros(
                (batch, self.value_heads, self.value_head_dim, self.key_head_dim), dtype=mx.float32
            ),
        )

    def __call__(self, x: mx.array, conv: mx.array, memory: mx.array) -> tuple[mx.array, mx.array, mx.array]:
        """``x [B, T, H]`` and the layer state -> ``(output, conv, memory)``."""
        batch, steps, _ = x.shape
        z_start = self.conv_dim
        b_start = z_start + self.value_dim
        qkv, z, b, a = mx.split(self.in_proj(x), [z_start, b_start, b_start + self.value_heads], axis=-1)

        conv_input = mx.concatenate([conv, qkv], axis=1)
        conv = conv_input[:, -(self.kernel - 1) :]
        mixed = nn.silu(self.conv1d(conv_input))
        q, k, v = mx.split(mixed, [self.key_dim, 2 * self.key_dim], axis=-1)
        q = q.reshape(batch, steps, self.key_heads, self.key_head_dim)
        k = k.reshape(batch, steps, self.key_heads, self.key_head_dim)
        v = v.reshape(batch, steps, self.value_heads, self.value_head_dim)

        # Unit-length keys and queries, the queries scaled by 1 / sqrt(Dk).
        # rms_norm divides by the root *mean* square, hence the rescaling.
        scale = self.key_head_dim**-0.5
        eps = 1e-6 * scale**2
        q = scale**2 * mx.fast.rms_norm(q, None, eps)
        k = scale * mx.fast.rms_norm(k, None, eps)

        beta = mx.sigmoid(b)
        # float32: the decay compounds over the whole conversation.
        decay = mx.exp(-mx.exp(self.A_log.astype(mx.float32)) * nn.softplus(a.astype(mx.float32) + self.dt_bias))
        y, memory = gated_delta_rule(q, k, v, decay, beta, memory)

        y = self.norm(y, z.reshape(batch, steps, self.value_heads, self.value_head_dim))
        return self.out_proj(y.reshape(batch, steps, -1)), conv, memory


class Attention(nn.Module):
    """Grouped-query attention with partial rotary positions and an output gate."""

    def __init__(self, config: TextConfig):
        super().__init__()
        self.heads, self.kv_heads = config.num_attention_heads, config.num_key_value_heads
        self.head_dim = config.head_dim
        self.scale = self.head_dim**-0.5
        query_dim, key_dim = self.heads * self.head_dim, self.kv_heads * self.head_dim
        # Rows: per head [query, gate] (2 * query_dim), then keys, then values.
        self.qkv = nn.Linear(config.hidden_size, 2 * query_dim + 2 * key_dim, bias=False)
        self.q_norm = RMSNorm(self.head_dim, config.rms_norm_eps)
        self.k_norm = RMSNorm(self.head_dim, config.rms_norm_eps)
        self.o_proj = nn.Linear(query_dim, config.hidden_size, bias=False)
        self.rope = nn.RoPE(int(self.head_dim * config.partial_rotary_factor), base=config.rope_theta)

    def project(self, x: mx.array) -> tuple[mx.array, mx.array, mx.array, mx.array]:
        """``x [B, T, H]`` -> normalised ``q, k``, ``v`` as ``[B, heads, T, D]`` and the gate ``[B, T, Q]``."""
        batch, steps, _ = x.shape
        q_end = 2 * self.heads * self.head_dim
        q, k, v = mx.split(self.qkv(x), [q_end, q_end + self.kv_heads * self.head_dim], axis=-1)
        q, gate = mx.split(q.reshape(batch, steps, self.heads, -1), 2, axis=-1)
        q = self.q_norm(q).transpose(0, 2, 1, 3)
        k = self.k_norm(k.reshape(batch, steps, self.kv_heads, -1)).transpose(0, 2, 1, 3)
        v = v.reshape(batch, steps, self.kv_heads, -1).transpose(0, 2, 1, 3)
        return q, k, v, gate.reshape(batch, steps, -1)

    def attend(self, q: mx.array, k: mx.array, v: mx.array, cache: KVCache) -> mx.array:
        """Append the new positions to ``cache`` and attend over all of it."""
        q = self.rope(q, offset=cache.offset)
        k = self.rope(k, offset=cache.offset)
        k, v = cache.update_and_fetch(k, v)
        mask = "causal" if q.shape[2] > 1 else None
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale, mask=mask)
        batch, _, steps, _ = out.shape
        return out.transpose(0, 2, 1, 3).reshape(batch, steps, -1)

    def output(self, attended: mx.array, gate: mx.array) -> mx.array:
        return self.o_proj(attended * mx.sigmoid(gate))


class DecoderLayer(nn.Module):
    def __init__(self, config: TextConfig, kind: str):
        super().__init__()
        self.is_linear = kind == LINEAR
        self.input_layernorm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.post_attention_layernorm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        if self.is_linear:
            self.linear_attn = GatedDeltaNet(config)
        else:
            self.self_attn = Attention(config)
        self.mlp = MLP(config.hidden_size, config.intermediate_size)
        self.compile()

    def compile(self) -> None:
        """(Re)build the compiled single-position steps.

        They capture the weights when first run, so call this again after
        replacing weights (for example after quantizing).
        """
        if self.is_linear:
            self._step = mx.compile(self._linear_layer)
        else:
            self._before_cache = mx.compile(self._project)
            self._after_cache = mx.compile(self._finish)

    def _feed_forward(self, h: mx.array) -> mx.array:
        return h + self.mlp(self.post_attention_layernorm(h))

    def _linear_layer(self, x: mx.array, conv: mx.array, memory: mx.array):
        r, conv, memory = self.linear_attn(self.input_layernorm(x), conv, memory)
        return self._feed_forward(x + r), conv, memory

    def _project(self, x: mx.array):
        return self.self_attn.project(self.input_layernorm(x))

    def _finish(self, x: mx.array, attended: mx.array, gate: mx.array) -> mx.array:
        return self._feed_forward(x + self.self_attn.output(attended, gate))

    def __call__(self, x: mx.array, cache: LayerCache) -> mx.array:
        """Run new positions ``[B, T, H]``, updating ``cache`` in place."""
        single = x.shape[1] == 1
        if self.is_linear:
            step = self._step if single else self._linear_layer
            y, cache.conv, cache.memory = step(x, cache.conv, cache.memory)
            return y
        q, k, v, gate = (self._before_cache if single else self._project)(x)
        attended = self.self_attn.attend(q, k, v, cache)
        return (self._after_cache if single else self._finish)(x, attended, gate)


class Qwen3_5TextModel(nn.Module):
    def __init__(self, config: TextConfig):
        super().__init__()
        self.config = config
        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = [DecoderLayer(config, kind) for kind in config.layer_types]
        self.norm = RMSNorm(config.hidden_size, config.rms_norm_eps)

    def new_cache(self, batch: int, dtype: mx.Dtype) -> list[LayerCache]:
        """An empty per-layer cache for ``batch`` sequences."""
        return [
            layer.linear_attn.init_state(batch, dtype) if layer.is_linear else KVCache() for layer in self.layers
        ]

    def __call__(self, embeddings: mx.array, cache: list[LayerCache]) -> mx.array:
        """Run new positions ``[B, T, H]`` on top of ``cache`` -> hidden states ``[B, T, H]``."""
        h = embeddings
        for layer, layer_cache in zip(self.layers, cache, strict=True):
            h = layer(h, layer_cache)
        return self.norm(h)

    def compile(self) -> None:
        for layer in self.layers:
            layer.compile()
