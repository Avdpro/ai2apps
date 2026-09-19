"""Inference-only MLX port of Seed-VC v2's CAMPPlus style encoder."""

from __future__ import annotations

from collections.abc import Mapping

import mlx.core as mx
import numpy as np

from .mlx_layers import conv1d_nct


def _conv2d_nchw(x, weight, bias=None, *, stride=(1, 1), padding=(0, 0)):
    values = x.transpose(0, 2, 3, 1)
    kernel = weight.transpose(0, 2, 3, 1)
    values = mx.conv2d(values, kernel, stride=stride, padding=padding)
    if bias is not None:
        values += bias[None, None, None, :]
    return values.transpose(0, 3, 1, 2)


class CAMPPlus:
    def __init__(self, state: Mapping[str, np.ndarray]) -> None:
        self.state = {name: mx.array(value) for name, value in state.items()}

    def _get(self, name: str) -> mx.array:
        try:
            return self.state[name]
        except KeyError as error:
            raise ValueError(f"CAMPPlus checkpoint is missing weight {name}") from error

    def _batch_norm(self, x: mx.array, prefix: str) -> mx.array:
        mean = self._get(f"{prefix}.running_mean")
        variance = self._get(f"{prefix}.running_var")
        shape = (1, mean.shape[0]) + (1,) * (x.ndim - 2)
        values = (x - mean.reshape(shape)) * mx.rsqrt(variance.reshape(shape) + 1e-5)
        weight = self.state.get(f"{prefix}.weight")
        if weight is not None:
            values = values * weight.reshape(shape) + self._get(f"{prefix}.bias").reshape(shape)
        return values

    def _residual_2d(self, x: mx.array, prefix: str, stride: int) -> mx.array:
        values = _conv2d_nchw(
            x, self._get(f"{prefix}.conv1.weight"), stride=(stride, 1), padding=(1, 1)
        )
        values = mx.maximum(self._batch_norm(values, f"{prefix}.bn1"), 0)
        values = _conv2d_nchw(
            values, self._get(f"{prefix}.conv2.weight"), padding=(1, 1)
        )
        values = self._batch_norm(values, f"{prefix}.bn2")
        if f"{prefix}.shortcut.0.weight" in self.state:
            residual = _conv2d_nchw(
                x, self._get(f"{prefix}.shortcut.0.weight"), stride=(stride, 1)
            )
            residual = self._batch_norm(residual, f"{prefix}.shortcut.1")
        else:
            residual = x
        return mx.maximum(values + residual, 0)

    def _head(self, features: mx.array) -> mx.array:
        x = features[:, None]
        x = _conv2d_nchw(x, self._get("head.conv1.weight"), padding=(1, 1))
        x = mx.maximum(self._batch_norm(x, "head.bn1"), 0)
        x = self._residual_2d(x, "head.layer1.0", 2)
        x = self._residual_2d(x, "head.layer1.1", 1)
        x = self._residual_2d(x, "head.layer2.0", 2)
        x = self._residual_2d(x, "head.layer2.1", 1)
        x = _conv2d_nchw(
            x, self._get("head.conv2.weight"), stride=(2, 1), padding=(1, 1)
        )
        x = mx.maximum(self._batch_norm(x, "head.bn2"), 0)
        return x.reshape(x.shape[0], x.shape[1] * x.shape[2], x.shape[3])

    def _batch_relu(self, x: mx.array, prefix: str) -> mx.array:
        return mx.maximum(self._batch_norm(x, prefix), 0)

    @staticmethod
    def _segment_average(x: mx.array, length: int = 100) -> mx.array:
        chunks = []
        for start in range(0, x.shape[-1], length):
            chunks.append(mx.mean(x[..., start : start + length], axis=-1, keepdims=True))
        pooled = mx.concatenate(chunks, axis=-1)
        return mx.repeat(pooled, length, axis=-1)[..., : x.shape[-1]]

    def _dense_layer(self, x: mx.array, prefix: str, dilation: int) -> mx.array:
        values = self._batch_relu(x, f"{prefix}.nonlinear1.batchnorm")
        values = conv1d_nct(values, self._get(f"{prefix}.linear1.weight"))
        values = self._batch_relu(values, f"{prefix}.nonlinear2.batchnorm")
        local = conv1d_nct(
            values,
            self._get(f"{prefix}.cam_layer.linear_local.weight"),
            padding=dilation,
            dilation=dilation,
        )
        context = mx.mean(values, axis=-1, keepdims=True) + self._segment_average(values)
        context = mx.maximum(
            conv1d_nct(
                context,
                self._get(f"{prefix}.cam_layer.linear1.weight"),
                self._get(f"{prefix}.cam_layer.linear1.bias"),
            ),
            0,
        )
        context = mx.sigmoid(
            conv1d_nct(
                context,
                self._get(f"{prefix}.cam_layer.linear2.weight"),
                self._get(f"{prefix}.cam_layer.linear2.bias"),
            )
        )
        return mx.concatenate((x, local * context), axis=1)

    def __call__(self, features: mx.array, lengths: mx.array | None = None) -> mx.array:
        if features.ndim != 3 or features.shape[-1] != 80:
            raise ValueError("CAMPPlus features must have shape [batch, frames, 80]")
        x = self._head(features.transpose(0, 2, 1))
        x = conv1d_nct(x, self._get("xvector.tdnn.linear.weight"), stride=2, padding=2)
        x = self._batch_relu(x, "xvector.tdnn.nonlinear.batchnorm")
        for block, count, dilation in ((1, 12, 1), (2, 24, 2), (3, 16, 2)):
            for layer in range(1, count + 1):
                x = self._dense_layer(x, f"xvector.block{block}.tdnnd{layer}", dilation)
            transit = f"xvector.transit{block}"
            x = self._batch_relu(x, f"{transit}.nonlinear.batchnorm")
            x = conv1d_nct(x, self._get(f"{transit}.linear.weight"))
        x = self._batch_relu(x, "xvector.out_nonlinear.batchnorm")
        if lengths is None:
            mean = mx.mean(x, axis=-1)
            centered = x - mean[..., None]
            variance = mx.sum(mx.square(centered), axis=-1) / max(x.shape[-1] - 1, 1)
        else:
            pooled_mean = []
            pooled_variance = []
            for index in range(x.shape[0]):
                length = int(lengths[index].item())
                values = x[index, :, :length]
                value_mean = mx.mean(values, axis=-1)
                pooled_mean.append(value_mean)
                pooled_variance.append(
                    mx.sum(mx.square(values - value_mean[:, None]), axis=-1) / max(length - 1, 1)
                )
            mean = mx.stack(pooled_mean)
            variance = mx.stack(pooled_variance)
        stats = mx.concatenate((mean, mx.sqrt(variance)), axis=-1)[:, :, None]
        dense_prefix = "xvector.dense"
        output = conv1d_nct(stats, self._get(f"{dense_prefix}.linear.weight"))
        output = self._batch_norm(output, f"{dense_prefix}.nonlinear.batchnorm")
        return output[..., 0]
