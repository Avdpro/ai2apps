"""MLX port of the MuseTalk v1.5 UNet (diffusers UNet2DConditionModel, SD1.x topology).

in=8 (masked⊕ref latent), out=4, cross_attention_dim=384 (whisper audio), 8 attention
heads everywhere (attention_head_dim=8 is a NUM-HEADS misnomer; head_dim = ch//8).
Single-step inpainting: called at fixed timestep 0, but the time-embedding path still runs.

Isomorphic to the diffusers state_dict names. NHWC internally (MLX conv), NCHW public API.

Reference: musetalk/models/unet.py (wraps diffusers) + scripts/inference.py @ 0a89dec.
"""

from __future__ import annotations

import math

import mlx.core as mx
import mlx.nn as nn

from ..config import UNET_CONFIG

RESNET_EPS = 1e-5  # norm_eps (resnets + conv_norm_out)
TF_GN_EPS = 1e-6  # Transformer2DModel group_norm
N_HEADS = 8  # constant across the net (resolved empirically from the checkpoint)


# --------------------------------------------------------------------------- #
# timestep embedding
# --------------------------------------------------------------------------- #
def get_timestep_embedding(
    timesteps, dim, flip_sin_to_cos=True, downscale_freq_shift=1.0, max_period=10000
):
    half = dim // 2
    exponent = -math.log(max_period) * mx.arange(half, dtype=mx.float32)
    exponent = exponent / (half - downscale_freq_shift)
    emb = mx.exp(exponent)
    emb = timesteps.astype(mx.float32)[:, None] * emb[None, :]
    emb = mx.concatenate([mx.sin(emb), mx.cos(emb)], axis=-1)
    if flip_sin_to_cos:
        emb = mx.concatenate([emb[:, half:], emb[:, :half]], axis=-1)
    return emb


class TimestepEmbedding(nn.Module):
    def __init__(self, in_dim, time_dim):
        super().__init__()
        self.linear_1 = nn.Linear(in_dim, time_dim)
        self.linear_2 = nn.Linear(time_dim, time_dim)

    def __call__(self, x):
        return self.linear_2(nn.silu(self.linear_1(x)))


# --------------------------------------------------------------------------- #
# resnet / sampling
# --------------------------------------------------------------------------- #
class ResnetBlock2D(nn.Module):
    def __init__(self, in_ch, out_ch, time_dim, groups=32):
        super().__init__()
        self.norm1 = nn.GroupNorm(
            groups, in_ch, eps=RESNET_EPS, pytorch_compatible=True
        )
        self.conv1 = nn.Conv2d(in_ch, out_ch, 3, padding=1)
        self.time_emb_proj = nn.Linear(time_dim, out_ch)
        self.norm2 = nn.GroupNorm(
            groups, out_ch, eps=RESNET_EPS, pytorch_compatible=True
        )
        self.conv2 = nn.Conv2d(out_ch, out_ch, 3, padding=1)
        self.conv_shortcut = nn.Conv2d(in_ch, out_ch, 1) if in_ch != out_ch else None

    def __call__(self, x, temb):
        h = self.conv1(nn.silu(self.norm1(x)))
        h = h + self.time_emb_proj(nn.silu(temb))[:, None, None, :]  # NHWC broadcast
        h = self.conv2(nn.silu(self.norm2(h)))
        if self.conv_shortcut is not None:
            x = self.conv_shortcut(x)
        return x + h


class Downsample2D(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.conv = nn.Conv2d(
            ch, ch, 3, stride=2, padding=1
        )  # symmetric pad (UNet, unlike VAE)

    def __call__(self, x):
        return self.conv(x)


class Upsample2D(nn.Module):
    def __init__(self, ch):
        super().__init__()
        self.conv = nn.Conv2d(ch, ch, 3, padding=1)

    def __call__(self, x):
        b, h, w, c = x.shape
        x = mx.broadcast_to(x[:, :, None, :, None, :], (b, h, 2, w, 2, c)).reshape(
            b, h * 2, w * 2, c
        )
        return self.conv(x)


# --------------------------------------------------------------------------- #
# attention / transformer
# --------------------------------------------------------------------------- #
class CrossAttention(nn.Module):
    def __init__(self, query_dim, cross_dim=None, heads=N_HEADS):
        super().__init__()
        cross_dim = cross_dim or query_dim
        self.heads = heads
        self.dim_head = query_dim // heads
        self.scale = self.dim_head**-0.5
        self.to_q = nn.Linear(query_dim, query_dim, bias=False)
        self.to_k = nn.Linear(cross_dim, query_dim, bias=False)
        self.to_v = nn.Linear(cross_dim, query_dim, bias=False)
        self.to_out = [nn.Linear(query_dim, query_dim)]  # to_out.0 (to_out.1 = dropout)

    def _split(self, x):
        b, n, _ = x.shape
        return x.reshape(b, n, self.heads, self.dim_head).transpose(0, 2, 1, 3)

    def __call__(self, x, context=None):
        context = x if context is None else context
        q, k, v = self.to_q(x), self.to_k(context), self.to_v(context)
        q, k, v = self._split(q), self._split(k), self._split(v)
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)
        b, h, n, d = out.shape
        out = out.transpose(0, 2, 1, 3).reshape(b, n, h * d)
        return self.to_out[0](out)


class GEGLU(nn.Module):
    def __init__(self, dim_in, dim_out):
        super().__init__()
        self.proj = nn.Linear(dim_in, dim_out * 2)

    def __call__(self, x):
        x, gate = mx.split(self.proj(x), 2, axis=-1)
        return x * nn.gelu(gate)


class FeedForward(nn.Module):
    def __init__(self, dim, mult=4):
        super().__init__()
        inner = dim * mult
        self.net = [
            GEGLU(dim, inner),
            nn.Dropout(0.0),
            nn.Linear(inner, dim),
        ]  # net.0, (net.1), net.2

    def __call__(self, x):
        return self.net[2](self.net[0](x))


class BasicTransformerBlock(nn.Module):
    def __init__(self, dim, cross_dim, heads=N_HEADS):
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn1 = CrossAttention(dim, None, heads)  # self-attn
        self.norm2 = nn.LayerNorm(dim)
        self.attn2 = CrossAttention(dim, cross_dim, heads)  # cross-attn (audio)
        self.norm3 = nn.LayerNorm(dim)
        self.ff = FeedForward(dim)

    def __call__(self, x, context):
        x = self.attn1(self.norm1(x)) + x
        x = self.attn2(self.norm2(x), context) + x
        x = self.ff(self.norm3(x)) + x
        return x


class Transformer2DModel(nn.Module):
    def __init__(self, ch, cross_dim, n_blocks=1, groups=32):
        super().__init__()
        self.norm = nn.GroupNorm(groups, ch, eps=TF_GN_EPS, pytorch_compatible=True)
        self.proj_in = nn.Conv2d(ch, ch, 1)
        self.transformer_blocks = [
            BasicTransformerBlock(ch, cross_dim) for _ in range(n_blocks)
        ]
        self.proj_out = nn.Conv2d(ch, ch, 1)

    def __call__(self, x, context):
        b, h, w, c = x.shape
        res = x
        y = self.proj_in(self.norm(x)).reshape(b, h * w, c)
        for blk in self.transformer_blocks:
            y = blk(y, context)
        y = self.proj_out(y.reshape(b, h, w, c))
        return y + res


# --------------------------------------------------------------------------- #
# down / up blocks
# --------------------------------------------------------------------------- #
class DownBlock2D(nn.Module):
    def __init__(
        self, in_ch, out_ch, time_dim, n_layers, add_downsample, cross_dim=None
    ):
        super().__init__()
        self.has_cross = cross_dim is not None
        self.resnets = [
            ResnetBlock2D(in_ch if i == 0 else out_ch, out_ch, time_dim)
            for i in range(n_layers)
        ]
        self.attentions = (
            [Transformer2DModel(out_ch, cross_dim) for _ in range(n_layers)]
            if self.has_cross
            else None
        )
        self.downsamplers = [Downsample2D(out_ch)] if add_downsample else None

    def __call__(self, x, temb, context):
        res_samples = ()
        for i, resnet in enumerate(self.resnets):
            x = resnet(x, temb)
            if self.attentions is not None:
                x = self.attentions[i](x, context)
            res_samples += (x,)
        if self.downsamplers is not None:
            x = self.downsamplers[0](x)
            res_samples += (x,)
        return x, res_samples


class UpBlock2D(nn.Module):
    def __init__(
        self, in_ch, prev_ch, out_ch, time_dim, n_layers, add_upsample, cross_dim=None
    ):
        super().__init__()
        self.has_cross = cross_dim is not None
        self.resnets = []
        for i in range(n_layers):
            res_skip = in_ch if i == n_layers - 1 else out_ch
            res_in = prev_ch if i == 0 else out_ch
            self.resnets.append(ResnetBlock2D(res_in + res_skip, out_ch, time_dim))
        self.attentions = (
            [Transformer2DModel(out_ch, cross_dim) for _ in range(n_layers)]
            if self.has_cross
            else None
        )
        self.upsamplers = [Upsample2D(out_ch)] if add_upsample else None

    def __call__(self, x, res_list, temb, context):
        for i, resnet in enumerate(self.resnets):
            x = mx.concatenate([x, res_list[i]], axis=-1)  # NHWC: concat channels
            x = resnet(x, temb)
            if self.attentions is not None:
                x = self.attentions[i](x, context)
        if self.upsamplers is not None:
            x = self.upsamplers[0](x)
        return x


class UNetMidBlock2DCrossAttn(nn.Module):
    def __init__(self, ch, time_dim, cross_dim):
        super().__init__()
        self.resnets = [
            ResnetBlock2D(ch, ch, time_dim),
            ResnetBlock2D(ch, ch, time_dim),
        ]
        self.attentions = [Transformer2DModel(ch, cross_dim)]

    def __call__(self, x, temb, context):
        x = self.resnets[0](x, temb)
        x = self.attentions[0](x, context)
        x = self.resnets[1](x, temb)
        return x


# --------------------------------------------------------------------------- #
# top-level UNet
# --------------------------------------------------------------------------- #
class UNet2DConditionModel(nn.Module):
    def __init__(self, cfg=UNET_CONFIG):
        super().__init__()
        boc = cfg["block_out_channels"]  # [320,640,1280,1280]
        n_layers = cfg["layers_per_block"]  # 2
        cross_dim = cfg["cross_attention_dim"]  # 384
        time_dim = boc[0] * 4  # 1280
        self.in_dim = boc[0]
        self.flip_sin_to_cos = cfg["flip_sin_to_cos"]
        self.freq_shift = cfg["freq_shift"]

        self.conv_in = nn.Conv2d(cfg["in_channels"], boc[0], 3, padding=1)
        self.time_embedding = TimestepEmbedding(boc[0], time_dim)

        # down blocks
        self.down_blocks = []
        out_ch = boc[0]
        for i, dbt in enumerate(cfg["down_block_types"]):
            in_ch = out_ch
            out_ch = boc[i]
            is_final = i == len(boc) - 1
            self.down_blocks.append(
                DownBlock2D(
                    in_ch,
                    out_ch,
                    time_dim,
                    n_layers,
                    add_downsample=not is_final,
                    cross_dim=cross_dim if "CrossAttn" in dbt else None,
                )
            )

        self.mid_block = UNetMidBlock2DCrossAttn(boc[-1], time_dim, cross_dim)

        # up blocks
        self.up_blocks = []
        rev = list(reversed(boc))  # [1280,1280,640,320]
        out_ch = rev[0]
        for i, ubt in enumerate(cfg["up_block_types"]):
            prev_ch = out_ch
            out_ch = rev[i]
            in_ch = rev[min(i + 1, len(boc) - 1)]
            is_final = i == len(boc) - 1
            self.up_blocks.append(
                UpBlock2D(
                    in_ch,
                    prev_ch,
                    out_ch,
                    time_dim,
                    n_layers + 1,
                    add_upsample=not is_final,
                    cross_dim=cross_dim if "CrossAttn" in ubt else None,
                )
            )

        self.conv_norm_out = nn.GroupNorm(
            cfg["norm_num_groups"], boc[0], eps=RESNET_EPS, pytorch_compatible=True
        )
        self.conv_out = nn.Conv2d(boc[0], cfg["out_channels"], 3, padding=1)

    def __call__(self, sample_nchw, timesteps, encoder_hidden_states):
        # timestep -> embedding (computed fp32, cast to model/sample dtype)
        t_emb = get_timestep_embedding(
            timesteps, self.in_dim, self.flip_sin_to_cos, 1.0
        )
        t_emb = t_emb.astype(sample_nchw.dtype)
        temb = self.time_embedding(t_emb)

        x = sample_nchw.transpose(0, 2, 3, 1)  # NCHW -> NHWC
        x = self.conv_in(x)
        res_samples = (x,)
        for down in self.down_blocks:
            x, res = down(x, temb, encoder_hidden_states)
            res_samples += res

        x = self.mid_block(x, temb, encoder_hidden_states)

        for up in self.up_blocks:
            n = len(up.resnets)
            res = list(res_samples[-n:])[::-1]  # pop n, reverse (deepest first)
            res_samples = res_samples[:-n]
            x = up(x, res, temb, encoder_hidden_states)

        x = self.conv_out(nn.silu(self.conv_norm_out(x)))
        return x.transpose(0, 3, 1, 2)  # NHWC -> NCHW
