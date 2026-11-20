# Copyright (c) 2026 Zyphra, Inc.

"""Causal ZAC decoder: semantic/acoustic RVQ, windowed MOSS transformers,
ConvNeXt, multi-resolution iSTFT, and exact 44160-to-44100 Hz resampling.
Both whole-utterance and incremental decoding use native safetensors weights.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx
import numpy as np

from .weights import NativeFile, TensorStore

logger = logging.getLogger(__name__)
ARCH = "mossdual_istft"
_ATTN_BLOCK = 512  # query rows per windowed-attention block


@dataclass(frozen=True)
class StageHP:
    in_dim: int
    out_dim: int
    d_model: int
    n_head: int
    n_layer: int
    n_ff: int
    context: int
    patch: int


def _gelu(x: mx.array) -> mx.array:
    return 0.5 * x * (1.0 + mx.erf(x * (1.0 / math.sqrt(2.0))))


def _layer_norm(x: mx.array, w: mx.array, b: mx.array, eps: float) -> mx.array:
    return mx.fast.layer_norm(x, w, b, eps)


class Params(TensorStore):
    def __init__(self, f, host=()):
        super().__init__(f.config["tensors"])
        self.load_weights(
            list(mx.load(str(f.root / "model.safetensors")).items()), strict=True
        )
        self.host = {name: np.array(self.t[name]) for name in host}

    def lin(self, name, x, bias=None):
        y = self.w[name](x)
        return y if bias is None else y + self.t[bias]


def _identity(x: mx.array) -> mx.array:
    return x


def causal_depthwise(
    x: mx.array, w: mx.array, b: mx.array | None, hist: mx.array | None = None
) -> mx.array:
    """x [T, C], w [C, K] (tap 0 oldest): h[t] = sum_k x[t + k - (K - 1)] * w[:, k]; the K-1 rows before x are ``hist``
    [K-1, C] (zeros when None)."""
    T, K = x.shape[0], w.shape[1]
    if hist is None:
        hist = mx.zeros((K - 1, x.shape[1]), dtype=x.dtype)
    xf = mx.concatenate([hist.astype(x.dtype), x], axis=0)
    h = xf[0:T] * w[:, 0]
    for k in range(1, K):
        h = h + xf[k : k + T] * w[:, k]
    return h if b is None else h + b


def convnext_block(
    P: Params,
    x: mx.array,
    p: str,
    eps: float,
    rnd=_identity,
    round_out: bool = False,
    hist: mx.array | None = None,
) -> mx.array:
    """Causal ConvNeXt block. ``rnd`` marks the encoder's BF16 boundaries (zac.cpp ``encoder_round``; identity for the
    decoder), ``round_out`` its rounded output (the semantic encoder's blocks); ``hist``: the previous K-1 inputs.
    """
    h = causal_depthwise(rnd(x), P.t[p + ".dw.weight"], None, hist)
    h = rnd(rnd(h) + P.t[p + ".dw.bias"])
    h = rnd(_layer_norm(h, P.t[p + ".norm.weight"], P.t[p + ".norm.bias"], eps))
    h = rnd(_gelu(rnd(P.lin(p + ".pw1.weight", h, p + ".pw1.bias"))))
    h = rnd(P.lin(p + ".pw2.weight", h, p + ".pw2.bias"))
    y = x + h
    return rnd(y) if round_out else y


def patch_up(x: mx.array, h: int) -> mx.array:
    """out[t*h + j, ch] = in[t, ch*h + j]."""
    T, C = x.shape
    return x.reshape(T, C // h, h).transpose(0, 2, 1).reshape(T * h, C // h)


def windowed_attention(
    q: mx.array, k: mx.array, v: mx.array, context: int, scale: float
) -> mx.array:
    """q, k, v [heads, T, hd] at positions 0..T-1; keys with 0 <= q_pos - k_pos < context; blocked over queries."""
    T = q.shape[1]
    outs = []
    for a in range(0, T, _ATTN_BLOCK):
        e = min(a + _ATTN_BLOCK, T)
        left = max(0, a - context + 1)
        qp = mx.arange(a, e)[:, None]
        kp = mx.arange(left, e)[None, :]
        diff = qp - kp
        mask = (diff >= 0) & (diff < context)
        outs.append(
            mx.fast.scaled_dot_product_attention(
                q[None, :, a:e],
                k[None, :, left:e],
                v[None, :, left:e],
                scale=scale,
                mask=mask,
            )[0]
        )
    return outs[0] if len(outs) == 1 else mx.concatenate(outs, axis=1)


def moss_layer(
    P: Params, x: mx.array, p: str, hp: StageHP, ln_eps: float, rnd=_identity
) -> mx.array:
    """Pre-LN windowed-causal attention (adjacent-pair RoPE over absolute stage positions) + GELU FFN, layer scales.
    ``rnd``: the encoder's BF16 boundaries (identity for the decoder)."""
    T, d = x.shape
    nh = hp.n_head
    hd = d // nh
    h = _layer_norm(x, P.t[p + ".norm1.weight"], P.t[p + ".norm1.bias"], ln_eps)
    qkv = (
        rnd(P.lin(p + ".qkv.weight", rnd(h)))
        .reshape(T, 3, nh, hd)
        .transpose(1, 2, 0, 3)
    )  # [3, nh, T, hd]
    q = rnd(
        mx.fast.rope(qkv[0], hd, traditional=True, base=10000.0, scale=1.0, offset=0)
    )
    k = rnd(
        mx.fast.rope(qkv[1], hd, traditional=True, base=10000.0, scale=1.0, offset=0)
    )
    o = rnd(
        windowed_attention(q, k, qkv[2], hp.context, hd**-0.5)
        .transpose(1, 0, 2)
        .reshape(T, d)
    )
    x = x + rnd(P.lin(p + ".wo.weight", o)) * P.t[p + ".attn_scale"]
    h = _layer_norm(x, P.t[p + ".norm2.weight"], P.t[p + ".norm2.bias"], ln_eps)
    h = rnd(
        P.lin(p + ".ffn2.weight", rnd(_gelu(rnd(P.lin(p + ".ffn1.weight", rnd(h))))))
    )
    return x + h * P.t[p + ".ffn_scale"]


def moss_layer_cached(
    P: Params,
    x: mx.array,
    p: str,
    hp: StageHP,
    ln_eps: float,
    pos0: int,
    cache: tuple[mx.array, mx.array] | None,
) -> tuple[mx.array, tuple[mx.array, mx.array] | None]:
    """``moss_layer`` (decoder, no rounding) on stage positions [pos0, pos0+T) attending to ``cache``: the keys/values
    [nh, Lc, hd] of the previous positions. Returns the output and the cache of the last context-1 positions.
    """
    T, d = x.shape
    nh = hp.n_head
    hd = d // nh
    h = _layer_norm(x, P.t[p + ".norm1.weight"], P.t[p + ".norm1.bias"], ln_eps)
    qkv = (
        P.lin(p + ".qkv.weight", h).reshape(T, 3, nh, hd).transpose(1, 2, 0, 3)
    )  # [3, nh, T, hd]
    q = mx.fast.rope(qkv[0], hd, traditional=True, base=10000.0, scale=1.0, offset=pos0)
    k = mx.fast.rope(qkv[1], hd, traditional=True, base=10000.0, scale=1.0, offset=pos0)
    v = qkv[2]
    if cache is not None:
        k = mx.concatenate([cache[0], k], axis=1)
        v = mx.concatenate([cache[1], v], axis=1)
    lc = k.shape[1] - T
    diff = mx.arange(pos0, pos0 + T)[:, None] - mx.arange(pos0 - lc, pos0 + T)[None, :]
    mask = (diff >= 0) & (diff < hp.context)
    o = mx.fast.scaled_dot_product_attention(
        q[None], k[None], v[None], scale=hd**-0.5, mask=mask
    )[0]
    x = (
        x
        + P.lin(p + ".wo.weight", o.transpose(1, 0, 2).reshape(T, d))
        * P.t[p + ".attn_scale"]
    )
    h = _layer_norm(x, P.t[p + ".norm2.weight"], P.t[p + ".norm2.bias"], ln_eps)
    h = P.lin(p + ".ffn2.weight", _gelu(P.lin(p + ".ffn1.weight", h)))
    keep = hp.context - 1
    cache = (k[:, -keep:], v[:, -keep:]) if keep > 0 else None
    return x + h * P.t[p + ".ffn_scale"], cache


def read_stages(f: NativeFile, arch: str) -> list[StageHP]:
    k = lambda key: [int(v) for v in f.meta(f"{arch}.stage.{key}")]
    cols = [
        k(n)
        for n in (
            "in_dim",
            "out_dim",
            "d_model",
            "n_head",
            "n_layer",
            "n_ff",
            "context",
            "patch",
        )
    ]
    return [StageHP(*vals) for vals in zip(*cols)]


def sinc_resample(
    x: mx.array, kernel: mx.array, orig: int, new: int, width: int
) -> mx.array:
    """torchaudio-style polyphase resampling: out[n*new + i] = sum_k K[i][k] x[n*orig + k - width], zero outside,
    total ceil(new * len / orig) samples (zac.cpp ``resample``)."""
    L = int(x.shape[0])
    total = -(-new * L // orig)
    blocks = -(-total // new)
    KL = 2 * width + orig
    pad_right = blocks * orig + orig - (L + width)
    xp = mx.concatenate(
        [mx.zeros((width,), x.dtype), x, mx.zeros((max(pad_right, 0),), x.dtype)]
    )
    a = xp[: blocks * orig].reshape(blocks, orig)
    b = xp[orig : orig + blocks * orig].reshape(blocks, orig)[:, : KL - orig]
    windows = mx.concatenate([a, b], axis=1)  # [blocks, KL]
    return (windows @ kernel.T).reshape(-1)[:total]


class CodecDecoder:
    def __init__(self, path: str | Path):
        f = NativeFile(path)
        if f.arch != ARCH:
            raise ValueError(
                f"{path}: not a ZONOS3 Mini iSTFT decoder checkpoint (architecture {f.arch!r})"
            )
        k = lambda key: f.meta(f"{ARCH}.{key}")
        self.path = str(path)
        self.name = Path(path).name
        self.sample_rate = int(k("sample_rate"))
        self.hop = int(k("hop"))
        self.internal_hop = int(k("internal_hop"))
        self.n_codebooks = int(k("n_codebooks"))
        self.codebook_size = int(k("codebook_size"))
        self.sem_depth = int(k("sem_head.depth"))
        self.head_depth = int(k("head.depth"))
        self.head_hop = int(k("head.hop"))
        self.n_fft = [int(v) for v in k("head.n_fft")]
        self.max_log_mag = float(k("head.max_log_magnitude"))
        self.headroom_db = float(k("headroom_db"))
        self.ln_eps = float(k("ln_eps"))
        self.convnext_eps = float(k("convnext_eps"))
        self.rs = (
            int(k("resample.orig")),
            int(k("resample.new")),
            int(k("resample.width")),
        )
        self.stages = read_stages(f, ARCH)
        if (self.sample_rate, self.hop, self.internal_hop, self.n_codebooks) != (
            44100,
            2940,
            2944,
            10,
        ):
            raise ValueError(f"{path}: inconsistent decoder dimensions")
        self.P = Params(
            f,
            host=(
                "head.window.0",
                "head.window.1",
                "head.mixer.weight",
                "resample.kernel",
            ),
        )
        host = self.P.host
        self.windows = [mx.array(host[f"head.window.{i}"]) for i in range(2)]
        self.mixer = mx.array(host["head.mixer.weight"])  # [2, K]
        self.rs_kernel = mx.array(host["resample.kernel"])  # [new, 2w + orig]
        self.host_windows = [host[f"head.window.{i}"] for i in range(2)]
        self.host_mixer = host["head.mixer.weight"]
        self.host_rs_kernel = host["resample.kernel"]
        # per-codebook residual out_proj biases (``res.bias`` is their sum): a missing residual code drops its
        # codebook's table row and bias from the frame; without them the early partial-frame decode is off. A host
        # stack, not a lazy mx.stack: the codec thread evaluates it, on its own stream.
        res = [f"res.{i}.bias" for i in range(self.n_codebooks - 1)]
        self.res_biases = None
        if all(n in self.P.t for n in res):
            self.res_biases = mx.stack([self.P.t[n] for n in res])
        else:
            logger.info(
                "%s: no per-codebook residual biases: early partial-frame decode off",
                self.name,
            )

    @property
    def early_decode(self) -> bool:
        """Whether streams decode frames with missing residual codes (``CodecStream.decode`` code -1)."""
        return self.res_biases is not None

    @classmethod
    def load(cls, path: str | Path) -> CodecDecoder:
        return cls(path)

    def stream(self) -> CodecStream:
        """A fresh incremental decoder over one utterance."""
        return CodecStream(self)

    # -------------------------------------------------------------------------------------------------- trunk
    def _trunk(self, codes: mx.array) -> tuple[mx.array, mx.array]:
        P = self.P
        x = P.t["sem.table"][codes[:, 0]] + P.t["sem.bias"]
        for b in range(self.sem_depth):
            x = convnext_block(P, x, f"sem_head.{b}", self.convnext_eps)
        x = P.lin("sem_head.out.weight", x, "sem_head.out.bias")
        x = self._residual(x, codes)
        mx.eval(x)
        for s, hp in enumerate(self.stages):
            p = f"stage.{s}"
            x = P.lin(p + ".in.weight", x)
            for layer in range(hp.n_layer):
                x = moss_layer(P, x, f"{p}.l{layer}", hp, self.ln_eps)
                mx.eval(x)
            if hp.out_dim > 0:
                x = P.lin(p + ".out.weight", x)
            if hp.patch > 1:
                x = patch_up(x, hp.patch)
        for b in range(self.head_depth):
            x = convnext_block(P, x, f"head.{b}", self.convnext_eps)
            mx.eval(x)
        x = _layer_norm(
            x, P.t["head.norm.weight"], P.t["head.norm.bias"], self.convnext_eps
        )
        return P.lin("head.out.0.weight", x, "head.out.0.bias"), P.lin(
            "head.out.1.weight", x, "head.out.1.bias"
        )

    def _residual(
        self, x: mx.array, ids: mx.array, missing: np.ndarray | None = None
    ) -> mx.array:
        """x + the residual codebooks of ``ids`` [n, n_codebooks] (their folded tables and ``res.bias``). ``missing``
        [n, n_codebooks - 1] marks the residual codes left out: their table rows and biases are not added (the other
        frames' sums are bit-identical to the complete decode)."""
        P = self.P
        if missing is None or not missing.any():
            for c in range(1, self.n_codebooks):
                x = x + P.t[f"res.{c - 1}.table"][ids[:, c]]
            return x + P.t["res.bias"]
        if self.res_biases is None:
            raise ValueError(
                f"{self.name} has no per-codebook residual biases: residual codes cannot be missing"
            )
        present = mx.array(~missing)
        for c in range(1, self.n_codebooks):
            x = x + mx.where(
                present[:, c - 1 : c], P.t[f"res.{c - 1}.table"][ids[:, c]], 0.0
            )
        x = x + P.t["res.bias"]
        dropped = mx.array(missing.astype(np.float32)) @ self.res_biases
        return mx.where(mx.array(missing.any(axis=1))[:, None], x - dropped, x)

    # ---------------------------------------------------------------------------------------------- iSTFT head
    def _istft(self, spec: mx.array, i: int) -> mx.array:
        """torch.istft(center=True, length=F*hop) of one branch: spec [F, n_fft + 2] = logmag | phase."""
        n, hop = self.n_fft[i], self.head_hop
        bins = n // 2 + 1
        F = spec.shape[0]
        mag = mx.exp(mx.minimum(spec[:, :bins], self.max_log_mag))
        phase = spec[:, bins : 2 * bins]
        real = mag * mx.cos(phase)
        imag = mag * mx.sin(phase)
        edge = ((mx.arange(bins) > 0) & (mx.arange(bins) < bins - 1)).astype(mx.float32)
        frames = (
            mx.fft.irfft(real + 1j * (imag * edge), n=n, axis=-1).astype(mx.float32)
            * self.windows[i]
        )
        r = n // hop
        chunks = frames.reshape(F, r, hop)
        ola = mx.zeros((F + r - 1, hop), dtype=mx.float32)
        for j in range(r):
            ola = ola + mx.pad(chunks[:, j], [(j, r - 1 - j), (0, 0)])
        win2 = mx.square(self.windows[i]).reshape(r, hop)
        env = mx.zeros((F + r - 1, hop), dtype=mx.float32)
        for j in range(r):
            env[j : j + F] += win2[j]
        pad, length = n // 2, F * hop
        return (ola.reshape(-1) / mx.maximum(env.reshape(-1), 1e-12))[
            pad : pad + length
        ]

    def _mix(self, s0: mx.array, s1: mx.array) -> mx.array:
        K = self.mixer.shape[1]
        x = mx.stack([s0, s1], axis=-1)[None]  # [1, L, 2]
        w = self.mixer.T[None]  # [1, K, 2]
        return mx.conv1d(x, w, padding=(K - 1) // 2)[0, :, 0]

    # ------------------------------------------------------------------------------------------------- public
    def decode(self, codes: mx.array) -> mx.array:
        """Ordinary codes [frames, n_codebooks] -> float32 PCM [frames * hop] at 44100 Hz (pre-gain)."""
        codes = mx.array(codes)
        if codes.ndim != 2 or codes.shape[1] != self.n_codebooks:
            raise ValueError(
                f"codes must be [frames, {self.n_codebooks}], got {codes.shape}"
            )
        frames = int(codes.shape[0])
        if frames == 0:
            return mx.zeros((0,), dtype=mx.float32)
        if mx.any((codes < 0) | (codes >= self.codebook_size)).item():
            raise ValueError("codes contain non-codec tokens")
        ids = codes.astype(mx.int32)
        y0, y1 = self._trunk(ids)
        mixed = self._mix(self._istft(y0, 0), self._istft(y1, 1))
        audio = sinc_resample(mixed, self.rs_kernel, *self.rs)
        mx.eval(audio)
        # every prefix length is a new set of buffer sizes: without this the MLX buffer cache grows past 9 GiB over one
        # long stream, and the memory pressure slows the next decodes and stalls the backbone's next prefill for seconds
        mx.clear_cache()
        want = frames * self.hop
        if len(audio) >= want:
            return audio[:want]
        return mx.pad(audio, [(0, want - len(audio))])

    def output_gain(self, headroom_db: float | None) -> float:
        db = self.headroom_db if headroom_db is None else float(headroom_db)
        return float(10.0 ** (-db / 20.0))


class CodecStream:
    """Incremental ``CodecDecoder.decode``: ``decode(codes [n, n_codebooks])`` returns the 44100 Hz samples that are
    final (2940*F - 1470 after F frames), ``flush()`` the rest; the concatenation equals the whole decode. Conv
    histories and per-layer KV caches carry the trunk state; the overlap-add iSTFT, the FIR mixer and the resampler run
    on the host (zonos3.codec.stream_host, ports of zac.cpp's). A residual code (codebook >= 1) of -1 is missing:
    that codebook's contribution is left out of the frame, a coarser RVQ decode (the codec trained with quantizer
    dropout; ``CodecDecoder.early_decode`` decoders only)."""

    def __init__(self, dec: CodecDecoder, max_chunk: int = 32):
        from .streaming import IstftHeadStream, ResamplerStream

        self.dec = dec
        self.max_chunk = int(max_chunk)
        self.frames = 0
        self.sem_hist: list[mx.array | None] = [None] * dec.sem_depth
        self.head_hist: list[mx.array | None] = [None] * dec.head_depth
        self.kv: list[list] = [[None] * hp.n_layer for hp in dec.stages]
        self.head = IstftHeadStream(
            dec.n_fft, dec.head_hop, dec.host_windows, dec.host_mixer, dec.max_log_mag
        )
        self.resampler = ResamplerStream(dec.host_rs_kernel, *dec.rs)

    def decode(self, codes: np.ndarray) -> np.ndarray:
        codes = np.asarray(codes)
        size = self.dec.codebook_size
        if codes.ndim != 2 or codes.shape[1] != self.dec.n_codebooks:
            raise ValueError(
                f"codes must be [frames, {self.dec.n_codebooks}], got {codes.shape}"
            )
        if ((codes < -1) | (codes >= size)).any() or (codes[:, 0] < 0).any():
            raise ValueError(
                f"codes must be codec ids 0..{size - 1} (residual codebooks: -1 = missing)"
            )
        if len(codes) == 0:
            return np.zeros(0, dtype=np.float32)
        codes = codes.astype(np.int32)
        return np.concatenate(
            [
                self._chunk(codes[i : i + self.max_chunk])
                for i in range(0, len(codes), self.max_chunk)
            ]
        )

    def flush(self) -> np.ndarray:
        out = np.concatenate(
            [self.resampler.push(self.head.flush()), self.resampler.flush()]
        )
        mx.clear_cache()
        return out

    def _block(self, x: mx.array, p: str, hists: list, b: int) -> mx.array:
        """convnext_block over the previous inputs' history; keeps the last K-1 inputs for the next chunk."""
        hist = hists[b]
        k = self.dec.P.t[p + ".dw.weight"].shape[1]
        y = convnext_block(self.dec.P, x, p, self.dec.convnext_eps, hist=hist)
        if hist is None:
            hist = mx.zeros((k - 1, x.shape[1]), dtype=x.dtype)
        hists[b] = mx.concatenate([hist, x], axis=0)[-(k - 1) :]
        return y

    def _chunk(self, codes: np.ndarray) -> np.ndarray:
        d, P = self.dec, self.dec.P
        ids = mx.array(np.maximum(codes, 0))
        x = P.t["sem.table"][ids[:, 0]] + P.t["sem.bias"]
        for b in range(d.sem_depth):
            x = self._block(x, f"sem_head.{b}", self.sem_hist, b)
        x = P.lin("sem_head.out.weight", x, "sem_head.out.bias")
        x = d._residual(x, ids, codes[:, 1:] < 0)
        mx.eval(x)
        cpf = 1  # stage positions per code frame
        for s, hp in enumerate(d.stages):
            p = f"stage.{s}"
            x = P.lin(p + ".in.weight", x)
            for layer in range(hp.n_layer):
                x, self.kv[s][layer] = moss_layer_cached(
                    P,
                    x,
                    f"{p}.l{layer}",
                    hp,
                    d.ln_eps,
                    self.frames * cpf,
                    self.kv[s][layer],
                )
                mx.eval(x, self.kv[s][layer])
            if hp.out_dim > 0:
                x = P.lin(p + ".out.weight", x)
            if hp.patch > 1:
                x = patch_up(x, hp.patch)
                cpf *= hp.patch
        for b in range(d.head_depth):
            x = self._block(x, f"head.{b}", self.head_hist, b)
            mx.eval(x)
        x = _layer_norm(
            x, P.t["head.norm.weight"], P.t["head.norm.bias"], d.convnext_eps
        )
        y0 = P.lin("head.out.0.weight", x, "head.out.0.bias")
        y1 = P.lin("head.out.1.weight", x, "head.out.1.bias")
        mx.eval(y0, y1, [h for h in self.sem_hist + self.head_hist if h is not None])
        out = self.resampler.push(
            self.head.push(
                np.array(y0, dtype=np.float32), np.array(y1, dtype=np.float32)
            )
        )
        self.frames += len(codes)
        return out
