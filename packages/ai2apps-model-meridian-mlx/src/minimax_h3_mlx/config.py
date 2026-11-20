"""Configuration for the MiniMax-H3 MLX port.

Field names follow the *original* checkpoint `config.json` (``MiniMaxH3DiTModel``), not the
diffusers port, so a config file can be loaded verbatim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Every row of the packed sequence carries a modality tag: 0 = video, 1 = text, 2 = audio.
# One set of AdaLN modulation parameters is kept per (timestep, modality) pair.
MODALITY_NUM = 3

# Modality tags, matching the reference.
TAG_VIDEO = 0
TAG_TEXT = 1
TAG_AUDIO = 2
TAG_PAD = -1


@dataclass
class DiTConfig:
    """MiniMax-H3 diffusion transformer (33B, 50 blocks).

    Note ``num_attention_heads * attention_head_dim`` (7168) is *larger* than ``hidden_size``
    (5376); the attention inner dimension is deliberately wider than the residual stream.
    """

    hidden_size: int = 5376
    num_layers: int = 50
    token_refiner_num_layers: int = 2
    num_attention_heads: int = 56
    attention_head_dim: int = 128
    ffn_hidden_size: int = 14336
    latents_dim: int = 24
    audio_latents_dim: int = 32
    patch_size: tuple[int, int, int] = (1, 2, 2)
    text_dim: int = 5120
    timestep_input_dim: int = 256
    time_embed_hidden_size: int = 5376
    time_embed_dim: int = 2688
    adaln_out_features: int = 96768
    final_adaln_out_features: int = 10752
    rope_inv_freq_len: int = 16
    rope_theta: float = 10000.0
    norm_eps: float = 1e-5
    qk_norm_eps: float = 1e-5
    final_norm_eps: float = 1e-5

    @property
    def inner_dim(self) -> int:
        return self.num_attention_heads * self.attention_head_dim

    @property
    def video_patch_dim(self) -> int:
        t, h, w = self.patch_size
        return self.latents_dim * t * h * w

    @property
    def rotary_dim(self) -> int:
        """Channels rotated by RoPE: three axes, doubled for the rotate-half convention."""
        return 2 * 3 * self.rope_inv_freq_len

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DiTConfig":
        known = {f for f in cls.__dataclass_fields__}
        kwargs = {k: v for k, v in raw.items() if k in known}
        if "patch_size" in kwargs:
            kwargs["patch_size"] = tuple(kwargs["patch_size"])
        return cls(**kwargs)

    @classmethod
    def from_json(cls, path: str | Path) -> "DiTConfig":
        with open(path) as fh:
            return cls.from_dict(json.load(fh))


@dataclass
class PipelineConfig:
    """Top-level pipeline metadata from `model_index.json` (`_minimax_h3` block)."""

    partition: str = "fl2va"
    tasks: list[str] = field(default_factory=lambda: ["t2va", "fl2va"])
    sigma_shift_video: float = 12.0
    sigma_shift_audio: float = 3.0

    @classmethod
    def from_model_index(cls, path: str | Path) -> "PipelineConfig":
        with open(path) as fh:
            raw = json.load(fh)
        meta = raw.get("_minimax_h3", {})
        shifts = meta.get("sigma_shift_scales", {})
        return cls(
            partition=meta.get("partition", "fl2va"),
            tasks=list(meta.get("tasks", ["t2va", "fl2va"])),
            sigma_shift_video=float(shifts.get("video", 12.0)),
            sigma_shift_audio=float(shifts.get("audio", 3.0)),
        )
