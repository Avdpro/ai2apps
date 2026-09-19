"""Native MLX implementation of the RMVPE pitch estimator used by RVC."""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np


class ConvBlockRes(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = [
            nn.Conv2d(in_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm(out_channels, momentum=0.01),
            nn.ReLU(),
            nn.Conv2d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm(out_channels, momentum=0.01),
            nn.ReLU(),
        ]
        self.shortcut = (
            nn.Conv2d(in_channels, out_channels, 1)
            if in_channels != out_channels
            else None
        )

    def __call__(self, x: mx.array) -> mx.array:
        residual = x
        for layer in self.conv:
            x = layer(x)
        return x + (self.shortcut(residual) if self.shortcut is not None else residual)


class ResEncoderBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, n_blocks: int = 4):
        super().__init__()
        self.conv = [ConvBlockRes(in_channels, out_channels)] + [
            ConvBlockRes(out_channels, out_channels) for _ in range(n_blocks - 1)
        ]
        self.pool = nn.AvgPool2d((2, 2), stride=(2, 2))

    def __call__(self, x: mx.array) -> tuple[mx.array, mx.array]:
        for layer in self.conv:
            x = layer(x)
        return x, self.pool(x)


class Encoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.bn = nn.BatchNorm(1, momentum=0.01)
        channels = [1, 16, 32, 64, 128, 256]
        self.layers = [
            ResEncoderBlock(channels[index], channels[index + 1]) for index in range(5)
        ]

    def __call__(self, x: mx.array) -> tuple[mx.array, list[mx.array]]:
        x = self.bn(x)
        skip = []
        for layer in self.layers:
            residual, x = layer(x)
            skip.append(residual)
        return x, skip


class Intermediate(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = [ResEncoderBlockNoPool(256, 512)] + [
            ResEncoderBlockNoPool(512, 512) for _ in range(3)
        ]

    def __call__(self, x: mx.array) -> mx.array:
        for layer in self.layers:
            x = layer(x)
        return x


class ResEncoderBlockNoPool(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, n_blocks: int = 4):
        super().__init__()
        self.conv = [ConvBlockRes(in_channels, out_channels)] + [
            ConvBlockRes(out_channels, out_channels) for _ in range(n_blocks - 1)
        ]

    def __call__(self, x: mx.array) -> mx.array:
        for layer in self.conv:
            x = layer(x)
        return x


class ResDecoderBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv1 = [
            nn.ConvTranspose2d(
                in_channels,
                out_channels,
                3,
                stride=(2, 2),
                padding=(1, 1),
                output_padding=(1, 1),
                bias=False,
            ),
            nn.BatchNorm(out_channels, momentum=0.01),
            nn.ReLU(),
        ]
        self.conv2 = [ConvBlockRes(out_channels * 2, out_channels)] + [
            ConvBlockRes(out_channels, out_channels) for _ in range(3)
        ]

    def __call__(self, x: mx.array, skip: mx.array) -> mx.array:
        for layer in self.conv1:
            x = layer(x)
        x = mx.concatenate((x, skip), axis=-1)
        for layer in self.conv2:
            x = layer(x)
        return x


class RMVPENetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.unet = DeepUnet()
        self.cnn = nn.Conv2d(16, 3, 3, padding=1)
        self.gru_forward = nn.GRU(384, 256)
        self.gru_reverse = nn.GRU(384, 256)
        self.linear = nn.Linear(512, 360)

    def __call__(self, mel: mx.array) -> mx.array:
        x = mel.transpose(0, 2, 1)[..., None]
        x = (
            self.cnn(self.unet(x))
            .transpose(0, 1, 3, 2)
            .reshape(x.shape[0], x.shape[1], 384)
        )
        forward = self.gru_forward(x)
        reverse = mx.flip(self.gru_reverse(mx.flip(x, axis=1)), axis=1)
        return mx.sigmoid(self.linear(mx.concatenate((forward, reverse), axis=-1)))


class DeepUnet(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = Encoder()
        self.intermediate = Intermediate()
        channels = [(512, 256), (256, 128), (128, 64), (64, 32), (32, 16)]
        self.decoder = [ResDecoderBlock(in_ch, out_ch) for in_ch, out_ch in channels]

    def __call__(self, x: mx.array) -> mx.array:
        x, skip = self.encoder(x)
        x = self.intermediate(x)
        for index, layer in enumerate(self.decoder):
            x = layer(x, skip[-1 - index])
        return x


def _convert_gru(weights: dict[str, mx.array], prefix: str, target: str) -> None:
    ih = weights.pop(f"{prefix}.weight_ih_l0")
    hh = weights.pop(f"{prefix}.weight_hh_l0")
    bih = weights.pop(f"{prefix}.bias_ih_l0")
    bhh = weights.pop(f"{prefix}.bias_hh_l0")
    hidden = hh.shape[1]
    weights[f"{target}.Wx"] = ih
    weights[f"{target}.Wh"] = hh
    weights[f"{target}.b"] = mx.concatenate(
        (bih[: 2 * hidden] + bhh[: 2 * hidden], bih[2 * hidden :])
    )
    weights[f"{target}.bhn"] = bhh[2 * hidden :]


def sanitize_rmvpe_weights(raw: dict[str, mx.array]) -> dict[str, mx.array]:
    weights = {
        name.replace("unet.decoder.layers.", "unet.decoder."): value
        for name, value in raw.items()
        if not name.endswith("num_batches_tracked")
    }
    _convert_gru(weights, "fc.0.gru", "gru_forward")
    reverse_names = {
        name.replace("_reverse", ""): value
        for name, value in list(weights.items())
        if name.startswith("fc.0.gru.") and name.endswith("_reverse")
    }
    for name in list(weights):
        if name.startswith("fc.0.gru.") and name.endswith("_reverse"):
            weights.pop(name)
    weights.update(reverse_names)
    _convert_gru(weights, "fc.0.gru", "gru_reverse")
    weights["linear.weight"] = weights.pop("fc.1.weight")
    weights["linear.bias"] = weights.pop("fc.1.bias")
    for name in list(weights):
        if name.endswith(".weight") and weights[name].ndim == 4:
            if ".conv1.0." in name:
                weights[name] = weights[name].transpose(1, 2, 3, 0)
            else:
                weights[name] = weights[name].transpose(0, 2, 3, 1)
    return weights


class RMVPE:
    def __init__(self, model: RMVPENetwork, mel_basis: mx.array):
        self.model = model
        self.mel_basis = mel_basis
        self.cents_mapping = mx.array(20 * np.arange(360) + 1997.3794084376191)

    @classmethod
    def from_directory(cls, path: str | Path) -> RMVPE:
        root = Path(path)
        model = RMVPENetwork()
        weights = sanitize_rmvpe_weights(
            mx.load(str(root / "model.safetensors"), format="safetensors")
        )
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mel_basis = mx.load(str(root / "mel_basis.safetensors"), format="safetensors")[
            "mel_basis"
        ]
        mx.eval(model.parameters(), mel_basis)
        return cls(model, mel_basis)

    def mel_spectrogram(self, audio: mx.array) -> mx.array:
        if audio.ndim == 1:
            audio = audio[None, :]
        audio = mx.concatenate(
            (
                mx.flip(audio[:, 1:513], axis=1),
                audio,
                mx.flip(audio[:, -513:-1], axis=1),
            ),
            axis=1,
        )
        frame_count = 1 + (audio.shape[1] - 1024) // 160
        window = mx.array(np.hanning(1025)[:-1].astype(np.float32))
        frames = mx.stack(
            [
                audio[:, index * 160 : index * 160 + 1024]
                for index in range(frame_count)
            ],
            axis=1,
        )
        magnitude = mx.abs(mx.fft.rfft(frames * window, axis=-1)).transpose(0, 2, 1)
        return mx.log(mx.maximum(self.mel_basis @ magnitude, 1e-5))

    def __call__(self, audio: mx.array, *, threshold: float = 0.03) -> mx.array:
        mel = self.mel_spectrogram(audio)
        frames = mel.shape[-1]
        pad = 32 * ((frames - 1) // 32 + 1) - frames
        if pad:
            mel = mx.pad(mel, ((0, 0), (0, 0), (0, pad)))
        salience = self.model(mel)[:, :frames][0]
        centers = mx.argmax(salience, axis=1)
        offsets = mx.arange(-4, 5)
        indices = mx.clip(centers[:, None] + offsets[None, :], 0, 359)
        local = mx.take_along_axis(salience, indices, axis=1)
        cents = mx.sum(local * self.cents_mapping[indices], axis=1) / mx.maximum(
            mx.sum(local, axis=1), 1e-12
        )
        cents = mx.where(mx.max(salience, axis=1) > threshold, cents, 0)
        frequency = 10 * mx.power(2.0, cents / 1200)
        return mx.where(cents > 0, frequency, 0)
