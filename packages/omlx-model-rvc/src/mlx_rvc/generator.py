"""MLX implementation of the RVC v2 NSF waveform generator."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from .mlx_layers import conv1d_nct, conv_transpose1d_nct, linear, weight_norm


class NSFGenerator:
    def __init__(
        self,
        state: Mapping[str, np.ndarray],
        *,
        sample_rate: int,
        upsample_rates: Sequence[int],
        upsample_kernel_sizes: Sequence[int],
        resblock_kernel_sizes: Sequence[int] = (3, 7, 11),
        resblock_dilations: Sequence[Sequence[int]] = ((1, 3, 5),) * 3,
        prefix: str = "dec",
    ) -> None:
        import mlx.core as mx

        if len(upsample_rates) != len(upsample_kernel_sizes):
            raise ValueError("upsample rates and kernels must have equal length")
        if len(resblock_kernel_sizes) != len(resblock_dilations):
            raise ValueError(
                "resblock kernels and dilation groups must have equal length"
            )
        self.mx = mx
        self.prefix = prefix
        self.sample_rate = int(sample_rate)
        self.upsample_rates = tuple(int(value) for value in upsample_rates)
        self.upsample_kernel_sizes = tuple(
            int(value) for value in upsample_kernel_sizes
        )
        self.resblock_kernel_sizes = tuple(
            int(value) for value in resblock_kernel_sizes
        )
        self.resblock_dilations = tuple(
            tuple(int(item) for item in group) for group in resblock_dilations
        )
        self.hop_length = math.prod(self.upsample_rates)

        materialized: dict[str, np.ndarray] = dict(state)
        marker = f"{prefix}."
        for name in tuple(state):
            if not name.startswith(marker) or not name.endswith(".weight_v"):
                continue
            base = name.removesuffix(".weight_v")
            gain_name = f"{base}.weight_g"
            if gain_name in state and f"{base}.weight" not in state:
                materialized[f"{base}.weight"] = weight_norm(
                    state[gain_name], state[name]
                )
        self.state = {name: mx.array(value) for name, value in materialized.items()}

    def _get(self, suffix: str) -> Any:
        name = f"{self.prefix}.{suffix}"
        try:
            return self.state[name]
        except KeyError as error:
            raise KeyError(f"missing RVC generator tensor: {name}") from error

    def _leaky_relu(self, values: Any) -> Any:
        return self.mx.where(values >= 0, values, values * 0.1)

    def _sine_source(self, f0: Any) -> Any:
        """Generate the deterministic voiced NSF excitation.

        The parity path uses voiced F0 and zero source noise. Production will
        add an explicit request seed and MLX random noise for unvoiced frames.
        """

        mx = self.mx
        if f0.ndim != 2:
            raise ValueError("NSF F0 input must have shape [batch, frames]")
        radial = (
            f0[:, :, None]
            / self.sample_rate
            * mx.arange(1, self.hop_length + 1)[None, None]
        )
        wrapped = mx.remainder(radial[:, :, -1:] + 0.5, 1.0) - 0.5
        accumulated = mx.remainder(mx.cumsum(wrapped, axis=1), 1.0)
        previous = mx.pad(accumulated, ((0, 0), (1, 0), (0, 0)))[:, :-1]
        radial = radial + previous
        sine = mx.sin(2.0 * math.pi * mx.reshape(radial, (f0.shape[0], -1, 1))) * 0.1
        merged = self.mx.tanh(
            linear(
                sine,
                self._get("m_source.l_linear.weight"),
                self._get("m_source.l_linear.bias"),
            )
        )
        return self.mx.transpose(merged, (0, 2, 1))

    def _resblock(
        self, values: Any, block: int, kernel: int, dilations: Sequence[int]
    ) -> Any:
        for layer, dilation in enumerate(dilations):
            hidden = self._leaky_relu(values)
            hidden = conv1d_nct(
                hidden,
                self._get(f"resblocks.{block}.convs1.{layer}.weight"),
                self._get(f"resblocks.{block}.convs1.{layer}.bias"),
                padding=(kernel * dilation - dilation) // 2,
                dilation=dilation,
            )
            hidden = self._leaky_relu(hidden)
            hidden = conv1d_nct(
                hidden,
                self._get(f"resblocks.{block}.convs2.{layer}.weight"),
                self._get(f"resblocks.{block}.convs2.{layer}.bias"),
                padding=(kernel - 1) // 2,
            )
            values = values + hidden
        return values

    def __call__(
        self,
        latent: Any,
        f0: Any,
        conditioning: Any,
        *,
        trace: dict[str, Any] | None = None,
    ) -> Any:
        mx = self.mx
        if latent.ndim != 3 or f0.ndim != 2 or conditioning.ndim != 3:
            raise ValueError("RVC generator inputs have invalid ranks")
        source = self._sine_source(f0)
        values = conv1d_nct(
            latent, self._get("conv_pre.weight"), self._get("conv_pre.bias"), padding=3
        )
        values = values + conv1d_nct(
            conditioning, self._get("cond.weight"), self._get("cond.bias")
        )
        if trace is not None:
            trace["conditioned"] = values
        kernels_per_stage = len(self.resblock_kernel_sizes)
        for stage, (rate, kernel_size) in enumerate(
            zip(self.upsample_rates, self.upsample_kernel_sizes)
        ):
            values = self._leaky_relu(values)
            if trace is not None:
                trace[f"stage_{stage}_activated"] = values
            values = conv_transpose1d_nct(
                values,
                self._get(f"ups.{stage}.weight"),
                self._get(f"ups.{stage}.bias"),
                stride=rate,
                padding=(kernel_size - rate) // 2,
            )
            if trace is not None:
                trace[f"stage_{stage}_upsample"] = values
            if stage + 1 < len(self.upsample_rates):
                source_stride = math.prod(self.upsample_rates[stage + 1 :])
                source_stage = conv1d_nct(
                    source,
                    self._get(f"noise_convs.{stage}.weight"),
                    self._get(f"noise_convs.{stage}.bias"),
                    stride=source_stride,
                    padding=source_stride // 2,
                )
                # PyTorch's even-kernel stride convolution emits one extra frame.
                source_stage = source_stage[:, :, : values.shape[-1]]
            else:
                source_stage = conv1d_nct(
                    source,
                    self._get(f"noise_convs.{stage}.weight"),
                    self._get(f"noise_convs.{stage}.bias"),
                )
            if trace is not None:
                trace[f"stage_{stage}_source"] = source_stage
            values = values + source_stage
            if trace is not None:
                trace[f"stage_{stage}_excited"] = values
            branches = []
            for branch, (kernel, dilations) in enumerate(
                zip(self.resblock_kernel_sizes, self.resblock_dilations)
            ):
                block = stage * kernels_per_stage + branch
                branches.append(self._resblock(values, block, kernel, dilations))
            values = sum(branches[1:], branches[0]) / kernels_per_stage
            if trace is not None:
                trace[f"stage_{stage}_resblocks"] = values
        values = self._leaky_relu(values)
        values = conv1d_nct(values, self._get("conv_post.weight"), padding=3)
        return mx.tanh(values)
