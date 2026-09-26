# Emotion conditioning for the GPT-AR emo-reference path — MLX port of
# windextts/models/emo_conditioning.py (conformer -> perceiver -> emovec).
import math

import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25.ops import Seq


def _pad_mask(lengths, max_len):  # [B,max_len] True=pad
    return mx.arange(max_len)[None] >= lengths[:, None]


class _FF(nn.Module):  # per-position 2-layer MLP (SiLU)
    def __init__(self, idim, hidden):
        super().__init__()
        self.w_1 = nn.Linear(idim, hidden)
        self.w_2 = nn.Linear(hidden, idim)

    def __call__(self, xs):
        z = self.w_1(xs)
        return self.w_2(mx.sigmoid(z) * z)


class _ConvMod(nn.Module):  # conformer conv block: pointwise->GLU->depthwise->norm->pointwise
    def __init__(self, channels, kernel_size=15):
        super().__init__()
        self.pointwise_conv1 = nn.Conv1d(channels, 2 * channels, 1)
        self.depthwise_conv = nn.Conv1d(channels, channels, kernel_size,
                                        padding=(kernel_size - 1) // 2, groups=channels)
        self.norm = nn.LayerNorm(channels)
        self.pointwise_conv2 = nn.Conv1d(channels, channels, 1)

    def __call__(self, x, mask_pad):  # x [B,T,C]; mask_pad [B,1,T] True=valid
        x = mx.where(mask_pad.transpose(0, 2, 1), x, 0.0)  # [B,T,C]
        x = self.pointwise_conv1(x)  # [B,T,2C]
        a, b = mx.split(x, 2, axis=-1)
        d = self.norm(self.depthwise_conv(a * mx.sigmoid(b)))
        x = self.pointwise_conv2(mx.sigmoid(d) * d)
        return mx.where(mask_pad.transpose(0, 2, 1), x, 0.0)


class _RelPosEnc(nn.Module):  # sinusoidal pos encoding (pe buffer from ckpt)
    def __init__(self, d_model, max_len=5000):
        super().__init__()
        self.xscale = math.sqrt(d_model)
        pe = mx.zeros((max_len, d_model))
        pos = mx.arange(max_len, dtype=mx.float32)[:, None]
        div = mx.exp(mx.arange(0, d_model, 2, dtype=mx.float32) * -(math.log(10000.0) / d_model))
        pe = pe.at[:, 0::2].add(mx.sin(pos * div))  # zeros base: add == set
        pe = pe.at[:, 1::2].add(mx.cos(pos * div))
        self.pe = pe[None]  # [1,max_len,d_model]

    def __call__(self, x):
        return x * self.xscale, self.pe[:, : x.shape[1]]


class _RelPosMHA(nn.Module):
    # Transformer-XL rel-pos attention folded into ONE SDPA: q'=cat([q+bu,q+bv],-1),
    # k'=cat([k,p],-1) -> q'·k'ᵀ = (q+bu)·kᵀ + (q+bv)·pᵀ
    def __init__(self, n_head, n_feat, dropout_rate=0.0):
        super().__init__()
        self.d_k = n_feat // n_head
        self.h = n_head
        self.linear_q, self.linear_k, self.linear_v = [nn.Linear(n_feat, n_feat) for _ in range(3)]
        self.linear_out = nn.Linear(n_feat, n_feat)
        self.linear_pos = nn.Linear(n_feat, n_feat, bias=False)
        self.pos_bias_u = mx.zeros((self.h, self.d_k))
        self.pos_bias_v = mx.zeros((self.h, self.d_k))

    def __call__(self, query, key, value, mask, pos_emb):  # mask [B,1,T] True=valid
        b, t = query.shape[0], query.shape[1]
        q = self.linear_q(query).reshape(b, t, self.h, self.d_k)
        k = self.linear_k(key).reshape(b, t, self.h, self.d_k)
        v = self.linear_v(value).reshape(b, t, self.h, self.d_k)
        p = self.linear_pos(pos_emb).reshape(1, t, self.h, self.d_k)
        q = mx.concatenate([q + self.pos_bias_u, q + self.pos_bias_v], -1).transpose(0, 2, 1, 3)  # [B,h,T,2dk]
        k = mx.concatenate([k, p], -1).transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)
        m = mx.broadcast_to(mx.where(mask[:, None, :, :], 0.0, float("-inf")), (b, 1, t, t))
        s = q @ k.transpose(0, 1, 3, 2) / math.sqrt(self.d_k) + m
        o = mx.softmax(s, -1) @ v
        return self.linear_out(o.transpose(0, 2, 1, 3).reshape(b, t, self.h * self.d_k))


class _ConfLayer(nn.Module):
    # pre-norm conformer block (normalize_before=True; macaron_style=False)
    def __init__(self, size, attn, ff, conv):
        super().__init__()
        self.self_attn, self.feed_forward, self.conv_module = attn, ff, conv
        self.norm_ff, self.norm_mha, self.norm_conv, self.norm_final = (
            nn.LayerNorm(size, eps=1e-5), nn.LayerNorm(size, eps=1e-5),
            nn.LayerNorm(size, eps=1e-5), nn.LayerNorm(size, eps=1e-5))

    def __call__(self, x, mask, pos_emb, mask_pad):
        xn = self.norm_mha(x)
        x = x + self.self_attn(xn, xn, xn, mask, pos_emb)
        x = x + self.conv_module(self.norm_conv(x), mask_pad)
        x = x + self.feed_forward(self.norm_ff(x))
        return self.norm_final(x)


class EmoConformerEncoder(nn.Module):
    # conv2d2 subsample: Conv2d(1,512,3,s=2) halves T (133->66) and feat to 511
    # -> Linear(512*511=261632->512); rel_pos; 4 macaron-free blocks
    def __init__(self, input_size=1024, output_size=512, attention_heads=4, linear_units=1024,
                 num_blocks=4, cnn_module_kernel=15):
        super().__init__()
        conv_inner = output_size * ((input_size - 1) // 2)  # 261632
        self.embed = nn.Module()
        self.embed.conv = Seq({"0": nn.Conv2d(1, output_size, 3, stride=2), "1": nn.ReLU()})
        self.embed.out = Seq({"0": nn.Linear(conv_inner, output_size)})
        self.embed.pos_enc = _RelPosEnc(output_size)
        self.after_norm = nn.LayerNorm(output_size, eps=1e-5)
        self.encoders = Seq({str(i): _ConfLayer(output_size, _RelPosMHA(attention_heads, output_size, 0.0),
                                                _FF(output_size, linear_units),
                                                _ConvMod(output_size, cnn_module_kernel))
                             for i in range(num_blocks)})

    def __call__(self, xs, xs_lens):  # xs [B,T,1024] -> (out [B,T',512], mask [B,1,T'])
        T = xs.shape[1]
        masks = ~_pad_mask(xs_lens, T)[:, None]  # [B,1,T] True=valid
        x = self.embed.conv(xs[..., None])  # [B,T',511,512] (mlx NHWC)
        b, t, f, c = x.shape
        x = self.embed.out(x.transpose(0, 1, 3, 2).reshape(b, t, f * c))  # torch view order (T,C,F)
        x, pos_emb = self.embed.pos_enc(x)
        masks = masks[:, :, 2::2]  # conv stride-2 sample grid (positions 2,4,..)
        for i in self.encoders._order:
            x = getattr(self.encoders, i)(x, masks, pos_emb, masks)
        return self.after_norm(x), masks


class _RMSNorm(nn.Module):  # F.normalize * dim^0.5 * gamma
    def __init__(self, dim):
        super().__init__()
        self.scale = dim ** 0.5
        self.gamma = mx.ones(dim)

    def __call__(self, x):
        return x / mx.sqrt(mx.sum(x * x, -1, keepdims=True) + 1e-12) * self.scale * self.gamma


class _FF2(nn.Module):  # GEGLU FFN; Linear named "0"/"2" to match ckpt keys
    def __init__(self, dim, mult=2):
        super().__init__()
        dim_inner = int(dim * mult * 2 / 3)  # 1024*2*2/3 = 1365
        setattr(self, "0", nn.Linear(dim, dim_inner * 2))
        setattr(self, "2", nn.Linear(dim_inner, dim))

    def __call__(self, x):
        x, gate = mx.split(getattr(self, "0")(x), 2, axis=-1)
        return getattr(self, "2")(nn.GELU()(gate) * x)


class _Attn(nn.Module):  # cross-attention, optionally prepending the latent query
    def __init__(self, dim, dim_context, dim_head=64, heads=8, cross_attn_include_queries=False):
        super().__init__()
        self.scale = dim_head ** -0.5
        self.heads = heads
        self.cross_attn_include_queries = cross_attn_include_queries
        dim_inner = dim_head * heads
        self.to_q = nn.Linear(dim, dim_inner, bias=False)
        self.to_kv = nn.Linear(dim_context, dim_inner * 2, bias=False)
        self.to_out = nn.Linear(dim_inner, dim, bias=False)

    def __call__(self, x, context=None, mask=None):  # x [B,N,D]; mask [B,J'] True=keep
        h = self.heads
        has_context = context is not None
        context = x if context is None else context
        if has_context and self.cross_attn_include_queries:
            context = mx.concatenate([x, context], axis=-2)  # [B, 1+J, Dc]
        q = self.to_q(x)
        k, v = mx.split(self.to_kv(context), 2, axis=-1)
        q = q.reshape(*q.shape[:2], h, -1).transpose(0, 2, 1, 3)
        k = k.reshape(*k.shape[:2], h, -1).transpose(0, 2, 1, 3)
        v = v.reshape(*v.shape[:2], h, -1).transpose(0, 2, 1, 3)
        j = k.shape[-2]
        m = None
        if mask is not None:
            m = mx.broadcast_to(mx.where(mask[:, None, None, :], 0.0, float("-inf")), (mask.shape[0], 1, 1, j))
        s = q @ k.transpose(0, 1, 3, 2) * self.scale
        if m is not None:
            s = s + m
        o = mx.softmax(s, -1) @ v
        o = o.transpose(0, 2, 1, 3)
        return self.to_out(o.reshape(*o.shape[:2], -1))


class EmoPerceiverEncoder(nn.Module):
    # PerceiverResampler: dim=1024, dim_context=512, num_latents=1, heads=4, depth=2
    def __init__(self, dim=1024, depth=2, dim_context=512, num_latents=1, dim_head=64, heads=4, ff_mult=2):
        super().__init__()
        self.proj_context = nn.Linear(dim_context, dim)
        self.latents = mx.random.normal((num_latents, dim)) * 0.02
        self.layers = Seq({str(i): Seq({"0": _Attn(dim=dim, dim_context=dim, dim_head=dim_head, heads=heads,
                                                   cross_attn_include_queries=True),
                                        "1": _FF2(dim=dim, mult=ff_mult)})
                           for i in range(depth)})
        self.norm = _RMSNorm(dim)

    def __call__(self, x, mask=None):  # x [B,S,512]; mask [B,1+S] True=keep
        batch = x.shape[0]
        x = self.proj_context(x)
        latents = mx.broadcast_to(self.latents[None], (batch, 1, self.latents.shape[1]))
        for i in self.layers._order:
            layer = getattr(self.layers, i)
            latents = getattr(layer, "0")(latents, x, mask=mask) + latents
            latents = getattr(layer, "1")(latents) + latents
        return self.norm(latents)  # [B,1,1024]


def get_emovec(conformer, perceiver, emovec_layer, emo_layer, speech_conditioning_latent, cond_mel_lengths):
    # conformer -> perceiver -> emovec_layer -> emo_layer (GPT.get_emovec)
    seq, mask = conformer(speech_conditioning_latent, cond_mel_lengths)  # [B,T',512], [B,1,T']
    conds = perceiver(seq, mx.concatenate([mx.ones((mask.shape[0], 1), dtype=mx.bool_), mask.squeeze(1)], 1))
    return emo_layer(emovec_layer(conds.squeeze(1)))  # [B,1280]
