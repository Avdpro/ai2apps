"""MLX-native forward path for the released four-source HTDemucs model."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path

import numpy as np

from .mlx_layers import (
    State,
    add_frequency_embedding,
    channel_projection,
    hdec_frequency,
    hdec_time,
    henc_frequency,
    henc_time,
)
from .mlx_stft import demucs_ispectro, demucs_spectro
from .mlx_transformer import cross_transformer


def load_raw_npz(path: str | Path) -> dict[str, np.ndarray]:
    """Load the safe raw-tensor artifact emitted by ``export_raw_npz``."""
    with np.load(Path(path), allow_pickle=False) as package:
        return {name: package[name] for name in package.files}


_DCONV_COMPONENT = re.compile(
    r"(\.dconv\.layers\.\d+)\.layers\.(\d+)(?:\.conv)?\."
)


def load_converted_safetensors(path: str | Path) -> dict[str, np.ndarray]:
    """Adapt ``mlx-community/demucs-mlx`` weights to the explicit op boundary.

    That public artifact stores convolution weights in MLX layout and splits
    PyTorch's packed Q/K/V tensors. The returned mapping deliberately restores
    the original PyTorch names/layout consumed by this experiment's parity-
    tested operators; it does not write or duplicate another checkpoint file.
    """
    from safetensors import safe_open

    values: dict[str, np.ndarray] = {}
    attention: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    with safe_open(str(Path(path)), framework="numpy") as package:
        for stored_name in package.keys():  # noqa: SIM118 - safe_open is not iterable
            if not stored_name.startswith("model_0."):
                raise ValueError(f"Unsupported safetensors key: {stored_name}")
            name = stored_name.removeprefix("model_0.")
            array = np.asarray(package.get_tensor(stored_name))

            match = re.match(
                r"(.+\.(?:attn|cross_attn))\.(query_proj|key_proj|value_proj)\.(weight|bias)$",
                name,
            )
            if match:
                root, projection, kind = match.groups()
                if root.endswith(".attn"):
                    root = root.removesuffix(".attn") + ".self_attn"
                attention.setdefault((root, kind), {})[projection] = array
                continue

            if ".attn.out_proj." in name:
                name = name.replace(".attn.out_proj.", ".self_attn.out_proj.")
            name = name.replace(".norm_out.gn.", ".norm_out.")
            name = _DCONV_COMPONENT.sub(r"\1.\2.", name)
            name = name.replace(".conv_tr.conv.", ".conv_tr.")
            name = name.replace(".rewrite.conv.", ".rewrite.")
            name = name.replace(".conv.conv.", ".conv.")
            if name.startswith("channel_"):
                name = name.replace(".conv.", ".", 1)

            if stored_name.endswith(".weight") and ".conv" in stored_name:
                if ".conv_tr.conv.weight" in stored_name:
                    axes = (3, 0, 1, 2) if array.ndim == 4 else (2, 0, 1)
                else:
                    axes = (0, 3, 1, 2) if array.ndim == 4 else (0, 2, 1)
                array = np.transpose(array, axes)
            if name in values:
                raise ValueError(f"Duplicate adapted safetensors key: {name}")
            values[name] = array

    order = ("query_proj", "key_proj", "value_proj")
    for (root, kind), projections in attention.items():
        if set(projections) != set(order):
            raise ValueError(f"Incomplete attention projections: {root}.{kind}")
        values[f"{root}.in_proj_{kind}"] = np.concatenate(
            [projections[item] for item in order], axis=0
        )
    return values


def load_checkpoint(path: str | Path) -> dict[str, np.ndarray]:
    source = Path(path)
    if source.suffix == ".npz":
        return load_raw_npz(source)
    if source.suffix == ".safetensors":
        return load_converted_safetensors(source)
    raise ValueError(f"Unsupported Demucs checkpoint format: {source.suffix}")


def _sample_standard_deviation(mx, values, axes: tuple[int, ...]):
    """Match ``torch.std``'s default Bessel correction."""
    count = math.prod(values.shape[axis] for axis in axes)
    if count <= 1:
        raise ValueError("Sample standard deviation requires at least two values")
    mean = mx.mean(values, axis=axes, keepdims=True)
    squared = mx.sum(mx.square(values - mean), axis=axes, keepdims=True)
    return mean, mx.sqrt(squared / (count - 1))


class MlxHTDemucs:
    """Inference-only MLX implementation of official ``htdemucs``.

    The input and output contracts are channels-first:
    ``[batch, 2, samples]`` -> ``[batch, 4, 2, samples]``.
    """

    sources = ("drums", "bass", "other", "vocals")
    sample_rate = 44_100
    audio_channels = 2
    segment_seconds = 7.8
    n_fft = 4096
    hop_length = 1024

    def __init__(self, state: State):
        self.state: Mapping[str, np.ndarray] = state

    @property
    def segment_samples(self) -> int:
        return int(self.segment_seconds * self.sample_rate)

    def __call__(self, mixture, *, pad_to_segment: bool = True):
        import mlx.core as mx

        if mixture.ndim != 3 or mixture.shape[1] != self.audio_channels:
            raise ValueError("mixture must have shape [batch, 2, samples]")
        original_length = mixture.shape[-1]
        if original_length == 0:
            return mx.zeros(
                (mixture.shape[0], len(self.sources), self.audio_channels, 0),
                dtype=mixture.dtype,
            )
        inference_length = original_length
        if pad_to_segment:
            inference_length = self.segment_samples
            if original_length > inference_length:
                raise ValueError("Input is longer than the 7.8-second model segment")
            if original_length < inference_length:
                mixture = mx.pad(mixture, ((0, 0), (0, 0), (0, inference_length - original_length)))

        spectrum = demucs_spectro(
            mixture,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
        )
        magnitude = mx.stack([mx.real(spectrum), mx.imag(spectrum)], axis=2)
        batch, channels, _, frequencies, frames = magnitude.shape
        magnitude = magnitude.reshape((batch, channels * 2, frequencies, frames))
        frequency_mean, frequency_std = _sample_standard_deviation(
            mx, magnitude, (1, 2, 3)
        )
        magnitude = (magnitude - frequency_mean) / (frequency_std + 1e-5)

        time_mean, time_std = _sample_standard_deviation(mx, mixture, (1, 2))
        time = (mixture - time_mean) / (time_std + 1e-5)
        frequency = mx.transpose(magnitude, (0, 2, 3, 1))
        time = mx.transpose(time, (0, 2, 1))

        frequency_saved = []
        time_saved = []
        frequency_lengths = []
        time_lengths = []
        for index in range(4):
            frequency_lengths.append(frequency.shape[2])
            time_lengths.append(time.shape[1])
            time = henc_time(time, self.state, f"tencoder.{index}")
            frequency = henc_frequency(frequency, self.state, f"encoder.{index}")
            if index == 0:
                frequency = add_frequency_embedding(
                    frequency,
                    self.state,
                    prefix="freq_emb.embedding",
                )
            frequency_saved.append(frequency)
            time_saved.append(time)
            mx.eval(frequency, time)

        batch, bottom_frequencies, bottom_frames, bottom_channels = frequency.shape
        frequency = channel_projection(
            frequency.reshape((batch, bottom_frequencies * bottom_frames, bottom_channels)),
            self.state,
            "channel_upsampler",
        ).reshape((batch, bottom_frequencies, bottom_frames, 512))
        time = channel_projection(time, self.state, "channel_upsampler_t")
        frequency, time = cross_transformer(
            frequency,
            time,
            self.state,
            "crosstransformer",
        )
        mx.eval(frequency, time)
        frequency = channel_projection(
            frequency.reshape((batch, bottom_frequencies * bottom_frames, 512)),
            self.state,
            "channel_downsampler",
        ).reshape((batch, bottom_frequencies, bottom_frames, bottom_channels))
        time = channel_projection(time, self.state, "channel_downsampler_t")

        for index in range(4):
            frequency, _ = hdec_frequency(
                frequency,
                frequency_saved.pop(),
                self.state,
                f"decoder.{index}",
                last=index == 3,
            )
            time, _ = hdec_time(
                time,
                time_saved.pop(),
                self.state,
                f"tdecoder.{index}",
                length=time_lengths.pop(),
                last=index == 3,
            )
            frequency_lengths.pop()
            mx.eval(frequency, time)

        frequency = frequency.reshape(
            (batch, frequencies, frames, len(self.sources), self.audio_channels, 2)
        )
        frequency = mx.transpose(frequency, (0, 3, 4, 1, 2, 5))
        frequency = frequency[..., 0] + 1j * frequency[..., 1]
        frequency = (
            frequency * frequency_std[:, None, ...] + frequency_mean[:, None, ...]
        )
        frequency_audio = demucs_ispectro(
            frequency,
            length=inference_length,
            hop_length=self.hop_length,
        )

        time = time.reshape(
            (batch, inference_length, len(self.sources), self.audio_channels)
        )
        time = mx.transpose(time, (0, 2, 3, 1))
        time = time * time_std[:, None, ...] + time_mean[:, None, ...]
        output = time + frequency_audio
        output = output[..., :original_length]
        mx.eval(output)
        return output
