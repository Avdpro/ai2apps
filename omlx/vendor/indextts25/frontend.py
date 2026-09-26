# MLX frontend: SeamlessM4T featurizer, HiFiGAN log-mel, kaldi fbank, sinc resample.
# Bit-mirrors windextts/frontend/{audio_utils,mel}.py + torchaudio kaldi/sinc on GPU.
import math
from pathlib import Path

import mlx.core as mx

from omlx.vendor.indextts25 import ops

_DATA = Path(__file__).resolve().parent / "data"

_FRAME_LENGTH, _HOP_LENGTH, _FFT_LENGTH = 400, 160, 512
_PREEMPHASIS, _N_MELS, _STRIDE = 0.97, 80, 2
_MEL_FLOOR, _NORM_EPS = 1.192092955078125e-07, 1e-7


def _povey(n):
    # (0.5 - 0.5*cos(2*pi*k/n))^0.85 symmetric (f64 to match the cache builder)
    k = mx.arange(n, dtype=mx.float64)
    return mx.power(0.5 - 0.5 * mx.cos(2 * math.pi * k / n), 0.85)


class SeamlessM4TFeaturizer:
    # 16k mono [-1,1] -> input_features [B, T//2, 160] (f64 compute like official)
    def __init__(self, cache_path=None):
        d = Path(cache_path) if cache_path else _DATA / "seamless_frontend.npz"
        import numpy as np

        z = np.load(d)
        self.mel_filters = mx.array(z["mel_filters"], dtype=mx.float64)  # [257,80]
        self.window = mx.array(z["window"], dtype=mx.float64) if "window" in z else _povey(_FRAME_LENGTH)
        self.window = self.window.astype(mx.float64) if self.window.shape[0] != _FRAME_LENGTH else self.window

    def __call__(self, waveform, return_mask=False):
        # waveform [B,N] fp32 -> [B,T//2,160] fp32 (T = 1 + (N-400)//160).
        # Runs on the CPU stream: torch's fp64 reference values need f64 which
        # the Metal GPU does not support.
        with mx.stream(mx.cpu):
            if waveform.ndim == 1:
                waveform = waveform[None]
            fr = (waveform.astype(mx.float64) * 2 ** 15)
            fr = ops.frames(fr, _FRAME_LENGTH, _HOP_LENGTH)  # [B,F,400]
            fr = fr - fr.mean(-1, keepdims=True)  # dc offset
            pre = mx.concatenate([fr[..., :1], fr[..., 1:] - _PREEMPHASIS * fr[..., :-1]], -1)
            c = mx.fft.rfft(pre * self.window, n=_FFT_LENGTH, axis=-1)  # [B,F,257]
            mel = mx.log(mx.clip((c.real ** 2 + c.imag ** 2) @ self.mel_filters, _MEL_FLOOR, None))
            mel = (mel - mel.mean(1, keepdims=True)) / mx.sqrt(mel.var(1, keepdims=True, ddof=1) + _NORM_EPS)
            T, rem = mel.shape[1], mel.shape[1] % _STRIDE
            if rem:
                mel = mx.concatenate([mel, mx.full((mel.shape[0], _STRIDE - rem, mel.shape[2]), 1.0, dtype=mx.float64)], 1)
                T = mel.shape[1]
            mel = mel.reshape(mel.shape[0], T // _STRIDE, _N_MELS * _STRIDE).astype(mx.float32)
        if not return_mask:
            return mel
        mask = mx.ones((mel.shape[0], T // _STRIDE), dtype=mx.int32)
        if rem:
            mask = mask.at[:, -1].multiply(0)
        return mel, mask


class MelSpectrogram:
    # 22k -> log-mel [B,80,T']; reflect-pad (n_fft-hop)//2, |STFT|, mel_basis, log(clamp 1e-5)
    def __init__(self, mel_basis=None, cache_path=None):
        if mel_basis is None:
            p = Path(cache_path) if cache_path else _DATA / "mel_basis_hifigan.npz"
            import numpy as np

            mel_basis = mx.array(np.load(p)["basis"], dtype=mx.float32)  # [80,513]
        self.mel_basis = mel_basis
        self.hann = mx.hann(1024).astype(mx.float32) if hasattr(mx, "hann") else _hann(1024)

    def __call__(self, y):
        if y.ndim == 1:
            y = y[None]
        pad = (1024 - 256) // 2
        spec = mx.sqrt(ops.stft_power(ops.reflect_pad(y, pad, pad), 1024, 256, self.hann) + 1e-9)  # [B,F,513]
        return mx.log(mx.clip(spec @ self.mel_basis.T, 1e-5, None)).transpose(0, 2, 1)  # [B,80,F]


def _hann(n):  # torch.hann_window default: PERIODIC (denominator n, not n-1)
    k = mx.arange(n, dtype=mx.float32)
    return 0.5 - 0.5 * mx.cos(2 * math.pi * k / n)


class KaldiFbank:
    # torchaudio.compliance.kaldi.fbank(num_mel_bins=80, dither=0, sr=16000) on GPU
    def __init__(self, num_mel_bins=80, sample_frequency=16000, frame_length=25.0, frame_shift=10.0):
        self.num_mel_bins = num_mel_bins
        self.sr = sample_frequency
        self.window_size = int(sample_frequency * frame_length * 1e-3)
        self.window_shift = int(sample_frequency * frame_shift * 1e-3)
        self.padded = 2 ** ((self.window_size - 1).bit_length())
        self.window = ops.kaldi_povey_window(self.window_size).astype(mx.float32)
        self.banks = ops.kaldi_mel_banks(num_mel_bins, self.padded, sample_frequency)  # [80,257]
        self.eps = mx.array(1.1920928955078125e-07, dtype=mx.float32)

    def __call__(self, x):
        # x [B,T] 16k -> [B,m,80]; snip_edges, per-frame dc-mean, preemphasis 0.97
        fr = ops.frames(x, self.window_size, self.window_shift)  # [B,m,400]
        fr = fr - fr.mean(-1, keepdims=True)
        fr = mx.concatenate([fr[..., :1], fr[..., 1:] - 0.97 * fr[..., :-1]], -1)
        fr = fr * self.window
        fr = mx.pad(fr, [(0, 0), (0, 0), (0, self.padded - self.window_size)])
        c = mx.fft.rfft(fr, n=self.padded, axis=-1)
        spec = c.real ** 2 + c.imag ** 2  # [B,m,257]
        e = mx.log(mx.clip(spec @ self.banks.T, self.eps, None))
        return e  # [B,m,80]


class Resample:
    # torchaudio.transforms.Resample(orig_freq, new_freq) sinc_interp_hann, GPU
    def __init__(self, orig_freq, new_freq, lowpass_filter_width=6, rolloff=0.99):
        self.orig_freq = orig_freq
        self.new_freq = new_freq
        self.kernel, self.width = ops.sinc_kernel(orig_freq, new_freq, lowpass_filter_width, rolloff)

    def __call__(self, x):
        if self.orig_freq == self.new_freq:
            return x
        return ops.sinc_resample(x, self.orig_freq, self.new_freq, self.kernel)
