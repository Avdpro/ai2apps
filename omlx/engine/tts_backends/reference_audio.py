"""Reference decoding compatible with the pinned Runtime dependencies."""
import mlx.core as mx
from mlx_audio.audio_io import read
from .sinc_resample import sinc_resample


def load_audio(path, sample_rate, resampling_method="sinc_interp_hann"):
    if resampling_method != "sinc_interp_hann":
        raise ValueError("Unsupported reference resampling method")
    samples, rate = read(path, dtype="float32", always_2d=True)
    return sinc_resample(mx.array(samples.mean(axis=1)), rate, sample_rate)
