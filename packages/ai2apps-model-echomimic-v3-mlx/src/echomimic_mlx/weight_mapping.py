"""Explicit checkpoint-name mapping into close-reference MLX parameter objects."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import mlx.core as mx

from .audio_condition import AudioProjectionWeights
from .config import FlashTransformerConfiguration
from .transformer import (
    CrossAttentionParameters,
    ImageEmbeddingParameters,
    LayerNormParameters,
    LinearParameters,
    OutputHeadParameters,
    PatchEmbeddingParameters,
    SelfAttentionParameters,
    TwoLayerMLPParameters,
    WanBlockParameters,
    WanTransformerGlobalParameters,
)


@dataclass(frozen=True, slots=True)
class WanTransformerParameters:
    """Complete pinned Flash Transformer parameters, grouped by execution stage."""

    global_parameters: WanTransformerGlobalParameters
    audio_projection: AudioProjectionWeights
    blocks: tuple[WanBlockParameters, ...]


def _require(tensors: Mapping[str, mx.array], name: str) -> mx.array:
    try:
        return tensors[name]
    except KeyError as error:
        raise KeyError(f"required checkpoint tensor is missing: {name}") from error


def _linear(tensors: Mapping[str, mx.array], prefix: str) -> LinearParameters:
    weight = _require(tensors, f"{prefix}.weight")
    bias = _require(tensors, f"{prefix}.bias")
    if weight.ndim != 2 or bias.shape != (weight.shape[0],):
        raise ValueError(f"invalid Linear parameter schema for {prefix}")
    return LinearParameters(weight=weight, bias=bias)


def _bias(parameters: LinearParameters) -> mx.array:
    if parameters.bias is None:  # Defensive: checkpoint Linear mappings always require bias.
        raise ValueError("checkpoint Linear unexpectedly has no bias")
    return parameters.bias


def block_tensor_names(block_index: int) -> tuple[str, ...]:
    """Return the exact 39 tensors required by one pinned EchoMimicV3 block."""

    if block_index < 0:
        raise ValueError("block index must be non-negative")
    prefix = f"blocks.{block_index}"
    linear_prefixes = (
        "self_attn.q",
        "self_attn.k",
        "self_attn.v",
        "self_attn.o",
        "cross_attn.q",
        "cross_attn.k",
        "cross_attn.v",
        "cross_attn.o",
        "cross_attn.k_img",
        "cross_attn.v_img",
        "cross_attn.q_audio",
        "cross_attn.k_audio",
        "cross_attn.v_audio",
        "ffn.0",
        "ffn.2",
    )
    names = [
        *(f"{prefix}.{item}.{suffix}" for item in linear_prefixes for suffix in ("weight", "bias")),
        f"{prefix}.self_attn.norm_q.weight",
        f"{prefix}.self_attn.norm_k.weight",
        f"{prefix}.cross_attn.norm_q.weight",
        f"{prefix}.cross_attn.norm_k.weight",
        f"{prefix}.cross_attn.norm_k_img.weight",
        f"{prefix}.cross_attn.norm_k_audio.weight",
        f"{prefix}.norm3.weight",
        f"{prefix}.norm3.bias",
        f"{prefix}.modulation",
    ]
    return tuple(sorted(names))


def wan_block_parameters_from_tensors(
    tensors: Mapping[str, mx.array], block_index: int
) -> WanBlockParameters:
    """Validate and map upstream names into one explicit Wan block."""

    prefix = f"blocks.{block_index}"
    modulation = _require(tensors, f"{prefix}.modulation")
    if modulation.ndim != 3 or modulation.shape[:2] != (1, 6):
        raise ValueError("block modulation must have shape [1, 6, dim]")
    dim = modulation.shape[2]

    def norm(name: str) -> mx.array:
        value = _require(tensors, f"{prefix}.{name}.weight")
        if value.shape != (dim,):
            raise ValueError(f"invalid norm parameter schema for {prefix}.{name}")
        return value

    self_attention = SelfAttentionParameters(
        q=_linear(tensors, f"{prefix}.self_attn.q"),
        k=_linear(tensors, f"{prefix}.self_attn.k"),
        v=_linear(tensors, f"{prefix}.self_attn.v"),
        output=_linear(tensors, f"{prefix}.self_attn.o"),
        q_norm=norm("self_attn.norm_q"),
        k_norm=norm("self_attn.norm_k"),
    )
    cross_attention = CrossAttentionParameters(
        q=_linear(tensors, f"{prefix}.cross_attn.q"),
        k=_linear(tensors, f"{prefix}.cross_attn.k"),
        v=_linear(tensors, f"{prefix}.cross_attn.v"),
        output=_linear(tensors, f"{prefix}.cross_attn.o"),
        q_norm=norm("cross_attn.norm_q"),
        k_norm=norm("cross_attn.norm_k"),
        k_image=_linear(tensors, f"{prefix}.cross_attn.k_img"),
        v_image=_linear(tensors, f"{prefix}.cross_attn.v_img"),
        k_image_norm=norm("cross_attn.norm_k_img"),
        k_audio=_linear(tensors, f"{prefix}.cross_attn.k_audio"),
        v_audio=_linear(tensors, f"{prefix}.cross_attn.v_audio"),
        k_audio_norm=norm("cross_attn.norm_k_audio"),
        q_audio=_linear(tensors, f"{prefix}.cross_attn.q_audio"),
    )
    norm3_weight = norm("norm3")
    norm3_bias = _require(tensors, f"{prefix}.norm3.bias")
    if norm3_bias.shape != (dim,):
        raise ValueError(f"invalid norm parameter schema for {prefix}.norm3")
    parameters = WanBlockParameters(
        modulation=modulation,
        self_attention=self_attention,
        cross_attention=cross_attention,
        ffn_in=_linear(tensors, f"{prefix}.ffn.0"),
        ffn_out=_linear(tensors, f"{prefix}.ffn.2"),
        cross_norm_weight=norm3_weight,
        cross_norm_bias=norm3_bias,
    )
    _validate_block_dimensions(parameters, dim)
    return parameters


def _validate_block_dimensions(parameters: WanBlockParameters, dim: int) -> None:
    projections = (
        parameters.self_attention.q,
        parameters.self_attention.k,
        parameters.self_attention.v,
        parameters.self_attention.output,
        parameters.cross_attention.q,
        parameters.cross_attention.k,
        parameters.cross_attention.v,
        parameters.cross_attention.output,
        parameters.cross_attention.k_image,
        parameters.cross_attention.v_image,
        parameters.cross_attention.q_audio,
        parameters.cross_attention.k_audio,
        parameters.cross_attention.v_audio,
    )
    if any(item is None or item.weight.shape != (dim, dim) for item in projections):
        raise ValueError("attention projection dimensions disagree with block hidden dim")
    if parameters.ffn_in.weight.shape[1] != dim:
        raise ValueError("FFN input projection disagrees with block hidden dim")
    if parameters.ffn_out.weight.shape != (dim, parameters.ffn_in.weight.shape[0]):
        raise ValueError("FFN output projection disagrees with FFN input projection")


def audio_projection_tensor_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            f"audio_injection.{layer}.{suffix}"
            for layer in ("proj1", "proj1_vf", "proj2", "proj3", "norm")
            for suffix in ("weight", "bias")
        )
    )


def audio_projection_weights_from_tensors(
    tensors: Mapping[str, mx.array],
) -> AudioProjectionWeights:
    """Validate and map the ten global AudioProjModel tensors."""

    prefix = "audio_injection"
    proj1 = _linear(tensors, f"{prefix}.proj1")
    proj1_vf = _linear(tensors, f"{prefix}.proj1_vf")
    proj2 = _linear(tensors, f"{prefix}.proj2")
    proj3 = _linear(tensors, f"{prefix}.proj3")
    norm_weight = _require(tensors, f"{prefix}.norm.weight")
    norm_bias = _require(tensors, f"{prefix}.norm.bias")
    if proj1.weight.shape[0] != proj1_vf.weight.shape[0]:
        raise ValueError("first-frame and later-frame audio projections must have equal output")
    if proj2.weight.shape != (proj1.weight.shape[0], proj1.weight.shape[0]):
        raise ValueError("audio proj2 dimensions disagree with proj1")
    if proj3.weight.shape[1] != proj2.weight.shape[0]:
        raise ValueError("audio proj3 dimensions disagree with proj2")
    if norm_weight.shape != norm_bias.shape or norm_weight.shape != (proj3.weight.shape[0] // 32,):
        raise ValueError("audio norm dimension disagrees with 32-token proj3 output")
    return AudioProjectionWeights(
        proj1_weight=proj1.weight,
        proj1_bias=_bias(proj1),
        proj1_vf_weight=proj1_vf.weight,
        proj1_vf_bias=_bias(proj1_vf),
        proj2_weight=proj2.weight,
        proj2_bias=_bias(proj2),
        proj3_weight=proj3.weight,
        proj3_bias=_bias(proj3),
        norm_weight=norm_weight,
        norm_bias=norm_bias,
    )


def transformer_global_tensor_names() -> tuple[str, ...]:
    """Return the exact 23 non-block, non-audio tensors in the pinned Transformer."""

    linear_prefixes = (
        "head.head",
        "img_emb.proj.1",
        "img_emb.proj.3",
        "text_embedding.0",
        "text_embedding.2",
        "time_embedding.0",
        "time_embedding.2",
        "time_projection.1",
    )
    names = [
        *(f"{prefix}.{suffix}" for prefix in linear_prefixes for suffix in ("weight", "bias")),
        "head.modulation",
        "img_emb.proj.0.bias",
        "img_emb.proj.0.weight",
        "img_emb.proj.4.bias",
        "img_emb.proj.4.weight",
        "patch_embedding.bias",
        "patch_embedding.weight",
    ]
    return tuple(sorted(names))


def full_transformer_tensor_names(num_layers: int) -> tuple[str, ...]:
    """Return every checkpoint tensor required by the complete Flash Transformer."""

    if num_layers <= 0:
        raise ValueError("Transformer layer count must be positive")
    names = [*transformer_global_tensor_names(), *audio_projection_tensor_names()]
    for block_index in range(num_layers):
        names.extend(block_tensor_names(block_index))
    return tuple(sorted(names))


def _layer_norm(
    tensors: Mapping[str, mx.array], prefix: str, expected_dim: int
) -> LayerNormParameters:
    weight = _require(tensors, f"{prefix}.weight")
    bias = _require(tensors, f"{prefix}.bias")
    if weight.shape != (expected_dim,) or bias.shape != (expected_dim,):
        raise ValueError(f"invalid LayerNorm parameter schema for {prefix}")
    return LayerNormParameters(weight=weight, bias=bias)


def wan_transformer_global_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
    configuration: FlashTransformerConfiguration | None = None,
) -> WanTransformerGlobalParameters:
    """Validate and map only the 23 global Transformer tensors."""

    config = configuration or FlashTransformerConfiguration()
    expected_names = set(transformer_global_tensor_names())
    actual_names = set(tensors)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ValueError(
            f"global Transformer tensor set mismatch: missing={missing}, unexpected={unexpected}"
        )

    dim = config.dim
    patch_weight = _require(tensors, "patch_embedding.weight")
    patch_bias = _require(tensors, "patch_embedding.bias")
    expected_patch = (dim, config.in_dim, *config.patch_size)
    if patch_weight.shape != expected_patch or patch_bias.shape != (dim,):
        raise ValueError("invalid patch embedding parameter schema")

    time_embedding = TwoLayerMLPParameters(
        first=_linear(tensors, "time_embedding.0"),
        second=_linear(tensors, "time_embedding.2"),
    )
    time_projection = _linear(tensors, "time_projection.1")
    text_embedding = TwoLayerMLPParameters(
        first=_linear(tensors, "text_embedding.0"),
        second=_linear(tensors, "text_embedding.2"),
    )
    if (
        time_embedding.first.weight.shape != (dim, config.freq_dim)
        or time_embedding.second.weight.shape != (dim, dim)
        or time_projection.weight.shape != (6 * dim, dim)
        or text_embedding.first.weight.shape != (dim, config.text_dim)
        or text_embedding.second.weight.shape != (dim, dim)
    ):
        raise ValueError("time or text embedding dimensions disagree with pinned config")

    image_input_norm_weight = _require(tensors, "img_emb.proj.0.weight")
    if image_input_norm_weight.ndim != 1:
        raise ValueError("image embedding input LayerNorm weight must be rank one")
    image_dim = image_input_norm_weight.shape[0]
    image_embedding = ImageEmbeddingParameters(
        input_norm=_layer_norm(tensors, "img_emb.proj.0", image_dim),
        input_projection=_linear(tensors, "img_emb.proj.1"),
        output_projection=_linear(tensors, "img_emb.proj.3"),
        output_norm=_layer_norm(tensors, "img_emb.proj.4", dim),
    )
    if image_embedding.input_projection.weight.shape != (
        image_dim,
        image_dim,
    ) or image_embedding.output_projection.weight.shape != (dim, image_dim):
        raise ValueError("image embedding projection dimensions are inconsistent")

    head = OutputHeadParameters(
        modulation=_require(tensors, "head.modulation"),
        projection=_linear(tensors, "head.head"),
    )
    output_features = math.prod(config.patch_size) * config.out_dim
    if head.modulation.shape != (1, 2, dim) or head.projection.weight.shape != (
        output_features,
        dim,
    ):
        raise ValueError("output head dimensions disagree with pinned config")
    return WanTransformerGlobalParameters(
        patch_embedding=PatchEmbeddingParameters(weight=patch_weight, bias=patch_bias),
        time_embedding=time_embedding,
        time_projection=time_projection,
        text_embedding=text_embedding,
        image_embedding=image_embedding,
        output_head=head,
    )


def wan_transformer_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
    configuration: FlashTransformerConfiguration | None = None,
) -> WanTransformerParameters:
    """Validate and map all 1,203 tensors in the pinned 30-block Flash Transformer."""

    config = configuration or FlashTransformerConfiguration()
    expected_names = set(full_transformer_tensor_names(config.num_layers))
    actual_names = set(tensors)
    if actual_names != expected_names:
        missing = sorted(expected_names - actual_names)
        unexpected = sorted(actual_names - expected_names)
        raise ValueError(
            f"complete Transformer tensor set mismatch: missing={missing}, unexpected={unexpected}"
        )

    dim = config.dim
    audio_projection = audio_projection_weights_from_tensors(tensors)
    if audio_projection.norm_weight is None or audio_projection.norm_weight.shape != (dim,):
        raise ValueError("audio projection output dimension disagrees with hidden dim")

    global_parameters = wan_transformer_global_parameters_from_tensors(
        {name: tensors[name] for name in transformer_global_tensor_names()}, config
    )
    blocks = tuple(
        wan_block_parameters_from_tensors(tensors, block_index)
        for block_index in range(config.num_layers)
    )
    return WanTransformerParameters(
        global_parameters=global_parameters,
        audio_projection=audio_projection,
        blocks=blocks,
    )
