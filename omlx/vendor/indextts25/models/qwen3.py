# Qwen3-0.6B greedy decode for QwenEmotion — MLX port of windextts/models/qwen3.py.
# 28 layers, hidden 1024, 16 heads / 8 KV (GQA), head_dim 128, RoPE theta 1e6,
# RMSNorm eps 1e-6, SwiGLU 3072, per-head q/k RMSNorm, tied lm_head.
import json
import math

import mlx.core as mx
import mlx.nn as nn

from omlx.vendor.indextts25.ops import Seq


def _rope_cache(head_dim, max_seq_len, theta=1_000_000.0):
    # GPT-NeoX half-rotation layout (halves paired, NOT interleaved)
    inv_freq = 1.0 / (theta ** (mx.arange(0, head_dim, 2, dtype=mx.float32) / head_dim))
    freqs = mx.outer(mx.arange(max_seq_len, dtype=mx.float32), inv_freq)
    emb = mx.concatenate([freqs, freqs], -1)  # [seq, head_dim]
    return mx.cos(emb), mx.sin(emb)


def _apply_rope(x, cos, sin):  # x [B,T,H,hd]; rotate-half: out = x*cos + rot(x)*sin
    x1, x2 = mx.split(x, 2, axis=-1)
    return x * cos[None, None] + mx.concatenate([-x2, x1], -1) * sin[None, None]


def _rmsnorm(x, weight, eps):
    # fp32 accumulation (matches torch transformers RMSNorm)
    xf = x.astype(mx.float32)
    y = xf * mx.rsqrt((xf * xf).mean(-1, keepdims=True) + eps)
    return y.astype(x.dtype) * weight


class Qwen3Attention(nn.Module):
    def __init__(self, hidden_size, n_heads, n_kv_heads, head_dim):
        super().__init__()
        self.n_heads, self.n_kv_heads, self.head_dim, self.n_rep = n_heads, n_kv_heads, head_dim, n_heads // n_kv_heads
        qo, ko = n_heads * head_dim, n_kv_heads * head_dim
        self.q_proj = nn.Linear(hidden_size, qo, bias=False)
        self.k_proj = nn.Linear(hidden_size, ko, bias=False)
        self.v_proj = nn.Linear(hidden_size, ko, bias=False)
        self.o_proj = nn.Linear(qo, hidden_size, bias=False)
        self.q_norm = mx.ones(head_dim)  # per-head RMSNorm weights (before RoPE)
        self.k_norm = mx.ones(head_dim)

    def __call__(self, x, rope, mask=None, kv_cache=None):  # x [B,T,hs]
        B, T, _ = x.shape
        q = self.q_proj(x).reshape(B, T, self.n_heads, self.head_dim)
        k = self.k_proj(x).reshape(B, T, self.n_kv_heads, self.head_dim)
        v = self.v_proj(x).reshape(B, T, self.n_kv_heads, self.head_dim)
        cos, sin = rope
        q = _apply_rope(_rmsnorm(q, self.q_norm, 1e-6), cos[:T], sin[:T])
        k = _apply_rope(_rmsnorm(k, self.k_norm, 1e-6), cos[:T], sin[:T])
        if kv_cache is not None:
            kc, vc = kv_cache
            k = mx.concatenate([kc, k], 2)
            v = mx.concatenate([vc, v], 2)
        if self.n_rep > 1:
            k = mx.repeat(k, self.n_rep, 1)
            v = mx.repeat(v, self.n_rep, 1)
        q, k, v = q.transpose(0, 2, 1, 3), k.transpose(0, 2, 1, 3), v.transpose(0, 2, 1, 3)
        s = q @ k.transpose(0, 1, 3, 2) / math.sqrt(self.head_dim)
        if mask is not None:
            s = s + mask
        o = mx.softmax(s, -1) @ v
        return self.o_proj(o.transpose(0, 2, 1, 3).reshape(B, T, -1))


class Qwen3DecoderLayer(nn.Module):
    def __init__(self, config):
        super().__init__()
        hs, nh = config["hidden_size"], config["num_attention_heads"]
        nkv, hd = config["num_key_value_heads"], config.get("head_dim", hs // nh)
        inter, eps = config["intermediate_size"], config.get("rms_norm_eps", 1e-6)
        self.input_layernorm = mx.ones(hs)
        self.self_attn = Qwen3Attention(hs, nh, nkv, hd)
        self.post_attention_layernorm = mx.ones(hs)
        self.mlp = nn.Module()
        self.mlp.gate_proj = nn.Linear(hs, inter, bias=False)
        self.mlp.up_proj = nn.Linear(hs, inter, bias=False)
        self.mlp.down_proj = nn.Linear(inter, hs, bias=False)
        self.eps = eps

    def __call__(self, x, rope, mask=None, kv_cache=None):
        h = x + self.self_attn(_rmsnorm(x, self.input_layernorm, self.eps), rope, mask, kv_cache)
        p = _rmsnorm(h, self.post_attention_layernorm, self.eps)
        return h + self.mlp.down_proj(mx.sigmoid(self.mlp.gate_proj(p)) * self.mlp.gate_proj(p) * self.mlp.up_proj(p))


class Qwen3ForCausalLM(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.embed_tokens = nn.Embedding(config["vocab_size"], config["hidden_size"])
        self.layers = Seq({str(i): Qwen3DecoderLayer(config) for i in range(config["num_hidden_layers"])})
        self.norm = mx.ones(config["hidden_size"])
        hd = config.get("head_dim", config["hidden_size"] // config["num_attention_heads"])
        self._rope = _rope_cache(hd, 8192, config.get("rope_theta", 1_000_000.0))

    def __call__(self, input_ids, kv_caches=None, cache_pos=0):
        B, T = input_ids.shape
        x = self.embed_tokens(input_ids)
        cos, sin = self._rope
        rope = (cos[cache_pos:cache_pos + T], sin[cache_pos:cache_pos + T])
        mask = None
        if T > 1:
            mask = mx.triu(mx.full((T, T), float("-inf"), dtype=x.dtype), 1)[None, None]
        for i in self.layers._order:
            x = getattr(self.layers, i)(x, rope, mask, kv_caches[i] if kv_caches is not None else None)
        return _rmsnorm(x, self.norm, 1e-6) @ self.embed_tokens.weight.T  # tied head [B,T,V]

    def generate(self, input_ids, max_new_tokens=512, eos_token_id=151643):
        B = input_ids.shape[0]
        n_kv = self.config["num_key_value_heads"]
        hd = self.config.get("head_dim", 128)
        total_max = input_ids.shape[1] + max_new_tokens
        mdtype = self.embed_tokens.weight.dtype
        kv_caches = [[mx.zeros((B, n_kv, total_max, hd), dtype=mdtype) for _ in range(2)]
                     for _ in self.layers]
        logits = self.__call__(input_ids, kv_caches, cache_pos=0)
        next_token = mx.argmax(logits[:, -1, :], -1)
        gen_tokens = [next_token]
        cache_pos = input_ids.shape[1]
        for _ in range(max_new_tokens - 1):
            if next_token.item() == eos_token_id:
                break
            logits = self.__call__(next_token[:, None], kv_caches, cache_pos=cache_pos)
            next_token = mx.argmax(logits[:, -1, :], -1)
            gen_tokens.append(next_token)
            cache_pos += 1
        return mx.concatenate([input_ids, mx.stack(gen_tokens, 1)], 1)


def load_qwen3(weights_dir, dtype=None):
    """converted-mlx dir (qwen_config.json + qwen_emotion.safetensors) -> Qwen3ForCausalLM"""
    from pathlib import Path

    from omlx.vendor.indextts25.weights import load_into, load_mlx

    d = Path(weights_dir)
    config = json.load(open(d / "qwen_config.json"))
    model = Qwen3ForCausalLM(config)
    load_into(model, load_mlx(d, "qwen_emotion"), dtype)
    return model
