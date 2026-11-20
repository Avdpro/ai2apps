"""Backbone hyper-parameters (the ``lm`` section of ``config.json``)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LINEAR = "linear_attention"
FULL = "full_attention"


@dataclass(frozen=True)
class TextConfig:
    """Qwen3.5 text model: Gated DeltaNet layers with periodic full attention."""

    vocab_size: int
    hidden_size: int
    intermediate_size: int
    num_attention_heads: int
    num_key_value_heads: int
    head_dim: int
    linear_num_key_heads: int
    linear_num_value_heads: int
    linear_key_head_dim: int
    linear_value_head_dim: int
    linear_conv_kernel_dim: int
    layer_types: tuple[str, ...]
    rms_norm_eps: float = 1e-6
    rope_theta: float = 10_000_000.0
    partial_rotary_factor: float = 0.25

    @property
    def key_dim(self) -> int:
        return self.linear_num_key_heads * self.linear_key_head_dim

    @property
    def value_dim(self) -> int:
        return self.linear_num_value_heads * self.linear_value_head_dim

    @property
    def conv_dim(self) -> int:
        """Width of the Gated DeltaNet convolution: queries, keys and values."""
        return 2 * self.key_dim + self.value_dim

    @classmethod
    def from_dict(cls, params: dict[str, Any]) -> "TextConfig":
        if not params.get("attn_output_gate", True):
            raise ValueError("the backbone needs attn_output_gate=true")
        layers = int(params["num_hidden_layers"])
        interval = int(params.get("full_attention_interval", 4))
        layer_types = tuple(
            params.get("layer_types") or (FULL if (i + 1) % interval == 0 else LINEAR for i in range(layers))
        )
        if len(layer_types) != layers or set(layer_types) - {LINEAR, FULL}:
            raise ValueError("layer_types must name num_hidden_layers linear_attention / full_attention layers")
        if int(params["linear_num_value_heads"]) % int(params["linear_num_key_heads"]):
            raise ValueError("linear_num_value_heads must be a multiple of linear_num_key_heads")
        rope = params.get("rope_parameters") or {}
        hidden, heads = int(params["hidden_size"]), int(params["num_attention_heads"])
        return cls(
            vocab_size=int(params["vocab_size"]),
            hidden_size=hidden,
            intermediate_size=int(params["intermediate_size"]),
            num_attention_heads=heads,
            num_key_value_heads=int(params["num_key_value_heads"]),
            head_dim=int(params.get("head_dim") or hidden // heads),
            linear_num_key_heads=int(params["linear_num_key_heads"]),
            linear_num_value_heads=int(params["linear_num_value_heads"]),
            linear_key_head_dim=int(params["linear_key_head_dim"]),
            linear_value_head_dim=int(params["linear_value_head_dim"]),
            linear_conv_kernel_dim=int(params["linear_conv_kernel_dim"]),
            layer_types=layer_types,
            rms_norm_eps=float(params.get("rms_norm_eps", 1e-6)),
            rope_theta=float(rope.get("rope_theta", 10_000_000.0)),
            partial_rotary_factor=float(
                rope.get("partial_rotary_factor", params.get("partial_rotary_factor", 0.25))
            ),
        )
