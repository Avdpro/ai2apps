# ruff: noqa
"""ConvNeXtV2-Tiny used as the backbone of motion_extractor.

Layout follows the upstream PyTorch model so that, after channel-axis
permutation of the conv weights, parameter keys map 1:1 onto the
`detector.*` keys in the released motion_extractor.pth checkpoint.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from .util import GRN


class Block(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.dwconv = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.norm = nn.LayerNorm(dim, eps=1e-6)
        self.pwconv1 = nn.Linear(dim, 4 * dim)
        self.act = nn.GELU()
        self.grn = GRN(4 * dim)
        self.pwconv2 = nn.Linear(4 * dim, dim)

    def __call__(self, x: mx.array) -> mx.array:
        residual = x
        x = self.dwconv(x)
        x = self.norm(x)
        x = self.pwconv1(x)
        x = self.act(x)
        x = self.grn(x)
        x = self.pwconv2(x)
        return residual + x


class ConvNeXtV2(nn.Module):
    def __init__(
        self,
        in_chans: int = 3,
        depths=(3, 3, 9, 3),
        dims=(96, 192, 384, 768),
        num_kp: int = 21,
        num_bins: int = 66,
    ):
        super().__init__()

        # downsample_layers[0] = stem (Conv 4x4 s4, LayerNorm).
        # downsample_layers[i>0] = (LayerNorm, Conv 2x2 s2).
        # Use plain Python lists so flat parameter keys match the PyTorch
        # checkpoint's `0.0.weight`, `0.1.weight` layout.
        self.downsample_layers = [
            [
                nn.Conv2d(in_chans, dims[0], kernel_size=4, stride=4),
                nn.LayerNorm(dims[0], eps=1e-6),
            ]
        ]
        for i in range(3):
            self.downsample_layers.append([
                nn.LayerNorm(dims[i], eps=1e-6),
                nn.Conv2d(dims[i], dims[i + 1], kernel_size=2, stride=2),
            ])

        self.stages = [[Block(dims[i]) for _ in range(d)] for i, d in enumerate(depths)]

        self.norm = nn.LayerNorm(dims[-1], eps=1e-6)

        self.fc_kp = nn.Linear(dims[-1], 3 * num_kp)
        self.fc_scale = nn.Linear(dims[-1], 1)
        self.fc_pitch = nn.Linear(dims[-1], num_bins)
        self.fc_yaw = nn.Linear(dims[-1], num_bins)
        self.fc_roll = nn.Linear(dims[-1], num_bins)
        self.fc_t = nn.Linear(dims[-1], 3)
        self.fc_exp = nn.Linear(dims[-1], 3 * num_kp)

    def forward_features(self, x):
        for stage_idx in range(4):
            for layer in self.downsample_layers[stage_idx]:
                x = layer(x)
            for blk in self.stages[stage_idx]:
                x = blk(x)
        x = mx.mean(x, axis=(1, 2))  # global average pool over spatial dims
        return self.norm(x)

    def __call__(self, x):
        x = self.forward_features(x)
        return {
            "pitch": self.fc_pitch(x),
            "yaw": self.fc_yaw(x),
            "roll": self.fc_roll(x),
            "t": self.fc_t(x),
            "exp": self.fc_exp(x),
            "scale": self.fc_scale(x),
            "kp": self.fc_kp(x),
        }


def convnextv2_tiny(num_kp: int = 21, num_bins: int = 66, in_chans: int = 3) -> ConvNeXtV2:
    return ConvNeXtV2(
        in_chans=in_chans,
        depths=(3, 3, 9, 3),
        dims=(96, 192, 384, 768),
        num_kp=num_kp,
        num_bins=num_bins,
    )
