"""Ex-Omni's learned speech projector and text/query fusion in MLX."""

import mlx.core as mx
import mlx.nn as nn


class EncoderProjectorConcat(nn.Module):
    def __init__(self, encoder_dim, llm_dim, downsample=5):
        super().__init__()
        self.k = downsample
        self.encoder_dim = encoder_dim
        self.linear1 = nn.Linear(encoder_dim * downsample, 2048)
        self.linear2 = nn.Linear(2048, llm_dim)

    def __call__(self, x):
        b, t, c = x.shape
        if c != self.encoder_dim:
            raise ValueError("Speech encoder hidden size mismatch")
        x = x[:, : t - t % self.k].reshape(b, t // self.k, c * self.k)
        return self.linear2(nn.relu(self.linear1(x)))


class TQGFCrossAttention(nn.Module):
    def __init__(self, dim=896, dim_head=256, heads=16):
        super().__init__()
        self.heads = heads
        self.dim_head = dim_head
        self.norm_text = nn.LayerNorm(dim)
        self.norm_query = nn.LayerNorm(dim)
        self.to_q = nn.Linear(dim, dim_head * heads, bias=False)
        self.to_kv = nn.Linear(dim, dim_head * heads * 2, bias=False)
        self.to_out = nn.Linear(dim_head * heads, dim, bias=False)
        self.gate_proj = nn.Linear(dim, dim_head * heads, bias=False)

    def __call__(self, text, query, text_mask=None):
        if text.shape[1] == 0:
            return mx.zeros_like(query)
        text = self.norm_text(text)
        query = self.norm_query(query)
        b, n, _ = query.shape
        q = (
            self.to_q(query)
            .reshape(b, n, self.heads, self.dim_head)
            .transpose(0, 2, 1, 3)
        )
        k, v = mx.split(self.to_kv(text), 2, axis=-1)
        k = k.reshape(b, -1, self.heads, self.dim_head).transpose(0, 2, 1, 3)
        v = v.reshape(b, -1, self.heads, self.dim_head).transpose(0, 2, 1, 3)
        scores = (q * self.dim_head**-0.5) @ k.transpose(0, 1, 3, 2)
        if text_mask is not None:
            mask = text_mask[:, None, None, :].astype(mx.bool_)
            scores = mx.where(
                mx.any(mask, axis=-1, keepdims=True),
                mx.where(mask, scores, -float("inf")),
                mx.zeros_like(scores),
            )
        out = mx.softmax(scores, axis=-1) @ v
        gate = (
            mx.sigmoid(self.gate_proj(query))
            .reshape(b, n, self.heads, self.dim_head)
            .transpose(0, 2, 1, 3)
        )
        return self.to_out((out * gate).transpose(0, 2, 1, 3).reshape(b, n, -1))


class TQGF(nn.Module):
    def __init__(self, dim, depth=2, dim_head=256, heads=16, ff_mult=4):
        super().__init__()
        self.layers = [
            [
                TQGFCrossAttention(dim, dim_head, heads),
                nn.Sequential(
                    nn.LayerNorm(dim),
                    nn.Linear(dim, int(dim * ff_mult), bias=False),
                    nn.GELU(),
                    nn.Linear(int(dim * ff_mult), dim, bias=False),
                ),
            ]
            for _ in range(depth)
        ]
        self.norm = nn.LayerNorm(dim)

    def __call__(self, text, query, text_mask=None):
        for attn, ff in self.layers:
            query = query + attn(text, query, text_mask)
            query = query + ff(query)
        return self.norm(query)


def convert_fusion_weights(weights):
    out = {}
    for key, value in weights.items():
        parts = key.split(".")
        if len(parts) > 3 and parts[0] == "layers" and parts[2] == "1":
            parts.insert(3, "layers")
        out[".".join(parts)] = mx.array(value)
    return out
