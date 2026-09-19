# ruff: noqa
"""Appearance feature extractor (F): maps a source image to a 3D appearance
volume that the warping module consumes."""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from .util import SameBlock2d, DownBlock2d, ResBlock3d


class AppearanceFeatureExtractor(nn.Module):
    def __init__(
        self,
        image_channel: int,
        block_expansion: int,
        num_down_blocks: int,
        max_features: int,
        reshape_channel: int,
        reshape_depth: int,
        num_resblocks: int,
    ):
        super().__init__()
        self.reshape_channel = reshape_channel
        self.reshape_depth = reshape_depth

        self.first = SameBlock2d(
            image_channel,
            block_expansion,
            kernel_size=3,
            padding=1,
        )

        # down_blocks: list of DownBlock2d, matches PyTorch ModuleList key layout
        self.down_blocks = []
        for i in range(num_down_blocks):
            in_features = min(max_features, block_expansion * (2 ** i))
            out_features = min(max_features, block_expansion * (2 ** (i + 1)))
            self.down_blocks.append(
                DownBlock2d(in_features, out_features, kernel_size=3, padding=1)
            )

        last_down = min(max_features, block_expansion * (2 ** num_down_blocks))
        self.second = nn.Conv2d(last_down, max_features, kernel_size=1, stride=1)

        # resblocks_3d as a list (PyTorch upstream uses Sequential with named
        # children "3dr0".."3drN" so this won't auto-match key names; we expose
        # `resblocks_3d` as a plain list and rely on the converter to reindex.)
        self.resblocks_3d = [
            ResBlock3d(reshape_channel, kernel_size=3, padding=1)
            for _ in range(num_resblocks)
        ]

    def __call__(self, source_image: mx.array) -> mx.array:
        # source_image: (N, H, W, C). Following the SameBlock2d/DownBlock2d
        # path leaves us with (N, H', W', max_features). Then we reshape into
        # the 3D appearance volume (N, D, H', W', reshape_channel).
        out = self.first(source_image)
        for blk in self.down_blocks:
            out = blk(out)
        out = self.second(out)

        n, h, w, c = out.shape
        # PyTorch did out.view(N, R, D, H, W) on a (N, R*D, H, W) tensor, where
        # the C axis splits as outer=R, inner=D. In NHWC, the C axis is last,
        # so we reshape to (N, H, W, R, D) and then transpose to (N, D, H, W, R).
        out = out.reshape(n, h, w, self.reshape_channel, self.reshape_depth)
        out = mx.transpose(out, (0, 4, 1, 2, 3))  # (N, D, H, W, R)

        for blk in self.resblocks_3d:
            out = blk(out)
        return out
