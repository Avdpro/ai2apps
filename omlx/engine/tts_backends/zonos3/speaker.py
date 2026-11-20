# Copyright (c) 2026 Zyphra, Inc.

"""ZONOS3 Mini speaker encoder (ownmect_s2: Kaldi fbank + MECT-B2 + ASTP, 192-d) on MLX.

A port of servers/ggml/src/spk-encoder.cpp over the GGUF layout of ``tools/convert_gguf.py speaker-encoder`` (SPK_DOC).
The frontend uses float64 on the CPU: MLX for 16 kHz resampling, NumPy for Kaldi fbank and CMN.
The network runs in MLX with NHWC activations ``[1, F, T, C]`` (mel = height, time = width).
"""

from __future__ import annotations

import math
from pathlib import Path

import mlx.core as mx
import numpy as np

from .audio import polyphase_resample
from .weights import NativeFile

ARCH = "mect_spk"
HIDDEN, FEAT = 64, 2560
MAX_SAMPLES_16K = 60 * 16000
# MECT_B2 per stage: (cnn depth, out channels, stride F, stride T, expansion) per block.
MECT_B2 = (
    [(3, 32, 1, 1, 4)] * 2,
    [(3, 64, 2, 1, 2)] + [(3, 64, 1, 2, 2)] * 3,
    [(3, 128, 2, 1, 2)] + [(3, 128, 1, 2, 2)] * 4,
    [(3, 256, 2, 1, 1)] + [(2, 256, 1, 2, 1)] * 2,
)


def _new_gelu(x: mx.array) -> mx.array:
    return (
        0.5 * x * (1.0 + mx.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x * x * x)))
    )


def _gelu_erf(x: mx.array) -> mx.array:
    return 0.5 * x * (1.0 + mx.erf(x * (1.0 / math.sqrt(2.0))))


class SpeakerEncoder:
    def __init__(self, path: str | Path):
        f = NativeFile(path)
        if f.arch != ARCH or f.meta(f"{ARCH}.backbone") != "MECT_B2":
            raise ValueError(f"{path}: expected a MECT-B2 speaker encoder checkpoint")
        k = lambda key: f.meta(f"{ARCH}.{key}")
        self.path = str(path)
        self.embedding_length = int(k("embedding_length"))
        self.n_mels, self.frame_length, self.frame_shift = (
            int(k("n_mels")),
            int(k("frame_length")),
            int(k("frame_shift")),
        )
        self.n_fft = int(k("n_fft"))
        self.n_heads = int(k("n_heads"))
        self.pos_kernel = int(k("pos_kernel"))
        self.preemph = float(k("preemphasis"))
        self.scale = float(k("waveform_scale"))
        self.log_floor = float(k("log_floor"))
        self.ln_eps = float(k("ln_eps"))
        self.var_floor = float(k("pool_var_floor"))
        self.window = f.array("frontend.window").astype(np.float64)
        self.mel_banks = f.array("frontend.mel_banks").astype(np.float64)  # [80, 257]
        with mx.stream(mx.cpu):
            self.resample_kernel = mx.array(
                f.array("frontend.resample_44100"), dtype=mx.float64
            )  # [160, 475]
        self.t: dict[str, mx.array] = {}
        names = set(f.names())
        for name in names:
            if name.startswith("frontend."):
                continue
            self.t[name] = mx.array(f.array(name).astype(np.float32))
        # Grouped 3x3 convs: the per-slot w{j} [OC, 1, 3, 3] tensors -> MLX [OC, 3, 3, a] with groups = IC / a.
        self.grouped: dict[str, mx.array] = {}
        for name in sorted(n for n in names if n.endswith(".w0")):
            prefix = name[:-3]
            slots = []
            while f"{prefix}.w{len(slots)}" in names:
                slots.append(f.array(f"{prefix}.w{len(slots)}").astype(np.float32))
            self.grouped[prefix] = mx.array(
                np.concatenate(slots, axis=1).transpose(0, 2, 3, 1)
            )
        mx.eval(list(self.t.values()) + list(self.grouped.values()))

    @classmethod
    def load(cls, path: str | Path) -> SpeakerEncoder:
        return cls(path)

    # --------------------------------------------------------------------------------------------- frontend
    def fbank(self, wav16: np.ndarray) -> np.ndarray:
        """Kaldi fbank (spk-encoder.cpp fbank_host) of the first <= 60 s of 16 kHz audio -> [T, 80]."""
        wav = np.asarray(wav16, dtype=np.float64)[:MAX_SAMPLES_16K]
        fl, fs = self.frame_length, self.frame_shift
        if len(wav) < fl:
            raise ValueError("speaker audio is shorter than 25 ms")
        T = 1 + (len(wav) - fl) // fs
        frames = wav[np.arange(T)[:, None] * fs + np.arange(fl)[None, :]] * self.scale
        frames = frames - frames.mean(axis=1, keepdims=True)
        shifted = np.concatenate([frames[:, :1], frames[:, :-1]], axis=1)
        frames = (frames - self.preemph * shifted) * self.window
        spec = np.fft.rfft(frames, n=self.n_fft, axis=1)
        power = spec.real**2 + spec.imag**2
        return np.log(np.maximum(power @ self.mel_banks.T, self.log_floor)).astype(
            np.float32
        )

    # -------------------------------------------------------------------------------------------- network
    def _bn(self, x, p):
        return x * self.t[p + ".scale"] + self.t[p + ".shift"]

    def _pw(self, x, p, bias=True):
        w = self.t[p + ".weight"]
        y = x @ w.reshape(w.shape[0], w.shape[1]).T
        return y + self.t[p + ".bias"] if bias else y

    def _lin(self, x, p, bias=True):
        y = x @ self.t[p + ".weight"].T
        return y + self.t[p + ".bias"] if bias else y

    def _ln(self, x, p):
        return mx.fast.layer_norm(
            x, self.t[p + ".weight"], self.t[p + ".bias"], self.ln_eps
        )

    def _grouped(self, x, p, s_f, s_t):
        w = self.grouped[p]
        groups = x.shape[-1] // w.shape[-1]
        return mx.conv2d(x, w, stride=(s_f, s_t), padding=1, groups=groups)

    def _res_block(self, x, q, s_f, s_t):
        t = self._grouped(x, q + "conv1", s_f, s_t)
        t = mx.maximum(self._bn(self._pw(t, q + "pw1"), q + "bn1"), 0.0)
        t = self._grouped(t, q + "conv2", 1, 1)
        t = mx.maximum(self._bn(self._pw(t, q + "pw2"), q + "bn2"), 0.0)
        sc = x
        if q + "sc.weight" in self.t:
            sc = self._bn(
                self._pw(x[:, ::s_f, ::s_t, :], q + "sc", bias=False), q + "sc.bn"
            )
        return t + sc

    def _attention(self, h, p):
        T = h.shape[0]
        nh, hd = self.n_heads, HIDDEN // self.n_heads
        heads = lambda z: z.reshape(T, nh, hd).transpose(1, 0, 2)[None]
        q = heads(self._lin(h, p + "attn.q") * (1.0 / math.sqrt(hd)))
        k, v = heads(self._lin(h, p + "attn.k")), heads(self._lin(h, p + "attn.v"))
        o = (
            mx.fast.scaled_dot_product_attention(q, k, v, scale=1.0)[0]
            .transpose(1, 0, 2)
            .reshape(T, HIDDEN)
        )
        return self._lin(o, p + "attn.o")

    def _moe(self, h, p):
        r = mx.softmax(h @ self.t[p + "moe.gate.weight"].T, axis=-1)  # [T, 4]
        e = _new_gelu(h @ self.t[p + "moe.experts.weight"].T).reshape(
            h.shape[0], -1, HIDDEN
        )  # [T, 4, 64]
        mix = (e * r[:, :, None]).sum(axis=1)
        return self._lin(_new_gelu(mix), p + "ffn_out")

    def _pos_conv(self, h, p):
        """Zero-padded depthwise Conv1d (K = 113) over time, BN, exact GELU, pointwise."""
        pad = self.pos_kernel // 2
        w = self.t[p + "pos.dw.weight"]  # [64, K]
        hp = mx.concatenate(
            [mx.zeros((pad, HIDDEN)), h, mx.zeros((pad, HIDDEN))], axis=0
        )
        acc = mx.conv1d(hp[None], w[:, :, None], groups=HIDDEN)[0]  # [T, 64]
        acc = acc + self.t[p + "pos.dw.bias"]
        acc = acc * self.t[p + "pos.bn.scale"] + self.t[p + "pos.bn.shift"]
        return self._lin(_gelu_erf(acc), p + "pos.pw")

    @staticmethod
    def _flatten(x):
        """[1, F, T, C] -> [T, F*C] with k = f*C + c."""
        _, F, T, C = x.shape
        return x[0].transpose(1, 0, 2).reshape(T, F * C)

    @staticmethod
    def _unflatten(x, F, C):
        return x.reshape(x.shape[0], F, C).transpose(1, 0, 2)[None]

    def _block(self, x, xf, cfg, p):
        cnn, _out_ch, s_f, s_t, _expansion = cfg
        T = x.shape[2]
        y = x
        for r in range(cnn):
            y = self._res_block(
                y, f"{p}cnn.{r}.", s_f if r == 0 else 1, s_t if r == 0 else 1
            )
        if p + "reduce.weight" in self.t:
            y = self._bn(self._pw(y, p + "reduce"), p + "reduce.bn")
        _, F2, _, C2 = y.shape
        x2 = self._flatten(y)
        h = self._ln(self._lin(x2, p + "rproj"), p + "rproj.ln")
        h = h + self._pos_conv(h, p)
        h = self._ln(h + self._attention(h, p), p + "ln1")
        h = self._ln(h + self._moe(h, p), p + "ln2")
        e = self._lin(h, p + "eproj") + x2
        if s_t > 1:
            e = mx.repeat(e, s_t, axis=0)[:T]
        out = e + xf
        return self._unflatten(out, F2, C2), out

    def embed(self, pcm44100: np.ndarray, dump: dict | None = None) -> np.ndarray:
        """Mono float32 44.1 kHz PCM -> the 192-d speaker embedding (not L2-normalized)."""
        wav16 = polyphase_resample(pcm44100, self.resample_kernel, 441, 160, 17)
        fb = self.fbank(wav16)
        cmn = (
            fb.astype(np.float64) - fb.astype(np.float64).mean(axis=0, keepdims=True)
        ).astype(np.float32)
        if dump is not None:
            dump["fbank"], dump["fbank_cmn"] = fb, cmn
        x = mx.array(cmn.T[None, :, :, None])  # [1, 80, T, 1]
        w = self.t["fe.head.conv.weight"].transpose(0, 2, 3, 1)  # [32, 3, 3, 1]
        x = self._bn(
            mx.conv2d(x, w, padding=1) + self.t["fe.head.conv.bias"], "fe.head.bn"
        )
        xf = self._flatten(x)
        feats = []
        for s, stage in enumerate(MECT_B2):
            for k, cfg in enumerate(stage):
                x, xf = self._block(x, xf, cfg, f"fe.b{s + 1}.{k}.")
                mx.eval(x, xf)
            feats.append(xf)
        dense = self.t["fe.dense_w"]  # [4, 2560]
        fused = sum(feats[s] * dense[s] for s in range(4))
        att = self._lin(mx.tanh(self._lin(fused, "pool.l1")), "pool.l2")  # [T, 2560]
        alpha = mx.softmax(att, axis=0)
        mean = (alpha * fused).sum(axis=0)
        var = (alpha * fused * fused).sum(axis=0) - mean * mean
        std = mx.sqrt(mx.maximum(var, self.var_floor))
        pooled = mx.concatenate([mean, std])
        emb = (pooled * self.t["bn.scale"] + self.t["bn.shift"]) @ self.t[
            "linear.weight"
        ].T
        mx.eval(emb, pooled)
        out = np.array(emb, dtype=np.float32)
        if dump is not None:
            for s in range(4):
                dump[f"feat_{s + 1}"] = np.array(feats[s])
            dump["pooled"] = np.array(pooled)[None]
            dump["embedding"] = out[None]
        if not np.isfinite(out).all():
            raise ValueError("speaker encoder produced a non-finite embedding")
        return out
