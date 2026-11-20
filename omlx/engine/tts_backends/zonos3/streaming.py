# Copyright (c) 2026 Zyphra, Inc.

"""Streaming host half of the iSTFT codec decoder: overlap-add iSTFT + FIR mixer, then the 44160 -> 44100 Hz resampler.

Line-for-line NumPy ports of the web server's `IstftHead` (servers/web/src/istft.ts) and `Resampler`
(servers/web/src/resample.ts), which port zac.cpp's head_push / ola_finalize / mix_emit / head_flush / resample.
Both return only final samples: after F head frames pushed, the iSTFT stream has emitted everything the whole
`torch.istft(center=True)` + mixer decode would produce up to the mixer's right-hand taps; `flush()` emits the rest.
Arithmetic is float64; outputs are float32.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

_EMPTY = np.zeros(0, np.float32)


class IstftHeadStream:
    """Two-branch centered iSTFT (shared hop) followed by the linear FIR mixer, fed head frames incrementally."""

    def __init__(self, n_ffts, hop, windows, mixer, max_log_mag):
        self.n_ffts = [int(n) for n in n_ffts]
        self.hop = int(hop)
        self.windows = [np.asarray(w, np.float64) for w in windows]
        self.mixer = np.asarray(mixer, np.float64)
        if (
            self.mixer.ndim != 2
            or self.mixer.shape[0] != 2
            or self.mixer.shape[1] % 2 != 1
        ):
            raise ValueError("istft: mixer kernel must be odd")
        for n, w in zip(self.n_ffts, self.windows):
            if len(w) != n or n % self.hop:
                raise ValueError(
                    f"istft: window of {len(w)} taps for n_fft {n}, hop {self.hop}"
                )
        self.max_log_mag = float(max_log_mag)
        self.K = self.mixer.shape[1]
        self.h = (self.K - 1) // 2
        self.ola = [np.zeros(0), np.zeros(0)]
        self.env = [np.zeros(0), np.zeros(0)]
        self.ola_base = [0, 0]
        self.mix_in = [
            np.zeros(self.h),
            np.zeros(self.h),
        ]  # index 0 sits at absolute mix_base
        self.mix_base = self.mix_next = 0
        self.frames = 0
        self.done = False

    def push(self, y0, y1):
        """y_i [cols, n_i + 2]: log-magnitude for n_i//2+1 bins, then phase. Returns the 44160 Hz samples now final."""
        if self.done:
            raise RuntimeError("istft: push after flush")
        cols = None
        for i, y in enumerate((y0, y1)):
            n, hop = self.n_ffts[i], self.hop
            bins = n // 2 + 1
            y = np.asarray(y, np.float64)
            if (
                y.ndim != 2
                or y.shape[1] != n + 2
                or (cols is not None and y.shape[0] != cols)
            ):
                raise ValueError(
                    f"istft: branch {i} has shape {y.shape}, expected [cols, {n + 2}]"
                )
            cols = y.shape[0]
            if cols == 0:
                return _EMPTY
            mag = np.exp(np.minimum(y[:, :bins], self.max_log_mag))
            ph = y[:, bins:]
            imag = mag * np.sin(ph)
            imag[:, 0] = 0.0
            imag[:, -1] = 0.0
            win = self.windows[i]
            frames = np.fft.irfft(mag * np.cos(ph) + 1j * imag, n, axis=-1) * win
            r = n // hop
            span = (cols + r - 1) * hop
            add = np.zeros(span)
            env = np.zeros(span)
            parts = frames.reshape(cols, r, hop)
            w2 = np.broadcast_to((win * win).reshape(r, hop), (cols, r, hop))
            for j in range(r):
                add[j * hop : (j + cols) * hop] += parts[:, j].ravel()
                env[j * hop : (j + cols) * hop] += w2[:, j].ravel()
            o = self.frames * hop - self.ola_base[i]
            need = o + span
            if len(self.ola[i]) < need:
                grow = need - len(self.ola[i])
                self.ola[i] = np.concatenate([self.ola[i], np.zeros(grow)])
                self.env[i] = np.concatenate([self.env[i], np.zeros(grow)])
            self.ola[i][o:need] += add
            self.env[i][o:need] += env
        self.frames += cols
        for i in range(2):
            self._finalize(i, self.frames * self.hop)
        return self._mix_emit()

    def flush(self):
        """End of stream: every sample m < frames*hop is final; the mixer sees h zeros after the last sample."""
        if self.done or self.frames == 0:
            return _EMPTY
        self.done = True
        L = self.frames * self.hop
        for i in range(2):
            self._finalize(i, self.ola_base[i] + len(self.ola[i]))
            keep = self.h + L - self.mix_base
            m = self.mix_in[i]
            m = (
                m[:keep]
                if len(m) >= keep
                else np.concatenate([m, np.zeros(keep - len(m))])
            )
            self.mix_in[i] = np.concatenate([m, np.zeros(self.h)])
        return self._mix_emit()

    def _finalize(self, i, pf):
        """Moves overlap-add positions [ola_base, pf) of branch i into the mixer input, dropping the centre padding."""
        n = pf - self.ola_base[i]
        if n <= 0:
            return
        skip = min(n, max(0, self.n_ffts[i] // 2 - self.ola_base[i]))
        self.mix_in[i] = np.concatenate(
            [self.mix_in[i], self.ola[i][skip:n] / self.env[i][skip:n]]
        )
        self.ola[i] = self.ola[i][n:]
        self.env[i] = self.env[i][n:]
        self.ola_base[i] = pf

    def _mix_emit(self):
        """y[m] = sum_c sum_k mixer[c][k] * mix_in_c[m + k] for every m whose taps are available."""
        K = self.K
        m1 = min(len(m) for m in self.mix_in) + self.mix_base - K + 1
        if m1 <= self.mix_next:
            return _EMPTY
        take = m1 - self.mix_base + K - 1
        y = sum(
            np.correlate(self.mix_in[c][:take], self.mixer[c], "valid")
            for c in range(2)
        )
        drop = m1 - self.mix_base
        self.mix_in = [m[drop:] for m in self.mix_in]
        self.mix_base = self.mix_next = m1
        return y.astype(np.float32)


class ResamplerStream:
    """Streaming torchaudio sinc resampler: out[n*new + i] = sum_k kernel[i][k] * x[n*orig + k - width]."""

    def __init__(self, kernel, orig, new, width):
        self.orig, self.new, self.width = int(orig), int(new), int(width)
        self.kl = 2 * self.width + self.orig
        self.kernel = np.asarray(kernel, np.float64)
        if self.kernel.shape != (self.new, self.kl):
            raise ValueError(
                f"resampler: kernel shape {self.kernel.shape}, expected {(self.new, self.kl)}"
            )
        self.buf = np.zeros(0)
        self.base = 0  # absolute index of buf[0]
        self.n_in = 0  # samples pushed
        self.next_block = 0

    def push(self, x):
        x = np.asarray(x, np.float64).ravel()
        self.buf = np.concatenate([self.buf, x])
        self.n_in += len(x)
        return self._run(False)

    def flush(self):
        return self._run(True)

    def _run(self, flush):
        O, N, W, KL = self.orig, self.new, self.width, self.kl
        if flush:
            total = -(-N * self.n_in // O)
            end = -(-total // N)
        else:
            reach = self.n_in + W - KL
            end = reach // O + 1 if reach >= 0 else 0
        out = _EMPTY
        if end > self.next_block:
            lo = self.next_block * O - W
            hi = (end - 1) * O - W + KL
            seg = np.zeros(hi - lo)
            a, b = max(lo, 0), min(hi, self.n_in)
            if b > a:
                seg[a - lo : b - lo] = self.buf[a - self.base : b - self.base]
            win = sliding_window_view(seg, KL)[::O][: end - self.next_block]
            y = (win @ self.kernel.T).ravel()
            if flush:
                y = y[: total - self.next_block * N]
            out = y.astype(np.float32)
            self.next_block = end
        keep_from = min(self.n_in, max(0, self.next_block * O - W))
        if keep_from > self.base:
            self.buf = self.buf[keep_from - self.base :]
            self.base = keep_from
        return out
