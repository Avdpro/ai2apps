"""Learned spatial x2 latent upsampling and SoL's AdaIN conditioning."""

import mlx.core as mx

from .precision import silu
from .weights import conv_layout, load_component


def adain(x, reference):
    axes = (2, 3, 4)

    def stats(z):
        n = z.shape[2] * z.shape[3] * z.shape[4]
        if n < 2:
            raise ValueError(
                "AdaIN requires at least two latent spatial/temporal values"
            )
        mean = mx.mean(z.astype(mx.float32), axis=axes, keepdims=True).astype(z.dtype)
        std = mx.sqrt(
            mx.var(z.astype(mx.float32), axis=axes, keepdims=True) * n / (n - 1)
        ).astype(z.dtype)
        return mean, std

    mean, std = stats(x)
    rm, rs = stats(reference)
    if bool(mx.any(std == 0).item()):
        raise ValueError("Zero variance in upsampled latent")
    return ((x - mean) / std) * rs + rm


class LatentUpsampler:
    def __init__(self, root):
        self.w = {
            k: conv_layout(v)
            for k, v in load_component(root, "latent_upsampler").items()
        }

    def conv(self, x, name):
        w = self.w[name + ".weight"]
        op = mx.conv3d if w.ndim == 5 else mx.conv2d
        return op(x, w, padding=1) + self.w[name + ".bias"]

    def norm(self, x, name):
        # PyTorch GroupNorm reduces all spatial positions within each channel group.
        shape = x.shape
        b = shape[0]
        c = shape[-1]
        y = x.astype(mx.float32).reshape(b, -1, 32, c // 32)
        mean = mx.mean(y, axis=(1, 3), keepdims=True)
        var = mx.var(y, axis=(1, 3), keepdims=True)
        y = ((y - mean) * mx.rsqrt(var + 1e-5)).reshape(shape)
        return (
            y * self.w[name + ".weight"].astype(mx.float32)
            + self.w[name + ".bias"].astype(mx.float32)
        ).astype(x.dtype)

    def blocks(self, x, prefix):
        for i in range(4):
            p = f"{prefix}.{i}"
            y = silu(self.norm(self.conv(x, p + ".conv1"), p + ".norm1"))
            x = silu(self.norm(self.conv(y, p + ".conv2"), p + ".norm2") + x)
            mx.eval(x)
        return x

    def __call__(self, raw):
        x = raw.transpose(0, 2, 3, 4, 1)
        x = silu(self.norm(self.conv(x, "initial_conv"), "initial_norm"))
        x = self.blocks(x, "res_blocks")
        b, t, h, w, c = x.shape
        x = self.conv(x.reshape(b * t, h, w, c), "upsampler.0")
        x = (
            x.reshape(b, t, h, w, c, 2, 2)
            .transpose(0, 1, 2, 5, 3, 6, 4)
            .reshape(b, t, h * 2, w * 2, c)
        )
        x = self.blocks(x, "post_upsample_res_blocks")
        return self.conv(x, "final_conv").transpose(0, 4, 1, 2, 3)
