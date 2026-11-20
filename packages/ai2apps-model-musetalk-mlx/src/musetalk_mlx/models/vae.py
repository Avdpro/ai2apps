"""MLX port of the SD AutoencoderKL (stabilityai/sd-vae-ft-mse) used by MuseTalk.

Isomorphic to diffusers `AutoencoderKL` (module/param names mirror the state_dict).
Everything runs **channels-last (NHWC)** internally — MLX-native conv layout — with
NCHW<->NHWC transposes only at the public encode/decode boundary.

Reference: musetalk/models/vae.py (wraps diffusers.AutoencoderKL) @ commit 0a89dec.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from ..config import VAE_CONFIG, VAE_SCALING_FACTOR

GN_EPS = 1e-6  # diffusers VAE GroupNorm eps (NOT 1e-5)


# --------------------------------------------------------------------------- #
# building blocks (names mirror diffusers)
# --------------------------------------------------------------------------- #
class ResnetBlock2D(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, groups: int = 32):
        super().__init__()
        self.norm1 = nn.GroupNorm(groups, in_ch, eps=GN_EPS, pytorch_compatible=True)
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, padding=1)
        self.norm2 = nn.GroupNorm(groups, out_ch, eps=GN_EPS, pytorch_compatible=True)
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, padding=1)
        self.conv_shortcut = nn.Conv2d(in_ch, out_ch, 1) if in_ch != out_ch else None

    def __call__(self, x):
        h = self.conv1(nn.silu(self.norm1(x)))
        h = self.conv2(nn.silu(self.norm2(h)))
        if self.conv_shortcut is not None:
            x = self.conv_shortcut(x)
        return x + h


class Downsample2D(nn.Module):
    # diffusers: asymmetric pad (0,1,0,1) then stride-2 conv, padding=0
    def __init__(self, ch: int):
        super().__init__()
        self.conv = nn.Conv2d(ch, ch, 3, stride=2, padding=0)

    def __call__(self, x):
        x = mx.pad(x, [(0, 0), (0, 1), (0, 1), (0, 0)])  # NHWC: pad H,W bottom/right
        return self.conv(x)


class Upsample2D(nn.Module):
    # diffusers: nearest x2 then stride-1 conv padding=1
    def __init__(self, ch: int):
        super().__init__()
        self.conv = nn.Conv2d(ch, ch, 3, padding=1)

    def __call__(self, x):
        b, h, w, c = x.shape
        x = mx.broadcast_to(x[:, :, None, :, None, :], (b, h, 2, w, 2, c)).reshape(
            b, h * 2, w * 2, c
        )
        return self.conv(x)


class Attention(nn.Module):
    """Single-head spatial self-attention (VAE mid block). residual_connection=True."""

    def __init__(self, ch: int, groups: int = 32):
        super().__init__()
        self.ch = ch
        self.group_norm = nn.GroupNorm(groups, ch, eps=GN_EPS, pytorch_compatible=True)
        self.to_q = nn.Linear(ch, ch)
        self.to_k = nn.Linear(ch, ch)
        self.to_v = nn.Linear(ch, ch)
        self.to_out = [nn.Linear(ch, ch)]  # to_out.0 (to_out.1 = dropout, omitted)

    def __call__(self, x):
        b, h, w, c = x.shape
        res = x
        y = self.group_norm(x).reshape(b, h * w, c)  # (B, HW, C)
        q, k, v = self.to_q(y), self.to_k(y), self.to_v(y)
        scale = 1.0 / (c**0.5)  # dim_head = C (single head)
        attn = mx.softmax((q @ k.transpose(0, 2, 1)) * scale, axis=-1)
        y = attn @ v
        y = self.to_out[0](y).reshape(b, h, w, c)
        return y + res


class MidBlock(nn.Module):
    def __init__(self, ch: int):
        super().__init__()
        self.resnets = [ResnetBlock2D(ch, ch), ResnetBlock2D(ch, ch)]
        self.attentions = [Attention(ch)]

    def __call__(self, x):
        x = self.resnets[0](x)
        x = self.attentions[0](x)
        x = self.resnets[1](x)
        return x


class DownBlock(nn.Module):
    def __init__(self, in_ch, out_ch, n_res, add_downsample):
        super().__init__()
        self.resnets = [
            ResnetBlock2D(in_ch if i == 0 else out_ch, out_ch) for i in range(n_res)
        ]
        self.downsamplers = [Downsample2D(out_ch)] if add_downsample else None

    def __call__(self, x):
        for r in self.resnets:
            x = r(x)
        if self.downsamplers is not None:
            x = self.downsamplers[0](x)
        return x


class UpBlock(nn.Module):
    def __init__(self, in_ch, out_ch, n_res, add_upsample):
        super().__init__()
        self.resnets = [
            ResnetBlock2D(in_ch if i == 0 else out_ch, out_ch) for i in range(n_res)
        ]
        self.upsamplers = [Upsample2D(out_ch)] if add_upsample else None

    def __call__(self, x):
        for r in self.resnets:
            x = r(x)
        if self.upsamplers is not None:
            x = self.upsamplers[0](x)
        return x


# --------------------------------------------------------------------------- #
# encoder / decoder
# --------------------------------------------------------------------------- #
class Encoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        boc = cfg["block_out_channels"]  # [128,256,512,512]
        n_res = cfg["layers_per_block"]
        self.conv_in = nn.Conv2d(cfg["in_channels"], boc[0], 3, padding=1)
        self.down_blocks = []
        in_ch = boc[0]
        for i, out_ch in enumerate(boc):
            self.down_blocks.append(
                DownBlock(in_ch, out_ch, n_res, add_downsample=(i != len(boc) - 1))
            )
            in_ch = out_ch
        self.mid_block = MidBlock(boc[-1])
        self.conv_norm_out = nn.GroupNorm(
            cfg["norm_num_groups"], boc[-1], eps=GN_EPS, pytorch_compatible=True
        )
        self.conv_out = nn.Conv2d(boc[-1], 2 * cfg["latent_channels"], 3, padding=1)

    def __call__(self, x):
        x = self.conv_in(x)
        for b in self.down_blocks:
            x = b(x)
        x = self.mid_block(x)
        x = self.conv_out(nn.silu(self.conv_norm_out(x)))
        return x


class Decoder(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        boc = cfg["block_out_channels"]
        rev = list(reversed(boc))  # [512,512,256,128]
        n_res = cfg["layers_per_block"] + 1
        self.conv_in = nn.Conv2d(cfg["latent_channels"], rev[0], 3, padding=1)
        self.mid_block = MidBlock(rev[0])
        self.up_blocks = []
        in_ch = rev[0]
        for i, out_ch in enumerate(rev):
            self.up_blocks.append(
                UpBlock(in_ch, out_ch, n_res, add_upsample=(i != len(rev) - 1))
            )
            in_ch = out_ch
        self.conv_norm_out = nn.GroupNorm(
            cfg["norm_num_groups"], rev[-1], eps=GN_EPS, pytorch_compatible=True
        )
        self.conv_out = nn.Conv2d(rev[-1], cfg["out_channels"], 3, padding=1)

    def __call__(self, x):
        x = self.conv_in(x)
        x = self.mid_block(x)
        for b in self.up_blocks:
            x = b(x)
        x = self.conv_out(nn.silu(self.conv_norm_out(x)))
        return x


class DiagonalGaussian:
    def __init__(self, moments_nchw):  # moments: (B,8,H,W) NCHW
        self.mean, self.logvar = mx.split(moments_nchw, 2, axis=1)
        self.logvar = mx.clip(self.logvar, -30.0, 20.0)
        self.std = mx.exp(0.5 * self.logvar)

    def sample(self, key=None):
        noise = mx.random.normal(self.mean.shape, key=key)
        return self.mean + self.std * noise


# --------------------------------------------------------------------------- #
# top-level AutoencoderKL
# --------------------------------------------------------------------------- #
class AutoencoderKL(nn.Module):
    def __init__(self, cfg=VAE_CONFIG, scaling_factor=VAE_SCALING_FACTOR):
        super().__init__()
        self.encoder = Encoder(cfg)
        self.decoder = Decoder(cfg)
        lc = cfg["latent_channels"]
        self.quant_conv = nn.Conv2d(2 * lc, 2 * lc, 1)
        self.post_quant_conv = nn.Conv2d(lc, lc, 1)
        self.scaling_factor = scaling_factor

    # ---- NHWC core (for parity tests / internal use) ----
    def encode_moments(self, x_nhwc):
        return self.quant_conv(self.encoder(x_nhwc))

    def decode_nhwc(self, z_nhwc):
        return self.decoder(self.post_quant_conv(z_nhwc))

    # ---- NCHW public API (matches diffusers/MuseTalk tensor layout) ----
    def encode(self, x_nchw) -> DiagonalGaussian:
        x = x_nchw.transpose(0, 2, 3, 1)
        moments_nhwc = self.encode_moments(x)
        return DiagonalGaussian(moments_nhwc.transpose(0, 3, 1, 2))  # -> NCHW

    def decode(self, z_nchw):
        z = z_nchw.transpose(0, 2, 3, 1)
        return self.decode_nhwc(z).transpose(0, 3, 1, 2)
