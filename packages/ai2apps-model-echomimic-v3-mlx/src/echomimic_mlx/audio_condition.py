"""EchoMimicV3 audio projection implemented with explicit MLX weights."""

from __future__ import annotations

from dataclasses import dataclass

import mlx.core as mx

from .tensor_utils import linear, wan_layer_norm


@dataclass(frozen=True, slots=True)
class AudioProjectionWeights:
    """PyTorch-layout parameters for the upstream ``AudioProjModel``."""

    proj1_weight: mx.array
    proj1_bias: mx.array
    proj1_vf_weight: mx.array
    proj1_vf_bias: mx.array
    proj2_weight: mx.array
    proj2_bias: mx.array
    proj3_weight: mx.array
    proj3_bias: mx.array
    norm_weight: mx.array | None = None
    norm_bias: mx.array | None = None


def _flatten_windows(audio: mx.array) -> mx.array:
    if audio.ndim != 5:
        raise ValueError(
            "audio projection input must have shape [batch, frames, window, blocks, channels]"
        )
    batch, frames = audio.shape[:2]
    return mx.reshape(audio, (batch * frames, -1))


def project_audio_condition(
    first_frame_audio: mx.array,
    later_frame_audio: mx.array,
    weights: AudioProjectionWeights,
    *,
    context_tokens: int,
    norm_eps: float = 1e-5,
) -> mx.array:
    """Match the pinned upstream audio projection and output layout.

    Inputs use ``[batch, frames, window, blocks, channels]`` and the result uses
    ``[batch, total_frames, context_tokens, output_dim]``.
    """

    if context_tokens <= 0:
        raise ValueError("context_tokens must be positive")
    if first_frame_audio.ndim != 5 or later_frame_audio.ndim != 5:
        raise ValueError("both audio projection inputs must be rank five")
    if first_frame_audio.shape[0] != later_frame_audio.shape[0]:
        raise ValueError("audio projection inputs must use the same batch size")
    batch = first_frame_audio.shape[0]
    first_frames = first_frame_audio.shape[1]
    later_frames = later_frame_audio.shape[1]
    total_frames = first_frames + later_frames
    first = mx.maximum(
        linear(_flatten_windows(first_frame_audio), weights.proj1_weight, weights.proj1_bias),
        0,
    )
    later = mx.maximum(
        linear(
            _flatten_windows(later_frame_audio),
            weights.proj1_vf_weight,
            weights.proj1_vf_bias,
        ),
        0,
    )
    first = mx.reshape(first, (batch, first_frames, -1))
    later = mx.reshape(later, (batch, later_frames, -1))
    combined = mx.reshape(mx.concatenate([first, later], axis=1), (batch * total_frames, -1))
    hidden = mx.maximum(linear(combined, weights.proj2_weight, weights.proj2_bias), 0)
    projected = linear(hidden, weights.proj3_weight, weights.proj3_bias)
    if projected.shape[-1] % context_tokens:
        raise ValueError("proj3 output dimension must be divisible by context_tokens")
    output_dim = projected.shape[-1] // context_tokens
    projected = mx.reshape(projected, (batch * total_frames, context_tokens, output_dim))
    if weights.norm_weight is not None or weights.norm_bias is not None:
        if weights.norm_weight is None or weights.norm_bias is None:
            raise ValueError("audio output LayerNorm requires both weight and bias")
        # CUDA autocast runs the upstream nn.LayerNorm in FP32 and leaves its output
        # in FP32 even though the projection inputs and affine parameters are BF16.
        projected = wan_layer_norm(
            projected.astype(mx.float32),
            weights.norm_weight.astype(mx.float32),
            weights.norm_bias.astype(mx.float32),
            eps=norm_eps,
        )
    return mx.reshape(projected, (batch, total_frames, context_tokens, output_dim))
