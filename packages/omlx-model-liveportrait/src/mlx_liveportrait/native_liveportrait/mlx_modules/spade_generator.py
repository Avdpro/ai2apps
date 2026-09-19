# ruff: noqa
"""SPADE-based decoder (G) producing the output image from the warped feature."""

from __future__ import annotations

import os

import mlx.core as mx
import mlx.nn as nn

from .tensor_ops import conv2d_1x1_tensorops


_BF16_NATIVE_INSTANCE_NORM = os.environ.get("FLP_MLX_SPADE_BF16_NATIVE_NORM", "1") == "1"
_SPADE_SHORTCUT_BACKEND = os.environ.get("FLP_MLX_SPADE_SHORTCUT_BACKEND", "native")
_SPADE_SHORTCUT_MIN_OUT = int(os.environ.get("FLP_MLX_SPADE_SHORTCUT_MIN_OUT", "128"))


def _nearest_upsample_nhwc(x: mx.array, factor: int) -> mx.array:
    """Nearest-neighbor 2D upsample in NHWC by an integer factor."""
    if factor == 1:
        return x
    n, h, w, c = x.shape
    # Insert size-1 axes after H and W, broadcast, reshape.
    x = mx.broadcast_to(
        x[:, :, None, :, None, :],
        (n, h, factor, w, factor, c),
    )
    return x.reshape(n, h * factor, w * factor, c)


def _pixel_shuffle_nhwc(x: mx.array, factor: int) -> mx.array:
    """PixelShuffle for NHWC: (N, H, W, C) -> (N, H*r, W*r, C/(r*r)).

    Matches PyTorch's PixelShuffle data layout: input channels are taken in
    order (out_c outer, r_h, r_w inner)."""
    n, h, w, c = x.shape
    out_c = c // (factor * factor)
    x = x.reshape(n, h, w, out_c, factor, factor)
    # (N, H, r_h, W, r_w, out_c)
    x = mx.transpose(x, (0, 1, 4, 2, 5, 3))
    return x.reshape(n, h * factor, w * factor, out_c)


def _instance_norm_fp32(x: mx.array, eps: float = 1e-5) -> mx.array:
    """Per-instance normalization across spatial dims, computed in fp32.

    Input layout: NHWC. Equivalent to InstanceNorm2d(affine=False) in PyTorch.
    Reduce in fp32 to avoid fp16 variance overflow on large activations.
    """
    if x.dtype == mx.bfloat16 and _BF16_NATIVE_INSTANCE_NORM:
        mean = mx.mean(x, axis=(1, 2), keepdims=True)
        var = mx.var(x, axis=(1, 2), keepdims=True)
        return (x - mean) * mx.rsqrt(var + eps)

    in_dtype = x.dtype
    x32 = x.astype(mx.float32)
    mean = mx.mean(x32, axis=(1, 2), keepdims=True)
    var = mx.var(x32, axis=(1, 2), keepdims=True)
    out = (x32 - mean) * mx.rsqrt(var + eps)
    return out.astype(in_dtype)


class SPADE(nn.Module):
    def __init__(self, norm_nc: int, label_nc: int, hidden: int = 128):
        super().__init__()
        # We use a manual instance-norm path (param-free) so we can upcast
        # the reductions to fp32 even when the rest of the model is fp16.
        # mlp_shared is a Sequential of (Conv2d, ReLU); ReLU is parameter-free
        # so the checkpoint only stores the Conv2d parameters at "mlp_shared.0.*".
        self.mlp_shared = [nn.Conv2d(label_nc, hidden, kernel_size=3, padding=1)]
        self.mlp_gamma = nn.Conv2d(hidden, norm_nc, kernel_size=3, padding=1)
        self.mlp_beta = nn.Conv2d(hidden, norm_nc, kernel_size=3, padding=1)

    def __call__(self, x: mx.array, segmap: mx.array) -> mx.array:
        normalized = _instance_norm_fp32(x)
        # Nearest-neighbor resize segmap to x's spatial size.
        n_x, h_x, w_x, _ = x.shape
        n_s, h_s, w_s, _ = segmap.shape
        if (h_x, w_x) != (h_s, w_s):
            assert h_x % h_s == 0 and w_x % w_s == 0, "non-integer SPADE upscale"
            factor_h = h_x // h_s
            factor_w = w_x // w_s
            assert factor_h == factor_w, "non-square SPADE upscale"
            segmap = _nearest_upsample_nhwc(segmap, factor_h)
        actv = self.mlp_shared[0](segmap)
        actv = nn.relu(actv)
        gamma = self.mlp_gamma(actv)
        beta = self.mlp_beta(actv)
        return normalized * (1 + gamma) + beta


class SPADEResnetBlock(nn.Module):
    def __init__(self, fin: int, fout: int, label_nc: int):
        super().__init__()
        self.learned_shortcut = fin != fout
        fmiddle = min(fin, fout)
        self.conv_0 = nn.Conv2d(fin, fmiddle, kernel_size=3, padding=1)
        self.conv_1 = nn.Conv2d(fmiddle, fout, kernel_size=3, padding=1)
        if self.learned_shortcut:
            self.conv_s = nn.Conv2d(fin, fout, kernel_size=1, bias=False)
        self.norm_0 = SPADE(fin, label_nc)
        self.norm_1 = SPADE(fmiddle, label_nc)
        if self.learned_shortcut:
            self.norm_s = SPADE(fin, label_nc)

    def __call__(self, x, seg):
        # When the residual stream is in fp16, conv accumulation can overflow
        # past G_middle_4 (activations exceed sqrt(fp16 max ~ 256) per element
        # for a 9-tap conv). Run the inner block ops in fp32 and cast back at
        # the residual sum. fp32 reductions also keep InstanceNorm stable.
        in_dtype = x.dtype
        upcast = in_dtype in (mx.float16,)
        x32 = x.astype(mx.float32) if upcast else x
        seg32 = seg.astype(mx.float32) if upcast else seg
        if self.learned_shortcut:
            x_s_in = self.norm_s(x32, seg32)
            if (
                _SPADE_SHORTCUT_BACKEND == "tensorops"
                and x_s_in.dtype in (mx.float16, mx.bfloat16)
                and self.conv_s.weight.shape[0] >= _SPADE_SHORTCUT_MIN_OUT
            ):
                x_s = conv2d_1x1_tensorops(x_s_in, self.conv_s.weight, getattr(self.conv_s, "bias", None))
            else:
                x_s = self.conv_s(x_s_in)
        else:
            x_s = x32
        dx = self.conv_0(nn.leaky_relu(self.norm_0(x32, seg32), 2e-1))
        dx = self.conv_1(nn.leaky_relu(self.norm_1(dx, seg32), 2e-1))
        out = x_s + dx
        return out.astype(in_dtype) if upcast else out


class SPADEDecoder(nn.Module):
    """Mirror of upstream src.modules.spade_generator.SPADEDecoder."""

    def __init__(
        self,
        upscale: int = 1,
        max_features: int = 256,
        block_expansion: int = 64,
        out_channels: int = 64,
        num_down_blocks: int = 2,
    ):
        super().__init__()
        # Upstream computes input_channels in a loop that always lands on
        # min(max_features, block_expansion * 2 ** num_down_blocks). We just
        # mirror that explicitly here.
        input_channels = min(max_features, block_expansion * (2 ** num_down_blocks))
        label_nc = input_channels
        self.upscale = upscale

        self.fc = nn.Conv2d(input_channels, 2 * input_channels, kernel_size=3, padding=1)

        self.G_middle_0 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.G_middle_1 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.G_middle_2 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.G_middle_3 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.G_middle_4 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.G_middle_5 = SPADEResnetBlock(2 * input_channels, 2 * input_channels, label_nc)
        self.up_0 = SPADEResnetBlock(2 * input_channels, input_channels, label_nc)
        self.up_1 = SPADEResnetBlock(input_channels, out_channels, label_nc)

        if upscale is None or upscale <= 1:
            self.conv_img = nn.Conv2d(out_channels, 3, kernel_size=3, padding=1)
            self._use_pixelshuffle = False
        else:
            # Sequential(Conv2d -> PixelShuffle(2)) in PyTorch maps to keys
            # `conv_img.0.weight/bias`. Mirror that here as a plain list.
            self.conv_img = [
                nn.Conv2d(out_channels, 3 * (2 * 2), kernel_size=3, padding=1),
            ]
            self._use_pixelshuffle = True

    def __call__(self, feature: mx.array) -> mx.array:
        # feature: NHWC, e.g. (N, 64, 64, 256)
        seg = feature
        x = self.fc(feature)
        x = self.G_middle_0(x, seg)
        x = self.G_middle_1(x, seg)
        x = self.G_middle_2(x, seg)
        x = self.G_middle_3(x, seg)
        x = self.G_middle_4(x, seg)
        x = self.G_middle_5(x, seg)
        x = _nearest_upsample_nhwc(x, 2)
        x = self.up_0(x, seg)
        x = _nearest_upsample_nhwc(x, 2)
        x = self.up_1(x, seg)

        if self._use_pixelshuffle:
            x = self.conv_img[0](nn.leaky_relu(x, 2e-1))
            x = _pixel_shuffle_nhwc(x, 2)
        else:
            x = self.conv_img(nn.leaky_relu(x, 2e-1))
        return mx.sigmoid(x)
