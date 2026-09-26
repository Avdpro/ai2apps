# S2Mel-DiT velocity estimator (13-layer, dim 512, 8 heads, RoPE/adaLN/uvit) +
# gated WaveNet tail — MLX port of windextts/models/s2mel_dit.py. Eval-only.
import math
import os

import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25 import ops
from omlx.vendor.indextts25.ops import Seq


def find_multiple(n, k):
    return (n + k - 1) // k * k


class RMSNorm(nn.Module):
    def __init__(self, dim, eps=1e-5):
        super().__init__()
        self.eps = eps
        self.weight = mx.ones(dim)

    def __call__(self, x):
        return x * mx.rsqrt((x * x).mean(-1, keepdims=True) + self.eps) * self.weight


class AdaptiveLayerNorm(nn.Module):
    def __init__(self, d_model, norm):
        super().__init__()
        self.project_layer = nn.Linear(d_model, 2 * d_model)
        self.norm = norm

    def __call__(self, x, embedding=None):
        if embedding is None:
            return self.norm(x)
        w, b = mx.split(self.project_layer(embedding), 2, axis=-1)
        return w * self.norm(x) + b


def _rope(x, f):  # x [..,T,dim]; f [T,dim/2,2] (cos,sin); half-rotation pairs
    x = x.reshape(*x.shape[:-1], -1, 2)
    f = f.reshape(1, x.shape[1], 1, x.shape[3], 2)
    return mx.stack([x[..., 0] * f[..., 0] - x[..., 1] * f[..., 1],
                     x[..., 1] * f[..., 0] + x[..., 0] * f[..., 1]], -1).reshape(*x.shape[:-2], -1)


class Attention(nn.Module):
    def __init__(self, dim, n_head, n_local_heads, head_dim):
        super().__init__()
        self.wqkv = nn.Linear(dim, (n_head + 2 * n_local_heads) * head_dim, bias=False)
        self.wo = nn.Linear(head_dim * n_head, dim, bias=False)
        self.n_head, self.head_dim, self.n_local_heads = n_head, head_dim, n_local_heads

    def __call__(self, x, freqs_cis, mask):
        bsz, seqlen, _ = x.shape
        kv = self.n_local_heads * self.head_dim
        q, k, v = mx.split(self.wqkv(x), [kv, 2 * kv], axis=-1)
        q = _rope(q.reshape(bsz, seqlen, self.n_head, self.head_dim), freqs_cis)
        k = _rope(k.reshape(bsz, seqlen, self.n_local_heads, self.head_dim), freqs_cis)
        v = v.reshape(bsz, seqlen, self.n_local_heads, self.head_dim)
        q, k, v = q.transpose(0, 2, 1, 3), k.transpose(0, 2, 1, 3), v.transpose(0, 2, 1, 3)
        r = self.n_head // self.n_local_heads  # MHA: r=1
        if r > 1:
            k = mx.repeat(k, r, axis=1)
            v = mx.repeat(v, r, axis=1)
        if not os.environ.get("WINDEXTTS_NO_ATTN_SDPA"):
            # Wave-6: one fused kernel in place of the qk/softmax/av chain. Its
            # internal accumulate is fp32, so it is safe at the real activations
            # (|q|~116, |k|~133, |s|~48k) where a plain fp16 matmul chain
            # overflows to inf (D-chain inf; SDPA mel max|D|<=1e-5).
            # Per-step -44ms/-14% same-window; WINDEXTTS_NO_ATTN_SDPA=1 legacy.
            o = mx.fast.scaled_dot_product_attention(
                q, k, v, scale=1.0 / math.sqrt(self.head_dim), mask=mask)
            return self.wo(o.transpose(0, 2, 1, 3).reshape(bsz, seqlen, -1))
        s = q @ k.transpose(0, 1, 3, 2) / math.sqrt(self.head_dim)
        if mask is not None:
            s = s + mask
        o = mx.softmax(s, -1) @ v  # [B,H,T,D]
        return self.wo(o.transpose(0, 2, 1, 3).reshape(bsz, seqlen, -1))


class FeedForward(nn.Module):
    def __init__(self, dim, intermediate_size):
        super().__init__()
        self.w1, self.w3, self.w2 = [nn.Linear(i, o, bias=False)
                                     for i, o in [(dim, intermediate_size), (dim, intermediate_size), (intermediate_size, dim)]]

    def __call__(self, x):
        z = self.w1(x)
        return self.w2(mx.sigmoid(z) * z * self.w3(x))


class TransformerBlock(nn.Module):
    def __init__(self, dim, n_head, n_local_heads, head_dim, intermediate_size, norm_eps, uvit):
        super().__init__()
        self.attention = Attention(dim, n_head, n_local_heads, head_dim)
        self.feed_forward = FeedForward(dim, intermediate_size)
        self.ffn_norm = AdaptiveLayerNorm(dim, RMSNorm(dim, eps=norm_eps))
        self.attention_norm = AdaptiveLayerNorm(dim, RMSNorm(dim, eps=norm_eps))
        self.uvit_skip_connection = uvit
        if uvit:
            self.skip_in_linear = nn.Linear(dim * 2, dim)

    def __call__(self, x, c, freqs_cis, mask, skip_in_x=None):
        if self.uvit_skip_connection and skip_in_x is not None:
            x = self.skip_in_linear(mx.concatenate([x, skip_in_x], -1))
        h = x + self.attention(self.attention_norm(x, c), freqs_cis, mask)
        return h + self.feed_forward(self.ffn_norm(h, c))


class Transformer(nn.Module):
    def __init__(self, n_layer, dim, n_head, head_dim, intermediate_size,
                 block_size=16384, rope_base=10000.0, norm_eps=1e-5, uvit_skip_connection=True):
        super().__init__()
        self.n_layer, self.dim, self.n_head, self.head_dim = n_layer, dim, n_head, head_dim
        self.block_size, self.rope_base = block_size, rope_base
        self.layers = Seq({str(i): TransformerBlock(dim, n_head, n_head, head_dim, intermediate_size, norm_eps,
                                                    uvit_skip_connection) for i in range(n_layer)})
        self.norm = AdaptiveLayerNorm(dim, RMSNorm(dim, eps=norm_eps))
        half = n_layer // 2
        self.layers_emit_skip = list(range(half)) if uvit_skip_connection else []
        self.layers_receive_skip = list(range(half + 1, n_layer)) if uvit_skip_connection else []
        # cos/sin pair tables [block, dim/2, 2]; rebuilt only if the cached size shrinks
        self._freqs = None

    def _ensure_freqs(self, T):
        if self._freqs is not None and self._freqs.shape[0] >= T:
            return self._freqs
        freqs = 1.0 / (self.rope_base ** (mx.arange(0, self.head_dim, 2, dtype=mx.float32) / self.head_dim))
        ang = mx.outer(mx.arange(self.block_size, dtype=mx.float32), freqs)
        self._freqs = mx.stack([mx.cos(ang), mx.sin(ang)], -1)
        return self._freqs

    def __call__(self, x, c, input_pos, mask):
        freqs_cis = mx.take(self._ensure_freqs(x.shape[1]), input_pos, axis=0)
        skips = []
        for i, layer in enumerate(self.layers._order):
            s = skips.pop() if i in self.layers_receive_skip else None
            x = getattr(self.layers, layer)(x, c, freqs_cis, mask, s)
            mx.eval(x)  # per-layer eval: first-time kernel compile < watchdog
            if i in self.layers_emit_skip:
                skips.append(x)
        return self.norm(x, c)


# ---------------- Wavenet (asymmetric reflect padding) ----------------

class SConv1d(nn.Module):  # non-causal asymmetric reflect pad (weight_norm flattened)
    def __init__(self, i, o, k, stride=1, dilation=1, groups=1, bias=True, causal=False):
        super().__init__()
        self.conv = nn.Module()
        self.conv.conv = nn.Conv1d(i, o, k, stride=stride, dilation=dilation, groups=groups, bias=bias)
        self.causal = causal

    def __call__(self, x):  # x [B,T,C] NLC; reflect-pad along the TIME axis
        c = self.conv.conv
        k, s, d = c.weight.shape[1], c.stride, c.dilation  # mlx stores no kernel_size attr
        ek = (k - 1) * d + 1
        pad_total = ek - s
        n = (x.shape[1] - k + pad_total) / s + 1  # output frames before rounding
        extra = int((math.ceil(n) - 1) * s + k - pad_total - x.shape[1])
        if self.causal:
            pl, pr = pad_total, extra
        else:
            r = pad_total // 2
            pl, pr = pad_total - r, r + extra
        x = ops.reflect_pad(x.transpose(0, 2, 1), pl, pr).transpose(0, 2, 1)
        return c(x)


class WN(nn.Module):  # gated residual stack (tanh*sigmoid), conditioned on t2
    def __init__(self, hidden_channels, kernel_size, dilation_rate, n_layers, gin_channels=0):
        super().__init__()
        self.hidden_channels, self.n_layers = hidden_channels, n_layers
        self.in_layers = Seq({str(i): SConv1d(hidden_channels, 2 * hidden_channels, kernel_size,
                                              dilation=dilation_rate ** i) for i in range(n_layers)})
        self.res_skip_layers = Seq({str(i): SConv1d(
            hidden_channels, 2 * hidden_channels if i < n_layers - 1 else hidden_channels, 1)
            for i in range(n_layers)})
        self.cond_layer = SConv1d(gin_channels, 2 * hidden_channels * n_layers, 1) if gin_channels else None

    def __call__(self, x, x_mask, g=None):  # x [B,T,hc]; x_mask [B,T,1] float
        out = mx.zeros_like(x)
        hc = self.hidden_channels
        g = self.cond_layer(g) if g is not None else None  # [B,1,2*hc*n]
        for i in range(self.n_layers):
            a = getattr(self.in_layers, str(i))(x)
            if g is not None:
                a = a + g[:, :, i * 2 * hc:(i + 1) * 2 * hc]
            a = mx.tanh(a[..., :hc]) * mx.sigmoid(a[..., hc:])
            rs = getattr(self.res_skip_layers, str(i))(a)
            if i < self.n_layers - 1:
                x = (x + rs[..., :hc]) * x_mask
                out = out + rs[..., hc:]
            else:
                out = out + rs
            mx.eval(out)  # per-layer eval: first-time kernel compile < watchdog
        return out * x_mask


# ---------------- DiT ----------------

class TimestepEmbedder(nn.Module):
    def __init__(self, hidden_size, frequency_embedding_size=256):
        super().__init__()
        self.mlp = Seq({"0": nn.Linear(frequency_embedding_size, hidden_size), "1": nn.SiLU(),
                        "2": nn.Linear(hidden_size, hidden_size)})
        self.freqs = mx.exp(-math.log(10000) * mx.arange(0, frequency_embedding_size // 2, dtype=mx.float32)
                            / (frequency_embedding_size // 2))

    def __call__(self, t):  # t [B]
        args = 1000 * t[:, None] * self.freqs[None]
        emb = mx.concatenate([mx.cos(args), mx.sin(args)], -1)
        return self.mlp(emb)


class FinalLayer(nn.Module):
    def __init__(self, hidden_size, patch_size, out_channels):
        super().__init__()
        self.norm_final = nn.LayerNorm(hidden_size, affine=False, eps=1e-6)
        self.linear = nn.Linear(hidden_size, patch_size * patch_size * out_channels)
        self.adaLN_modulation = Seq({"0": nn.SiLU(), "1": nn.Linear(hidden_size, 2 * hidden_size)})

    def __call__(self, x, c):
        shift, scale = mx.split(self.adaLN_modulation(c), 2, axis=-1)
        return self.linear(self.norm_final(x) * (1 + scale[:, None, :]) + shift[:, None, :])


class DiT(nn.Module):
    def __init__(self):
        super().__init__()
        D, A = 512, 8  # hidden_dim, num_heads (config.yaml s2mel.DiT)
        self.transformer = Transformer(n_layer=13, dim=D, n_head=A, head_dim=D // A,
                                       intermediate_size=find_multiple(int(2 * (4 * D) / 3), 256),
                                       block_size=16384)
        self.x_embedder = nn.Linear(80, D)  # weight_norm flattened at conversion
        self.cond_embedder = nn.Embedding(1024, D)  # discrete content path (unused, in ckpt)
        self.cond_projection = nn.Linear(512, D)
        self.t_embedder = TimestepEmbedder(D)
        self.input_pos = mx.arange(16384, dtype=mx.int32)
        self.t_embedder2 = TimestepEmbedder(512)
        self.conv1 = nn.Linear(D, 512)
        self.conv2 = nn.Conv1d(512, 80, 1)
        self.wavenet = WN(512, 5, 1, 8, gin_channels=512)
        self.final_layer = FinalLayer(512, 1, 512)
        self.res_projection = nn.Linear(D, 512)
        self.content_mask_embedder = nn.Embedding(1, D)
        self.skip_linear = nn.Linear(D + 80, D)
        self.cond_x_merge_linear = nn.Linear(80 + 80 + 512 + 192, D)  # x|prompt_x|cond|style = 864

    def _compiled_forward(self, no_mask=False):
        # O1: mx.compile of the full DiT forward (no internal mx.eval; freqs
        # passed in). Static shapes — the CFM loop calls it 2*n_timesteps times
        # with identical shapes, so it traces once. Seq modules must run with
        # _no_sync=True during tracing (mx.eval is illegal inside mx.compile).
        # O5 no-mask: x_lens == T at inference makes the [B,1,T,T] additive
        # attention mask exactly zero — adding 0.0 is a no-op, so skip it
        # (bit-identical, verified) and save the fp32 score materialization.
        D, A = 512, 8  # hidden_dim, num_heads (config.yaml s2mel.DiT)
        HD = D // A
        order = self.transformer.layers._order
        emit = set(self.transformer.layers_emit_skip)
        recv = set(self.transformer.layers_receive_skip)
        wn_order = self.wavenet.in_layers._order
        hc = self.wavenet.hidden_channels

        def _transformer(x, c, freqs, mask):
            skips = []
            for pos, i in enumerate(order):
                lay = getattr(self.transformer.layers, i)
                s = skips.pop() if pos in recv else None
                if s is not None:
                    x = lay.skip_in_linear(mx.concatenate([x, s], -1))
                h = x + lay.attention(lay.attention_norm(x, c), freqs, mask)
                x = h + lay.feed_forward(lay.ffn_norm(h, c))
                if pos in emit:
                    skips.append(x)
            return self.transformer.norm(x, c)

        def _wavenet(x, x_mask, g):
            gc = self.wavenet.cond_layer(g) if self.wavenet.cond_layer is not None else None
            out = mx.zeros_like(x)
            for pos, i in enumerate(wn_order):
                inl = getattr(self.wavenet.in_layers, i)
                rsl = getattr(self.wavenet.res_skip_layers, str(i))
                a = inl(x)
                if gc is not None:
                    a = a + gc[:, :, pos * 2 * hc: (pos + 1) * 2 * hc]
                a = mx.tanh(a[..., :hc]) * mx.sigmoid(a[..., hc:])
                rs = rsl(a)
                if pos < len(wn_order) - 1:
                    x = (x + rs[..., :hc]) * x_mask
                    out = out + rs[..., hc:]
                else:
                    out = out + rs
            return out * x_mask

        def forward(x, prompt_x, x_lens, t, style, cond, freqs):
            B, _, T = x.shape
            t1 = self.t_embedder(t)
            x, prompt_x, cond = x.transpose(0, 2, 1), prompt_x.transpose(0, 2, 1), self.cond_projection(cond)
            x_in = mx.concatenate([x, prompt_x, cond, mx.broadcast_to(style[:, None], (B, T, 192))], -1)
            x_in = self.cond_x_merge_linear(x_in)
            x_mask = ops.sequence_mask(x_lens, x_in.shape[1])[:, None]
            mask = None if no_mask else mx.where(
                mx.broadcast_to(x_mask[:, None], (B, 1, T, T)), 0.0, float("-inf"))
            x_res = _transformer(x_in, t1[:, None], freqs, mask)
            x_res = self.skip_linear(mx.concatenate([x_res, x], -1))
            x = self.conv1(x_res)
            t2 = self.t_embedder2(t)
            if os.environ.get("WINDEXTTS_NO_WN_DECOUPLE"):
                # legacy: WaveNet fused inside the compiled graph
                if os.environ.get("WINDEXTTS_SKIP_WN"):
                    x = mx.zeros_like(x) + self.res_projection(x_res)
                else:
                    x = _wavenet(x, x_mask.transpose(0, 2, 1).astype(mx.float32), g=t2[:, None, :]) + self.res_projection(x_res)
                return self.conv2(self.final_layer(x, t1)).transpose(0, 2, 1)
            # Wave-5: WaveNet runs eager OUTSIDE this graph (bit-exact; the
            # in-graph conv chain measured 44x slower than standalone — same
            # window A/B: FULL 4.21s vs decouple 3.62s per 8-step solve).
            return x, x_res, x_mask.transpose(0, 2, 1).astype(mx.float32), t1, t2

        def _all_modules(m):
            yield m
            for v in m.values():
                if isinstance(v, nn.Module):
                    yield from _all_modules(v)

        for sub in _all_modules(self):
            if isinstance(sub, ops.Seq):
                sub._no_sync = True
        fn = mx.compile(forward)
        # NOTE: mx.compile traces lazily on FIRST call — caller must keep the
        # Seq _no_sync flags set during that call (S2MelCFM does set/reset per
        # call); compiled executions afterwards never re-enter Python code.
        if not os.environ.get("WINDEXTTS_NO_WN_DECOUPLE"):
            # Wave-5 decoupled head (eager WaveNet between fn and fn_head)
            def forward_head(x, x_res, t1):
                return self.conv2(self.final_layer(x + self.res_projection(x_res), t1)).transpose(0, 2, 1)
            return (fn, mx.compile(forward_head)), [sub for sub in _all_modules(self) if isinstance(sub, ops.Seq)]
        return fn, [sub for sub in _all_modules(self) if isinstance(sub, ops.Seq)]

    def __call__(self, x, prompt_x, x_lens, t, style, cond):
        # x/prompt_x [B,80,T] -> [B,T,80]; cond [B,T,512]
        import os

        B, _, T = x.shape
        t1 = self.t_embedder(t)  # [B,D]
        x, prompt_x, cond = x.transpose(0, 2, 1), prompt_x.transpose(0, 2, 1), self.cond_projection(cond)
        mx.eval(x)
        x_in = mx.concatenate([x, prompt_x, cond, mx.broadcast_to(style[:, None], (B, T, 192))], -1)
        x_in = self.cond_x_merge_linear(x_in)  # [B,T,D]
        mx.eval(x_in)
        x_mask = ops.sequence_mask(x_lens, x_in.shape[1])[:, None]  # [B,1,T]
        no_mask = (not os.environ.get("WINDEXTTS_NO_O5_NOMASK")) and bool(mx.min(x_lens).item() >= T)
        mask = None if no_mask else mx.where(
            mx.broadcast_to(x_mask[:, None], (B, 1, T, T)), 0.0, float("-inf"))
        x_res = self.transformer(x_in, t1[:, None], self.input_pos[:x_in.shape[1]], mask)
        mx.eval(x_res)
        x_res = self.skip_linear(mx.concatenate([x_res, x], -1))
        mx.eval(x_res)
        x = self.conv1(x_res)  # [B,T,512]
        mx.eval(x)
        t2 = self.t_embedder2(t)
        x = self.wavenet(x, x_mask.transpose(0, 2, 1).astype(mx.float32), g=t2[:, None, :]) + self.res_projection(x_res)
        mx.eval(x)
        return self.conv2(self.final_layer(x, t1)).transpose(0, 2, 1)  # [B,80,T]
