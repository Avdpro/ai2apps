# Copyright (c) 2026 Zyphra, Inc.

from __future__ import annotations

from dataclasses import dataclass, field

import mlx.core as mx
import numpy as np
from mlx import nn

from .config import LMConfig
from .gdn_kernel import gated_delta
from .weights import TensorStore

_KV_BLOCK = 256


@dataclass
class LMState:
    """Decoding state of one sequence: the next absolute position, the global layers' KV cache (``[n_kv_heads, capacity,
    head_dim]``, grown in blocks of 256 rows; rows ``< position`` are valid), each GDN layer's recurrent state
    (``[heads, value, key]``) and causal-conv history (``[channels, kernel - 1]``)."""

    position: int = 0
    kv: dict[int, tuple[mx.array, mx.array]] = field(default_factory=dict)
    gdn_state: dict[int, mx.array] = field(default_factory=dict)
    conv_state: dict[int, mx.array] = field(default_factory=dict)

    def fork(self) -> LMState:
        return LMState(
            self.position,
            {k: (mx.array(a), mx.array(b)) for k, (a, b) in self.kv.items()},
            {k: mx.array(v) for k, v in self.gdn_state.items()},
            {k: mx.array(v) for k, v in self.conv_state.items()},
        )

    def arrays(self) -> list[mx.array]:
        out = [a for pair in self.kv.values() for a in pair]
        return out + list(self.gdn_state.values()) + list(self.conv_state.values())


def _to_mx(value) -> mx.array:
    if isinstance(value, mx.array):
        return value.astype(mx.float32)
    return mx.array(np.asarray(value, dtype=np.float32))


def _rms(x: mx.array, weight: mx.array | None, eps: float) -> mx.array:
    return mx.fast.rms_norm(x, weight, eps)


def _silu(x: mx.array) -> mx.array:
    return x * mx.sigmoid(x)


def _softplus(x: mx.array) -> mx.array:
    return mx.logaddexp(x, mx.zeros_like(x))


def _gather_matmul(x, weight, indices):
    return weight(x, indices)


class Backbone(nn.Module):
    def __init__(self, config: LMConfig, tensors: dict):
        super().__init__()
        self.config = config
        self.params = TensorStore(tensors)

    @property
    def t(self):
        return self.params.t

    @property
    def w(self):
        return self.params.w

    def _lin(self, base, x):
        return self.w[base + ".weight"](x)

    def _global_attention(self, x, layer: int, state: LMState):
        c, p = self.config, f"blk.{layer}."
        n, nh, nkv, hd = x.shape[0], c.n_heads, c.n_kv_heads, c.head_dim
        lo = state.position
        gate = mx.sigmoid(self._lin(p + "attn_gate", x))
        q = self._lin(p + "attn_q", x).reshape(n, nh, hd)
        k = self._lin(p + "attn_k", x).reshape(n, nkv, hd)
        v = self._lin(p + "attn_v", x).reshape(n, nkv, hd)
        q = _rms(q, None, c.qk_eps) * self.t[p + "attn_temp"][:, None]
        k = _rms(k, None, c.qk_eps)
        q = mx.fast.rope(
            q.transpose(1, 0, 2),
            hd,
            traditional=True,
            base=c.rope_theta,
            scale=1.0,
            offset=lo,
        )
        k = mx.fast.rope(
            k.transpose(1, 0, 2),
            hd,
            traditional=True,
            base=c.rope_theta,
            scale=1.0,
            offset=lo,
        )
        v = v.transpose(1, 0, 2)
        kc, vc = state.kv.get(layer, (None, None))
        need = lo + n
        if kc is None or kc.shape[1] < need:
            cap = -(-need // _KV_BLOCK) * _KV_BLOCK
            grow = cap - (0 if kc is None else kc.shape[1])
            pad = mx.zeros((nkv, grow, hd), dtype=mx.float32)
            kc = pad if kc is None else mx.concatenate([kc, pad], axis=1)
            vc = (
                mx.zeros((nkv, grow, hd), dtype=mx.float32)
                if vc is None
                else mx.concatenate([vc, pad], axis=1)
            )
        kc[:, lo:need] = k
        vc[:, lo:need] = v
        state.kv[layer] = (kc, vc)
        keys, values = kc[:, :need], vc[:, :need]
        mask = None
        if n > 1:
            mask = mx.arange(need)[None, :] <= (lo + mx.arange(n))[:, None]
        out = mx.fast.scaled_dot_product_attention(
            q[None], keys[None], values[None], scale=hd**-0.5, mask=mask
        )[0]
        out = out.transpose(1, 0, 2) * gate[:, :, None]
        return self._lin(p + "attn_output", out.reshape(n, nh * hd))

    def _gdn(self, x, layer: int, state: LMState):
        c, p = self.config, f"blk.{layer}."
        H, S, K = c.gdn_heads, c.gdn_head_dim, c.gdn_kernel
        inner = H * S
        n = x.shape[0]
        projection = self._lin(p + "gdn_in", x)
        qkv = projection[:, : 3 * inner]
        z = projection[:, 3 * inner : 4 * inner]
        a = projection[:, 4 * inner : 4 * inner + H]
        b = projection[:, 4 * inner + H : 4 * inner + 2 * H]
        history = state.conv_state.get(layer)
        if history is None:
            history = mx.zeros((3 * inner, K - 1), dtype=mx.float32)
        sequence = mx.concatenate(
            [history.T, qkv], axis=0
        )  # [K - 1 + n, channels], oldest first
        weight = self.t[p + "gdn_conv.weight"]  # [channels, K], tap 0 oldest
        conv = sequence[0:n] * weight[:, 0]
        for j in range(1, K):
            conv = conv + sequence[j : j + n] * weight[:, j]
        conv = _silu(conv)
        state.conv_state[layer] = sequence[-(K - 1) :].T
        q = conv[:, :inner].reshape(n, H, S)
        k = conv[:, inner : 2 * inner].reshape(n, H, S)
        v = conv[:, 2 * inner :].reshape(n, H, S)
        q = q * mx.rsqrt((q * q).sum(-1, keepdims=True) + 1e-6)
        k = k * mx.rsqrt((k * k).sum(-1, keepdims=True) + 1e-6)
        decay = mx.exp(
            -mx.exp(self.t[p + "gdn_A_log"]) * _softplus(a + self.t[p + "gdn_dt_bias"])
        )
        beta = mx.sigmoid(b)
        s0 = state.gdn_state.get(layer)
        if s0 is None:
            s0 = mx.zeros((H, S, S), dtype=mx.float32)
        y, s1 = gated_delta(
            (q * S**-0.5)[None], k[None], v[None], decay[None], beta[None], s0[None]
        )
        state.gdn_state[layer] = s1[0]
        recurrent = y[0]
        normalized = _rms(recurrent, self.t[p + "gdn_norm.weight"], 1e-5)
        gated = (normalized * _silu(z.reshape(n, H, S))).reshape(n, inner)
        return self._lin(p + "attn_output", gated)

    def _feed_forward(self, x, layer: int):
        c, p = self.config, f"blk.{layer}."
        if p + "ffn_up.weight" in self.w:
            return self._lin(
                p + "ffn_down",
                self._lin(p + "ffn_up", x) * _silu(self._lin(p + "ffn_gate", x)),
            )
        logits = self._lin(
            p + "router", _rms(x, self.t[p + "router_norm.weight"], c.norm_eps)
        )
        bias = self.t[p + "router_bias"]
        k = c.moe_topk
        choices = mx.argpartition(bias - logits, kth=k - 1, axis=-1)[:, :k]
        weights = mx.softmax(mx.take_along_axis(logits, choices, axis=-1), axis=-1)
        latent = self._lin(p + "ffn_latent_down", x)
        z = latent[:, None, None, :]
        gate = _gather_matmul(z, self.w[p + "ffn_gate_exps.weight"], choices)
        up = _gather_matmul(z, self.w[p + "ffn_up_exps.weight"], choices)
        hidden = _silu(gate) * up
        down = _gather_matmul(hidden, self.w[p + "ffn_down_exps.weight"], choices)
        output = (down[:, :, 0, :] * weights[:, :, None]).sum(axis=1)
        return self._lin(p + "ffn_latent_up", output)

    def _replace_rows(self, x, lo, speaker_rows, condition_rows):
        hi = lo + x.shape[0]
        for row, vec in (speaker_rows or {}).items():
            if lo <= row < hi:
                projected = self.w["speaker_proj.weight"](_to_mx(vec).reshape(1, -1))[0]
                x[row - lo] = projected + self.t["speaker_proj.bias"]
        for table, row in enumerate(sorted(condition_rows or {})):
            if lo <= row < hi:
                x[row - lo] = self.t[f"cond_embd.{table}.weight"][
                    int(condition_rows[row])
                ]
        return x

    def __call__(self, ids, state: LMState, *, speaker_rows=None, condition_rows=None, hidden_deltas=None):
        c = self.config
        idx = mx.array(ids, dtype=mx.int32)
        if idx.ndim != 2 or idx.shape[1] != c.n_codebooks + 1 or idx.shape[0] == 0:
            raise ValueError(f"expected nonempty rows with width {c.n_codebooks + 1}")
        n = idx.shape[0]
        lo = state.position
        if lo + n > c.max_seqlen:
            raise ValueError(f"{lo + n} rows exceed the model context {c.max_seqlen}")
        x = self.t["audio_embd.0.weight"][idx[:, 0]]
        for cb in range(1, c.n_codebooks):
            x = x + self.t[f"audio_embd.{cb}.weight"][idx[:, cb]]
        x = x + self.t["text_embd.weight"][idx[:, c.n_codebooks]]
        if speaker_rows or condition_rows:
            x = self._replace_rows(x, lo, speaker_rows, condition_rows)
        x = _rms(x, None, c.norm_eps)
        queries = self.t["attnres_q.weight"]
        bank, scores = [], []

        def route(source, query):
            delta = (hidden_deltas or {}).get(len(bank))
            if delta is not None:
                source = source + _to_mx(delta)
            bank.append(source)
            scores.append(_rms(source, None, c.norm_eps) @ queries.T)
            if len(bank) == 1:
                return source
            weights = mx.softmax(mx.stack([s[:, query] for s in scores]), axis=0)
            return (mx.stack(bank) * weights[:, :, None]).sum(axis=0)

        mixed = route(x, 0)
        for layer in range(c.n_layers):
            p = f"blk.{layer}."
            if layer:
                mixed = route(x, 2 * layer)
            attn_in = _rms(mixed, self.t[p + "attn_norm.weight"], c.norm_eps)
            if c.uses_gdn(layer):
                attention = self._gdn(attn_in, layer, state)
            else:
                attention = self._global_attention(attn_in, layer, state)
            mixed = route(attention, 2 * layer + 1)
            ffn_in = _rms(mixed, self.t[p + "ffn_norm.weight"], c.norm_eps)
            x = self._feed_forward(ffn_in, layer)
        mixed = route(x, 2 * c.n_layers)
        normalized = _rms(mixed, self.t["output_norm.weight"], c.norm_eps)
        logits = self._lin("output", normalized).reshape(
            n, c.n_codebooks, c.audio_vocab
        )
        state.position = lo + n
        return c.loss_softcap * mx.tanh(logits / c.loss_softcap)
