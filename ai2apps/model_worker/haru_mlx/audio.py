"""Audio file helpers (everything is mono float32 at 24 kHz inside Haru)."""

from __future__ import annotations

import io
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np

SAMPLE_RATE = 24_000
_SILENCE_DBFS = -45.0
_SILENCE_MARGIN_SECONDS = 0.2


def decode_audio(data: bytes, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Audio file bytes -> mono float32. WAV/FLAC/Ogg natively, anything else via ffmpeg."""
    import soundfile as sf
    from scipy.signal import resample_poly

    try:
        waveform, source_rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception:
        return _decode_with_ffmpeg(data, sample_rate)
    mono = waveform.mean(axis=1)
    if int(source_rate) != sample_rate:
        g = math.gcd(int(source_rate), sample_rate)
        mono = resample_poly(mono, sample_rate // g, int(source_rate) // g)
    return mono.astype(np.float32)


def _decode_with_ffmpeg(data: bytes, sample_rate: int) -> np.ndarray:
    with tempfile.NamedTemporaryFile(suffix=".audio") as source:
        source.write(data)
        source.flush()
        command = [
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", source.name,
            "-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(sample_rate), "pipe:1",
        ]
        try:
            result = subprocess.run(command, capture_output=True, timeout=60, check=False)
        except FileNotFoundError as error:
            raise ValueError("unsupported audio format (install ffmpeg to decode it)") from error
    if result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "could not decode audio")
    return np.frombuffer(result.stdout, dtype="<i2").astype(np.float32) / 32768.0


def load_audio(path: str | Path, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    return decode_audio(Path(path).read_bytes(), sample_rate)


def save_audio(path: str | Path, audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    import soundfile as sf

    sf.write(str(path), np.asarray(audio, dtype=np.float32), sample_rate)


def trim_silence(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Cut leading and trailing audio quieter than -45 dBFS (20 ms RMS windows)."""
    window = sample_rate // 50
    count = audio.shape[0] // window
    if count == 0:
        return audio
    rms = np.sqrt(np.mean(audio[: count * window].reshape(count, window) ** 2, axis=1) + 1e-12)
    voiced = np.flatnonzero(20.0 * np.log10(rms) > _SILENCE_DBFS)
    if voiced.size == 0:
        return audio[:0]
    margin = int(_SILENCE_MARGIN_SECONDS * sample_rate)
    start = max(0, int(voiced[0]) * window - margin)
    end = min(audio.shape[0], (int(voiced[-1]) + 1) * window + margin)
    return audio[start:end]


def prepare_reference(audio: np.ndarray, max_seconds: float = 180.0, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Voice reference clip: silence trimmed, at most the last ``max_seconds``."""
    audio = trim_silence(np.asarray(audio, dtype=np.float32), sample_rate)
    return audio[-int(max_seconds * sample_rate) :]
