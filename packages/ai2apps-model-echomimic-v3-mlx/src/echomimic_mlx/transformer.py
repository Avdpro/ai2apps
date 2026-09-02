"""Close-reference Wan transformer block components for EchoMimicV3."""

from __future__ import annotations

import math
from dataclasses import dataclass

import mlx.core as mx

from .attention import scaled_dot_product_attention
from .rope import RopeTable, apply_3d_rope
from .tensor_utils import gelu_tanh, linear, wan_layer_norm, wan_rms_norm


@dataclass(frozen=True, slots=True)
class LinearParameters:
    weight: mx.array
    bias: mx.array | None = None


@dataclass(frozen=True, slots=True)
class SelfAttentionParameters:
    q: LinearParameters
    k: LinearParameters
    v: LinearParameters
    output: LinearParameters
    q_norm: mx.array
    k_norm: mx.array


@dataclass(frozen=True, slots=True)
class CrossAttentionParameters:
    q: LinearParameters
    k: LinearParameters
    v: LinearParameters
    output: LinearParameters
    q_norm: mx.array
    k_norm: mx.array
    k_image: LinearParameters
    v_image: LinearParameters
    k_image_norm: mx.array
    k_audio: LinearParameters
    v_audio: LinearParameters
    k_audio_norm: mx.array
    # The pinned upstream 2512 forward constructs q_audio but then attends with q.
    # Retain the parameter for checkpoint completeness without using it in this forward.
    q_audio: LinearParameters | None = None


@dataclass(frozen=True, slots=True)
class WanBlockParameters:
    modulation: mx.array
    self_attention: SelfAttentionParameters
    cross_attention: CrossAttentionParameters
    ffn_in: LinearParameters
    ffn_out: LinearParameters
    cross_norm_weight: mx.array | None = None
    cross_norm_bias: mx.array | None = None


@dataclass(frozen=True, slots=True)
class LayerNormParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class TwoLayerMLPParameters:
    first: LinearParameters
    second: LinearParameters


@dataclass(frozen=True, slots=True)
class PatchEmbeddingParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class ImageEmbeddingParameters:
    input_norm: LayerNormParameters
    input_projection: LinearParameters
    output_projection: LinearParameters
    output_norm: LayerNormParameters


@dataclass(frozen=True, slots=True)
class OutputHeadParameters:
    modulation: mx.array
    projection: LinearParameters


@dataclass(frozen=True, slots=True)
class WanTransformerGlobalParameters:
    patch_embedding: PatchEmbeddingParameters
    time_embedding: TwoLayerMLPParameters
    time_projection: LinearParameters
    text_embedding: TwoLayerMLPParameters
    image_embedding: ImageEmbeddingParameters
    output_head: OutputHeadParameters


@dataclass(frozen=True, slots=True)
class WanTransformerInputs:
    hidden: mx.array
    timestep_embedding: mx.array
    timestep_modulation: mx.array
    context: mx.array
    grid_sizes: list[tuple[int, int, int]]


@dataclass(frozen=True, slots=True)
class CrossAttentionTrace:
    text_image_attention: mx.array
    audio_attention: mx.array
    output: mx.array


@dataclass(frozen=True, slots=True)
class WanBlockTrace:
    norm1: mx.array
    self_attention: mx.array
    cross_input: mx.array
    text_image_attention: mx.array
    audio_attention: mx.array
    cross_attention: mx.array
    ffn_input: mx.array
    ffn: mx.array
    output: mx.array


def _project(value: mx.array, parameters: LinearParameters) -> mx.array:
    return linear(value, parameters.weight, parameters.bias)


def _rms_norm(
    value: mx.array,
    weight: mx.array | None,
    *,
    eps: float,
    fast_norms: bool,
) -> mx.array:
    return (
        mx.fast.rms_norm(value, weight, eps) if fast_norms else wan_rms_norm(value, weight, eps=eps)
    )


def _wan_layer_norm(
    value: mx.array,
    weight: mx.array | None = None,
    bias: mx.array | None = None,
    *,
    eps: float,
    fast_norms: bool,
) -> mx.array:
    return (
        mx.fast.layer_norm(value, weight, bias, eps)
        if fast_norms
        else wan_layer_norm(value, weight, bias, eps=eps)
    )


def _heads(value: mx.array, num_heads: int) -> mx.array:
    if num_heads <= 0 or value.shape[-1] % num_heads:
        raise ValueError("hidden dimension must be divisible by a positive head count")
    return mx.reshape(value, (*value.shape[:-1], num_heads, value.shape[-1] // num_heads))


def _silu(value: mx.array) -> mx.array:
    return value * mx.sigmoid(value)


def _layer_norm(value: mx.array, parameters: LayerNormParameters, *, eps: float = 1e-5) -> mx.array:
    values = value.astype(mx.float32)
    mean = mx.mean(values, axis=-1, keepdims=True)
    centered = values - mean
    variance = mx.mean(mx.square(centered), axis=-1, keepdims=True)
    normalized = centered * mx.rsqrt(variance + eps)
    return normalized * parameters.weight.astype(mx.float32) + parameters.bias.astype(mx.float32)


def sinusoidal_embedding_1d(position: mx.array, dim: int) -> mx.array:
    """Build the pinned Wan cosine-then-sine timestep embedding."""

    if dim <= 0 or dim % 2:
        raise ValueError("sinusoidal embedding dimension must be positive and even")
    if position.ndim == 0:
        position = position[None]
    if position.ndim != 1:
        raise ValueError("timestep position must be a scalar or rank-one array")
    half = dim // 2
    frequencies = mx.exp(-math.log(10000.0) * mx.arange(half, dtype=mx.float32) / float(half))
    phase = position.astype(mx.float32)[:, None] * frequencies[None, :]
    return mx.concatenate([mx.cos(phase), mx.sin(phase)], axis=1)


def wan_patch_embedding(
    latent: mx.array,
    inpaint_condition: mx.array,
    parameters: PatchEmbeddingParameters,
) -> tuple[mx.array, list[tuple[int, int, int]]]:
    """Match the stride-equals-kernel Conv3D patch embedding without layout conversion."""

    if latent.ndim != 5 or inpaint_condition.ndim != 5:
        raise ValueError(
            "latent and inpaint condition must use [batch, channels, frames, height, width]"
        )
    if (
        latent.shape[0] != inpaint_condition.shape[0]
        or latent.shape[2:] != inpaint_condition.shape[2:]
    ):
        raise ValueError("latent and inpaint condition geometry must match")
    weight = parameters.weight
    if weight.ndim != 5:
        raise ValueError("patch embedding weight must use [out, in, time, height, width]")
    patch_size = tuple(int(extent) for extent in weight.shape[2:])
    value = mx.concatenate([latent, inpaint_condition], axis=1)
    if value.shape[1] != weight.shape[1]:
        raise ValueError("concatenated latent channels disagree with patch embedding weight")
    if any(value.shape[index + 2] % extent for index, extent in enumerate(patch_size)):
        raise ValueError("input geometry must be divisible by the patch size")
    batch, channels, frames, height, width = value.shape
    patch_frames, patch_height, patch_width = patch_size
    grid = (frames // patch_frames, height // patch_height, width // patch_width)
    patches = mx.reshape(
        value,
        (
            batch,
            channels,
            grid[0],
            patch_frames,
            grid[1],
            patch_height,
            grid[2],
            patch_width,
        ),
    )
    patches = mx.transpose(patches, (0, 2, 4, 6, 1, 3, 5, 7))
    patches = mx.reshape(patches, (batch, math.prod(grid), -1))
    flattened_weight = mx.reshape(weight, (weight.shape[0], -1))
    return linear(patches, flattened_weight, parameters.bias), [grid] * batch


def wan_transformer_context(
    text_context: mx.array,
    image_context: mx.array,
    parameters: WanTransformerGlobalParameters,
    *,
    text_len: int = 512,
) -> mx.array:
    """Project the timestep-invariant text and image encoder outputs once."""

    if text_context.ndim != 3:
        raise ValueError("text context must use [batch, tokens, features]")
    if text_context.shape[1] > text_len:
        raise ValueError("text context is longer than the configured text length")
    if text_context.shape[1] < text_len:
        text_context = mx.pad(
            text_context,
            [(0, 0), (0, text_len - text_context.shape[1]), (0, 0)],
        )
    text = _project(
        gelu_tanh(_project(text_context, parameters.text_embedding.first)),
        parameters.text_embedding.second,
    )

    if image_context.ndim != 3 or image_context.shape[0] != text_context.shape[0]:
        raise ValueError("image context must use [batch, tokens, features]")
    image = _layer_norm(image_context, parameters.image_embedding.input_norm).astype(
        parameters.image_embedding.input_projection.weight.dtype
    )
    image = _project(image, parameters.image_embedding.input_projection)
    image = 0.5 * image * (1.0 + mx.erf(image / math.sqrt(2.0)))
    image = _project(image, parameters.image_embedding.output_projection)
    image = _layer_norm(image, parameters.image_embedding.output_norm)
    return mx.concatenate([image, text], axis=1)


def wan_transformer_inputs(
    latent: mx.array,
    inpaint_condition: mx.array,
    timestep: mx.array,
    text_context: mx.array,
    image_context: mx.array,
    parameters: WanTransformerGlobalParameters,
    *,
    text_len: int = 512,
    seq_len: int | None = None,
    projected_context: mx.array | None = None,
) -> WanTransformerInputs:
    """Prepare raw latent and encoder outputs for the complete Transformer backbone."""

    hidden, grid_sizes = wan_patch_embedding(latent, inpaint_condition, parameters.patch_embedding)
    sequence_lengths = [math.prod(grid) for grid in grid_sizes]
    padded_length = max(sequence_lengths) if seq_len is None else seq_len
    if padded_length < max(sequence_lengths):
        raise ValueError("seq_len is shorter than the patch sequence")
    if hidden.shape[1] < padded_length:
        hidden = mx.pad(hidden, [(0, 0), (0, padded_length - hidden.shape[1]), (0, 0)])

    time = sinusoidal_embedding_1d(timestep, parameters.time_embedding.first.weight.shape[1])
    time = _project(
        _silu(_project(time, parameters.time_embedding.first)),
        parameters.time_embedding.second,
    )
    modulation = _project(_silu(time), parameters.time_projection)
    modulation = mx.reshape(modulation, (modulation.shape[0], 6, hidden.shape[-1]))
    time = time.astype(hidden.dtype)
    modulation = modulation.astype(hidden.dtype)

    context = (
        wan_transformer_context(text_context, image_context, parameters, text_len=text_len)
        if projected_context is None
        else projected_context
    )
    if context.ndim != 3 or context.shape[0] != hidden.shape[0]:
        raise ValueError("projected context must use [batch, image + text tokens, hidden]")
    return WanTransformerInputs(
        hidden=hidden,
        timestep_embedding=time,
        timestep_modulation=modulation,
        context=context,
        grid_sizes=grid_sizes,
    )


def wan_self_attention(
    x: mx.array,
    parameters: SelfAttentionParameters,
    *,
    num_heads: int,
    grid_sizes: list[tuple[int, int, int]],
    rope_table: RopeTable,
    fast_attention: bool = False,
    fast_norms: bool = False,
    eps: float = 1e-6,
) -> mx.array:
    """Run one upstream-layout Wan self-attention branch."""

    query = _heads(
        _rms_norm(_project(x, parameters.q), parameters.q_norm, eps=eps, fast_norms=fast_norms),
        num_heads,
    )
    key = _heads(
        _rms_norm(_project(x, parameters.k), parameters.k_norm, eps=eps, fast_norms=fast_norms),
        num_heads,
    )
    value = _heads(_project(x, parameters.v), num_heads)
    # Pinned upstream computes complex RoPE in FP32, then casts q/k back to the
    # model dtype immediately before attention.
    query = apply_3d_rope(query, grid_sizes, rope_table).astype(value.dtype)
    key = apply_3d_rope(key, grid_sizes, rope_table).astype(value.dtype)
    attended = scaled_dot_product_attention(query, key, value, fast=fast_attention)
    return _project(mx.flatten(attended, start_axis=2), parameters.output)


def wan_i2v_cross_attention_audio(
    x: mx.array,
    context: mx.array,
    audio_context: mx.array,
    parameters: CrossAttentionParameters,
    *,
    latent_frames: int,
    num_heads: int,
    fast_attention: bool = False,
    fast_norms: bool = False,
    eps: float = 1e-6,
) -> mx.array:
    """Run pinned text, image, and per-latent-frame audio attention branches."""

    return _wan_i2v_cross_attention_audio_trace(
        x,
        context,
        audio_context,
        parameters,
        latent_frames=latent_frames,
        num_heads=num_heads,
        fast_attention=fast_attention,
        fast_norms=fast_norms,
        eps=eps,
    ).output


def _wan_i2v_cross_attention_audio_trace(
    x: mx.array,
    context: mx.array,
    audio_context: mx.array,
    parameters: CrossAttentionParameters,
    *,
    latent_frames: int,
    num_heads: int,
    fast_attention: bool = False,
    fast_norms: bool = False,
    eps: float = 1e-6,
) -> CrossAttentionTrace:

    if context.ndim != 3 or context.shape[0] != x.shape[0] or context.shape[1] < 257:
        raise ValueError("I2V context must contain 257 image tokens followed by text tokens")
    if audio_context.ndim != 4 or audio_context.shape[:2] != (x.shape[0], latent_frames):
        raise ValueError("audio context must have shape [batch, latent_frames, tokens, hidden]")
    if latent_frames <= 0 or x.shape[1] % latent_frames:
        raise ValueError("video sequence must divide evenly across latent frames")

    image_context = context[:, :257]
    text_context = context[:, 257:]
    compute_dtype = x.dtype
    query = _heads(
        _rms_norm(
            _project(x.astype(compute_dtype), parameters.q),
            parameters.q_norm,
            eps=eps,
            fast_norms=fast_norms,
        ),
        num_heads,
    )

    text_key = _heads(
        _rms_norm(
            _project(text_context.astype(compute_dtype), parameters.k),
            parameters.k_norm,
            eps=eps,
            fast_norms=fast_norms,
        ),
        num_heads,
    )
    text_value = _heads(_project(text_context.astype(compute_dtype), parameters.v), num_heads)
    text_output = scaled_dot_product_attention(query, text_key, text_value, fast=fast_attention)

    image_key = _heads(
        _rms_norm(
            _project(image_context.astype(compute_dtype), parameters.k_image),
            parameters.k_image_norm,
            eps=eps,
            fast_norms=fast_norms,
        ),
        num_heads,
    )
    image_value = _heads(
        _project(image_context.astype(compute_dtype), parameters.v_image), num_heads
    )
    image_output = scaled_dot_product_attention(query, image_key, image_value, fast=fast_attention)

    batch, _, audio_tokens, hidden = audio_context.shape
    flattened_audio = mx.reshape(
        audio_context.astype(compute_dtype), (batch * latent_frames, audio_tokens, hidden)
    )
    audio_key = _heads(
        _rms_norm(
            _project(flattened_audio, parameters.k_audio),
            parameters.k_audio_norm,
            eps=eps,
            fast_norms=fast_norms,
        ),
        num_heads,
    )
    audio_value = _heads(_project(flattened_audio, parameters.v_audio), num_heads)
    tokens_per_frame = x.shape[1] // latent_frames
    audio_query = mx.reshape(
        query, (batch * latent_frames, tokens_per_frame, query.shape[2], query.shape[3])
    )
    audio_output = scaled_dot_product_attention(
        audio_query, audio_key, audio_value, fast=fast_attention
    )
    audio_output = mx.reshape(audio_output, query.shape)

    text_image = mx.flatten(text_output + image_output, start_axis=2)
    audio = mx.flatten(audio_output, start_axis=2)
    return CrossAttentionTrace(
        text_image_attention=text_image,
        audio_attention=audio,
        output=_project(text_image + audio, parameters.output),
    )


def wan_attention_block(
    x: mx.array,
    timestep_modulation: mx.array,
    context: mx.array,
    audio_context: mx.array,
    parameters: WanBlockParameters,
    *,
    latent_frames: int,
    num_heads: int,
    grid_sizes: list[tuple[int, int, int]],
    rope_table: RopeTable,
    fast_attention: bool = False,
    fast_norms: bool = False,
    eps: float = 1e-6,
) -> mx.array:
    """Run the pinned AdaLN/self/cross/FFN Wan block in reference order."""

    return wan_attention_block_trace(
        x,
        timestep_modulation,
        context,
        audio_context,
        parameters,
        latent_frames=latent_frames,
        num_heads=num_heads,
        grid_sizes=grid_sizes,
        rope_table=rope_table,
        fast_attention=fast_attention,
        fast_norms=fast_norms,
        eps=eps,
    ).output


def wan_transformer_backbone(
    x: mx.array,
    timestep_modulation: mx.array,
    context: mx.array,
    audio_context: mx.array,
    blocks: tuple[WanBlockParameters, ...],
    *,
    latent_frames: int,
    num_heads: int,
    grid_sizes: list[tuple[int, int, int]],
    rope_table: RopeTable,
    fast_attention: bool = False,
    fast_norms: bool = False,
    evaluation_interval: int = 0,
    eps: float = 1e-6,
) -> mx.array:
    """Run the complete ordered Wan block stack on precomputed conditions."""

    if not blocks:
        raise ValueError("Transformer backbone requires at least one block")
    if evaluation_interval < 0:
        raise ValueError("evaluation interval must be non-negative")
    for block_index, parameters in enumerate(blocks, start=1):
        x = wan_attention_block(
            x,
            timestep_modulation,
            context,
            audio_context,
            parameters,
            latent_frames=latent_frames,
            num_heads=num_heads,
            grid_sizes=grid_sizes,
            rope_table=rope_table,
            fast_attention=fast_attention,
            fast_norms=fast_norms,
            eps=eps,
        )
        if evaluation_interval and block_index % evaluation_interval == 0:
            mx.eval(x)
    return x


def wan_unpatchify(
    patches: mx.array,
    grid_sizes: list[tuple[int, int, int]],
    *,
    patch_size: tuple[int, int, int],
    out_dim: int,
) -> mx.array:
    """Restore upstream `[batch, channels, frames, height, width]` layout."""

    if patches.ndim != 3 or len(grid_sizes) != patches.shape[0]:
        raise ValueError("patches and grid sizes must have matching batch dimensions")
    if any(extent <= 0 for extent in patch_size) or out_dim <= 0:
        raise ValueError("patch and output dimensions must be positive")
    patch_features = math.prod(patch_size) * out_dim
    if patches.shape[-1] != patch_features:
        raise ValueError("patch feature dimension disagrees with patch size and output channels")

    outputs: list[mx.array] = []
    for batch_index, grid_size in enumerate(grid_sizes):
        if any(extent <= 0 for extent in grid_size):
            raise ValueError("grid dimensions must be positive")
        frames, height, width = grid_size
        sequence = math.prod(grid_size)
        if sequence > patches.shape[1]:
            raise ValueError("unpatchify grid contains more tokens than the input sequence")
        value = mx.reshape(
            patches[batch_index, :sequence],
            (frames, height, width, *patch_size, out_dim),
        )
        value = mx.transpose(value, (6, 0, 3, 1, 4, 2, 5))
        outputs.append(
            mx.reshape(
                value,
                (
                    out_dim,
                    frames * patch_size[0],
                    height * patch_size[1],
                    width * patch_size[2],
                ),
            )
        )
    return mx.stack(outputs)


def wan_output_head(
    x: mx.array,
    timestep_embedding: mx.array,
    parameters: OutputHeadParameters,
    *,
    grid_sizes: list[tuple[int, int, int]],
    patch_size: tuple[int, int, int],
    out_dim: int,
    eps: float = 1e-6,
) -> mx.array:
    """Run the pinned adaptive output head and restore the latent-video layout."""

    if timestep_embedding.shape != (x.shape[0], x.shape[-1]):
        raise ValueError("head timestep embedding must have shape [batch, hidden]")
    if parameters.modulation.shape != (1, 2, x.shape[-1]):
        raise ValueError("head modulation must have shape [1, 2, hidden]")
    shift, scale = mx.split(parameters.modulation + timestep_embedding[:, None, :], 2, axis=1)
    patches = _project(wan_layer_norm(x, eps=eps) * (1 + scale) + shift, parameters.projection)
    return wan_unpatchify(
        patches,
        grid_sizes,
        patch_size=patch_size,
        out_dim=out_dim,
    )


def wan_attention_block_trace(
    x: mx.array,
    timestep_modulation: mx.array,
    context: mx.array,
    audio_context: mx.array,
    parameters: WanBlockParameters,
    *,
    latent_frames: int,
    num_heads: int,
    grid_sizes: list[tuple[int, int, int]],
    rope_table: RopeTable,
    fast_attention: bool = False,
    fast_norms: bool = False,
    eps: float = 1e-6,
) -> WanBlockTrace:
    """Run one block and expose exact stage boundaries used by parity fixtures."""

    if parameters.modulation.shape != (1, 6, x.shape[-1]):
        raise ValueError("block modulation must have shape [1, 6, hidden]")
    if timestep_modulation.shape[-2:] != (6, x.shape[-1]):
        raise ValueError("timestep modulation must have shape [batch, 6, hidden]")
    modulation = parameters.modulation + timestep_modulation
    shift_attention, scale_attention, gate_attention, shift_ffn, scale_ffn, gate_ffn = [
        value for value in mx.split(modulation, 6, axis=1)
    ]

    attention_input = (
        _wan_layer_norm(x, eps=eps, fast_norms=fast_norms) * (1 + scale_attention) + shift_attention
    )
    attention_output = wan_self_attention(
        attention_input,
        parameters.self_attention,
        num_heads=num_heads,
        grid_sizes=grid_sizes,
        rope_table=rope_table,
        fast_attention=fast_attention,
        fast_norms=fast_norms,
        eps=eps,
    )
    x = x + attention_output * gate_attention

    cross_input = _wan_layer_norm(
        x,
        parameters.cross_norm_weight,
        parameters.cross_norm_bias,
        eps=eps,
        fast_norms=fast_norms,
    )
    cross_trace = _wan_i2v_cross_attention_audio_trace(
        cross_input,
        context,
        audio_context,
        parameters.cross_attention,
        latent_frames=latent_frames,
        num_heads=num_heads,
        fast_attention=fast_attention,
        fast_norms=fast_norms,
        eps=eps,
    )
    x = x + cross_trace.output

    ffn_input = _wan_layer_norm(x, eps=eps, fast_norms=fast_norms) * (1 + scale_ffn) + shift_ffn
    ffn_output = _project(gelu_tanh(_project(ffn_input, parameters.ffn_in)), parameters.ffn_out)
    output = x + ffn_output * gate_ffn
    return WanBlockTrace(
        norm1=attention_input,
        self_attention=attention_output,
        cross_input=cross_input,
        text_image_attention=cross_trace.text_image_attention,
        audio_attention=cross_trace.audio_attention,
        cross_attention=cross_trace.output,
        ffn_input=ffn_input,
        ffn=ffn_output,
        output=output,
    )
