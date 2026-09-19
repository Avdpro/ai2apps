"""MLX implementation of the normalized STFT boundary used by HTDemucs."""

from __future__ import annotations

import math


def _hann_window(mx, length: int):
    # torch.hann_window(length) is periodic by default; mx.hanning follows the
    # symmetric NumPy convention, so construct the periodic form explicitly.
    positions = mx.arange(length, dtype=mx.float32)
    return 0.5 - 0.5 * mx.cos((2 * math.pi / length) * positions)


def _reflect_pad_last(mx, values, amount: int):
    return _reflect_pad_last_asymmetric(mx, values, amount, amount)


def _reflect_pad_last_asymmetric(mx, values, left_amount: int, right_amount: int):
    """Match PyTorch reflection padding on the final dimension."""
    if left_amount < 0 or right_amount < 0:
        raise ValueError("Reflection padding cannot be negative")
    if left_amount == 0 and right_amount == 0:
        return values
    length = values.shape[-1]
    if length <= max(left_amount, right_amount):
        raise ValueError("Reflection padding must be smaller than the input")
    left_indices = mx.arange(left_amount, 0, -1)
    right_indices = mx.arange(length - 2, length - right_amount - 2, -1)
    left = mx.take(values, left_indices, axis=-1)
    right = mx.take(values, right_indices, axis=-1)
    return mx.concatenate([left, values, right], axis=-1)


def demucs_spectro(values, *, n_fft: int = 4096, hop_length: int = 1024):
    """Apply HTDemucs' alignment padding and return its cropped spectrum."""
    import mlx.core as mx

    if hop_length != n_fft // 4:
        raise ValueError("HTDemucs requires hop_length == n_fft // 4")
    length = values.shape[-1]
    frames = math.ceil(length / hop_length)
    alignment_pad = 3 * hop_length // 2
    values = _reflect_pad_last_asymmetric(
        mx,
        values,
        alignment_pad,
        alignment_pad + frames * hop_length - length,
    )
    spectrum = spectro(values, n_fft=n_fft, hop_length=hop_length)
    spectrum = spectrum[..., :-1, 2 : 2 + frames]
    if spectrum.shape[-2:] != (n_fft // 2, frames):
        raise RuntimeError(f"Unexpected HTDemucs spectrum shape: {spectrum.shape}")
    return spectrum


def demucs_ispectro(spectrum, *, length: int, hop_length: int = 1024):
    """Invert a cropped HTDemucs spectrum back to an exact sample length."""
    import mlx.core as mx

    if length < 0:
        raise ValueError("length cannot be negative")
    spectrum = mx.pad(spectrum, [(0, 0)] * (spectrum.ndim - 2) + [(0, 1), (2, 2)])
    alignment_pad = 3 * hop_length // 2
    padded_length = hop_length * math.ceil(length / hop_length) + 2 * alignment_pad
    values = ispectro(spectrum, hop_length=hop_length, length=padded_length)
    return values[..., alignment_pad : alignment_pad + length]


def spectro(values, *, n_fft: int = 4096, hop_length: int | None = None):
    """Match ``demucs.spec.spectro`` for ``pad=0`` and normalized FFT."""
    import mlx.core as mx

    if n_fft <= 0:
        raise ValueError("n_fft must be positive")
    hop = hop_length or n_fft // 4
    if hop <= 0:
        raise ValueError("hop_length must be positive")
    leading = values.shape[:-1]
    length = values.shape[-1]
    flattened = values.reshape((-1, length))
    padded = _reflect_pad_last(mx, flattened, n_fft // 2)
    frame_count = 1 + (padded.shape[-1] - n_fft) // hop
    indices = mx.arange(frame_count)[:, None] * hop + mx.arange(n_fft)[None, :]
    frames = mx.take(padded, indices, axis=-1)
    frames = frames * _hann_window(mx, n_fft)
    spectrum = mx.fft.rfft(frames, n=n_fft, axis=-1, norm="ortho")
    spectrum = mx.swapaxes(spectrum, -1, -2)
    return spectrum.reshape((*leading, n_fft // 2 + 1, frame_count))


def ispectro(spectrum, *, hop_length: int | None = None, length: int | None = None):
    """Inverse of :func:`spectro`, including center trim and window envelope."""
    import mlx.core as mx

    leading = spectrum.shape[:-2]
    frequencies, frame_count = spectrum.shape[-2:]
    n_fft = 2 * frequencies - 2
    hop = hop_length or n_fft // 4
    frames = mx.swapaxes(spectrum.reshape((-1, frequencies, frame_count)), -1, -2)
    frames = mx.fft.irfft(frames, n=n_fft, axis=-1, norm="ortho")
    window = _hann_window(mx, n_fft)
    frames = frames * window
    padded_length = n_fft + hop * (frame_count - 1)
    output = mx.zeros((frames.shape[0], padded_length), dtype=frames.dtype)
    envelope = mx.zeros((padded_length,), dtype=frames.dtype)
    window_square = window * window
    for index in range(frame_count):
        start = index * hop
        stop = start + n_fft
        output = output.at[:, start:stop].add(frames[:, index, :])
        envelope = envelope.at[start:stop].add(window_square)
    output = output / mx.maximum(envelope, 1e-11)
    center = n_fft // 2
    available = padded_length - 2 * center
    requested = available if length is None else length
    if requested < 0:
        raise ValueError(f"Invalid inverse length {requested}")
    retained = min(requested, available)
    output = output[:, center : center + retained]
    if requested > retained:
        output = mx.pad(output, ((0, 0), (0, requested - retained)))
    return output.reshape((*leading, requested))
