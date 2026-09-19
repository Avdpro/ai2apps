"""Functional MLX port of the inference-only RVC text/content encoder."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np

from .mlx_layers import conv1d_nct, linear


class TextEncoder:
    def __init__(
        self, state: Mapping[str, np.ndarray], *, prefix: str = "enc_p"
    ) -> None:
        import mlx.core as mx

        self.mx = mx
        self.state = {name: mx.array(value) for name, value in state.items()}
        self.prefix = prefix
        phone_weight = self._get("emb_phone.weight")
        self.hidden_channels = int(phone_weight.shape[0])
        self.input_channels = int(phone_weight.shape[1])
        self.heads = 2
        self.head_channels = self.hidden_channels // self.heads
        self.layers = self._layer_count()
        relative = self._get("encoder.attn_layers.0.emb_rel_k")
        self.window_size = (int(relative.shape[1]) - 1) // 2

    def _get(self, suffix: str) -> Any:
        name = f"{self.prefix}.{suffix}"
        try:
            return self.state[name]
        except KeyError as error:
            raise KeyError(f"missing RVC TextEncoder tensor: {name}") from error

    def _layer_count(self) -> int:
        marker = f"{self.prefix}.encoder.attn_layers."
        layers = {
            int(name[len(marker) :].split(".", 1)[0])
            for name in self.state
            if name.startswith(marker)
        }
        if not layers or layers != set(range(max(layers) + 1)):
            raise ValueError("RVC TextEncoder attention layers are not contiguous")
        return len(layers)

    def _layer_norm(self, values: Any, prefix: str, epsilon: float = 1e-5) -> Any:
        mx = self.mx
        transposed = mx.transpose(values, (0, 2, 1))
        mean = mx.mean(transposed, axis=-1, keepdims=True)
        variance = mx.mean(mx.square(transposed - mean), axis=-1, keepdims=True)
        normalized = (transposed - mean) * mx.rsqrt(variance + epsilon)
        output = normalized * self._get(f"{prefix}.gamma") + self._get(f"{prefix}.beta")
        return mx.transpose(output, (0, 2, 1))

    def _relative_embeddings(self, values: Any, length: int) -> Any:
        mx = self.mx
        pad_length = max(length - (self.window_size + 1), 0)
        slice_start = max((self.window_size + 1) - length, 0)
        if pad_length:
            values = mx.pad(values, ((0, 0), (pad_length, pad_length), (0, 0)))
        return values[:, slice_start : slice_start + 2 * length - 1]

    def _relative_to_absolute(self, values: Any) -> Any:
        mx = self.mx
        batch, heads, length, _ = values.shape
        values = mx.pad(values, ((0, 0), (0, 0), (0, 0), (0, 1)))
        flat = mx.reshape(values, (batch, heads, length * 2 * length))
        flat = mx.pad(flat, ((0, 0), (0, 0), (0, length - 1)))
        return mx.reshape(flat, (batch, heads, length + 1, 2 * length - 1))[
            :, :, :length, length - 1 :
        ]

    def _absolute_to_relative(self, values: Any) -> Any:
        mx = self.mx
        batch, heads, length, _ = values.shape
        values = mx.pad(values, ((0, 0), (0, 0), (0, 0), (0, length - 1)))
        flat = mx.reshape(
            values, (batch, heads, length * length + length * (length - 1))
        )
        flat = mx.pad(flat, ((0, 0), (0, 0), (length, 0)))
        return mx.reshape(flat, (batch, heads, length, 2 * length))[:, :, :, 1:]

    def _attention(self, values: Any, mask: Any, layer: int) -> Any:
        mx = self.mx
        prefix = f"encoder.attn_layers.{layer}"

        def project(name: str) -> Any:
            return conv1d_nct(
                values,
                self._get(f"{prefix}.{name}.weight"),
                self._get(f"{prefix}.{name}.bias"),
            )

        batch, channels, length = values.shape
        query = mx.transpose(
            mx.reshape(
                project("conv_q"), (batch, self.heads, self.head_channels, length)
            ),
            (0, 1, 3, 2),
        )
        key = mx.transpose(
            mx.reshape(
                project("conv_k"), (batch, self.heads, self.head_channels, length)
            ),
            (0, 1, 3, 2),
        )
        value = mx.transpose(
            mx.reshape(
                project("conv_v"), (batch, self.heads, self.head_channels, length)
            ),
            (0, 1, 3, 2),
        )
        scaled_query = query / math.sqrt(self.head_channels)
        scores = scaled_query @ mx.transpose(key, (0, 1, 3, 2))
        relative_key = self._relative_embeddings(
            self._get(f"{prefix}.emb_rel_k"), length
        )
        relative_logits = scaled_query @ mx.transpose(relative_key[None], (0, 1, 3, 2))
        scores += self._relative_to_absolute(relative_logits)
        scores = mx.where(
            mask[:, None, :, :] != 0, scores, mx.array(-1e4, scores.dtype)
        )
        probabilities = mx.softmax(scores, axis=-1)
        output = probabilities @ value
        relative_weights = self._absolute_to_relative(probabilities)
        relative_value = self._relative_embeddings(
            self._get(f"{prefix}.emb_rel_v"), length
        )
        output += relative_weights @ relative_value[None]
        output = mx.reshape(
            mx.transpose(output, (0, 1, 3, 2)), (batch, channels, length)
        )
        return conv1d_nct(
            output,
            self._get(f"{prefix}.conv_o.weight"),
            self._get(f"{prefix}.conv_o.bias"),
        )

    def _ffn(self, values: Any, mask: Any, layer: int) -> Any:
        mx = self.mx
        prefix = f"encoder.ffn_layers.{layer}"
        hidden = conv1d_nct(
            values * mask,
            self._get(f"{prefix}.conv_1.weight"),
            self._get(f"{prefix}.conv_1.bias"),
            padding=1,
        )
        hidden = mx.maximum(hidden, 0)
        return (
            conv1d_nct(
                hidden,
                self._get(f"{prefix}.conv_2.weight"),
                self._get(f"{prefix}.conv_2.bias"),
                padding=1,
            )
            * mask
        )

    def __call__(
        self, phone: Any, pitch: Any | None, lengths: Any
    ) -> tuple[Any, Any, Any]:
        mx = self.mx
        if phone.ndim != 3 or int(phone.shape[-1]) != self.input_channels:
            raise ValueError("phone features have the wrong shape")
        if lengths.ndim != 1 or lengths.size != phone.shape[0]:
            raise ValueError("RVC feature batch and lengths do not match")
        if bool(mx.any(lengths <= 0).item()) or bool(
            mx.any(lengths > phone.shape[1]).item()
        ):
            raise ValueError("RVC feature lengths are outside the padded sequence")
        embedded = linear(
            phone, self._get("emb_phone.weight"), self._get("emb_phone.bias")
        )
        if pitch is not None:
            embedded += self._get("emb_pitch.weight")[pitch]
        embedded *= math.sqrt(self.hidden_channels)
        embedded = mx.where(embedded >= 0, embedded, embedded * 0.1)
        values = mx.transpose(embedded, (0, 2, 1))
        positions = mx.arange(values.shape[-1])[None, :]
        mask = (positions < lengths[:, None]).astype(values.dtype)[:, None, :]
        attention_mask = mask[:, :, :, None] * mask[:, :, None, :]
        values *= mask
        for layer in range(self.layers):
            values = self._layer_norm(
                values + self._attention(values, attention_mask[:, 0], layer),
                f"encoder.norm_layers_1.{layer}",
            )
            values = self._layer_norm(
                values + self._ffn(values, mask, layer),
                f"encoder.norm_layers_2.{layer}",
            )
        values *= mask
        statistics = (
            conv1d_nct(
                values,
                self._get("proj.weight"),
                self._get("proj.bias"),
            )
            * mask
        )
        midpoint = statistics.shape[1] // 2
        return statistics[:, :midpoint], statistics[:, midpoint:], mask
