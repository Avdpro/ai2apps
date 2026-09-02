"""Native MLX implementation of the Ideogram 4 diffusion transformer.

Parameter names intentionally mirror ideogram-oss/ideogram4 so converted
checkpoints can be loaded without a second model-specific rename table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import mlx.core as mx  # type: ignore[import-not-found]
import mlx.nn as nn  # type: ignore[import-not-found]
import numpy as np
from fused_qk_rope import fused_qk_rms_mrope

LLM_TOKEN_INDICATOR = 3
OUTPUT_IMAGE_INDICATOR = 2


@dataclass(frozen=True)
class Ideogram4Config:
    emb_dim: int = 4608
    num_layers: int = 34
    num_heads: int = 18
    intermediate_size: int = 12288
    adaln_dim: int = 512
    in_channels: int = 128
    llm_features_dim: int = 4096 * 13
    rope_theta: int = 5_000_000
    mrope_section: tuple[int, int, int] = (24, 20, 20)
    norm_eps: float = 1e-5

    def __post_init__(self) -> None:
        if self.emb_dim % self.num_heads:
            raise ValueError("emb_dim must be divisible by num_heads")
        head_dim = self.emb_dim // self.num_heads
        if head_dim % 2 or sum(self.mrope_section) > head_dim // 2:
            raise ValueError("mrope_section exceeds half of head_dim")


@dataclass(frozen=True)
class PreparedConditioning:
    text_value: mx.array
    indicator_value: mx.array
    cos: mx.array
    sin: mx.array
    attention_mask: mx.array | None


class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float) -> None:
        super().__init__()
        self.weight = mx.ones((dim,))
        self.eps = eps

    def __call__(self, value: mx.array) -> mx.array:
        return mx.fast.rms_norm(value, self.weight, self.eps)


def rotate_half(value: mx.array) -> mx.array:
    half = value.shape[-1] // 2
    return mx.concatenate((-value[..., half:], value[..., :half]), axis=-1)


class MRoPE(nn.Module):
    def __init__(
        self, head_dim: int, base: int, sections: tuple[int, int, int]
    ) -> None:
        super().__init__()
        self.head_dim = head_dim
        self.base = base
        self.sections = sections

    def __call__(self, position_ids: mx.array) -> tuple[mx.array, mx.array]:
        if position_ids.ndim != 3 or position_ids.shape[-1] != 3:
            raise ValueError("position_ids must have shape [batch, sequence, 3]")
        inv_freq = 1.0 / (
            self.base
            ** (mx.arange(0, self.head_dim, 2, dtype=mx.float32) / self.head_dim)
        )
        frequencies = position_ids.astype(mx.float32)[..., None] * inv_freq
        selected = frequencies[:, :, 0, :]
        indices = mx.arange(inv_freq.shape[0])
        height_mask = (indices % 3 == 1) & (indices < self.sections[1] * 3)
        width_mask = (indices % 3 == 2) & (indices < self.sections[2] * 3)
        selected = mx.where(height_mask, frequencies[:, :, 1, :], selected)
        selected = mx.where(width_mask, frequencies[:, :, 2, :], selected)
        embedding = mx.concatenate((selected, selected), axis=-1)
        return mx.cos(embedding), mx.sin(embedding)


class Attention(nn.Module):
    def __init__(self, hidden_size: int, num_heads: int) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_dim = hidden_size // num_heads
        self.sdpa_dtype: mx.Dtype | None = None
        self.qkv = nn.Linear(hidden_size, hidden_size * 3, bias=False)
        self.norm_q = RMSNorm(self.head_dim, 1e-5)
        self.norm_k = RMSNorm(self.head_dim, 1e-5)
        self.o = nn.Linear(hidden_size, hidden_size, bias=False)

    def __call__(
        self,
        value: mx.array,
        attention_mask: mx.array | None,
        cos: mx.array,
        sin: mx.array,
    ) -> mx.array:
        batch, sequence, _ = value.shape
        qkv = self.qkv(value).reshape(batch, sequence, 3, self.num_heads, self.head_dim)
        query, key, values = (
            mx.squeeze(part, axis=2) for part in mx.split(qkv, 3, axis=2)
        )
        values = values.transpose(0, 2, 1, 3)
        fused = fused_qk_rms_mrope(
            query,
            key,
            self.norm_q.weight,
            self.norm_k.weight,
            cos,
            sin,
            self.norm_q.eps,
        )
        if fused is None:
            query = self.norm_q(query).transpose(0, 2, 1, 3)
            key = self.norm_k(key).transpose(0, 2, 1, 3)
            cos = cos[:, None, :, :]
            sin = sin[:, None, :, :]
            query = query * cos + rotate_half(query) * sin
            key = key * cos + rotate_half(key) * sin
        else:
            query, key = fused

        output_dtype = query.dtype
        if self.sdpa_dtype is not None:
            query = query.astype(self.sdpa_dtype)
            key = key.astype(self.sdpa_dtype)
            values = values.astype(self.sdpa_dtype)
        output = mx.fast.scaled_dot_product_attention(
            query,
            key,
            values,
            scale=self.head_dim**-0.5,
            mask=attention_mask,
        )
        output = output.astype(output_dtype)
        output = output.transpose(0, 2, 1, 3).reshape(batch, sequence, self.hidden_size)
        return self.o(output)


class MLP(nn.Module):
    def __init__(self, dim: int, hidden_dim: int) -> None:
        super().__init__()
        self.activation_dtype: mx.Dtype | None = None
        self.w1 = nn.Linear(dim, hidden_dim, bias=False)
        self.w2 = nn.Linear(hidden_dim, dim, bias=False)
        self.w3 = nn.Linear(dim, hidden_dim, bias=False)

    def __call__(self, value: mx.array) -> mx.array:
        # Q4 projection scales are BF16, and Apple GPU NAX executes this
        # bandwidth-heavy path materially faster with BF16 activations. Keep
        # the surrounding residual stream in its original dtype so attention
        # and accumulation retain their existing numerical behavior.
        output_dtype = value.dtype
        if self.activation_dtype is None:
            return self.w2(nn.silu(self.w1(value)) * self.w3(value))
        value = value.astype(self.activation_dtype)
        output = self.w2(nn.silu(self.w1(value)) * self.w3(value))
        return output.astype(output_dtype)


class TransformerBlock(nn.Module):
    def __init__(self, config: Ideogram4Config) -> None:
        super().__init__()
        self.attention = Attention(config.emb_dim, config.num_heads)
        self.feed_forward = MLP(config.emb_dim, config.intermediate_size)
        self.attention_norm1 = RMSNorm(config.emb_dim, config.norm_eps)
        self.ffn_norm1 = RMSNorm(config.emb_dim, config.norm_eps)
        self.attention_norm2 = RMSNorm(config.emb_dim, config.norm_eps)
        self.ffn_norm2 = RMSNorm(config.emb_dim, config.norm_eps)
        self.adaln_modulation = nn.Linear(config.adaln_dim, 4 * config.emb_dim)

    def __call__(
        self,
        value: mx.array,
        attention_mask: mx.array | None,
        cos: mx.array,
        sin: mx.array,
        adaln_input: mx.array,
    ) -> mx.array:
        scale_msa, gate_msa, scale_mlp, gate_mlp = mx.split(
            self.adaln_modulation(adaln_input), 4, axis=-1
        )
        attention = self.attention(
            self.attention_norm1(value) * (1.0 + scale_msa),
            attention_mask,
            cos,
            sin,
        )
        value = value + mx.tanh(gate_msa) * self.attention_norm2(attention)
        feed_forward = self.feed_forward(self.ffn_norm1(value) * (1.0 + scale_mlp))
        return value + mx.tanh(gate_mlp) * self.ffn_norm2(feed_forward)


def sinusoidal_embedding(value: mx.array, dim: int, scale: float = 1e4) -> mx.array:
    half = dim // 2
    frequency = mx.exp(
        mx.arange(half, dtype=mx.float32) * (-math.log(scale) / (half - 1))
    )
    phase = value.astype(mx.float32)[..., None] * frequency
    embedding = mx.concatenate((mx.sin(phase), mx.cos(phase)), axis=-1)
    if dim % 2:
        embedding = mx.pad(embedding, [(0, 0)] * (embedding.ndim - 1) + [(0, 1)])
    return embedding


class EmbedScalar(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = dim
        self.mlp_in = nn.Linear(dim, dim)
        self.mlp_out = nn.Linear(dim, dim)

    def __call__(self, value: mx.array) -> mx.array:
        embedding = sinusoidal_embedding(1e4 * value, self.dim)
        return self.mlp_out(nn.silu(self.mlp_in(embedding)))


class FinalLayer(nn.Module):
    def __init__(self, config: Ideogram4Config) -> None:
        super().__init__()
        self.linear = nn.Linear(config.emb_dim, config.in_channels)
        self.adaln_modulation = nn.Linear(config.adaln_dim, config.emb_dim)

    @staticmethod
    def layer_norm(value: mx.array) -> mx.array:
        return mx.fast.layer_norm(value, None, None, 1e-6)

    def __call__(self, value: mx.array, conditioning: mx.array) -> mx.array:
        scale = 1.0 + self.adaln_modulation(nn.silu(conditioning))
        return self.linear(self.layer_norm(value) * scale)


class Ideogram4Transformer(nn.Module):
    def __init__(self, config: Ideogram4Config | None = None) -> None:
        super().__init__()
        config = config or Ideogram4Config()
        self.config = config
        self.compute_dtype = mx.float32
        self.input_proj = nn.Linear(config.in_channels, config.emb_dim)
        self.llm_cond_norm = RMSNorm(config.llm_features_dim, 1e-6)
        self.llm_cond_proj = nn.Linear(config.llm_features_dim, config.emb_dim)
        self.t_embedding = EmbedScalar(config.emb_dim)
        self.adaln_proj = nn.Linear(config.emb_dim, config.adaln_dim)
        self.embed_image_indicator = nn.Embedding(2, config.emb_dim)
        self.rotary_emb = MRoPE(
            config.emb_dim // config.num_heads,
            config.rope_theta,
            config.mrope_section,
        )
        self.layers = [TransformerBlock(config) for _ in range(config.num_layers)]
        self.final_layer = FinalLayer(config)

    def _project_roles(
        self,
        llm_features: mx.array,
        value: mx.array,
        indicator: mx.array,
        *,
        project_text: bool = True,
    ) -> tuple[mx.array, mx.array]:
        """Project only the tokens consumed by each input projection.

        The reference implementation masks before projection and masks again
        afterwards. Skipping the opposite-role rows is algebraically identical,
        including for projection biases, and avoids applying the 53,248-wide
        text projection to thousands of image tokens.
        """
        text_rows = []
        image_rows = []
        sequence = indicator.shape[1]
        for batch_index in range(indicator.shape[0]):
            roles = np.asarray(indicator[batch_index].tolist())
            text_indices = np.flatnonzero(roles == LLM_TOKEN_INDICATOR).astype(
                np.uint32
            )
            image_indices = np.flatnonzero(roles == OUTPUT_IMAGE_INDICATOR).astype(
                np.uint32
            )
            text_row = mx.zeros(
                (sequence, self.config.emb_dim), dtype=llm_features.dtype
            )
            image_row = mx.zeros((sequence, self.config.emb_dim), dtype=value.dtype)
            if project_text and text_indices.size:
                indices = mx.array(text_indices)
                projected = self.llm_cond_proj(
                    self.llm_cond_norm(
                        llm_features[batch_index, indices].astype(self.compute_dtype)
                    )
                )
                text_row[indices] = projected
            if image_indices.size:
                indices = mx.array(image_indices)
                projected = self.input_proj(
                    value[batch_index, indices].astype(self.compute_dtype)
                )
                image_row[indices] = projected
            text_rows.append(text_row)
            image_rows.append(image_row)
        return mx.stack(text_rows), mx.stack(image_rows)

    def prepare_conditioning(
        self,
        *,
        llm_features: mx.array,
        value: mx.array,
        position_ids: mx.array,
        segment_ids: mx.array,
        indicator: mx.array,
        uniform_segments: bool = False,
    ) -> PreparedConditioning:
        text_value, _ = self._project_roles(llm_features, value, indicator)
        image_mask = (indicator == OUTPUT_IMAGE_INDICATOR)[..., None]
        indicator_value = self.embed_image_indicator(
            image_mask[..., 0].astype(mx.int32)
        )
        cos, sin = self.rotary_emb(position_ids)
        # The eager reference casts RoPE and the mask after image/text values
        # are combined. Image latents are float32 in the sampler, so preserve
        # that promotion rather than inheriting the quantized text path dtype.
        compute_dtype = self.compute_dtype
        cos = cos.astype(compute_dtype)
        sin = sin.astype(compute_dtype)
        attention_mask = None
        if not uniform_segments:
            same_segment = segment_ids[:, :, None] == segment_ids[:, None, :]
            attention_mask = mx.where(same_segment[:, None, :, :], 0.0, -1e9).astype(
                compute_dtype
            )
        prepared = PreparedConditioning(
            text_value=text_value,
            indicator_value=indicator_value,
            cos=cos,
            sin=sin,
            attention_mask=attention_mask,
        )
        evaluated = [
            prepared.text_value,
            prepared.indicator_value,
            prepared.cos,
            prepared.sin,
        ]
        if prepared.attention_mask is not None:
            evaluated.append(prepared.attention_mask)
        mx.eval(*evaluated)
        return prepared

    def __call__(
        self,
        *,
        llm_features: mx.array,
        value: mx.array,
        timestep: mx.array,
        position_ids: mx.array,
        segment_ids: mx.array,
        indicator: mx.array,
        prepared: PreparedConditioning | None = None,
    ) -> mx.array:
        if prepared is None:
            prepared = self.prepare_conditioning(
                llm_features=llm_features,
                value=value,
                position_ids=position_ids,
                segment_ids=segment_ids,
                indicator=indicator,
            )
        _, image_value = self._project_roles(
            llm_features, value, indicator, project_text=False
        )

        conditioning = self.t_embedding(timestep)
        if timestep.ndim == 1:
            conditioning = conditioning[:, None, :]
        conditioning = conditioning.astype(self.compute_dtype)
        conditioning = nn.silu(self.adaln_proj(conditioning))

        hidden = image_value + prepared.text_value
        hidden += prepared.indicator_value
        for layer in self.layers:
            hidden = layer(
                hidden,
                prepared.attention_mask,
                prepared.cos,
                prepared.sin,
                conditioning,
            )
        return self.final_layer(hidden, conditioning).astype(mx.float32)


def load_quantized_transformer(
    checkpoint: str | Path,
    *,
    bits: int,
    group_size: int,
) -> Ideogram4Transformer:
    weights = mx.load(str(checkpoint))
    model = Ideogram4Transformer()
    model.compute_dtype = mx.bfloat16 if bits == 16 else mx.float32

    def predicate(path: str, module: nn.Module) -> bool:
        return hasattr(module, "to_quantized") and f"{path}.scales" in weights

    if bits < 16:
        nn.quantize(
            model,
            bits=bits,
            group_size=group_size,
            class_predicate=predicate,
        )
    if bits == 4:
        for layer in model.layers:
            layer.attention.sdpa_dtype = mx.bfloat16
            layer.feed_forward.activation_dtype = mx.bfloat16
    model.load_weights(list(weights.items()), strict=True)
    model.eval()
    mx.eval(model.parameters())
    return model
