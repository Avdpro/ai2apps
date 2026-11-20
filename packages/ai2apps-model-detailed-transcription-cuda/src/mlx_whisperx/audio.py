"""Small audio boundary used by the standalone pipeline.

The standard-library WAV path keeps unit tests independent of MLX. Other
formats are decoded lazily through mlx-audio only in real experiment runs.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AudioBuffer:
    samples: np.ndarray
    sample_rate: int

    @property
    def duration(self) -> float:
        return len(self.samples) / self.sample_rate

    def slice(self, start: float, end: float) -> AudioBuffer:
        first = max(0, min(len(self.samples), round(start * self.sample_rate)))
        last = max(first, min(len(self.samples), round(end * self.sample_rate)))
        return AudioBuffer(self.samples[first:last].copy(), self.sample_rate)

    def write_wav(self, path: str | Path) -> None:
        clipped = np.clip(self.samples, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype("<i2")
        with wave.open(str(path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(pcm.tobytes())


def _read_pcm_wav(path: Path) -> AudioBuffer:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        sample_rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    if width == 1:
        samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768
    elif width == 4:
        samples = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"Unsupported PCM WAV sample width: {width}")
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return AudioBuffer(samples.astype(np.float32, copy=False), sample_rate)


def read_audio(path: str | Path, *, target_rate: int = 16000) -> AudioBuffer:
    # The Model Worker grants access to the uploaded file, not to every parent
    # directory used while canonicalizing it.  On macOS, resolving /tmp also
    # walks /private and can therefore fail inside the production sandbox even
    # though the file itself is readable.
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".wav":
        audio = _read_pcm_wav(source)
    else:
        from mlx_audio.audio_io import read as mlx_audio_read

        samples, sample_rate = mlx_audio_read(str(source), always_2d=True)
        values = np.asarray(samples, dtype=np.float32)
        if values.ndim > 1:
            values = values.mean(axis=1)
        audio = AudioBuffer(values, int(sample_rate))
    if audio.sample_rate == target_rate:
        return audio
    if not len(audio.samples):
        return AudioBuffer(audio.samples, target_rate)
    target_count = max(1, round(len(audio.samples) * target_rate / audio.sample_rate))
    positions = np.linspace(0, len(audio.samples) - 1, target_count)
    resampled = np.interp(positions, np.arange(len(audio.samples)), audio.samples)
    return AudioBuffer(resampled.astype(np.float32), target_rate)
