"""Inference-only MLX port of Seed-VC v2's autoregressive token model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import mlx.core as mx
import numpy as np

from .mlx_layers import linear


@dataclass(frozen=True)
class ARConfig:
    dim: int = 768
    heads: int = 12
    kv_heads: int = 2
    head_dim: int = 64
    layers: int = 12
    vocabulary: int = 2049
    rope_base: float = 10000.0
    norm_epsilon: float = 1e-5


def _rms_norm(x: mx.array, weight: mx.array, epsilon: float) -> mx.array:
    return x * mx.rsqrt(mx.mean(mx.square(x), axis=-1, keepdims=True) + epsilon) * weight


def _rope(x: mx.array, positions: mx.array, base: float) -> mx.array:
    half = x.shape[-1] // 2
    frequencies = mx.power(
        base,
        -mx.arange(0, x.shape[-1], 2, dtype=mx.float32) / x.shape[-1],
    )
    angles = positions.astype(mx.float32)[..., None] * frequencies
    angles = angles[:, :, None, :]
    pairs = x.reshape(*x.shape[:-1], half, 2).astype(mx.float32)
    real = pairs[..., 0] * mx.cos(angles) - pairs[..., 1] * mx.sin(angles)
    imaginary = pairs[..., 1] * mx.cos(angles) + pairs[..., 0] * mx.sin(angles)
    return mx.stack((real, imaginary), axis=-1).reshape(x.shape).astype(x.dtype)


class SeedVCAR:
    def __init__(self, state: Mapping[str, np.ndarray], config: ARConfig | None = None) -> None:
        self.state = {
            name.removeprefix("module."): mx.array(value) for name, value in state.items()
        }
        self.config = config or ARConfig()

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"AR checkpoint is missing weight {name}") from error

    def embed_tokens(self, tokens: mx.array) -> mx.array:
        return self._get("model.embeddings.weight")[tokens.astype(mx.int32)]

    def _layer(
        self,
        x: mx.array,
        positions: mx.array,
        index: int,
        cache: tuple[mx.array, mx.array] | None,
    ) -> tuple[mx.array, tuple[mx.array, mx.array]]:
        config = self.config
        prefix = f"model.layers.{index}"
        normalized = _rms_norm(
            x, self._get(f"{prefix}.attention_norm.weight"), config.norm_epsilon
        )
        qkv = linear(normalized, self._get(f"{prefix}.attention.wqkv.weight"))
        q, k, v = mx.split(
            qkv, (config.dim, config.dim + config.kv_heads * config.head_dim), axis=-1
        )
        q = q.reshape(x.shape[0], x.shape[1], config.heads, config.head_dim)
        k = k.reshape(x.shape[0], x.shape[1], config.kv_heads, config.head_dim)
        v = v.reshape(x.shape[0], x.shape[1], config.kv_heads, config.head_dim)
        q = _rope(q, positions, config.rope_base).transpose(0, 2, 1, 3)
        k = _rope(k, positions, config.rope_base).transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)
        past_length = 0
        if cache is not None:
            past_length = cache[0].shape[2]
            k = mx.concatenate((cache[0], k), axis=2)
            v = mx.concatenate((cache[1], v), axis=2)
        new_cache = (k, v)
        repeat = config.heads // config.kv_heads
        keys = mx.repeat(k, repeat, axis=1)
        values = mx.repeat(v, repeat, axis=1)
        query_length = q.shape[2]
        key_length = keys.shape[2]
        query_indices = mx.arange(query_length)[:, None] + past_length
        key_indices = mx.arange(key_length)[None, :]
        mask = mx.where(query_indices >= key_indices, 0.0, -1e9).astype(q.dtype)
        attended = mx.fast.scaled_dot_product_attention(
            q, keys, values, scale=config.head_dim**-0.5, mask=mask
        )
        attended = attended.transpose(0, 2, 1, 3).reshape(
            x.shape[0], x.shape[1], config.dim
        )
        x = x + linear(attended, self._get(f"{prefix}.attention.wo.weight"))
        normalized = _rms_norm(
            x, self._get(f"{prefix}.ffn_norm.weight"), config.norm_epsilon
        )
        gate_values = linear(normalized, self._get(f"{prefix}.feed_forward.w1.weight"))
        gated = gate_values * mx.sigmoid(gate_values)
        gated *= linear(normalized, self._get(f"{prefix}.feed_forward.w3.weight"))
        x = x + linear(gated, self._get(f"{prefix}.feed_forward.w2.weight"))
        return x, new_cache

    def forward(
        self,
        embeddings: mx.array,
        positions: mx.array,
        caches: list[tuple[mx.array, mx.array]] | None = None,
    ) -> tuple[mx.array, list[tuple[mx.array, mx.array]]]:
        if embeddings.ndim != 3 or embeddings.shape[-1] != self.config.dim:
            raise ValueError("embeddings must have shape [batch, frames, 768]")
        if positions.ndim == 1:
            positions = mx.broadcast_to(positions[None], embeddings.shape[:2])
        next_caches = []
        x = embeddings
        for index in range(self.config.layers):
            cache = None if caches is None else caches[index]
            x, next_cache = self._layer(x, positions, index, cache)
            next_caches.append(next_cache)
        x = _rms_norm(x, self._get("model.norm.weight"), self.config.norm_epsilon)
        logits = linear(x, self._get("model.output.weight"))
        return logits, next_caches

    def prompt(self, condition: mx.array, target_tokens: mx.array) -> tuple[mx.array, mx.array]:
        if condition.ndim != 3 or condition.shape[0] != 1:
            raise ValueError("AR generation currently requires one condition sequence")
        if target_tokens.ndim == 1:
            target_tokens = target_tokens[None]
        separator = self._get("sep_token_emb")[None, None, :]
        embeddings = mx.concatenate(
            (separator, condition, separator, self.embed_tokens(target_tokens)), axis=1
        )
        condition_positions = mx.arange(condition.shape[1] + 1, dtype=mx.int32)
        target_positions = mx.arange(target_tokens.shape[1] + 1, dtype=mx.int32)
        positions = mx.concatenate((condition_positions, target_positions))[None]
        return embeddings, positions

    def generate_greedy(
        self,
        condition: mx.array,
        target_tokens: mx.array,
        *,
        max_new_tokens: int = 4000,
        min_new_tokens: int = 10,
    ) -> mx.array:
        if max_new_tokens < 1:
            raise ValueError("max_new_tokens must be positive")
        embeddings, positions = self.prompt(condition, target_tokens)
        logits, caches = self.forward(embeddings, positions)
        output: list[mx.array] = []
        next_position = int(target_tokens.shape[-1]) + 1
        for index in range(max_new_tokens):
            current_logits = logits[:, -1]
            if index < min_new_tokens:
                current_logits = mx.concatenate(
                    (current_logits[:, :-1], mx.full((1, 1), -1e9)), axis=-1
                )
            token = mx.argmax(current_logits, axis=-1).astype(mx.int32)
            mx.eval(token)
            if int(token.item()) == self.config.vocabulary - 1:
                break
            output.append(token)
            logits, caches = self.forward(
                self.embed_tokens(token[:, None]),
                mx.array([[next_position]], dtype=mx.int32),
                caches,
            )
            next_position += 1
        if not output:
            return mx.zeros((1, 0), dtype=mx.int32)
        return mx.stack(output, axis=1)
