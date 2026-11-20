"""MLX port of the whisper-tiny encoder (HF transformers WhisperEncoder).

MuseTalk feeds the **stacked hidden states** (output_hidden_states=True) as audio
conditioning, so we replicate HF's exact hidden-state collection:
  states = (in_layer0, in_layer1, in_layer2, in_layer3, layer_norm(out_layer3))   # 5 for 4 layers
stacked on a new axis -> (B, seq, 5, 384).

Isomorphic to the HF encoder state_dict names. Runs NLC (MLX conv1d) internally.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn


class WhisperEncoderLayer(nn.Module):
    def __init__(self, d_model=384, n_heads=6, ffn=1536):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.scale = self.head_dim**-0.5
        self.self_attn_layer_norm = nn.LayerNorm(d_model)
        self.self_attn = _Attn(d_model, n_heads)
        self.final_layer_norm = nn.LayerNorm(d_model)
        self.fc1 = nn.Linear(d_model, ffn)
        self.fc2 = nn.Linear(ffn, d_model)

    def __call__(self, x):
        x = x + self.self_attn(self.self_attn_layer_norm(x))
        x = x + self.fc2(nn.gelu(self.fc1(self.final_layer_norm(x))))
        return x


class _Attn(nn.Module):
    def __init__(self, d_model, n_heads):
        super().__init__()
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        self.scale = self.head_dim**-0.5
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model, bias=False)  # whisper: k has no bias
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)

    def _split(self, x):
        b, n, _ = x.shape
        return x.reshape(b, n, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)

    def __call__(self, x):
        q, k, v = (
            self._split(self.q_proj(x)),
            self._split(self.k_proj(x)),
            self._split(self.v_proj(x)),
        )
        out = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale)
        b, h, n, d = out.shape
        return self.out_proj(out.transpose(0, 2, 1, 3).reshape(b, n, h * d))


class WhisperEncoder(nn.Module):
    def __init__(
        self, n_mels=80, d_model=384, n_layers=4, n_heads=6, ffn=1536, max_pos=1500
    ):
        super().__init__()
        self.conv1 = nn.Conv1d(n_mels, d_model, 3, padding=1)
        self.conv2 = nn.Conv1d(d_model, d_model, 3, stride=2, padding=1)
        self.embed_positions = nn.Embedding(max_pos, d_model)
        self.layers = [
            WhisperEncoderLayer(d_model, n_heads, ffn) for _ in range(n_layers)
        ]
        self.layer_norm = nn.LayerNorm(d_model)

    def __call__(self, mel_bcl):
        """mel_bcl: (B, n_mels, L=3000) -> stacked hidden states (B, seq=1500, n_layers+1, d)."""
        x = mel_bcl.transpose(0, 2, 1)  # (B, L, n_mels) for MLX conv1d (NLC)
        x = nn.gelu(self.conv1(x))
        x = nn.gelu(self.conv2(x))  # (B, 1500, d)
        x = x + self.embed_positions.weight[None, : x.shape[1], :]

        states = []
        for layer in self.layers:
            states.append(x)  # input to this layer (HF collects pre-layer)
            x = layer(x)
        states.append(self.layer_norm(x))  # final = layer_norm(last)
        return mx.stack(states, axis=2)  # (B, seq, n_layers+1, d)
