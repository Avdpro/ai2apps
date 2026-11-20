"""Model configuration (``config.json`` of a Haru checkpoint)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


def _pick(cls, params: dict[str, Any]):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in params.items() if k in known})


@dataclass(frozen=True)
class CodecConfig:
    """VibeVoice acoustic codec: 24 kHz waveform <-> continuous latents."""

    latent_dim: int = 64
    base_channels: int = 32
    ratios: tuple[int, ...] = (8, 5, 5, 4, 2, 2)  # upsampling order
    encoder_depths: tuple[int, ...] = (3, 3, 3, 3, 3, 3, 8)
    decoder_depths: tuple[int, ...] = (8, 3, 3, 3, 3, 3, 3)
    norm_eps: float = 1e-5
    latent_std: float = 0.5

    @property
    def frame_samples(self) -> int:
        samples = 1
        for r in self.ratios:
            samples *= r
        return samples


@dataclass(frozen=True)
class HeadConfig:
    """MeanFlow head: LM hidden state -> next audio latent."""

    hidden_size: int = 2560
    latent_dim: int = 64
    num_layers: int = 4
    ffn_ratio: float = 3.0
    norm_eps: float = 1e-5
    interval_embed: float = 7.0
    num_steps: int = 1
    guidance_scale: float = 1.5
    guidance_range: tuple[float, float] = (1.0, 2.0)


@dataclass(frozen=True)
class HaruConfig:
    sample_rate: int = 24_000
    frame_samples: int = 3200
    latent_dim: int = 64
    pad_token_id: int = 248076
    eop_token_id: int = 248071
    dtype: str = "bfloat16"
    lm: dict[str, Any] = field(default_factory=dict)
    codec: CodecConfig = field(default_factory=CodecConfig)
    head: HeadConfig = field(default_factory=HeadConfig)

    @property
    def frame_rate(self) -> float:
        return self.sample_rate / self.frame_samples

    @property
    def hidden_size(self) -> int:
        return int(self.lm["hidden_size"])

    @property
    def eos_token_id(self) -> int | None:
        eos = self.lm.get("eos_token_id")
        return None if eos is None else int(eos)

    @classmethod
    def from_dict(cls, params: dict[str, Any]) -> "HaruConfig":
        if params.get("model_type", "haru") != "haru":
            raise ValueError(f"not a Haru checkpoint (model_type={params.get('model_type')!r})")
        params = dict(params)
        codec = dict(params.pop("codec", {}))
        head = dict(params.pop("head", {}))
        for key in ("ratios", "encoder_depths", "decoder_depths"):
            if key in codec:
                codec[key] = tuple(codec[key])
        if "guidance_range" in head:
            head["guidance_range"] = tuple(head["guidance_range"])
        config = _pick(cls, {**params, "codec": _pick(CodecConfig, codec), "head": _pick(HeadConfig, head)})
        if config.codec.frame_samples != config.frame_samples:
            raise ValueError("codec ratios do not match frame_samples")
        return config

    @classmethod
    def from_file(cls, path: str | Path) -> "HaruConfig":
        return cls.from_dict(json.loads(Path(path).read_text()))
