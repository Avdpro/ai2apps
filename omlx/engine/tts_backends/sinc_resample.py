"""Pinned upstream torchaudio-compatible reference resampler; see PROVENANCE.json."""
import math
import mlx.core as mx
import numpy as np

# torchaudio.functional.resample defaults, method "sinc_interp_hann".
_SINC_LOWPASS_FILTER_WIDTH = 6
_SINC_ROLLOFF = 0.99
_SINC_CHUNK_FRAMES = 1 << 16


def sinc_resample(
    waveform: mx.array, orig_sample_rate: int, sample_rate: int
) -> mx.array:
    """Resample a 1-D signal like ``torchaudio.functional.resample`` with defaults.

    Use it where the reference pipeline resamples with torchaudio and the model
    depends on its output. Its short Hann-windowed sinc passes tones up to 1 kHz
    above the new Nyquist at -9 to -17 dB. ``resample_audio_array`` suppresses
    them by more than 140 dB.

    Output sample ``k`` is row ``k % new`` of torchaudio's kernel applied to the
    padded input from ``floor(k * orig / new)`` on, with the reduced rates. Each
    row is zero outside ``2 * width + 1`` taps, so only those are gathered, one
    chunk at a time. Memory follows the signal, also for rates such as 44099 Hz.
    """
    if orig_sample_rate == sample_rate:
        return waveform
    gcd = math.gcd(int(orig_sample_rate), int(sample_rate))
    orig = int(orig_sample_rate) // gcd
    new = int(sample_rate) // gcd

    base_freq = min(orig, new) * _SINC_ROLLOFF
    width = math.ceil(_SINC_LOWPASS_FILTER_WIDTH * orig / base_freq)
    taps = 2 * width + 1

    # torchaudio's t from the first tap of each row on, in float64, because its
    # two terms nearly cancel.
    phases = np.arange(new)
    first = phases * orig // new
    t = (first[:, None] + np.arange(taps) - width) / orig - phases[:, None] / new
    t = np.clip(t * base_freq, -_SINC_LOWPASS_FILTER_WIDTH, _SINC_LOWPASS_FILTER_WIDTH)
    window = np.cos(t * np.pi / _SINC_LOWPASS_FILTER_WIDTH / 2) ** 2
    kernel = mx.array((np.sinc(t) * window * (base_freq / orig)).astype(np.float32))
    first = mx.array(first.astype(np.int32))

    padded = mx.pad(waveform.astype(mx.float32), (width, width + orig))
    offsets = mx.arange(taps)
    out_len = math.ceil(waveform.shape[0] * new / orig)
    chunks = []
    for start in range(0, out_len, _SINC_CHUNK_FRAMES):
        k = mx.arange(start, min(start + _SINC_CHUNK_FRAMES, out_len))
        phase = k % new
        rows = padded[(k // new * orig + first[phase])[:, None] + offsets]
        chunks.append((rows * kernel[phase]).sum(axis=1))
        # Keeps one chunk's gather in memory at a time.
        mx.eval(chunks[-1])
    return mx.concatenate(chunks) if chunks else padded[:0]
