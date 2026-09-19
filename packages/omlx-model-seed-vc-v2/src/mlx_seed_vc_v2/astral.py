"""Pure MLX ASTRAL ConvNeXtV2 and binary spherical quantizer."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import mlx.core as mx
import numpy as np

from .mlx_layers import conv1d_nct, linear


def _gelu(x: mx.array) -> mx.array:
    return 0.5 * x * (1.0 + mx.erf(x / np.sqrt(2.0)))


def _channel_norm(x: mx.array, weight: mx.array, bias: mx.array) -> mx.array:
    """ConvNeXt channel-first LayerNorm over C at every frame."""

    mean = mx.mean(x, axis=1, keepdims=True)
    variance = mx.mean(mx.square(x - mean), axis=1, keepdims=True)
    return (x - mean) * mx.rsqrt(variance + 1e-6) * weight[None, :, None] + bias[
        None, :, None
    ]


class AstralQuantizer:
    """ASTRAL post-HuBERT encoder and inference-only BSQ tokenizer."""

    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        self.state = {name: mx.array(value) for name, value in state.items()}
        mask = self._get("quantizer.mask")
        self.codebook_bits = int(mask.shape[0])

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"ASTRAL checkpoint is missing weight {name}") from error

    def encode(self, hidden_states: Any) -> mx.array:
        """Encode HuBERT layer-18 features shaped ``[B, T, 1024]``."""

        if hidden_states.ndim != 3 or hidden_states.shape[-1] != 1024:
            raise ValueError("hidden_states must have shape [batch, frames, 1024]")
        x = conv1d_nct(
            hidden_states.transpose(0, 2, 1),
            self._get("encoder.input_projection.weight"),
            self._get("encoder.input_projection.bias"),
        )
        for index in range(12):
            residual = x
            prefix = f"encoder.blocks.{index}"
            x = conv1d_nct(
                x,
                self._get(f"{prefix}.dwconv.weight"),
                self._get(f"{prefix}.dwconv.bias"),
                padding=3,
                groups=512,
            )
            x = _channel_norm(
                x,
                self._get(f"{prefix}.norm.weight"),
                self._get(f"{prefix}.norm.bias"),
            ).transpose(0, 2, 1)
            x = _gelu(
                linear(
                    x,
                    self._get(f"{prefix}.pwconv1.weight"),
                    self._get(f"{prefix}.pwconv1.bias"),
                )
            )
            spatial_norm = mx.sqrt(mx.sum(mx.square(x), axis=1, keepdims=True))
            normalized = spatial_norm / (mx.mean(spatial_norm, axis=-1, keepdims=True) + 1e-6)
            x = (
                self._get(f"{prefix}.grn.gamma") * (x * normalized)
                + self._get(f"{prefix}.grn.beta")
                + x
            )
            x = linear(
                x,
                self._get(f"{prefix}.pwconv2.weight"),
                self._get(f"{prefix}.pwconv2.bias"),
            ).transpose(0, 2, 1)
            x = residual + x
        return x.transpose(0, 2, 1)

    def quantize(self, encoded: Any) -> tuple[mx.array, mx.array]:
        if encoded.ndim != 3 or encoded.shape[-1] != 512:
            raise ValueError("encoded input must have shape [batch, frames, 512]")
        projected = linear(
            encoded,
            self._get("quantizer.project_in.weight"),
            self._get("quantizer.project_in.bias"),
        )
        projected = projected * mx.rsqrt(
            mx.sum(mx.square(projected), axis=-1, keepdims=True) + 1e-12
        )
        positive = projected > 0
        mask = self._get("quantizer.mask").astype(mx.int32)
        indices = mx.sum(positive.astype(mx.int32) * mask[None, None, :], axis=-1)
        codes = mx.where(positive, 1.0, -1.0).astype(mx.float32)
        codes = codes / np.sqrt(self.codebook_bits)
        quantized = linear(
            codes,
            self._get("quantizer.project_out.weight"),
            self._get("quantizer.project_out.bias"),
        )
        return quantized, indices

    def __call__(self, hidden_states: Any) -> tuple[mx.array, mx.array]:
        return self.quantize(self.encode(hidden_states))
