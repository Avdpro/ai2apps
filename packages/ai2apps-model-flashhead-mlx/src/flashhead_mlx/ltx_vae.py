"""Native MLX LTX VAE for the exact FlashHead Lite VAE_LTX configuration.

Channels-last internal activations; public inputs and outputs are BCTHW.
"""

import json
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn

BLOCKS = [
    ("res", 4),
    ("down", 1),
    ("grow", 1),
    ("res", 3),
    ("down", 1),
    ("grow", 1),
    ("res", 3),
    ("down", 1),
    ("res", 3),
    ("res", 4),
]
RENAME = {
    "decoder.up_blocks.3.conv_in": "decoder.up_blocks.7",
    "decoder.up_blocks.3.upsamplers.0": "decoder.up_blocks.8",
    "decoder.up_blocks.3": "decoder.up_blocks.9",
    "decoder.up_blocks.2.upsamplers.0": "decoder.up_blocks.5",
    "decoder.up_blocks.2.conv_in": "decoder.up_blocks.4",
    "decoder.up_blocks.2": "decoder.up_blocks.6",
    "decoder.up_blocks.1.upsamplers.0": "decoder.up_blocks.2",
    "decoder.up_blocks.1": "decoder.up_blocks.3",
    "decoder.up_blocks.0": "decoder.up_blocks.1",
    "decoder.mid_block": "decoder.up_blocks.0",
    "encoder.down_blocks.3": "encoder.down_blocks.8",
    "encoder.down_blocks.2.downsamplers.0": "encoder.down_blocks.7",
    "encoder.down_blocks.2": "encoder.down_blocks.6",
    "encoder.down_blocks.1.downsamplers.0": "encoder.down_blocks.4",
    "encoder.down_blocks.1.conv_out": "encoder.down_blocks.5",
    "encoder.down_blocks.1": "encoder.down_blocks.3",
    "encoder.down_blocks.0.conv_out": "encoder.down_blocks.2",
    "encoder.down_blocks.0.downsamplers.0": "encoder.down_blocks.1",
    "encoder.down_blocks.0": "encoder.down_blocks.0",
    "encoder.mid_block": "encoder.down_blocks.9",
    "conv_shortcut.conv": "conv_shortcut",
    "resnets": "res_blocks",
    "norm3": "norm3.norm",
    "latents_mean": "per_channel_statistics.mean-of-means",
    "latents_std": "per_channel_statistics.std-of-means",
}


def pixel_norm(x):
    return x / mx.sqrt(mx.mean(x * x, axis=-1, keepdims=True) + 1e-8)


def patchify(x, patch=4):
    b, t, h, w, c = x.shape
    if h % patch or w % patch:
        raise ValueError("LTX spatial dimensions must divide the patch size")
    return (
        x.reshape(b, t, h // patch, patch, w // patch, patch, c)
        .transpose(0, 1, 2, 4, 6, 5, 3)
        .reshape(b, t, h // patch, w // patch, c * patch * patch)
    )


def unpatchify(x, patch=4):
    b, t, h, w, c = x.shape
    return (
        x.reshape(b, t, h, w, c // (patch * patch), patch, patch)
        .transpose(0, 1, 2, 6, 3, 5, 4)
        .reshape(b, t, h * patch, w * patch, c // (patch * patch))
    )


class CausalConv3d(nn.Module):
    def __init__(self, inputs, outputs, stride=1):
        super().__init__()
        self.conv = nn.Conv3d(inputs, outputs, 3, stride=stride, padding=(0, 1, 1))

    def __call__(self, x, causal=True):
        if causal:
            x = mx.concatenate([mx.repeat(x[:, :1], 2, axis=1), x], axis=1)
        else:
            x = mx.concatenate([x[:, :1], x, x[:, -1:]], axis=1)
        return self.conv(x)


class LayerNorm(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.norm = nn.LayerNorm(channels, eps=1e-6)

    def __call__(self, x):
        return self.norm(x)


class ResnetBlock3D(nn.Module):
    def __init__(self, inputs, outputs=None):
        super().__init__()
        outputs = outputs or inputs
        self.conv1 = CausalConv3d(inputs, outputs)
        self.conv2 = CausalConv3d(outputs, outputs)
        self.norm3 = LayerNorm(inputs) if inputs != outputs else nn.Identity()
        self.conv_shortcut = (
            nn.Conv3d(inputs, outputs, 1) if inputs != outputs else nn.Identity()
        )

    def __call__(self, x, causal=True):
        h = self.conv1(nn.silu(pixel_norm(x)), causal)
        h = self.conv2(nn.silu(pixel_norm(h)), causal)
        return h + self.conv_shortcut(self.norm3(x))


class MidBlock(nn.Module):
    def __init__(self, channels, layers):
        super().__init__()
        self.res_blocks = [ResnetBlock3D(channels) for _ in range(layers)]

    def __call__(self, x, causal=True):
        for block in self.res_blocks:
            x = block(x, causal)
        return x


class Upsample(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv = CausalConv3d(channels, channels * 8)

    def __call__(self, x, causal=True):
        x = self.conv(x, causal)
        b, t, h, w, c = x.shape
        x = (
            x.reshape(b, t, h, w, c // 8, 2, 2, 2)
            .transpose(0, 1, 5, 2, 6, 3, 7, 4)
            .reshape(b, t * 2, h * 2, w * 2, c // 8)
        )
        return x[:, 1:]


class Encoder(nn.Module):
    def __init__(self, base=128, latent=128, blocks=BLOCKS):
        super().__init__()
        self.conv_in = CausalConv3d(48, base)
        channels = base
        self.down_blocks = []
        for kind, count in blocks:
            if kind == "res":
                layer = MidBlock(channels, count)
            elif kind == "down":
                layer = CausalConv3d(channels, channels, stride=2)
            elif kind == "grow":
                layer = ResnetBlock3D(channels, channels * 2)
                channels *= 2
            else:
                raise ValueError(kind)
            self.down_blocks.append(layer)
        self.conv_out = CausalConv3d(channels, latent + 1)

    def __call__(self, x):
        x = self.conv_in(patchify(x))
        for block in self.down_blocks:
            x = block(x)
        x = self.conv_out(nn.silu(pixel_norm(x)))
        return x[..., :-1], mx.repeat(x[..., -1:], x.shape[-1] - 1, axis=-1)


class Decoder(nn.Module):
    def __init__(self, base=128, latent=128, blocks=BLOCKS):
        super().__init__()
        channels = base * 2 ** sum(k == "grow" for k, _ in blocks)
        self.conv_in = CausalConv3d(latent, channels)
        self.up_blocks = []
        for kind, count in reversed(blocks):
            if kind == "res":
                layer = MidBlock(channels, count)
            elif kind == "down":
                layer = Upsample(channels)
            elif kind == "grow":
                layer = ResnetBlock3D(channels, channels // 2)
                channels //= 2
            else:
                raise ValueError(kind)
            self.up_blocks.append(layer)
        self.conv_out = CausalConv3d(channels, 48)

    def __call__(self, x):
        x = self.conv_in(x, False)
        for block in self.up_blocks:
            x = block(x, False)
        return unpatchify(self.conv_out(nn.silu(pixel_norm(x)), False))


class LtxVAE(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = Encoder()
        self.decoder = Decoder()
        self.per_channel_statistics = {
            "mean-of-means": mx.zeros((128,)),
            "std-of-means": mx.ones((128,)),
        }

    @classmethod
    def from_pretrained(cls, path, dtype=mx.bfloat16):
        path = Path(path)
        config = json.loads((path / "config.json").read_text())
        required = {
            "latent_channels": 128,
            "patch_size": 4,
            "encoder_causal": True,
            "decoder_causal": False,
            "block_out_channels": [128, 256, 512, 512],
            "layers_per_block": [4, 3, 3, 3, 4],
        }
        if any(config.get(k) != v for k, v in required.items()):
            raise ValueError(
                "This implementation requires the pinned FlashHead LTX VAE configuration"
            )
        raw = mx.load(str(path / "diffusion_pytorch_model.safetensors"))
        weights = {}
        for key, value in raw.items():
            for old, new in RENAME.items():
                key = key.replace(old, new)
            if value.ndim == 5 and key.endswith(".weight"):
                value = value.transpose(0, 2, 3, 4, 1)
            weights[key] = value.astype(dtype)
        model = cls()
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mx.eval(model.parameters())
        return model

    def encode(self, video, *, noise=None, sample=True):
        if (
            video.ndim != 5
            or video.shape[1] != 3
            or (video.shape[2] - 1) % 8
            or video.shape[3] % 32
            or video.shape[4] % 32
        ):
            raise ValueError("LTX expects B,3,(8N+1),32H,32W video")
        mean, logvar = self.encoder(video.transpose(0, 2, 3, 4, 1))
        if sample:
            noise = (
                mx.random.normal(mean.shape).astype(mean.dtype)
                if noise is None
                else noise.transpose(0, 2, 3, 4, 1)
            )
            mean = mean + mx.exp(0.5 * mx.clip(logvar, -30, 20)) * noise
        stats = self.per_channel_statistics
        return ((mean - stats["mean-of-means"]) / stats["std-of-means"]).transpose(
            0, 4, 1, 2, 3
        )

    def decode(self, latent):
        stats = self.per_channel_statistics
        x = (
            latent.transpose(0, 2, 3, 4, 1) * stats["std-of-means"]
            + stats["mean-of-means"]
        )
        return self.decoder(x).transpose(0, 4, 1, 2, 3)
