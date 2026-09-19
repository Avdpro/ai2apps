"""Native NHWC MLX implementation of the GhostV2 AAD generator."""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import mlx.nn as nn


def _leaky_relu(x, slope: float = 0.1):
    return mx.maximum(x, 0) + slope * mx.minimum(x, 0)


class NativeGhostV2Generator:
    def __init__(
        self,
        model_path: str | Path,
        *,
        precision: str = "fp16",
        compile_graph: bool = True,
    ):
        if precision not in {"fp16", "bf16"}:
            raise ValueError("precision must be fp16 or bf16")
        self.dtype = mx.float16 if precision == "fp16" else mx.bfloat16
        self.weights = {
            key: value.astype(self.dtype)
            for key, value in mx.load(str(Path(model_path) / "weights.safetensors")).items()
        }
        self.upsample = nn.Upsample(
            scale_factor=2, mode="linear", align_corners=True
        )
        self._forward = mx.compile(self._forward_impl) if compile_graph else self._forward_impl

    def _conv(self, x, prefix: str, *, stride: int = 1, padding: int = 0):
        weight = self.weights[f"{prefix}.weight"]
        bias = self.weights.get(f"{prefix}.bias")
        y = mx.conv2d(
            x,
            weight,
            stride=(stride, stride),
            padding=(padding, padding),
        )
        return y if bias is None else y + bias

    def _deconv(
        self, x, prefix: str, *, stride: int, padding: int = 0
    ):
        y = mx.conv_transpose2d(
            x,
            self.weights[f"{prefix}.weight"],
            stride=(stride, stride),
            padding=(padding, padding),
        )
        bias = self.weights.get(f"{prefix}.bias")
        return y if bias is None else y + bias

    def _linear(self, x, prefix: str):
        y = x @ self.weights[f"{prefix}.weight"].T
        bias = self.weights.get(f"{prefix}.bias")
        return y if bias is None else y + bias

    def _instance_norm(self, x, epsilon: float = 1e-5):
        mean = mx.mean(x, axis=(1, 2), keepdims=True)
        variance = mx.mean((x - mean) ** 2, axis=(1, 2), keepdims=True)
        return (x - mean) * mx.rsqrt(variance + epsilon)

    def _aad(self, h, attribute, identity, prefix: str, *, normalized=None):
        if normalized is None:
            normalized = self._instance_norm(h)
        gamma_attribute = self._conv(attribute, f"{prefix}.conv1")
        beta_attribute = self._conv(attribute, f"{prefix}.conv2")
        gamma_identity = self._linear(identity, f"{prefix}.fc1")[:, None, None, :]
        beta_identity = self._linear(identity, f"{prefix}.fc2")[:, None, None, :]
        attribute_value = gamma_attribute * normalized + beta_attribute
        identity_value = gamma_identity * normalized + beta_identity
        mask = mx.sigmoid(self._conv(normalized, f"{prefix}.conv_h"))
        return (1 - mask) * attribute_value + mask * identity_value

    def _aad_block(self, h, attribute, identity, block: int):
        prefix = f"generator.AADBlk{block}"
        normalized_h = self._instance_norm(h)
        value = self._aad(
            h,
            attribute,
            identity,
            f"{prefix}.add_blocks.0",
            normalized=normalized_h,
        )
        value = self._conv(
            mx.maximum(value, 0), f"{prefix}.add_blocks.2", padding=1
        )
        value = self._aad(
            value, attribute, identity, f"{prefix}.add_blocks.3"
        )
        value = self._conv(
            mx.maximum(value, 0), f"{prefix}.add_blocks.5", padding=1
        )
        if f"{prefix}.last_add_block.2.weight" in self.weights:
            shortcut = self._aad(
                h,
                attribute,
                identity,
                f"{prefix}.last_add_block.0",
                normalized=normalized_h,
            )
            shortcut = self._conv(
                mx.maximum(shortcut, 0), f"{prefix}.last_add_block.2", padding=1
            )
        else:
            shortcut = h
        return value + shortcut

    def _encode(self, target):
        features = []
        value = target
        for index in range(1, 8):
            value = _leaky_relu(
                self._conv(value, f"encoder.conv{index}", stride=2, padding=1)
            )
            features.append(value)
        attributes = [features[-1]]
        value = features[-1]
        for index, skip in enumerate(reversed(features[:-1]), start=1):
            value = _leaky_relu(
                self._deconv(
                    value, f"encoder.deconv{index}", stride=2, padding=1
                )
            )
            value = mx.concatenate((value, skip), axis=-1)
            attributes.append(value)
        attributes.append(self.upsample(value))
        return attributes

    def _forward_impl(self, target, identity):
        attributes = self._encode(target)
        value = self._deconv(
            identity[:, None, None, :], "generator.up1", stride=1
        )
        for block, attribute in enumerate(attributes, start=1):
            value = self._aad_block(value, attribute, identity, block)
            if block < 8:
                value = self.upsample(value)
        return mx.tanh(value)

    def __call__(self, target, identity):
        return self._forward(target, identity)
