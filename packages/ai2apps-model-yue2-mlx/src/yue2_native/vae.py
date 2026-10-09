"""FP32 Oobleck decoder port. NLC layout, folded weight norm, exact halo crops.

Derived from YuE2 / stable-audio-tools (Apache-2.0 / MIT), see notices.
"""

import json
import math
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np


class Snake(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.alpha = mx.zeros(channels)
        self.beta = mx.zeros(channels)

    def __call__(self, x):
        return x + mx.sin(x * mx.exp(self.alpha)) ** 2 / (mx.exp(self.beta) + 1e-9)


class Residual(nn.Module):
    def __init__(self, c, dilation, activation):
        super().__init__()
        self.layers = [
            activation(c),
            nn.Conv1d(c, c, 7, padding=3 * dilation, dilation=dilation),
            activation(c),
            nn.Conv1d(c, c, 1),
        ]

    def __call__(self, x):
        h = x
        for f in self.layers:
            h = f(h)
        return x + h


class Block(nn.Module):
    def __init__(self, ci, co, stride, activation):
        super().__init__()
        self.layers = [
            activation(ci),
            nn.ConvTranspose1d(
                ci, co, 2 * stride, stride=stride, padding=math.ceil(stride / 2)
            ),
            Residual(co, 1, activation),
            Residual(co, 3, activation),
            Residual(co, 9, activation),
        ]

    def __call__(self, x):
        for f in self.layers:
            x = f(x)
        return x


class Decoder(nn.Module):
    def __init__(self, c):
        super().__init__()
        if any(
            c.get(k, False)
            for k in ("antialias_activation", "use_nearest_upsample", "use_filter")
        ):
            raise ValueError("Unsupported VAE feature")
        if c.get("snake_type", "vanilla") != "vanilla":
            raise ValueError("Unsupported Snake variant")
        channels = c["channels"]
        mult = [1] + c["c_mults"]
        strides = c["strides"]
        activation = Snake if c.get("use_snake") else lambda _: nn.ELU()
        self.layers = [nn.Conv1d(c["latent_dim"], channels * mult[-1], 7, padding=3)]
        for i in range(len(mult) - 1, 0, -1):
            self.layers.append(
                Block(
                    mult[i] * channels,
                    mult[i - 1] * channels,
                    strides[i - 1],
                    activation,
                )
            )
        self.layers.extend(
            [
                activation(channels),
                nn.Conv1d(channels, c["out_channels"], 7, padding=3, bias=False),
                nn.Tanh() if c.get("final_tanh", True) else nn.Identity(),
            ]
        )

    def __call__(self, x):
        for f in self.layers:
            x = f(x)
            mx.eval(x)
        return x


def sequence(m):
    return m if isinstance(m, list) else getattr(m, "layers", None)


def interval(m, lo, hi):
    if isinstance(m, Residual):
        a, b = interval(m.layers, lo, hi)
        return min(a, lo), max(b, hi)
    seq = sequence(m)
    if seq is not None:
        for f in reversed(seq):
            lo, hi = interval(f, lo, hi)
    elif isinstance(m, nn.ConvTranspose1d):
        s, p, d, k = m.stride, m.padding, m.dilation, m.weight.shape[1]
        lo, hi = -(-(lo + p - d * (k - 1)) // s), (hi + p) // s
    elif isinstance(m, nn.Conv1d):
        s, p, d, k = m.stride, m.padding, m.dilation, m.weight.shape[1]
        lo, hi = lo * s - p, hi * s - p + d * (k - 1)
    return lo, hi


def length(m, n):
    if isinstance(m, Residual):
        return n
    seq = sequence(m)
    if seq is not None:
        for f in seq:
            n = length(f, n)
    elif isinstance(m, nn.ConvTranspose1d):
        n = (
            (n - 1) * m.stride
            - 2 * m.padding
            + m.dilation * (m.weight.shape[1] - 1)
            + m.output_padding
            + 1
        )
    elif isinstance(m, nn.Conv1d):
        n = (
            n + 2 * m.padding - m.dilation * (m.weight.shape[1] - 1) - 1
        ) // m.stride + 1
    return n


class VAE(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.decoder = Decoder(config["decoder_config"])
        if (
            math.prod(config["decoder_config"]["strides"])
            != config["downsampling_ratio"]
        ):
            raise ValueError("VAE stride mismatch")

    @classmethod
    def load(cls, path):
        from safetensors import safe_open

        path = Path(path)
        model = cls(json.loads((path / "config.json").read_text()))
        state = {}
        for p in sorted(path.glob("*.safetensors")):
            with safe_open(p, framework="numpy") as f:
                for key in f.keys():  # noqa: SIM118 -- safetensors handle is not iterable
                    if key.startswith("decoder."):
                        if key in state:
                            raise ValueError("Duplicate VAE tensor")
                        state[key] = mx.array(f.get_tensor(key))
        mapped = {}
        transpose = {
            f"decoder.layers.{i}.layers.1"
            for i in range(1, len(model.config["decoder_config"]["strides"]) + 1)
        }
        for key, v in state.items():
            if v.dtype != mx.float32:
                raise ValueError("VAE must be FP32")
            if key.endswith(".weight_g"):
                continue
            if key.endswith(".weight_v"):
                prefix = key[:-9]
                g = state[prefix + ".weight_g"]
                v = v * (g / mx.sqrt(mx.sum(v * v, axis=(1, 2), keepdims=True)))
                v = (
                    v.transpose(1, 2, 0)
                    if prefix in transpose
                    else v.transpose(0, 2, 1)
                )
                key = prefix + ".weight"
            mapped[key] = v
        model.load_weights(list(mapped.items()), strict=True)
        mx.eval(model.parameters())
        return model

    def decode(self, z):
        z = mx.array(z, dtype=mx.float32)
        if z.ndim != 3 or z.shape[-1] != self.config["latent_dim"] or z.shape[1] < 1:
            raise ValueError("Expected NLC latent")
        if not bool(mx.all(mx.isfinite(z)).item()):
            raise ValueError("Nonfinite latent")
        return self.decoder(z)

    def decode_tiled(
        self, z, core_frames=256, halo_frames=16, cancelled=None, progress=None
    ):
        if type(core_frames) is not int or core_frames < 1:
            raise ValueError("Invalid tile size")
        ratio = self.config["downsampling_ratio"]
        lo, hi = interval(self.decoder, 0, core_frames * ratio - 1)
        required = max(0, -lo, hi - core_frames + 1)
        if type(halo_frames) is not int or halo_frames < required:
            raise ValueError(f"VAE halo must be at least {required}")
        z = mx.array(z, dtype=mx.float32)
        frames = z.shape[1]
        total = length(self.decoder, frames)
        audio = np.empty((z.shape[0], total, self.config["audio_channels"]), np.float32)
        for i, start in enumerate(range(0, frames, core_frames)):
            if cancelled and cancelled():
                raise InterruptedError("Cancelled during VAE")
            end = min(frames, start + core_frames)
            left = max(0, start - halo_frames)
            right = min(frames, end + halo_frames)
            tile = self.decode(z[:, left:right])
            a = start * ratio
            b = min(end * ratio, total)
            crop = tile[:, (start - left) * ratio : (start - left) * ratio + b - a]
            if crop.shape[1] != b - a:
                raise ValueError("VAE tile coverage mismatch")
            audio[:, a:b] = np.array(crop)
            del tile, crop
            mx.clear_cache()
            if progress:
                progress(i + 1, math.ceil(frames / core_frames))
        return audio
