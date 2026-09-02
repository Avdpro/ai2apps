"""Native MLX vision path for the pinned OpenCLIP ViT-H/14 encoder."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import mlx.core as mx

from .attention import scaled_dot_product_attention
from .tensor_utils import linear


@dataclass(frozen=True, slots=True)
class WanClipVisionConfiguration:
    image_size: int = 224
    patch_size: int = 14
    dimension: int = 1280
    feed_forward_dimension: int = 5120
    num_heads: int = 16
    checkpoint_layers: int = 32
    output_layers: int = 31
    norm_epsilon: float = 1e-5

    @property
    def sequence_length(self) -> int:
        return 1 + (self.image_size // self.patch_size) ** 2


DEFAULT_WAN_CLIP_VISION_CONFIGURATION = WanClipVisionConfiguration()

_CLIP_MEAN = (0.48145466, 0.4578275, 0.40821073)
_CLIP_STANDARD_DEVIATION = (0.26862954, 0.26130258, 0.27577711)


@dataclass(frozen=True, slots=True)
class ClipLinearParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class ClipLayerNormParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class WanClipVisionBlockParameters:
    norm1: ClipLayerNormParameters
    qkv: ClipLinearParameters
    attention_output: ClipLinearParameters
    norm2: ClipLayerNormParameters
    feed_forward_input: ClipLinearParameters
    feed_forward_output: ClipLinearParameters


@dataclass(frozen=True, slots=True)
class WanClipVisionParameters:
    patch_embedding: mx.array
    class_embedding: mx.array
    position_embedding: mx.array
    pre_norm: ClipLayerNormParameters
    blocks: tuple[WanClipVisionBlockParameters, ...]


def wan_clip_preprocess(image: mx.array, *, output_size: int = 224) -> mx.array:
    """Resize an NHWC image in `[-1,1]` and apply upstream OpenCLIP normalization."""

    if image.ndim != 4 or image.shape[-1] != 3:
        raise ValueError("CLIP source image must have shape [batch, height, width, 3]")
    resized = _pytorch_bicubic_resize(image, output_size, output_size)
    values = resized * 0.5 + 0.5
    mean = mx.array(_CLIP_MEAN, dtype=values.dtype)
    deviation = mx.array(_CLIP_STANDARD_DEVIATION, dtype=values.dtype)
    return (values - mean) / deviation


def _cubic_weights(fraction: mx.array) -> mx.array:
    coefficient = -0.75

    def inner(value: mx.array) -> mx.array:
        return ((coefficient + 2.0) * value - (coefficient + 3.0)) * value**2 + 1.0

    def outer(value: mx.array) -> mx.array:
        return (
            (coefficient * value - 5.0 * coefficient) * value + 8.0 * coefficient
        ) * value - 4.0 * coefficient

    return mx.stack(
        [outer(fraction + 1.0), inner(fraction), inner(1.0 - fraction), outer(2.0 - fraction)],
        axis=1,
    )


def _resize_axis(length: int, output_length: int) -> tuple[mx.array, mx.array]:
    positions = (mx.arange(output_length, dtype=mx.float32) + 0.5) * (length / output_length) - 0.5
    base = mx.floor(positions).astype(mx.int32)
    fraction = positions - base.astype(mx.float32)
    offsets = mx.array([-1, 0, 1, 2], dtype=mx.int32)
    indices = mx.clip(base[:, None] + offsets[None], 0, length - 1)
    return indices, _cubic_weights(fraction)


def _pytorch_bicubic_resize(image: mx.array, height: int, width: int) -> mx.array:
    dtype = image.dtype
    values = image.astype(mx.float32)
    x_indices, x_weights = _resize_axis(image.shape[2], width)
    horizontal = mx.take(values, x_indices, axis=2)
    horizontal = mx.sum(horizontal * x_weights[None, None, :, :, None], axis=3)
    y_indices, y_weights = _resize_axis(image.shape[1], height)
    vertical = mx.take(horizontal, y_indices, axis=1)
    vertical = mx.sum(vertical * y_weights[None, :, :, None, None], axis=2)
    return vertical.astype(dtype)


def wan_clip_vision_tensor_names(
    configuration: WanClipVisionConfiguration = DEFAULT_WAN_CLIP_VISION_CONFIGURATION,
) -> tuple[str, ...]:
    """Return the exact production vision subset, excluding unused text/head tensors."""

    names = [
        "visual.patch_embedding.weight",
        "visual.cls_embedding",
        "visual.pos_embedding",
        "visual.pre_norm.weight",
        "visual.pre_norm.bias",
    ]
    suffixes = (
        "norm1.weight",
        "norm1.bias",
        "attn.to_qkv.weight",
        "attn.to_qkv.bias",
        "attn.proj.weight",
        "attn.proj.bias",
        "norm2.weight",
        "norm2.bias",
        "mlp.0.weight",
        "mlp.0.bias",
        "mlp.2.weight",
        "mlp.2.bias",
    )
    names.extend(
        f"visual.transformer.{layer}.{suffix}"
        for layer in range(configuration.output_layers)
        for suffix in suffixes
    )
    return tuple(sorted(names))


def _require(tensors: Mapping[str, mx.array], name: str) -> mx.array:
    try:
        return tensors[name]
    except KeyError as error:
        raise KeyError(f"required CLIP vision tensor is missing: {name}") from error


def _shape(value: mx.array, expected: tuple[int, ...], name: str) -> mx.array:
    if value.shape != expected:
        raise ValueError(f"CLIP tensor {name} has shape {value.shape}, expected {expected}")
    return value


def _linear_parameters(
    tensors: Mapping[str, mx.array],
    prefix: str,
    shape: tuple[int, int],
) -> ClipLinearParameters:
    return ClipLinearParameters(
        _shape(_require(tensors, f"{prefix}.weight"), shape, f"{prefix}.weight"),
        _shape(_require(tensors, f"{prefix}.bias"), (shape[0],), f"{prefix}.bias"),
    )


def _norm_parameters(
    tensors: Mapping[str, mx.array], prefix: str, dimension: int
) -> ClipLayerNormParameters:
    return ClipLayerNormParameters(
        _shape(_require(tensors, f"{prefix}.weight"), (dimension,), f"{prefix}.weight"),
        _shape(_require(tensors, f"{prefix}.bias"), (dimension,), f"{prefix}.bias"),
    )


def wan_clip_vision_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
    configuration: WanClipVisionConfiguration = DEFAULT_WAN_CLIP_VISION_CONFIGURATION,
) -> WanClipVisionParameters:
    """Strictly validate and map the complete production ViT-H/14 subset."""

    expected = set(wan_clip_vision_tensor_names(configuration))
    actual = set(tensors)
    if actual != expected:
        raise ValueError(
            "CLIP vision tensor set mismatch: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    dimension = configuration.dimension
    feed_forward = configuration.feed_forward_dimension
    blocks = []
    for index in range(configuration.output_layers):
        prefix = f"visual.transformer.{index}"
        blocks.append(
            WanClipVisionBlockParameters(
                norm1=_norm_parameters(tensors, f"{prefix}.norm1", dimension),
                qkv=_linear_parameters(
                    tensors, f"{prefix}.attn.to_qkv", (3 * dimension, dimension)
                ),
                attention_output=_linear_parameters(
                    tensors, f"{prefix}.attn.proj", (dimension, dimension)
                ),
                norm2=_norm_parameters(tensors, f"{prefix}.norm2", dimension),
                feed_forward_input=_linear_parameters(
                    tensors, f"{prefix}.mlp.0", (feed_forward, dimension)
                ),
                feed_forward_output=_linear_parameters(
                    tensors, f"{prefix}.mlp.2", (dimension, feed_forward)
                ),
            )
        )
    return WanClipVisionParameters(
        patch_embedding=_shape(
            _require(tensors, "visual.patch_embedding.weight"),
            (dimension, 3, configuration.patch_size, configuration.patch_size),
            "visual.patch_embedding.weight",
        ),
        class_embedding=_shape(
            _require(tensors, "visual.cls_embedding"), (1, 1, dimension), "class embedding"
        ),
        position_embedding=_shape(
            _require(tensors, "visual.pos_embedding"),
            (1, configuration.sequence_length, dimension),
            "position embedding",
        ),
        pre_norm=_norm_parameters(tensors, "visual.pre_norm", dimension),
        blocks=tuple(blocks),
    )


def _layer_norm(x: mx.array, parameters: ClipLayerNormParameters, epsilon: float) -> mx.array:
    # Upstream's CLIP LayerNorm calls torch.nn.LayerNorm on an FP32 input and only
    # casts the affine result back to the activation dtype. Keep the affine inside
    # the FP32 boundary as well; Wan's custom LayerNorm rounds earlier.
    dtype = x.dtype
    values = x.astype(mx.float32)
    mean = mx.mean(values, axis=-1, keepdims=True)
    centered = values - mean
    variance = mx.mean(mx.square(centered), axis=-1, keepdims=True)
    normalized = centered * mx.rsqrt(variance + epsilon)
    output = normalized * parameters.weight.astype(mx.float32)
    output = output + parameters.bias.astype(mx.float32)
    return output.astype(dtype)


def _linear(x: mx.array, parameters: ClipLinearParameters) -> mx.array:
    return linear(x, parameters.weight, parameters.bias)


def _gelu(x: mx.array) -> mx.array:
    values = x.astype(mx.float32)
    return (values * (1.0 + mx.erf(values / math.sqrt(2.0))) / 2.0).astype(x.dtype)


def wan_clip_vision_block(
    x: mx.array,
    parameters: WanClipVisionBlockParameters,
    configuration: WanClipVisionConfiguration,
    *,
    fast_attention: bool = True,
) -> mx.array:
    """Run one pre-norm OpenCLIP vision Transformer block."""

    batch, sequence, dimension = x.shape
    hidden = _layer_norm(x, parameters.norm1, configuration.norm_epsilon)
    qkv = _linear(hidden, parameters.qkv)
    qkv = mx.reshape(
        qkv,
        (batch, sequence, 3, configuration.num_heads, dimension // configuration.num_heads),
    )
    query, key, value = (mx.squeeze(part, axis=2) for part in mx.split(qkv, 3, axis=2))
    attended = scaled_dot_product_attention(query, key, value, fast=fast_attention)
    attended = mx.reshape(attended, (batch, sequence, dimension))
    x = x + _linear(attended, parameters.attention_output)
    hidden = _layer_norm(x, parameters.norm2, configuration.norm_epsilon)
    hidden = _gelu(_linear(hidden, parameters.feed_forward_input))
    return x + _linear(hidden, parameters.feed_forward_output)


def wan_clip_vision_encode(
    image: mx.array,
    parameters: WanClipVisionParameters,
    configuration: WanClipVisionConfiguration = DEFAULT_WAN_CLIP_VISION_CONFIGURATION,
    *,
    fast_attention: bool = True,
    evaluation_interval: int = 1,
    trace: dict[str, mx.array] | None = None,
) -> mx.array:
    """Encode a normalized NHWC 224x224 image through the first 31 ViT-H blocks."""

    expected = (configuration.image_size, configuration.image_size, 3)
    if image.ndim != 4 or image.shape[1:] != expected:
        raise ValueError(f"CLIP image must have shape [batch, {expected}]")
    weight = mx.transpose(parameters.patch_embedding, (0, 2, 3, 1))
    patches = mx.conv2d(image, weight, stride=configuration.patch_size)
    patches = mx.reshape(patches, (image.shape[0], -1, configuration.dimension))
    class_token = mx.broadcast_to(
        parameters.class_embedding, (image.shape[0], 1, configuration.dimension)
    )
    x = mx.concatenate([class_token, patches], axis=1) + parameters.position_embedding
    x = _layer_norm(x, parameters.pre_norm, configuration.norm_epsilon)
    if trace is not None:
        trace["image.embedding"] = x
    for index, block in enumerate(parameters.blocks):
        x = wan_clip_vision_block(x, block, configuration, fast_attention=fast_attention)
        if trace is not None:
            trace[f"image.blocks.{index}"] = x
        if evaluation_interval and (index + 1) % evaluation_interval == 0:
            mx.eval(x)
    if trace is not None:
        trace["image.output"] = x
    return x
