"""Stable configuration contracts shared by future pipeline stages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ReferenceConfiguration:
    """The fixed M0 numerical-reference configuration."""

    width: int = 512
    height: int = 512
    num_frames: int = 81
    fps: int = 25
    audio_sample_rate: int = 16_000
    sampler: str = "Flow_Unipc"
    steps: int = 8
    seed: int = 43
    guidance_scale: float = 6.0
    audio_guidance_scale: float = 3.0
    weight_dtype: str = "bfloat16"
    teacache: bool = False

    def __post_init__(self) -> None:
        if self.width != 512 or self.height != 512:
            raise ValueError("M0 reference exports must use 512x512 inputs")
        if self.num_frames != 81 or self.fps != 25:
            raise ValueError("M0 reference exports must use 81 frames at 25 FPS")
        if self.audio_sample_rate != 16_000:
            raise ValueError("M0 reference audio must be 16 kHz")
        if self.steps != 8:
            raise ValueError("EchoMimicV3-Flash reference exports must use 8 steps")
        if self.teacache:
            raise ValueError("TeaCache must be disabled for numerical reference exports")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Block0AcceptanceThresholds:
    """Frozen BF16 production-geometry parity gates for the real block fixture."""

    max_stage_relative_l2: float = 0.02
    min_stage_cosine: float = 0.9998
    max_output_relative_l2: float = 0.01
    min_output_cosine: float = 0.9999

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class DenoisingAcceptanceThresholds:
    """Frozen BF16 gates for the raw-latent full-Transformer M2 replay."""

    max_global_block_input_relative_l2: float = 0.001
    min_global_block_input_cosine: float = 0.999999
    max_global_context_relative_l2: float = 0.006
    min_global_context_cosine: float = 0.99998
    max_boundary_relative_l2: float = 0.025
    min_boundary_cosine: float = 0.99975
    max_branch_relative_l2: float = 0.012
    min_branch_cosine: float = 0.9999
    max_guided_noise_relative_l2: float = 0.04
    min_guided_noise_cosine: float = 0.9993
    max_scheduler_teacher_relative_l2: float = 0.01
    min_scheduler_teacher_cosine: float = 0.99998
    max_scheduler_closed_relative_l2: float = 0.01
    min_scheduler_closed_cosine: float = 0.99995
    max_denoising_teacher_latent_relative_l2: float = 0.03
    min_denoising_teacher_latent_cosine: float = 0.9996
    max_denoising_closed_latent_relative_l2: float = 0.035
    min_denoising_closed_latent_cosine: float = 0.9995

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class VaeDecoderAcceptanceThresholds:
    """Frozen BF16 gates for the real one-frame and full Wan VAE decoder traces."""

    max_stage_relative_l2: float = 0.015
    min_stage_cosine: float = 0.9999
    max_output_relative_l2: float = 0.012
    min_output_cosine: float = 0.99995

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Forward-compatible request contract; execution is implemented in later milestones."""

    image_path: str
    audio_path: str
    prompt: str = "A person is speaking."
    width: int = 512
    height: int = 512
    fps: int = 25
    num_frames: int = 81
    steps: int = 8
    seed: int = 43
    teacache_threshold: float = 0.0
    teacache_skip_start_steps: int = 5
    use_fused_norms: bool = False

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("width and height must be positive")
        if self.fps <= 0 or self.num_frames <= 0 or self.steps <= 0:
            raise ValueError("fps, num_frames, and steps must be positive")
        if self.teacache_threshold < 0:
            raise ValueError("TeaCache threshold must be non-negative")
        if not 0 <= self.teacache_skip_start_steps <= self.steps:
            raise ValueError("TeaCache skip-start steps must fit the denoising schedule")


@dataclass(frozen=True, slots=True)
class FlashTransformerConfiguration:
    """Pinned config.json fields that determine Transformer structure and behavior."""

    model_type: str = "i2v"
    patch_size: tuple[int, int, int] = (1, 2, 2)
    text_len: int = 512
    in_dim: int = 36
    dim: int = 1536
    ffn_dim: int = 8960
    freq_dim: int = 256
    text_dim: int = 4096
    out_dim: int = 16
    num_heads: int = 12
    num_layers: int = 30
    window_size: tuple[int, int] = (-1, -1)
    qk_norm: bool = True
    cross_attn_norm: bool = True
    eps: float = 1e-6
    add_control_adapter: bool = False
    add_ref_conv: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> FlashTransformerConfiguration:
        """Parse and require exact agreement with the pinned Flash model config."""

        expected = cls()
        normalized: dict[str, object] = {}
        for field, expected_value in asdict(expected).items():
            if field not in value:
                raise ValueError(f"Flash config is missing pinned field: {field}")
            actual = value[field]
            if isinstance(expected_value, tuple) and isinstance(actual, list):
                actual = tuple(actual)
            if actual != expected_value:
                raise ValueError(
                    f"Flash config drift for {field}: {actual!r} != {expected_value!r}"
                )
            normalized[field] = actual
        return cls(**normalized)  # type: ignore[arg-type]
