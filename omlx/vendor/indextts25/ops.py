# Shared DSP kernels for the MLX backend (one copy, cross-model). Everything
# here mirrors a torch/torchaudio primitive bit-for-bit (fp32 semantics).
import math

import mlx.core as mx
import mlx.nn as nn


class Seq(nn.Module):
    # name-preserving sequential: mlx nn.Sequential flattens children under
    # "layers.{i}" and would break ckpt key parity; this keeps torch names
    # (dict -> named attrs, list -> "0","1",...).
    def __init__(self, items):
        super().__init__()
        self._order = list(items)
        self._no_sync = False  # set by mx.compile callers during tracing only
        for n, m in items.items():
            setattr(self, n, m)

    def __call__(self, x):
        for n in self._order:
            x = getattr(self, n)(x)
            if not self._no_sync:
                mx.eval(x)  # per-module eval: first-time Metal compile < watchdog
        return x

    def __len__(self):
        return len(self._order)

    def __getitem__(self, i):
        # int index -> name-preserving lookup; str key must stay dict-native
        # (mlx Module is a dict subclass: update/quantize assign dst["0"])
        return dict.__getitem__(self, self._order[i] if isinstance(i, int) else i)


def reflect_pad(x, pl, pr):
    # torch F.pad reflect; top-up right with zeros when len <= max(pad) (encodec pad1d)
    T = x.shape[-1]
    extra = max(0, max(pl, pr) - T + 1)
    if extra:
        x = mx.pad(x, [(0, 0)] * (x.ndim - 1) + [(0, extra)])
        T += extra
    idx = mx.concatenate([mx.arange(pl, 0, -1), mx.arange(T), mx.arange(T - 2, T - pr - 2, -1)])
    return mx.take(x, idx, axis=-1)


def frames(x, win, hop):
    # x [B,T] -> [B,F,win] strided frames (torch as_strided/unfold semantics)
    B, T = x.shape
    F = (T - win) // hop + 1
    idx = mx.arange(F)[:, None] * hop + mx.arange(win)  # [F,win]
    return mx.take(x, idx, axis=1)


def stft_power(x, n_fft, hop, window):
    # x [B,T] pre-padded -> power spectrum [B,F,n_fft//2+1] (torch.stft, onesided)
    fr = frames(x, n_fft, hop) * window
    c = mx.fft.rfft(fr, n=n_fft, axis=-1)
    return c.real * c.real + c.imag * c.imag


def interpolate_nearest(x, size):
    # torch F.interpolate nearest, align_corners=False: src = floor(dst * scale)
    # with scale and the product BOTH in fp32 — exact-integer math disagrees with
    # torch at boundary indices (e.g. 64->110 i=55), so mirror the fp32 rounding.
    import numpy as np

    _, T, _ = x.shape  # [B,T,D]: time is axis 1
    scale = np.float32(T / size)
    idx = mx.floor(mx.arange(size, dtype=mx.float32) * scale).astype(mx.int32)
    return mx.take(x, idx, axis=1)


def avg_pool_expand(x, k):
    # avg_pool1d(k, stride=k, ceil_mode=True) then expand each pooled value k times.
    # torch ceil_mode divides the last (partial) window by its VALID count only.
    B, C, T = x.shape
    n = (T + k - 1) // k
    xp = mx.pad(x, [(0, 0), (0, 0), (0, n * k - T)])
    seg = xp.reshape(B, C, n, k).mean(axis=-1)  # sum/k (zeros add nothing)
    if n * k > T:
        valid = mx.array([k] * (n - 1) + [k - (n * k - T)], dtype=mx.float32)
        seg = seg * (k / valid)[None, None]  # sum/k -> sum/valid for the partial window
    return mx.repeat(seg, k, axis=-1)[..., :T]


def sequence_mask(lengths, max_len):
    # True where arange < length (int32 lengths)
    return mx.arange(max_len)[None] < lengths[:, None]


def kaldi_mel_banks(num_bins, padded_len, sr, low_freq=20.0, high_freq=0.0):
    # torchaudio.compliance.kaldi.get_mel_banks (no VTLN): [num_bins, padded_len//2+1]
    nfft = padded_len // 2
    nyq = 0.5 * sr
    if high_freq <= 0.0:
        high_freq += nyq
    scale = lambda f: 1127.0 * math.log(1.0 + f / 700.0)
    inv = lambda m: 700.0 * (math.exp(m / 1127.0) - 1.0)
    bin_w = sr / padded_len
    mel_l, mel_h = scale(low_freq), scale(high_freq)
    delta = (mel_h - mel_l) / (num_bins + 1)
    b = mx.arange(num_bins, dtype=mx.float32)
    left = mel_l + b * delta
    center = mel_l + (b + 1.0) * delta
    right = mel_l + (b + 2.0) * delta
    mel = mx.array([scale(bin_w * i) for i in range(nfft)], dtype=mx.float32)[None]  # [1,nfft]
    up = (mel - left[:, None]) / (center - left)[:, None]
    down = (right[:, None] - mel) / (right[:, None] - center[:, None])
    banks = mx.maximum(0.0, mx.minimum(up, down))  # [num_bins, nfft]
    return mx.pad(banks, [(0, 0), (0, 1)])  # [num_bins, nfft+1] (nyquist col zero)


def kaldi_povey_window(n):
    # torch.hann_window(n, periodic=False)**0.85
    k = mx.arange(n, dtype=mx.float32)
    return mx.power(0.5 - 0.5 * mx.cos(2 * math.pi * k / (n - 1)), 0.85)


def sinc_kernel(orig_freq, new_freq, lowpass_filter_width=6, rolloff=0.99):
    # torchaudio _get_sinc_resample_kernel (sinc_interp_hann), computed in f64
    # (numpy = IEEE f64, identical to torch; GPU has no fp64)
    import numpy as np

    g = math.gcd(orig_freq, new_freq)
    orig_freq, new_freq = orig_freq // g, new_freq // g
    base_freq = min(orig_freq, new_freq) * rolloff
    width = math.ceil(lowpass_filter_width * orig_freq / base_freq)
    idx = np.arange(-width, width + orig_freq, dtype=np.float64)[None, None] / orig_freq
    t = np.arange(0, -new_freq, -1, dtype=np.float64)[:, None, None] / new_freq + idx
    t = t * base_freq
    t = np.clip(t, -lowpass_filter_width, lowpass_filter_width)
    window = np.cos(t * math.pi / lowpass_filter_width / 2) ** 2
    t = t * math.pi
    # np.where evaluates both branches and therefore emitted a harmless
    # divide-by-zero warning at the exact sinc origin.  np.sinc(x / pi) is
    # the same normalized kernel and defines that point directly as 1.
    kernels = np.sinc(t / math.pi) * window * (base_freq / orig_freq)
    return mx.array(kernels.astype(np.float32)), width  # [new_freq,1,2w+orig] f32


def sinc_resample(x, orig_freq, new_freq, kernel):
    # torchaudio _apply_sinc_resample_kernel; freqs reduced by gcd first.
    # kernel [new_freq,1,K] (torch NCL) -> mlx [new_freq,K,1] via transpose(0,2,1)
    g = math.gcd(orig_freq, new_freq)
    orig_freq, new_freq = orig_freq // g, new_freq // g
    width = (kernel.shape[-1] - orig_freq) // 2
    B, T = x.shape
    xp = mx.pad(x, [(0, 0), (width, width + orig_freq)])
    y = mx.conv1d(xp[:, :, None], kernel.transpose(0, 2, 1), stride=orig_freq)  # [B, L', new] t-major (torch layout)
    y = y.reshape(B, -1)
    return y[:, : (new_freq * T + orig_freq - 1) // orig_freq]  # ceil(T*new/orig)
