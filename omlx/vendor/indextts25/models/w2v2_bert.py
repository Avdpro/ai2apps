# w2v-bert-2.0 conformer (24-layer macaron, hidden 1024, 16 heads, dconv k31,
# relative_key pos emb) — MLX port of windextts/models/w2v2_bert.py.
# Seam: hidden_states[17] (index 0 = feature_projection out).
import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25.ops import Seq


def _glu(x):  # F.glu dim=-1 on [...,2C]
    a, b = mx.split(x, 2, axis=-1)
    return a * mx.sigmoid(b)


class Wav2Vec2BertFeedForward(nn.Module):
    def __init__(self, hs=1024, is_=4096):
        super().__init__()
        self.intermediate_dense = nn.Linear(hs, is_)
        self.output_dense = nn.Linear(is_, hs)

    def __call__(self, x):
        z = self.intermediate_dense(x)
        return self.output_dense(mx.sigmoid(z) * z)


class Wav2Vec2BertSelfAttention(nn.Module):
    def __init__(self, hs=1024, heads=16, left=64, right=8):
        super().__init__()
        self.heads, self.left, self.right = heads, left, right
        self.distance_embedding = nn.Embedding(left + right + 1, hs // heads)
        self.linear_q, self.linear_k, self.linear_v, self.linear_out = [nn.Linear(hs, hs) for _ in range(4)]

    def __call__(self, h, attention_mask=None):  # h [B,T,hs]
        B, T, _ = h.shape
        H, d = self.heads, self.linear_q.weight.shape[0] // self.heads
        q, k, v = [l(h).reshape(B, T, H, d).transpose(0, 2, 1, 3) for l in (self.linear_q, self.linear_k, self.linear_v)]
        s = q @ k.transpose(0, 1, 3, 2) / (d ** 0.5)
        dist = mx.clip(mx.arange(T)[None] - mx.arange(T)[:, None], -self.left, self.right)  # [Tq,Tk]
        de = self.distance_embedding(dist + self.left).astype(q.dtype)  # [Tq,Tk,d]
        s = s + mx.einsum("bhld,lrd->bhlr", q, de) / (d ** 0.5)
        if attention_mask is not None:
            s = s + attention_mask
        o = mx.softmax(s, -1) @ v
        return self.linear_out(o.transpose(0, 2, 1, 3).reshape(B, T, -1))


class Wav2Vec2BertConvolutionModule(nn.Module):
    def __init__(self, hs=1024, k=31, eps=1e-5):
        super().__init__()
        self.layer_norm = nn.LayerNorm(hs, eps=eps)
        self.pointwise_conv1 = nn.Conv1d(hs, 2 * hs, 1, bias=False)
        self.depthwise_conv = nn.Conv1d(hs, hs, k, groups=hs, bias=False)
        self.depthwise_layer_norm = nn.LayerNorm(hs, eps=eps)
        self.pointwise_conv2 = nn.Conv1d(hs, hs, 1, bias=False)

    def __call__(self, x, conv_attention_mask=None):  # x [B,T,hs]
        if conv_attention_mask is not None:
            x = mx.where(conv_attention_mask[..., None], x, 0.0)
        x = self.layer_norm(x)
        x = _glu(self.pointwise_conv1(x))  # [B,T,2hs] -> [B,T,hs]
        x = mx.pad(x, [(0, 0), (self.depthwise_conv.weight.shape[1] - 1, 0), (0, 0)])  # causal left-pad k-1
        d = self.depthwise_layer_norm(self.depthwise_conv(x))
        return self.pointwise_conv2(mx.sigmoid(d) * d)
        return x


class Wav2Vec2BertEncoderLayer(nn.Module):
    def __init__(self, hs=1024, is_=4096, heads=16, k=31, left=64, right=8, eps=1e-5):
        super().__init__()
        self.ffn1, self.ffn2 = Wav2Vec2BertFeedForward(hs, is_), Wav2Vec2BertFeedForward(hs, is_)
        self.ffn1_layer_norm, self.self_attn_layer_norm, self.ffn2_layer_norm, self.final_layer_norm = (
            nn.LayerNorm(hs, eps=eps), nn.LayerNorm(hs, eps=eps), nn.LayerNorm(hs, eps=eps), nn.LayerNorm(hs, eps=eps))
        self.self_attn = Wav2Vec2BertSelfAttention(hs, heads, left, right)
        self.conv_module = Wav2Vec2BertConvolutionModule(hs, k, eps)

    def __call__(self, x, attention_mask=None, conv_attention_mask=None):
        # macaron: half-residual FFN -> attn -> conv -> half-residual FFN + final LN
        x = x + self.ffn1(self.ffn1_layer_norm(x)) * 0.5
        x = x + self.self_attn(self.self_attn_layer_norm(x), attention_mask)
        x = x + self.conv_module(x, conv_attention_mask)
        return self.final_layer_norm(x + self.ffn2(self.ffn2_layer_norm(x)) * 0.5)


class Wav2Vec2BertConformer(nn.Module):
    def __init__(self, hs=1024, layers=24, heads=16, is_=4096, k=31, inp=160, left=64, right=8, eps=1e-5):
        super().__init__()
        self.feature_projection = _FP(inp, hs, eps)
        self.encoder_layers = [Wav2Vec2BertEncoderLayer(hs, is_, heads, k, left, right, eps) for _ in range(layers)]

    def __call__(self, input_features, attention_mask=None, *, return_layer=17):
        h = self.feature_projection(input_features)
        attn_mask = conv_mask = None
        if attention_mask is not None:
            h = mx.where(attention_mask[..., None], h, 0.0)
            attn_mask = mx.broadcast_to(mx.where(attention_mask[:, None, None, :], 0.0,
                                                    mx.finfo(h.dtype).min), (h.shape[0], 1, h.shape[1], h.shape[1]))
            conv_mask = attention_mask
        for i, layer in enumerate(self.encoder_layers):
            h = layer(h, attention_mask=attn_mask, conv_attention_mask=conv_mask)
            mx.eval(h)  # per-layer eval: first-time kernel compile < watchdog
            if return_layer == i + 1:
                return h
        return h


class _FP(nn.Module):
    # feature_projection (named to match ckpt keys)
    def __init__(self, inp=160, hs=1024, eps=1e-5):
        super().__init__()
        self.layer_norm = nn.LayerNorm(inp, eps=eps)
        self.projection = nn.Linear(inp, hs)

    def __call__(self, x):
        return self.projection(self.layer_norm(x))
