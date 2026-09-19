"""Pure MLX Seed-VC v2 diffusion-transformer estimator."""

from __future__ import annotations

from collections.abc import Mapping

import mlx.core as mx
import numpy as np

from .ar import _rms_norm, _rope
from .mlx_layers import linear


def _silu(x: mx.array) -> mx.array:
    return x * mx.sigmoid(x)


class SeedVCDiT:
    hidden_dim = 512
    heads = 8
    head_dim = 64
    layers = 13

    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        self.state = {
            name.removeprefix("module.estimator.").removeprefix("estimator."): mx.array(value)
            for name, value in state.items()
        }

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"DiT checkpoint is missing weight {name}") from error

    def _time_embedding(self, time: mx.array) -> mx.array:
        half = 128
        frequencies = mx.exp(
            -np.log(10000.0) * mx.arange(half, dtype=mx.float32) / half
        )
        arguments = 1000.0 * time.astype(mx.float32)[:, None] * frequencies[None]
        values = mx.concatenate((mx.cos(arguments), mx.sin(arguments)), axis=-1)
        values = linear(
            values,
            self._get("t_embedder.mlp.0.weight"),
            self._get("t_embedder.mlp.0.bias"),
        )
        values = _silu(values)
        return linear(
            values,
            self._get("t_embedder.mlp.2.weight"),
            self._get("t_embedder.mlp.2.bias"),
        )

    def _transformer_layer(
        self, x: mx.array, time_embedding: mx.array, positions: mx.array, mask: mx.array, index: int
    ) -> mx.array:
        prefix = f"transformer.layers.{index}"
        adaptive = _silu(time_embedding)
        adaptive = linear(
            adaptive,
            self._get(f"{prefix}.attention_norm.linear.weight"),
            self._get(f"{prefix}.attention_norm.linear.bias"),
        )
        shift_attention, scale_attention, gate_attention, shift_mlp, scale_mlp, gate_mlp = mx.split(
            adaptive, 6, axis=-1
        )
        normalized = _rms_norm(
            x, self._get(f"{prefix}.attention_norm.norm.weight"), 1e-5
        )
        normalized = normalized * (1 + scale_attention) + shift_attention
        qkv = linear(normalized, self._get(f"{prefix}.attention.wqkv.weight"))
        q, k, v = mx.split(qkv, 3, axis=-1)
        q = q.reshape(x.shape[0], x.shape[1], self.heads, self.head_dim)
        k = k.reshape(x.shape[0], x.shape[1], self.heads, self.head_dim)
        v = v.reshape(x.shape[0], x.shape[1], self.heads, self.head_dim)
        q = _rope(q, positions, 10000.0).transpose(0, 2, 1, 3)
        k = _rope(k, positions, 10000.0).transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)
        attended = mx.fast.scaled_dot_product_attention(
            q, k, v, scale=self.head_dim**-0.5, mask=mask
        )
        attended = attended.transpose(0, 2, 1, 3).reshape(x.shape)
        attended = linear(attended, self._get(f"{prefix}.attention.wo.weight"))
        x = x + gate_attention * attended
        normalized = _rms_norm(x, self._get(f"{prefix}.ffn_norm.weight"), 1e-5)
        normalized = normalized * (1 + scale_mlp) + shift_mlp
        first = linear(normalized, self._get(f"{prefix}.feed_forward.w1.weight"))
        third = linear(normalized, self._get(f"{prefix}.feed_forward.w3.weight"))
        feed_forward = linear(
            _silu(first) * third, self._get(f"{prefix}.feed_forward.w2.weight")
        )
        return x + gate_mlp * feed_forward

    def __call__(
        self,
        x: mx.array,
        prompt: mx.array,
        lengths: mx.array,
        time: mx.array,
        style: mx.array,
        condition: mx.array,
    ) -> mx.array:
        if x.ndim != 3 or x.shape[1] != 80:
            raise ValueError("x must have shape [batch, 80, frames]")
        time_embedding = self._time_embedding(time)
        condition = linear(
            condition,
            self._get("cond_projection.weight"),
            self._get("cond_projection.bias"),
        )
        values = mx.concatenate((x.transpose(0, 2, 1), prompt.transpose(0, 2, 1), condition), axis=-1)
        values = linear(
            values,
            self._get("cond_x_merge_linear.weight"),
            self._get("cond_x_merge_linear.bias"),
        )
        style_token = linear(
            style, self._get("style_in.weight"), self._get("style_in.bias")
        )[:, None]
        values = mx.concatenate((time_embedding[:, None], style_token, values), axis=1)
        sequence_length = values.shape[1]
        valid = mx.arange(sequence_length)[None, :] < (lengths + 2)[:, None]
        mask = mx.where(valid[:, None, None, :], 0.0, -1e9).astype(values.dtype)
        positions = mx.broadcast_to(
            mx.arange(sequence_length, dtype=mx.int32)[None], values.shape[:2]
        )
        conditioning = time_embedding[:, None]
        for index in range(self.layers):
            values = self._transformer_layer(
                values, conditioning, positions, mask, index
            )
        final = _silu(conditioning)
        final = linear(
            final,
            self._get("transformer.norm.linear.weight"),
            self._get("transformer.norm.linear.bias"),
        )
        scale, shift = mx.split(final, 2, axis=-1)
        values = _rms_norm(values, self._get("transformer.norm.norm.weight"), 1e-5)
        values = values * (1 + scale) + shift
        values = values[:, 2:]
        values = linear(
            values,
            self._get("final_mlp.0.weight"),
            self._get("final_mlp.0.bias"),
        )
        values = _silu(values)
        values = linear(
            values,
            self._get("final_mlp.2.weight"),
            self._get("final_mlp.2.bias"),
        )
        return values.transpose(0, 2, 1)
