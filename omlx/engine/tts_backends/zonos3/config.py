# Copyright (c) 2026 Zyphra, Inc.

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LMConfig:
    n_layers: int
    max_seqlen: int
    dim: int
    head_dim: int
    n_heads: int
    n_kv_heads: int
    ffn_hidden: int
    n_experts: int
    moe_topk: int
    n_codebooks: int
    codebook_size: int
    audio_vocab: int
    eoa_id: int
    audio_pad_id: int
    span_end_id: int | None
    text_vocab: int
    text_extra_tokens: int
    gdn_heads: int
    gdn_head_dim: int
    gdn_kernel: int
    speaker_embedding_dim: int
    condition_count: int
    condition_bucket_counts: tuple[
        int, ...
    ]  # per condition row: ids 0..n-1, n = unknown (table has n + 1 rows)
    condition_names: tuple[str, ...]
    condition_units: dict[str, str]
    condition_edges: dict[str, tuple[float, ...]]
    rope_theta: float
    norm_eps: float
    qk_eps: float
    loss_softcap: float
    gdn_period: int
    silence_frame: tuple[int, ...]
    text_tokenizer_spec: dict
    tag_cfg_trained: bool = False
    # Not in the GGUF: the release architecture tools/convert_gguf.py validate_config accepts.
    audio_codec: str = "opus_dual_3n_600k_sched600k_r4096_step600000"
    speaker_embedding_codec: str = "ownmect_s2"
    speaker_reference_prefix_enabled: bool = True
    speaker_reference_max_seconds: float = 60.0

    @property
    def n_sources(self) -> int:
        return 2 * self.n_layers + 1

    @property
    def codebook_sizes(self) -> tuple[int, ...]:
        return (self.codebook_size,) * self.n_codebooks

    @property
    def text_rows(self) -> int:
        return self.text_vocab + 1 + self.text_extra_tokens

    @property
    def gdn_inner(self) -> int:
        return self.gdn_heads * self.gdn_head_dim

    def uses_gdn(self, layer: int) -> bool:
        return (layer + 1) % self.gdn_period != 0

    @property
    def attention_layers(self) -> tuple[int, ...]:
        return tuple(
            layer for layer in range(self.n_layers) if not self.uses_gdn(layer)
        )


@dataclass
class ModelConfig:
    model_type: str = "zonos3"
    backbone: dict = field(default_factory=dict)
    tensors: dict = field(default_factory=dict)
    model_path: str | None = None

    @classmethod
    def from_dict(cls, params):
        return cls(**{k: v for k, v in params.items() if k in cls.__dataclass_fields__})
