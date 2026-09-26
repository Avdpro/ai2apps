"""IndexTTS-2.5 config.yaml access — only runtime-consumed fields exposed;
defaults == official 2.5 release. Hyper-params living in module __init__
signatures (layers/model_dim/wavenet_*) are those signatures' defaults, not
mirrored here."""
from dataclasses import dataclass, field, fields


@dataclass
class SemanticCodec:
    codebook_size: int = 8192
    hidden_size: int = 1024
    codebook_dim: int = 8
    vocos_dim: int = 384
    vocos_intermediate_dim: int = 2048
    vocos_num_layers: int = 12


@dataclass
class LengthReg:
    channels: int = 512
    sampling_ratios: tuple = (1, 1, 1, 1)
    is_discrete: bool = False
    in_channels: int =  1024
    content_codebook_size: int = 2048


@dataclass
class DiTSec:
    in_channels: int = 80


@dataclass
class S2Mel:
    length_reg: LengthReg = field(default_factory=LengthReg)
    dit: DiTSec = field(default_factory=DiTSec)


@dataclass
class GPT:
    stop_mel_token: int = 8193


@dataclass
class Config:
    gpt: GPT = field(default_factory=GPT)
    semantic_codec: SemanticCodec = field(default_factory=SemanticCodec)
    s2mel: S2Mel = field(default_factory=S2Mel)
    _raw: dict = field(default_factory=dict)


def _sec(cls, d):
    ks = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in ks})


def from_yaml(path):
    import yaml
    raw = yaml.safe_load(open(path, encoding="utf-8"))
    g = raw.get("gpt", {}) or {}
    lr = (raw.get("s2mel", {}) or {}).get("length_regulator", {}) or {}
    dit = (raw.get("s2mel", {}) or {}).get("DiT", {}) or {}
    return Config(
        gpt=GPT(stop_mel_token=g.get("stop_mel_token", 8193)),
        semantic_codec=_sec(SemanticCodec, raw.get("semantic_codec", {}) or {}),
        s2mel=S2Mel(length_reg=_sec(LengthReg, lr), dit=_sec(DiTSec, dit)),
        _raw=raw,
    )


def load_default_config(weights_dir=None):
    import os
    d = weights_dir or os.environ.get("WINDEXTTS_WEIGHTS_DIR", "/root/IndexTTS-2.5")
    return from_yaml(os.path.join(d, "config.yaml"))
