"""Torch-free MLX log-mel spectrogram — matches HF WhisperFeatureExtractor (whisper-tiny).

Drops the transformers/torch dependency from the runtime audio path. Recipe (openai
whisper / HF identical): pad-or-trim to 30s, STFT(n_fft=400, hop=160, hann, center+reflect),
power, mel filterbank (80), log10 + clamp(max-8) + (x+4)/4.

The mel filterbank is the exact HF one (slaney norm/scale), shipped as assets/mel_filters_80.npy.
"""

from __future__ import annotations

from pathlib import Path

import mlx.core as mx
import numpy as np

N_FFT = 400
HOP = 160
N_MELS = 80
SAMPLE_RATE = 16000
CHUNK = 30
N_SAMPLES = SAMPLE_RATE * CHUNK  # 480000
N_FRAMES = N_SAMPLES // HOP  # 3000

_MEL = None


def _mel_filters():
    global _MEL
    if _MEL is None:
        f = Path(__file__).resolve().parent / "assets" / "mel_filters_80.npy"
        _MEL = mx.array(np.load(f).astype(np.float32))  # (201, 80)
    return _MEL


def _hann(n):
    # periodic Hann (matches np.hanning(n+1)[:-1] / torch.hann_window default)
    k = mx.arange(n, dtype=mx.float32)
    return 0.5 - 0.5 * mx.cos(2.0 * mx.pi * k / n)


def pad_or_trim(audio, length=N_SAMPLES):
    n = audio.shape[-1]
    if n > length:
        return audio[..., :length]
    if n < length:
        return mx.concatenate(
            [audio, mx.zeros((length - n,), dtype=audio.dtype)], axis=-1
        )
    return audio


def _reflect_pad(x, pad):
    left = x[1 : pad + 1][::-1]
    right = x[-pad - 1 : -1][::-1]
    return mx.concatenate([left, x, right], axis=0)


def log_mel_spectrogram(audio):
    """audio: 1-D mx.array @ 16 kHz -> (1, 80, 3000) log-mel (HF whisper layout)."""
    audio = pad_or_trim(audio.astype(mx.float32))
    x = _reflect_pad(audio, N_FFT // 2)  # center=True, reflect

    # frame into (n_frames, N_FFT)
    n_frames = 1 + (x.shape[0] - N_FFT) // HOP
    idx = mx.arange(N_FFT)[None, :] + (mx.arange(n_frames)[:, None] * HOP)
    frames = x[idx] * _hann(N_FFT)[None, :]

    spec = mx.fft.rfft(frames, n=N_FFT, axis=-1)  # (n_frames, 201) complex
    power = (spec.real**2 + spec.imag**2)[:-1]  # drop last frame -> (3000, 201)

    mel = power @ _mel_filters()  # (3000, 80)
    log = mx.log10(mx.maximum(mel, 1e-10))
    log = mx.maximum(log, log.max() - 8.0)
    log = (log + 4.0) / 4.0
    return log.T[None]  # (1, 80, 3000)
