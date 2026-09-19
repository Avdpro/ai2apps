"""MLX inference path for RVC's mean-only reverse residual coupling flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .mlx_layers import conv1d_nct, weight_norm


class ReverseResidualCouplingFlow:
    def __init__(
        self, state: Mapping[str, np.ndarray], *, prefix: str = "flow"
    ) -> None:
        import mlx.core as mx

        self.mx = mx
        self.prefix = prefix
        materialized: dict[str, np.ndarray] = dict(state)
        for name in tuple(state):
            if not name.startswith(f"{prefix}.flows.") or not name.endswith(
                ".weight_v"
            ):
                continue
            base = name.removesuffix(".weight_v")
            gain_name = f"{base}.weight_g"
            if gain_name in state and f"{base}.weight" not in state:
                materialized[f"{base}.weight"] = weight_norm(
                    state[gain_name], state[name]
                )
        self.state = {name: mx.array(value) for name, value in materialized.items()}
        marker = f"{prefix}.flows."
        self.flow_indices = sorted(
            {
                int(name[len(marker) :].split(".", 1)[0])
                for name in state
                if name.startswith(marker) and ".pre.weight" in name
            }
        )
        if not self.flow_indices or any(index % 2 for index in self.flow_indices):
            raise ValueError("RVC residual coupling flow indices are invalid")

    def _get(self, suffix: str) -> Any:
        name = f"{self.prefix}.{suffix}"
        try:
            return self.state[name]
        except KeyError as error:
            raise KeyError(f"missing RVC flow tensor: {name}") from error

    def _wn(self, hidden: Any, mask: Any, conditioning: Any, flow: int) -> Any:
        mx = self.mx
        prefix = f"flows.{flow}.enc"
        hidden_channels = hidden.shape[1]
        output = mx.zeros_like(hidden)
        condition = conv1d_nct(
            conditioning,
            self._get(f"{prefix}.cond_layer.weight"),
            self._get(f"{prefix}.cond_layer.bias"),
        )
        layers = condition.shape[1] // (2 * hidden_channels)
        for layer in range(layers):
            combined = conv1d_nct(
                hidden,
                self._get(f"{prefix}.in_layers.{layer}.weight"),
                self._get(f"{prefix}.in_layers.{layer}.bias"),
                padding=2,
            )
            offset = layer * 2 * hidden_channels
            combined += condition[:, offset : offset + 2 * hidden_channels]
            first, second = combined[:, :hidden_channels], combined[:, hidden_channels:]
            activated = mx.tanh(first) * mx.sigmoid(second)
            residual_skip = conv1d_nct(
                activated,
                self._get(f"{prefix}.res_skip_layers.{layer}.weight"),
                self._get(f"{prefix}.res_skip_layers.{layer}.bias"),
            )
            if layer < layers - 1:
                hidden = (hidden + residual_skip[:, :hidden_channels]) * mask
                output += residual_skip[:, hidden_channels:]
            else:
                output += residual_skip
        return output * mask

    def _coupling(self, values: Any, mask: Any, conditioning: Any, flow: int) -> Any:
        channels = values.shape[1] // 2
        first, second = values[:, :channels], values[:, channels:]
        prefix = f"flows.{flow}"
        hidden = (
            conv1d_nct(
                first,
                self._get(f"{prefix}.pre.weight"),
                self._get(f"{prefix}.pre.bias"),
            )
            * mask
        )
        hidden = self._wn(hidden, mask, conditioning, flow)
        mean = (
            conv1d_nct(
                hidden,
                self._get(f"{prefix}.post.weight"),
                self._get(f"{prefix}.post.bias"),
            )
            * mask
        )
        return self.mx.concatenate((first, (second - mean) * mask), axis=1)

    def __call__(self, values: Any, mask: Any, conditioning: Any) -> Any:
        if values.ndim != 3 or values.shape[1] % 2:
            raise ValueError("RVC flow input must be NCT with an even channel count")
        for flow in reversed(self.flow_indices):
            values = values[:, ::-1, :]
            values = self._coupling(values, mask, conditioning, flow)
        return values

    def forward(self, values: Any, mask: Any, conditioning: Any) -> Any:
        """Map posterior latents into the prior space during training."""

        if values.ndim != 3 or values.shape[1] % 2:
            raise ValueError("RVC flow input must be NCT with an even channel count")
        for flow in self.flow_indices:
            channels = values.shape[1] // 2
            first, second = values[:, :channels], values[:, channels:]
            prefix = f"flows.{flow}"
            hidden = (
                conv1d_nct(
                    first,
                    self._get(f"{prefix}.pre.weight"),
                    self._get(f"{prefix}.pre.bias"),
                )
                * mask
            )
            hidden = self._wn(hidden, mask, conditioning, flow)
            mean = (
                conv1d_nct(
                    hidden,
                    self._get(f"{prefix}.post.weight"),
                    self._get(f"{prefix}.post.bias"),
                )
                * mask
            )
            values = self.mx.concatenate((first, (second + mean) * mask), axis=1)
            values = values[:, ::-1, :]
        return values
