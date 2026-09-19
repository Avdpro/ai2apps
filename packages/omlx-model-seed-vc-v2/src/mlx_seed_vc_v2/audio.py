"""Torch-free audio preprocessing matching Seed-VC v2 conventions."""

from __future__ import annotations

import mlx.core as mx
import numpy as np


def _slaney_mel_basis(sample_rate: int, n_fft: int, bands: int) -> np.ndarray:
    """Construct librosa's default Slaney-normalized mel bank without numba."""

    minimum_log_hz = 1000.0
    frequency_spacing = 200.0 / 3
    minimum_log_mel = minimum_log_hz / frequency_spacing
    log_step = np.log(6.4) / 27.0

    def hz_to_mel(values):
        values = np.asarray(values)
        linear = values / frequency_spacing
        return np.where(
            values >= minimum_log_hz,
            minimum_log_mel + np.log(np.maximum(values, minimum_log_hz) / minimum_log_hz) / log_step,
            linear,
        )

    def mel_to_hz(values):
        values = np.asarray(values)
        linear = frequency_spacing * values
        return np.where(
            values >= minimum_log_mel,
            minimum_log_hz * np.exp(log_step * (values - minimum_log_mel)),
            linear,
        )

    edges = mel_to_hz(
        np.linspace(hz_to_mel(0.0), hz_to_mel(sample_rate / 2), bands + 2)
    )
    frequencies = np.linspace(0, sample_rate / 2, n_fft // 2 + 1)
    differences = np.diff(edges)
    ramps = edges[:, None] - frequencies[None, :]
    weights = np.maximum(
        0.0,
        np.minimum(-ramps[:-2] / differences[:-1, None], ramps[2:] / differences[1:, None]),
    )
    weights *= (2.0 / (edges[2:] - edges[:-2]))[:, None]
    return weights.astype(np.float32)


def mel_spectrogram(waveform: np.ndarray, sample_rate: int = 22050) -> mx.array:
    n_fft = window_size = 1024
    hop = 256
    padding = (n_fft - hop) // 2
    values = np.pad(np.asarray(waveform, dtype=np.float32), (padding, padding), mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(values, window_size)[::hop]
    window = np.hanning(window_size + 1)[:-1].astype(np.float32)
    spectrum = mx.fft.rfft(mx.array(frames * window[None]), axis=-1)
    magnitude = mx.sqrt(mx.square(spectrum.real) + mx.square(spectrum.imag) + 1e-9)
    basis = _slaney_mel_basis(sample_rate, n_fft, 80)
    mel = mx.array(basis) @ magnitude.T
    return mx.log(mx.maximum(mel, 1e-5))[None]


def kaldi_fbank(waveform: np.ndarray, sample_rate: int = 16000) -> mx.array:
    """80-bin, dither-free Kaldi-compatible fbank used by CAMPPlus."""

    if sample_rate != 16000:
        raise ValueError("CAMPPlus fbank requires 16 kHz audio")
    values = np.asarray(waveform, dtype=np.float32)
    frame_length, frame_shift, n_fft = 400, 160, 512
    if values.size < frame_length:
        values = np.pad(values, (0, frame_length - values.size))
    frames = np.lib.stride_tricks.sliding_window_view(values, frame_length)[::frame_shift].copy()
    frames -= frames.mean(axis=-1, keepdims=True)
    frames[:, 1:] -= 0.97 * frames[:, :-1].copy()
    frames[:, 0] *= 0.03
    sample = np.arange(frame_length, dtype=np.float32)
    povey = np.power(0.5 - 0.5 * np.cos(2 * np.pi * sample / (frame_length - 1)), 0.85)
    padded = np.pad(frames * povey[None], ((0, 0), (0, n_fft - frame_length)))
    spectrum = np.abs(np.fft.rfft(padded, axis=-1)) ** 2
    def mel(frequency):
        return 1127.0 * np.log1p(frequency / 700.0)

    def inverse_mel(value):
        return 700.0 * np.expm1(value / 1127.0)

    centers = inverse_mel(np.linspace(mel(20.0), mel(sample_rate / 2), 82))
    frequencies = np.arange(n_fft // 2 + 1) * sample_rate / n_fft
    filters = np.zeros((80, frequencies.size), dtype=np.float32)
    for index in range(80):
        left, center, right = centers[index : index + 3]
        filters[index] = np.maximum(
            0.0,
            np.minimum(
                (frequencies - left) / max(center - left, 1e-12),
                (right - frequencies) / max(right - center, 1e-12),
            ),
        )
    features = np.log(np.maximum(spectrum @ filters.T, np.finfo(np.float32).eps))
    features -= features.mean(axis=0, keepdims=True)
    return mx.array(features[None].astype(np.float32))
