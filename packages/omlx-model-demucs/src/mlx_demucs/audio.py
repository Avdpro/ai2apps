"""Multichannel audio boundary for the standalone separation experiment."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class AudioBuffer:
    """Floating point audio in channels-first layout: ``[channels, frames]``."""

    samples: np.ndarray
    sample_rate: int

    def __post_init__(self) -> None:
        values = np.asarray(self.samples)
        if values.ndim != 2:
            raise ValueError("Audio samples must have shape [channels, frames]")
        if values.shape[0] < 1:
            raise ValueError("Audio must contain at least one channel")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if not np.isfinite(values).all():
            raise ValueError("Audio contains non-finite samples")

    @property
    def channels(self) -> int:
        return int(self.samples.shape[0])

    @property
    def frames(self) -> int:
        return int(self.samples.shape[1])

    @property
    def duration(self) -> float:
        return self.frames / self.sample_rate

    @property
    def rms(self) -> float:
        if not self.frames:
            return 0.0
        return float(np.sqrt(np.mean(np.square(self.samples, dtype=np.float64))))

    def resample(self, target_rate: int) -> AudioBuffer:
        if target_rate <= 0:
            raise ValueError("target_rate must be positive")
        if target_rate == self.sample_rate or not self.frames:
            return self
        from scipy.signal import resample_poly

        divisor = int(np.gcd(self.sample_rate, target_rate))
        values = resample_poly(
            self.samples,
            target_rate // divisor,
            self.sample_rate // divisor,
            axis=1,
        )
        return AudioBuffer(values.astype(np.float32, copy=False), target_rate)

    def with_channels(self, channels: int) -> AudioBuffer:
        if channels == self.channels:
            return self
        if channels == 2 and self.channels == 1:
            return AudioBuffer(np.repeat(self.samples, 2, axis=0), self.sample_rate)
        if channels == 1:
            return AudioBuffer(self.samples.mean(axis=0, keepdims=True), self.sample_rate)
        raise ValueError(f"Cannot convert {self.channels} channels to {channels}")

    def write_wav(self, path: str | Path, *, float32: bool = True) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        values = np.asarray(self.samples, dtype=np.float32).T
        if float32:
            try:
                import soundfile as sf

                sf.write(destination, values, self.sample_rate, subtype="FLOAT")
                return
            except ImportError:
                pass
        clipped = np.clip(values, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype("<i2")
        with wave.open(str(destination), "wb") as output:
            output.setnchannels(self.channels)
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
        values = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        values = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768
    elif width == 4:
        values = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"Unsupported PCM WAV sample width: {width}")
    samples = values.reshape(-1, channels).T
    return AudioBuffer(samples.astype(np.float32, copy=False), sample_rate)


def read_audio(path: str | Path) -> AudioBuffer:
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)
    try:
        import soundfile as sf

        values, sample_rate = sf.read(source, dtype="float32", always_2d=True)
        return AudioBuffer(np.asarray(values).T, int(sample_rate))
    except (ImportError, RuntimeError) as error:
        if source.suffix.lower() != ".wav":
            raise ValueError(f"Unsupported audio without SoundFile: {source.suffix}") from error
        return _read_pcm_wav(source)
