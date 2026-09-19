# ruff: noqa
"""Shared MLX layer utilities ported from upstream LivePortrait."""

from __future__ import annotations

import math
import os

import mlx.core as mx
import mlx.nn as nn


_CONV3D_BACKEND = os.environ.get("FLP_MLX_CONV3D_BACKEND", "native")


class BatchNorm3d(nn.Module):
    """Inference-only 5D BatchNorm.

    Stores parameters as `weight`, `bias`, `running_mean`, `running_var` so
    PyTorch checkpoints map 1:1. We don't need training-time stats updates,
    so we just normalize with the running statistics directly.

    Input layout: (N, D, H, W, C). Normalization is over the C axis only.
    """

    def __init__(self, num_features: int, eps: float = 1e-5):
        super().__init__()
        self.eps = eps
        self.weight = mx.ones((num_features,))
        self.bias = mx.zeros((num_features,))
        self.running_mean = mx.zeros((num_features,))
        self.running_var = mx.ones((num_features,))
        self._frozen_dtype = None
        self._frozen_scale = None
        self._frozen_shift = None

    def freeze(self, dtype=None):
        """Precompute inference affine terms after checkpoint loading/casting."""
        target_dtype = dtype or self.weight.dtype
        w32 = self.weight.astype(mx.float32)
        b32 = self.bias.astype(mx.float32)
        m32 = self.running_mean.astype(mx.float32)
        v32 = self.running_var.astype(mx.float32)
        scale = w32 * mx.rsqrt(v32 + self.eps)
        shift = b32 - m32 * scale
        self._frozen_scale = scale.astype(target_dtype)
        self._frozen_shift = shift.astype(target_dtype)
        self._frozen_dtype = target_dtype
        mx.eval(self._frozen_scale, self._frozen_shift)

    def __call__(self, x: mx.array) -> mx.array:
        if (
            self._frozen_scale is not None
            and self._frozen_shift is not None
            and self._frozen_dtype is not None
            and self._frozen_dtype == x.dtype
        ):
            return x * self._frozen_scale + self._frozen_shift

        # Compute scale/shift in fp32 to keep the rsqrt and division stable
        # under fp16 inputs, then cast back to the input dtype.
        in_dtype = x.dtype
        w32 = self.weight.astype(mx.float32)
        b32 = self.bias.astype(mx.float32)
        m32 = self.running_mean.astype(mx.float32)
        v32 = self.running_var.astype(mx.float32)
        scale = w32 * mx.rsqrt(v32 + self.eps)
        shift = b32 - m32 * scale
        scale = scale.astype(in_dtype)
        shift = shift.astype(in_dtype)
        return x * scale + shift


class GRN(nn.Module):
    """Global Response Normalization layer.

    Operates on NHWC inputs (channels-last in MLX). Equivalent to the
    upstream PyTorch GRN, where parameters have shape (1, 1, 1, C).
    """

    def __init__(self, dim: int):
        super().__init__()
        self.gamma = mx.zeros((1, 1, 1, dim))
        self.beta = mx.zeros((1, 1, 1, dim))

    def __call__(self, x: mx.array) -> mx.array:
        # x: (N, H, W, C)
        gx = mx.linalg.norm(x, axis=(1, 2), keepdims=True)  # (N, 1, 1, C)
        nx = gx / (mx.mean(gx, axis=-1, keepdims=True) + 1e-6)
        return self.gamma * (x * nx) + self.beta + x


class SameBlock2d(nn.Module):
    """Conv -> BN -> activation, preserving spatial dims. Mirrors upstream
    SameBlock2d. lrelu=True swaps ReLU for LeakyReLU."""

    def __init__(self, in_features, out_features, groups=1, kernel_size=3,
                 padding=1, lrelu=False):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels=in_features,
            out_channels=out_features,
            kernel_size=kernel_size,
            padding=padding,
            groups=groups,
        )
        self.norm = nn.BatchNorm(out_features)
        self.lrelu = lrelu

    def __call__(self, x):
        x = self.conv(x)
        x = self.norm(x)
        if self.lrelu:
            return nn.leaky_relu(x, negative_slope=0.01)
        return nn.relu(x)


class DownBlock2d(nn.Module):
    def __init__(self, in_features, out_features, kernel_size=3, padding=1, groups=1):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels=in_features,
            out_channels=out_features,
            kernel_size=kernel_size,
            padding=padding,
            groups=groups,
        )
        self.norm = nn.BatchNorm(out_features)
        self.pool = nn.AvgPool2d(kernel_size=2)

    def __call__(self, x):
        x = self.conv(x)
        x = self.norm(x)
        x = nn.relu(x)
        x = self.pool(x)
        return x


class DownBlock3d(nn.Module):
    def __init__(self, in_features, out_features, kernel_size=3, padding=1, groups=1):
        super().__init__()
        if groups != 1:
            raise ValueError("MLX Conv3d does not support groups != 1")
        self.conv = nn.Conv3d(
            in_channels=in_features,
            out_channels=out_features,
            kernel_size=kernel_size,
            padding=padding,
        )
        self.norm = BatchNorm3d(out_features)
        self.pool = nn.AvgPool3d(kernel_size=(1, 2, 2))

    def __call__(self, x):
        x = self.conv(x)
        x = self.norm(x)
        x = nn.relu(x)
        x = self.pool(x)
        return x


class UpBlock3d(nn.Module):
    def __init__(self, in_features, out_features, kernel_size=3, padding=1, groups=1):
        super().__init__()
        if groups != 1:
            raise ValueError("MLX Conv3d does not support groups != 1")
        self.conv = nn.Conv3d(
            in_channels=in_features,
            out_channels=out_features,
            kernel_size=kernel_size,
            padding=padding,
        )
        self.norm = BatchNorm3d(out_features)

    def __call__(self, x):
        # x: (N, D, H, W, C). Spatial-only nearest upsample by 2 (D unchanged).
        n, d, h, w, c = x.shape
        x = mx.broadcast_to(x[:, :, :, None, :, None, :],
                            (n, d, h, 2, w, 2, c))
        x = x.reshape(n, d, h * 2, w * 2, c)
        x = _conv3d_call(self.conv, x)
        x = self.norm(x)
        x = nn.relu(x)
        return x


class ResBlock3d(nn.Module):
    """Pre-activation 3D residual block with BatchNorm and Conv3d."""

    def __init__(self, in_features, kernel_size=3, padding=1):
        super().__init__()
        self.norm1 = BatchNorm3d(in_features)
        self.norm2 = BatchNorm3d(in_features)
        self.conv1 = nn.Conv3d(in_features, in_features, kernel_size=kernel_size, padding=padding)
        self.conv2 = nn.Conv3d(in_features, in_features, kernel_size=kernel_size, padding=padding)

    def __call__(self, x):
        out = self.norm1(x)
        out = nn.relu(out)
        out = _conv3d_call(self.conv1, out)
        out = self.norm2(out)
        out = nn.relu(out)
        out = _conv3d_call(self.conv2, out)
        return out + x


class Encoder(nn.Module):
    """Hourglass encoder of stacked DownBlock3d."""

    def __init__(self, block_expansion, in_features, num_blocks=3, max_features=256):
        super().__init__()
        blocks = []
        for i in range(num_blocks):
            ic = in_features if i == 0 else min(max_features, block_expansion * (2 ** i))
            oc = min(max_features, block_expansion * (2 ** (i + 1)))
            blocks.append(DownBlock3d(ic, oc, kernel_size=3, padding=1))
        self.down_blocks = blocks

    def __call__(self, x):
        outs = [x]
        for blk in self.down_blocks:
            outs.append(blk(outs[-1]))
        return outs


class Decoder(nn.Module):
    """Hourglass decoder of stacked UpBlock3d."""

    def __init__(self, block_expansion, in_features, num_blocks=3, max_features=256):
        super().__init__()
        blocks = []
        for i in reversed(range(num_blocks)):
            in_filters = (1 if i == num_blocks - 1 else 2) * min(max_features, block_expansion * (2 ** (i + 1)))
            out_filters = min(max_features, block_expansion * (2 ** i))
            blocks.append(UpBlock3d(in_filters, out_filters, kernel_size=3, padding=1))
        self.up_blocks = blocks
        self.out_filters = block_expansion + in_features

        self.conv = nn.Conv3d(self.out_filters, self.out_filters, kernel_size=3, padding=1)
        self.norm = BatchNorm3d(self.out_filters)

    def __call__(self, x_list):
        # x_list comes from the encoder; consume from the end (deepest first).
        out = x_list[-1]
        for i, blk in enumerate(self.up_blocks):
            out = blk(out)
            skip = x_list[-(i + 2)]
            out = mx.concatenate([out, skip], axis=-1)
        out = _conv3d_call(self.conv, out)
        out = self.norm(out)
        return nn.relu(out)


class Hourglass(nn.Module):
    def __init__(self, block_expansion, in_features, num_blocks=3, max_features=256):
        super().__init__()
        self.encoder = Encoder(block_expansion, in_features, num_blocks, max_features)
        self.decoder = Decoder(block_expansion, in_features, num_blocks, max_features)
        self.out_filters = self.decoder.out_filters

    def __call__(self, x):
        return self.decoder(self.encoder(x))


def conv3d_via_2d(x: mx.array, weight: mx.array, bias: mx.array | None, padding: int) -> mx.array:
    """Conv3d implemented as a series of 2D convs along the depth axis.

    For Conv3d configurations dominated by spatial work (K=7 here), this is
    measurably faster than MLX's stock Conv3d on Apple Silicon because the
    2D path is more mature in MPS Graph.

    Inputs:
      x      : (N, D, H, W, IC) NDHWC
      weight : (OC, kD, kH, kW, IC)
      bias   : (OC,)
    Output:
      (N, D, H, W, OC)
    """
    N, D, H, W, IC = x.shape
    OC, kD, kH, kW, _ = weight.shape
    pad_d = kD // 2
    x_padded = mx.pad(x, [(0, 0), (pad_d, pad_d), (0, 0), (0, 0), (0, 0)])
    out = None
    for kd in range(kD):
        x_slice = x_padded[:, kd:kd + D, :, :, :]  # (N, D, H, W, IC)
        x_2d = x_slice.reshape(N * D, H, W, IC)
        w_2d = weight[:, kd, :, :, :]  # (OC, kH, kW, IC)
        y = mx.conv2d(x_2d, w_2d, padding=padding)
        y = y.reshape(N, D, H, W, OC)
        out = y if out is None else (out + y)
    return out + bias if bias is not None else out


def _conv3d_auto_use_2d(x: mx.array, weight: mx.array, padding: int) -> bool:
    """Heuristic for Conv3d shapes where depth-sliced Conv2d won in benchmarks."""
    if padding != 1 or weight.ndim != 5 or weight.shape[1:4] != (3, 3, 3):
        return False
    _, _, h, w, ic = x.shape
    oc = weight.shape[0]
    if h != w:
        return False
    # DenseMotion hourglass shapes where conv3d_via_2d measured faster.
    return (
        (h == 16 and ic == 128 and oc == 256)
        or (h == 16 and ic == 512 and oc == 128)
        or (h == 32 and ic == 256 and oc == 64)
    )


def _conv3d_call(conv: nn.Conv3d, x: mx.array) -> mx.array:
    padding = conv.padding[0] if isinstance(conv.padding, tuple) else conv.padding
    if _CONV3D_BACKEND == "2d" or (
        _CONV3D_BACKEND == "auto" and _conv3d_auto_use_2d(x, conv.weight, padding)
    ):
        return conv3d_via_2d(x, conv.weight, getattr(conv, "bias", None), padding=padding)
    return conv(x)


_COORDINATE_GRID_CACHE = {}


def make_coordinate_grid(spatial_size, dtype=mx.float32):
    """3D coordinate grid in normalized [-1, 1] space, layout (D, H, W, 3).

    Order of last axis is (x, y, z) to match upstream LivePortrait.
    """
    d, h, w = (int(v) for v in spatial_size)
    key = (d, h, w, str(dtype))
    cached = _COORDINATE_GRID_CACHE.get(key)
    if cached is not None:
        return cached

    x = (mx.arange(w, dtype=dtype) / max(w - 1, 1)) * 2.0 - 1.0
    y = (mx.arange(h, dtype=dtype) / max(h - 1, 1)) * 2.0 - 1.0
    z = (mx.arange(d, dtype=dtype) / max(d - 1, 1)) * 2.0 - 1.0
    xx = mx.broadcast_to(x.reshape(1, 1, w), (d, h, w))
    yy = mx.broadcast_to(y.reshape(1, h, 1), (d, h, w))
    zz = mx.broadcast_to(z.reshape(d, 1, 1), (d, h, w))
    grid = mx.stack([xx, yy, zz], axis=-1)
    mx.eval(grid)
    _COORDINATE_GRID_CACHE[key] = grid
    return grid


def freeze_batch_norm_3d(module, dtype=None, _seen=None):
    """Freeze all inference-only BatchNorm3d instances below a module."""
    if _seen is None:
        _seen = set()
    obj_id = id(module)
    if obj_id in _seen:
        return
    _seen.add(obj_id)

    if isinstance(module, BatchNorm3d):
        module.freeze(dtype)
        return

    if isinstance(module, dict):
        values = module.values()
    elif isinstance(module, (list, tuple)):
        values = module
    elif isinstance(module, nn.Module):
        values = vars(module).values()
    else:
        return

    for value in values:
        freeze_batch_norm_3d(value, dtype=dtype, _seen=_seen)


def kp2gaussian(kp, spatial_size, kp_variance):
    """Gaussian heatmap representation of keypoints.

    kp:           (N, K, 3) in normalized [-1, 1] coords
    spatial_size: (D, H, W)
    returns:      (N, K, D, H, W) gaussian map
    """
    grid = make_coordinate_grid(spatial_size, dtype=kp.dtype)  # (D, H, W, 3)
    grid = grid.reshape(1, 1, *spatial_size, 3)
    mean = kp.reshape(kp.shape[0], kp.shape[1], 1, 1, 1, 3)
    diff = grid - mean  # (N, K, D, H, W, 3)
    return mx.exp(-0.5 * mx.sum(diff * diff, axis=-1) / kp_variance)
