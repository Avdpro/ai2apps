"""Haru: a full-duplex spoken dialogue model.

One language-model position is one 133 ms frame. Its input is the sum of three
streams at that frame: the model's text token, the model's audio latent and the
user's audio latent. The hidden state at frame ``t`` predicts frame ``t + 1``:
the text token through the tied output embedding and the audio latent through
the MeanFlow head.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from ..config import HaruConfig
from ..lm_config import TextConfig
from .meanflow_head import MeanFlowHead
from .qwen3_5 import LayerCache, Qwen3_5TextModel
from .vibevoice_codec import VibeVoiceCodec


class AudioProjector(nn.Module):
    """Audio latent -> LM embedding space."""

    def __init__(self, latent_dim: int, hidden: int):
        super().__init__()
        self.fc1 = nn.Linear(latent_dim, hidden)
        self.norm = nn.RMSNorm(hidden, eps=1e-6)
        self.fc2 = nn.Linear(hidden, hidden)

    def __call__(self, x: mx.array) -> mx.array:
        return self.fc2(self.norm(self.fc1(x)))


class HaruModel(nn.Module):
    def __init__(self, config: HaruConfig):
        super().__init__()
        self.config = config
        self.lm = Qwen3_5TextModel(TextConfig.from_dict(config.lm))
        self.model_audio_proj = AudioProjector(config.latent_dim, config.hidden_size)
        self.user_audio_proj = AudioProjector(config.latent_dim, config.hidden_size)
        self.head = MeanFlowHead(config.head)
        self.codec = VibeVoiceCodec(config.codec)
        self.latent_scale = mx.array(1.0, dtype=mx.float32)
        self.latent_bias = mx.array(0.0, dtype=mx.float32)
        self.tokenizer = None

    @classmethod
    def from_pretrained(cls, path_or_repo: str, **kwargs) -> "HaruModel":
        """Load from a local directory or a Hugging Face repository."""
        from .loaders import load_model

        return load_model(path_or_repo, **kwargs)

    @property
    def dtype(self) -> mx.Dtype:
        return self.model_audio_proj.fc1.weight.dtype

    # --------------------------------------------------------------- latents

    def scale_latents(self, raw: mx.array) -> mx.array:
        """Codec latents -> the normalized space of the head and projectors."""
        return (raw.astype(mx.float32) + self.latent_bias) * self.latent_scale

    def unscale_latents(self, normalized: mx.array) -> mx.array:
        return normalized.astype(mx.float32) / self.latent_scale - self.latent_bias

    # ------------------------------------------------------------ backbone

    def new_cache(self) -> list[LayerCache]:
        """An empty backbone cache for one conversation."""
        return self.lm.new_cache(1, self.dtype)

    def embed(
        self,
        tokens: mx.array,
        model_latents: mx.array | None = None,
        user_latents: mx.array | None = None,
        model_mask: mx.array | None = None,
        user_mask: mx.array | None = None,
    ) -> mx.array:
        """Sum the three streams: ``tokens [B, T]`` and raw latents ``[B, T, D]`` -> ``[B, T, H]``.

        A mask ``[B, T]`` zeroes an audio stream at positions that have none
        (the system prompt has neither, the voice reference has no user audio).
        """
        x = self.lm.embed_tokens(tokens)
        for proj, latents, mask in (
            (self.model_audio_proj, model_latents, model_mask),
            (self.user_audio_proj, user_latents, user_mask),
        ):
            if latents is None:
                continue
            y = proj(self.scale_latents(latents).astype(x.dtype))
            if mask is not None:
                y = y * mask[..., None].astype(y.dtype)
            x = x + y
        return x

    def forward(self, embeddings: mx.array, cache: list[LayerCache]) -> mx.array:
        """Run new positions ``[B, T, H]`` on top of ``cache`` -> hidden states ``[B, T, H]``."""
        return self.lm(embeddings, cache)

    def __call__(self, embeddings: mx.array, cache: list[LayerCache]) -> mx.array:
        return self.forward(embeddings, cache)

    def logits(self, hidden: mx.array) -> mx.array:
        """Text logits ``[..., vocab]`` in float32."""
        return self.lm.embed_tokens.as_linear(hidden).astype(mx.float32)

    def logits_fp32(self, hidden: mx.array, tokens: mx.array) -> mx.array:
        """Logits of a few ``tokens`` computed entirely in float32.

        The PAD / EOP decision (stay silent or start speaking) is often closer
        than the resolution of bfloat16 at the magnitude of those logits.
        """
        # The lookup also dequantizes the rows of a quantized table.
        rows = self.lm.embed_tokens(tokens).astype(mx.float32)
        return hidden.astype(mx.float32) @ rows.T

    # ---------------------------------------------------------- quantization

    def quantize(self, bits: int = 8, group_size: int = 64) -> None:
        """Quantize the backbone's weight matrices and the embedding table in place.

        A frame reads every backbone weight once, so fewer bytes per weight
        make a frame faster and the model smaller. Norm gains, the Gated
        DeltaNet convolution and gates, the audio projectors, the head and the
        codec keep their precision.

        Only 8 bits are offered: at 8 bits the hidden states stay as close to
        the float32 model as the bfloat16 checkpoint is, at 4 bits they do not
        follow it any more.
        """
        if bits != 8:
            raise ValueError("only 8-bit quantization is available")
        # One part at a time, so each part's full-precision weights are freed
        # before the next part is converted.
        for layer in self.lm.layers:
            nn.quantize(layer, group_size=group_size, bits=bits)
            mx.eval(layer.parameters())
        self.lm.embed_tokens = self.lm.embed_tokens.to_quantized(group_size=group_size, bits=bits)
        mx.eval(self.lm.embed_tokens.parameters())
        self.lm.compile()
