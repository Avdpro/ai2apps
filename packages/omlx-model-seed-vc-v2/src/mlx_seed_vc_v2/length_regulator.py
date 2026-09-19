"""MLX implementation of Seed-VC v1's continuous length regulator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import mlx.core as mx
import numpy as np

from .mlx_layers import conv1d_nct, linear


class ContinuousLengthRegulator:
    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        self.state = {
            name.removeprefix("module."): mx.array(value) for name, value in state.items()
        }

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"length regulator is missing weight {name}") from error

    @staticmethod
    def _group_norm_one(x: mx.array, weight: mx.array, bias: mx.array) -> mx.array:
        mean = mx.mean(x, axis=(1, 2), keepdims=True)
        variance = mx.mean(mx.square(x - mean), axis=(1, 2), keepdims=True)
        return (x - mean) * mx.rsqrt(variance + 1e-5) * weight[None, :, None] + bias[
            None, :, None
        ]

    def __call__(self, content: Any, output_length: int) -> mx.array:
        if content.ndim != 3 or content.shape[-1] != 768:
            raise ValueError("content must have shape [batch, frames, 768]")
        if output_length < 1:
            raise ValueError("output_length must be positive")
        x = linear(
            content,
            self._get("content_in_proj.weight"),
            self._get("content_in_proj.bias"),
        )
        indices = mx.floor(
            mx.arange(output_length, dtype=mx.float32) * x.shape[1] / output_length
        ).astype(mx.int32)
        x = x[:, indices].transpose(0, 2, 1)
        for conv_index, norm_index in ((0, 1), (3, 4), (6, 7), (9, 10)):
            x = conv1d_nct(
                x,
                self._get(f"model.{conv_index}.weight"),
                self._get(f"model.{conv_index}.bias"),
                padding=1,
            )
            x = self._group_norm_one(
                x,
                self._get(f"model.{norm_index}.weight"),
                self._get(f"model.{norm_index}.bias"),
            )
            x = x * mx.tanh(mx.logaddexp(x, mx.zeros_like(x)))
        x = conv1d_nct(x, self._get("model.12.weight"), self._get("model.12.bias"))
        return x.transpose(0, 2, 1)


class DiscreteLengthRegulator:
    """Seed-VC v2 discrete-token regulator for the AR and CFM paths."""

    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        self.state = {
            name.removeprefix("module."): mx.array(value) for name, value in state.items()
        }

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"length regulator is missing weight {name}") from error

    @staticmethod
    def _group_norm(x: mx.array, weight: mx.array, bias: mx.array) -> mx.array:
        mean = mx.mean(x, axis=(1, 2), keepdims=True)
        variance = mx.mean(mx.square(x - mean), axis=(1, 2), keepdims=True)
        return (x - mean) * mx.rsqrt(variance + 1e-5) * weight[None, :, None] + bias[
            None, :, None
        ]

    def __call__(self, tokens: Any, output_length: int | None = None) -> mx.array:
        if tokens.ndim == 3:
            tokens = tokens[:, 0]
        if tokens.ndim != 2:
            raise ValueError("tokens must have shape [batch, frames] or [batch, codebook, frames]")
        embedding = self._get("embedding.weight")
        x = embedding[tokens.astype(mx.int32)]
        if output_length is None:
            return x
        if output_length < 1:
            raise ValueError("output_length must be positive")
        indices = mx.floor(
            mx.arange(output_length, dtype=mx.float32) * x.shape[1] / output_length
        ).astype(mx.int32)
        x = x[:, indices].transpose(0, 2, 1)
        layer_indices = sorted(
            int(name.split(".")[1])
            for name in self.state
            if name.startswith("model.") and name.endswith(".weight")
            and self.state[name].ndim == 3
        )
        for conv_index in layer_indices:
            x = conv1d_nct(
                x,
                self._get(f"model.{conv_index}.weight"),
                self.state.get(f"model.{conv_index}.bias"),
                padding=1,
            )
            norm_index = conv_index + 1
            norm_weight = self.state.get(f"model.{norm_index}.weight")
            if norm_weight is not None:
                x = self._group_norm(
                    x, norm_weight, self._get(f"model.{norm_index}.bias")
                )
                x = x * mx.tanh(mx.logaddexp(x, mx.zeros_like(x)))
        return x.transpose(0, 2, 1)
