"""Native MLX Chinese Wav2Vec2 encoder used by EchoMimicV3."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import mlx.core as mx

from .attention import scaled_dot_product_attention
from .tensor_utils import linear


@dataclass(frozen=True, slots=True)
class Wav2Vec2Configuration:
    convolution_dimensions: tuple[int, ...] = (512, 512, 512, 512, 512, 512, 512)
    convolution_kernels: tuple[int, ...] = (10, 3, 3, 3, 3, 2, 2)
    convolution_strides: tuple[int, ...] = (5, 2, 2, 2, 2, 2, 2)
    hidden_dimension: int = 768
    feed_forward_dimension: int = 3072
    num_heads: int = 12
    num_layers: int = 12
    position_kernel: int = 128
    position_groups: int = 16
    norm_epsilon: float = 1e-5


DEFAULT_WAV2VEC2_CONFIGURATION = Wav2Vec2Configuration()


@dataclass(frozen=True, slots=True)
class AudioLinearParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class AudioNormParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class Wav2Vec2LayerParameters:
    query: AudioLinearParameters
    key: AudioLinearParameters
    value: AudioLinearParameters
    attention_output: AudioLinearParameters
    attention_norm: AudioNormParameters
    feed_forward_input: AudioLinearParameters
    feed_forward_output: AudioLinearParameters
    final_norm: AudioNormParameters


@dataclass(frozen=True, slots=True)
class Wav2Vec2Parameters:
    convolution_weights: tuple[mx.array, ...]
    first_convolution_norm: AudioNormParameters
    feature_norm: AudioNormParameters
    feature_projection: AudioLinearParameters
    position_weight_g: mx.array
    position_weight_v: mx.array
    position_bias: mx.array
    encoder_norm: AudioNormParameters
    layers: tuple[Wav2Vec2LayerParameters, ...]


def wav2vec2_tensor_names(
    configuration: Wav2Vec2Configuration = DEFAULT_WAV2VEC2_CONFIGURATION,
) -> tuple[str, ...]:
    """Return the exact inference subset, excluding unused pretraining/mask tensors."""

    names = [
        *(f"wav2vec2.feature_extractor.conv_layers.{index}.conv.weight" for index in range(7)),
        "wav2vec2.feature_extractor.conv_layers.0.layer_norm.weight",
        "wav2vec2.feature_extractor.conv_layers.0.layer_norm.bias",
        "wav2vec2.feature_projection.layer_norm.weight",
        "wav2vec2.feature_projection.layer_norm.bias",
        "wav2vec2.feature_projection.projection.weight",
        "wav2vec2.feature_projection.projection.bias",
        "wav2vec2.encoder.pos_conv_embed.conv.weight_g",
        "wav2vec2.encoder.pos_conv_embed.conv.weight_v",
        "wav2vec2.encoder.pos_conv_embed.conv.bias",
        "wav2vec2.encoder.layer_norm.weight",
        "wav2vec2.encoder.layer_norm.bias",
    ]
    suffixes = (
        "attention.q_proj.weight",
        "attention.q_proj.bias",
        "attention.k_proj.weight",
        "attention.k_proj.bias",
        "attention.v_proj.weight",
        "attention.v_proj.bias",
        "attention.out_proj.weight",
        "attention.out_proj.bias",
        "layer_norm.weight",
        "layer_norm.bias",
        "feed_forward.intermediate_dense.weight",
        "feed_forward.intermediate_dense.bias",
        "feed_forward.output_dense.weight",
        "feed_forward.output_dense.bias",
        "final_layer_norm.weight",
        "final_layer_norm.bias",
    )
    names.extend(
        f"wav2vec2.encoder.layers.{layer}.{suffix}"
        for layer in range(configuration.num_layers)
        for suffix in suffixes
    )
    return tuple(sorted(names))


def _require(tensors: Mapping[str, mx.array], name: str) -> mx.array:
    try:
        return tensors[name]
    except KeyError as error:
        raise KeyError(f"required Wav2Vec2 tensor is missing: {name}") from error


def _shape(value: mx.array, expected: tuple[int, ...], name: str) -> mx.array:
    if value.shape != expected:
        raise ValueError(f"Wav2Vec2 tensor {name} has shape {value.shape}, expected {expected}")
    return value


def _norm(tensors: Mapping[str, mx.array], prefix: str, dimension: int) -> AudioNormParameters:
    return AudioNormParameters(
        _shape(_require(tensors, f"{prefix}.weight"), (dimension,), f"{prefix}.weight"),
        _shape(_require(tensors, f"{prefix}.bias"), (dimension,), f"{prefix}.bias"),
    )


def _linear_parameters(
    tensors: Mapping[str, mx.array], prefix: str, output: int, input_: int
) -> AudioLinearParameters:
    return AudioLinearParameters(
        _shape(_require(tensors, f"{prefix}.weight"), (output, input_), f"{prefix}.weight"),
        _shape(_require(tensors, f"{prefix}.bias"), (output,), f"{prefix}.bias"),
    )


def wav2vec2_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
    configuration: Wav2Vec2Configuration = DEFAULT_WAV2VEC2_CONFIGURATION,
) -> Wav2Vec2Parameters:
    """Strictly validate and map the complete production Wav2Vec2 inference subset."""

    expected = set(wav2vec2_tensor_names(configuration))
    actual = set(tensors)
    if actual != expected:
        raise ValueError(
            "Wav2Vec2 tensor set mismatch: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    convolution_weights = []
    input_channels = 1
    for index, (output_channels, kernel) in enumerate(
        zip(configuration.convolution_dimensions, configuration.convolution_kernels, strict=True)
    ):
        name = f"wav2vec2.feature_extractor.conv_layers.{index}.conv.weight"
        convolution_weights.append(
            _shape(_require(tensors, name), (output_channels, input_channels, kernel), name)
        )
        input_channels = output_channels
    hidden = configuration.hidden_dimension
    layers = []
    for index in range(configuration.num_layers):
        prefix = f"wav2vec2.encoder.layers.{index}"
        layers.append(
            Wav2Vec2LayerParameters(
                query=_linear_parameters(tensors, f"{prefix}.attention.q_proj", hidden, hidden),
                key=_linear_parameters(tensors, f"{prefix}.attention.k_proj", hidden, hidden),
                value=_linear_parameters(tensors, f"{prefix}.attention.v_proj", hidden, hidden),
                attention_output=_linear_parameters(
                    tensors, f"{prefix}.attention.out_proj", hidden, hidden
                ),
                attention_norm=_norm(tensors, f"{prefix}.layer_norm", hidden),
                feed_forward_input=_linear_parameters(
                    tensors,
                    f"{prefix}.feed_forward.intermediate_dense",
                    configuration.feed_forward_dimension,
                    hidden,
                ),
                feed_forward_output=_linear_parameters(
                    tensors,
                    f"{prefix}.feed_forward.output_dense",
                    hidden,
                    configuration.feed_forward_dimension,
                ),
                final_norm=_norm(tensors, f"{prefix}.final_layer_norm", hidden),
            )
        )
    return Wav2Vec2Parameters(
        convolution_weights=tuple(convolution_weights),
        first_convolution_norm=_norm(
            tensors, "wav2vec2.feature_extractor.conv_layers.0.layer_norm", 512
        ),
        feature_norm=_norm(tensors, "wav2vec2.feature_projection.layer_norm", 512),
        feature_projection=_linear_parameters(
            tensors, "wav2vec2.feature_projection.projection", hidden, 512
        ),
        position_weight_g=_shape(
            _require(tensors, "wav2vec2.encoder.pos_conv_embed.conv.weight_g"),
            (1, 1, configuration.position_kernel),
            "position weight_g",
        ),
        position_weight_v=_shape(
            _require(tensors, "wav2vec2.encoder.pos_conv_embed.conv.weight_v"),
            (
                hidden,
                hidden // configuration.position_groups,
                configuration.position_kernel,
            ),
            "position weight_v",
        ),
        position_bias=_shape(
            _require(tensors, "wav2vec2.encoder.pos_conv_embed.conv.bias"),
            (hidden,),
            "position bias",
        ),
        encoder_norm=_norm(tensors, "wav2vec2.encoder.layer_norm", hidden),
        layers=tuple(layers),
    )


def _layer_norm(x: mx.array, parameters: AudioNormParameters, epsilon: float) -> mx.array:
    mean = mx.mean(x, axis=-1, keepdims=True)
    centered = x - mean
    variance = mx.mean(mx.square(centered), axis=-1, keepdims=True)
    return centered * mx.rsqrt(variance + epsilon) * parameters.weight + parameters.bias


def _gelu(x: mx.array) -> mx.array:
    return x * (1.0 + mx.erf(x / math.sqrt(2.0))) / 2.0


def _linear_interpolation(x: mx.array, output_length: int) -> mx.array:
    if output_length <= 0:
        raise ValueError("Wav2Vec2 output length must be positive")
    input_length = x.shape[1]
    if output_length == 1:
        return x[:, :1]
    positions = mx.arange(output_length, dtype=mx.float32)
    positions = positions * ((input_length - 1) / (output_length - 1))
    lower = mx.floor(positions).astype(mx.int32)
    upper = mx.minimum(lower + 1, input_length - 1)
    fraction = positions - lower.astype(mx.float32)
    return x[:, lower] * (1.0 - fraction[None, :, None]) + x[:, upper] * fraction[None, :, None]


def _extract_features(
    waveform: mx.array,
    parameters: Wav2Vec2Parameters,
    configuration: Wav2Vec2Configuration,
) -> mx.array:
    x = waveform[:, :, None]
    for index, (source_weight, stride) in enumerate(
        zip(parameters.convolution_weights, configuration.convolution_strides, strict=True)
    ):
        weight = mx.transpose(source_weight, (0, 2, 1))
        x = mx.conv1d(x, weight, stride=stride)
        if index == 0:
            mean = mx.mean(x, axis=1, keepdims=True)
            centered = x - mean
            variance = mx.mean(mx.square(centered), axis=1, keepdims=True)
            x = centered * mx.rsqrt(variance + configuration.norm_epsilon)
            x = x * parameters.first_convolution_norm.weight
            x = x + parameters.first_convolution_norm.bias
        x = _gelu(x)
    return x


def _position_embedding(
    x: mx.array,
    parameters: Wav2Vec2Parameters,
    configuration: Wav2Vec2Configuration,
) -> mx.array:
    value = parameters.position_weight_v
    norm = mx.sqrt(mx.sum(mx.square(value), axis=(0, 1), keepdims=True))
    source_weight = value * (parameters.position_weight_g / norm)
    weight = mx.transpose(source_weight, (0, 2, 1))
    padded = mx.pad(x, [(0, 0), (configuration.position_kernel // 2,) * 2, (0, 0)])
    output = mx.conv1d(padded, weight, groups=configuration.position_groups)
    output = output + parameters.position_bias
    return _gelu(output[:, :-1])


def _encoder_layer(
    x: mx.array,
    parameters: Wav2Vec2LayerParameters,
    configuration: Wav2Vec2Configuration,
    *,
    fast_attention: bool,
) -> mx.array:
    batch, sequence, hidden = x.shape
    head_dimension = hidden // configuration.num_heads
    query = linear(x, parameters.query.weight, parameters.query.bias)
    key = linear(x, parameters.key.weight, parameters.key.bias)
    value = linear(x, parameters.value.weight, parameters.value.bias)
    query = mx.reshape(query, (batch, sequence, configuration.num_heads, head_dimension))
    key = mx.reshape(key, (batch, sequence, configuration.num_heads, head_dimension))
    value = mx.reshape(value, (batch, sequence, configuration.num_heads, head_dimension))
    attended = scaled_dot_product_attention(query, key, value, fast=fast_attention)
    attended = mx.reshape(attended, (batch, sequence, hidden))
    attended = linear(
        attended, parameters.attention_output.weight, parameters.attention_output.bias
    )
    x = _layer_norm(x + attended, parameters.attention_norm, configuration.norm_epsilon)
    hidden_states = linear(
        x, parameters.feed_forward_input.weight, parameters.feed_forward_input.bias
    )
    hidden_states = _gelu(hidden_states)
    hidden_states = linear(
        hidden_states,
        parameters.feed_forward_output.weight,
        parameters.feed_forward_output.bias,
    )
    return _layer_norm(x + hidden_states, parameters.final_norm, configuration.norm_epsilon)


def wav2vec2_encode(
    waveform: mx.array,
    parameters: Wav2Vec2Parameters,
    *,
    output_length: int,
    configuration: Wav2Vec2Configuration = DEFAULT_WAV2VEC2_CONFIGURATION,
    fast_attention: bool = True,
    trace: dict[str, mx.array] | None = None,
) -> tuple[mx.array, ...]:
    """Encode a mono waveform and return the 12 production Transformer hidden states."""

    if waveform.ndim != 2:
        raise ValueError("Wav2Vec2 waveform must have shape [batch, samples]")
    convolution = _extract_features(waveform, parameters, configuration)
    interpolated = _linear_interpolation(convolution, output_length)
    normalized = _layer_norm(interpolated, parameters.feature_norm, configuration.norm_epsilon)
    x = linear(normalized, parameters.feature_projection.weight, parameters.feature_projection.bias)
    if trace is not None:
        trace["audio.convolution"] = convolution
        trace["audio.interpolated"] = interpolated
        trace["audio.projection"] = x
    x = _layer_norm(
        x + _position_embedding(x, parameters, configuration),
        parameters.encoder_norm,
        configuration.norm_epsilon,
    )
    if trace is not None:
        trace["audio.hidden_states.0"] = x
    outputs = []
    for index, layer in enumerate(parameters.layers):
        x = _encoder_layer(x, layer, configuration, fast_attention=fast_attention)
        outputs.append(x)
        if trace is not None:
            trace[f"audio.hidden_states.{index + 1}"] = x
    return tuple(outputs)


def wav2vec2_window_hidden_states(hidden_states: tuple[mx.array, ...]) -> mx.array:
    """Stack the 12 layer outputs and create upstream's clamped five-frame windows."""

    if len(hidden_states) != 12:
        raise ValueError("Wav2Vec2 windowing requires exactly 12 hidden states")
    stacked = mx.stack(list(hidden_states), axis=2)
    length = stacked.shape[1]
    indices = mx.arange(length)[:, None] + mx.arange(-2, 3)[None, :]
    indices = mx.clip(indices, 0, length - 1)
    return stacked[:, indices]


def split_wav2vec2_windows(windowed: mx.array) -> tuple[mx.array, mx.array]:
    """Match upstream's first-frame and four-frame VAE audio grouping."""

    if windowed.ndim != 5 or windowed.shape[1] < 5 or (windowed.shape[1] - 1) % 4:
        raise ValueError("audio windows must have shape [batch, 1 + 4*n, 5, 12, hidden]")
    batch, length, _, layers, hidden = windowed.shape
    first = windowed[:, :1]
    later = mx.reshape(windowed[:, 1:], (batch, (length - 1) // 4, 4, 5, layers, hidden))
    first_slice = mx.reshape(later[:, :, :1, :3], (batch, -1, 3, layers, hidden))
    middle_slice = mx.reshape(later[:, :, 1:-1, 2:3], (batch, -1, 2, layers, hidden))
    last_slice = mx.reshape(later[:, :, -1:, 2:], (batch, -1, 3, layers, hidden))
    return first, mx.concatenate([first_slice, middle_slice, last_slice], axis=2)
