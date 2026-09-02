"""Native MLX operators for the pinned Wan causal video VAE."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field

import mlx.core as mx

from .attention import scaled_dot_product_attention


@dataclass(frozen=True, slots=True)
class VaeConvParameters:
    """PyTorch-layout Conv3D parameters shaped ``[out, in, time, height, width]``."""

    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class VaeResidualParameters:
    norm1: mx.array
    conv1: VaeConvParameters
    norm2: mx.array
    conv2: VaeConvParameters
    shortcut: VaeConvParameters | None = None


@dataclass(frozen=True, slots=True)
class VaeConv2dParameters:
    weight: mx.array
    bias: mx.array


@dataclass(frozen=True, slots=True)
class VaeAttentionParameters:
    norm: mx.array
    qkv: VaeConv2dParameters
    projection: VaeConv2dParameters


@dataclass(frozen=True, slots=True)
class VaeResampleParameters:
    mode: str
    spatial: VaeConv2dParameters
    temporal: VaeConvParameters | None = None


VaeDecoderLayer = VaeResidualParameters | VaeResampleParameters
VaeEncoderLayer = VaeResidualParameters | VaeResampleParameters


@dataclass(frozen=True, slots=True)
class WanVaeEncoderParameters:
    input_projection: VaeConvParameters
    downsample_layers: tuple[VaeEncoderLayer, ...]
    middle_residual_0: VaeResidualParameters
    middle_attention: VaeAttentionParameters
    middle_residual_1: VaeResidualParameters
    output_norm: mx.array
    output_projection: VaeConvParameters
    distribution_projection: VaeConvParameters


@dataclass(frozen=True, slots=True)
class WanVaeDecoderParameters:
    latent_projection: VaeConvParameters
    input_projection: VaeConvParameters
    middle_residual_0: VaeResidualParameters
    middle_attention: VaeAttentionParameters
    middle_residual_1: VaeResidualParameters
    upsample_layers: tuple[VaeDecoderLayer, ...]
    output_norm: mx.array
    output_projection: VaeConvParameters


@dataclass(slots=True)
class WanVaeDecoderState:
    conv_cache: dict[str, mx.array] = field(default_factory=dict)
    temporal_started: set[str] = field(default_factory=set)


def _require(tensors: Mapping[str, mx.array], name: str) -> mx.array:
    try:
        return tensors[name]
    except KeyError as error:
        raise KeyError(f"required VAE tensor is missing: {name}") from error


def _conv3d_parameters(tensors: Mapping[str, mx.array], prefix: str) -> VaeConvParameters:
    weight = _require(tensors, f"{prefix}.weight")
    bias = _require(tensors, f"{prefix}.bias")
    if weight.ndim != 5 or bias.shape != (weight.shape[0],):
        raise ValueError(f"invalid VAE Conv3D parameters for {prefix}")
    return VaeConvParameters(weight, bias)


def _conv2d_parameters(tensors: Mapping[str, mx.array], prefix: str) -> VaeConv2dParameters:
    weight = _require(tensors, f"{prefix}.weight")
    bias = _require(tensors, f"{prefix}.bias")
    if weight.ndim != 4 or bias.shape != (weight.shape[0],):
        raise ValueError(f"invalid VAE Conv2D parameters for {prefix}")
    return VaeConv2dParameters(weight, bias)


def _residual_parameters(tensors: Mapping[str, mx.array], prefix: str) -> VaeResidualParameters:
    shortcut_name = f"{prefix}.shortcut.weight"
    return VaeResidualParameters(
        norm1=_require(tensors, f"{prefix}.residual.0.gamma"),
        conv1=_conv3d_parameters(tensors, f"{prefix}.residual.2"),
        norm2=_require(tensors, f"{prefix}.residual.3.gamma"),
        conv2=_conv3d_parameters(tensors, f"{prefix}.residual.6"),
        shortcut=(
            _conv3d_parameters(tensors, f"{prefix}.shortcut") if shortcut_name in tensors else None
        ),
    )


def _attention_parameters(tensors: Mapping[str, mx.array], prefix: str) -> VaeAttentionParameters:
    return VaeAttentionParameters(
        norm=_require(tensors, f"{prefix}.norm.gamma"),
        qkv=_conv2d_parameters(tensors, f"{prefix}.to_qkv"),
        projection=_conv2d_parameters(tensors, f"{prefix}.proj"),
    )


def vae_decoder_tensor_names() -> tuple[str, ...]:
    """Return the exact 108 tensors required by the pinned Wan VAE decoder."""

    prefixes_3d = ["conv2", "decoder.conv1", "decoder.head.2"]
    prefixes_2d: list[str] = []
    names = ["decoder.head.0.gamma"]
    residual_indices = (0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14)
    residual_prefixes = [
        "decoder.middle.0",
        "decoder.middle.2",
        *(f"decoder.upsamples.{index}" for index in residual_indices),
    ]
    for prefix in residual_prefixes:
        names.extend((f"{prefix}.residual.0.gamma", f"{prefix}.residual.3.gamma"))
        prefixes_3d.extend((f"{prefix}.residual.2", f"{prefix}.residual.6"))
    prefixes_3d.append("decoder.upsamples.4.shortcut")
    attention_prefix = "decoder.middle.1"
    names.append(f"{attention_prefix}.norm.gamma")
    prefixes_2d.extend((f"{attention_prefix}.to_qkv", f"{attention_prefix}.proj"))
    for index in (3, 7):
        prefixes_2d.append(f"decoder.upsamples.{index}.resample.1")
        prefixes_3d.append(f"decoder.upsamples.{index}.time_conv")
    prefixes_2d.append("decoder.upsamples.11.resample.1")
    names.extend(f"{prefix}.{suffix}" for prefix in prefixes_3d for suffix in ("weight", "bias"))
    names.extend(f"{prefix}.{suffix}" for prefix in prefixes_2d for suffix in ("weight", "bias"))
    return tuple(sorted(names))


def vae_encoder_tensor_names() -> tuple[str, ...]:
    """Return the exact 86 tensors required by the pinned Wan VAE encoder."""

    prefixes_3d = ["encoder.conv1", "encoder.head.2", "conv1"]
    prefixes_2d: list[str] = []
    names = ["encoder.head.0.gamma"]
    residual_indices = (0, 1, 3, 4, 6, 7, 9, 10)
    residual_prefixes = [
        *(f"encoder.downsamples.{index}" for index in residual_indices),
        "encoder.middle.0",
        "encoder.middle.2",
    ]
    for prefix in residual_prefixes:
        names.extend((f"{prefix}.residual.0.gamma", f"{prefix}.residual.3.gamma"))
        prefixes_3d.extend((f"{prefix}.residual.2", f"{prefix}.residual.6"))
    prefixes_3d.extend(("encoder.downsamples.3.shortcut", "encoder.downsamples.6.shortcut"))
    attention_prefix = "encoder.middle.1"
    names.append(f"{attention_prefix}.norm.gamma")
    prefixes_2d.extend((f"{attention_prefix}.to_qkv", f"{attention_prefix}.proj"))
    for index in (2, 5, 8):
        prefixes_2d.append(f"encoder.downsamples.{index}.resample.1")
    for index in (5, 8):
        prefixes_3d.append(f"encoder.downsamples.{index}.time_conv")
    names.extend(f"{prefix}.{suffix}" for prefix in prefixes_3d for suffix in ("weight", "bias"))
    names.extend(f"{prefix}.{suffix}" for prefix in prefixes_2d for suffix in ("weight", "bias"))
    return tuple(sorted(names))


def wan_vae_encoder_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
) -> WanVaeEncoderParameters:
    """Validate and map the complete pinned Wan VAE encoder checkpoint subset."""

    expected = set(vae_encoder_tensor_names())
    actual = set(tensors)
    if actual != expected:
        raise ValueError(
            "VAE encoder tensor set mismatch: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    layers: list[VaeEncoderLayer] = []
    for index in range(11):
        prefix = f"encoder.downsamples.{index}"
        if index in (2, 5, 8):
            layers.append(
                VaeResampleParameters(
                    "downsample3d" if index in (5, 8) else "downsample2d",
                    _conv2d_parameters(tensors, f"{prefix}.resample.1"),
                    _conv3d_parameters(tensors, f"{prefix}.time_conv") if index in (5, 8) else None,
                )
            )
        else:
            layers.append(_residual_parameters(tensors, prefix))
    return WanVaeEncoderParameters(
        input_projection=_conv3d_parameters(tensors, "encoder.conv1"),
        downsample_layers=tuple(layers),
        middle_residual_0=_residual_parameters(tensors, "encoder.middle.0"),
        middle_attention=_attention_parameters(tensors, "encoder.middle.1"),
        middle_residual_1=_residual_parameters(tensors, "encoder.middle.2"),
        output_norm=_require(tensors, "encoder.head.0.gamma"),
        output_projection=_conv3d_parameters(tensors, "encoder.head.2"),
        distribution_projection=_conv3d_parameters(tensors, "conv1"),
    )


def wan_vae_decoder_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
) -> WanVaeDecoderParameters:
    """Validate and map the complete pinned Wan VAE decoder checkpoint subset."""

    expected = set(vae_decoder_tensor_names())
    actual = set(tensors)
    if actual != expected:
        raise ValueError(
            "VAE decoder tensor set mismatch: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    layers: list[VaeDecoderLayer] = []
    for index in range(15):
        prefix = f"decoder.upsamples.{index}"
        if index in (3, 7):
            layers.append(
                VaeResampleParameters(
                    "upsample3d",
                    _conv2d_parameters(tensors, f"{prefix}.resample.1"),
                    _conv3d_parameters(tensors, f"{prefix}.time_conv"),
                )
            )
        elif index == 11:
            layers.append(
                VaeResampleParameters(
                    "upsample2d", _conv2d_parameters(tensors, f"{prefix}.resample.1")
                )
            )
        else:
            layers.append(_residual_parameters(tensors, prefix))
    return WanVaeDecoderParameters(
        latent_projection=_conv3d_parameters(tensors, "conv2"),
        input_projection=_conv3d_parameters(tensors, "decoder.conv1"),
        middle_residual_0=_residual_parameters(tensors, "decoder.middle.0"),
        middle_attention=_attention_parameters(tensors, "decoder.middle.1"),
        middle_residual_1=_residual_parameters(tensors, "decoder.middle.2"),
        upsample_layers=tuple(layers),
        output_norm=_require(tensors, "decoder.head.0.gamma"),
        output_projection=_conv3d_parameters(tensors, "decoder.head.2"),
    )


def vae_rms_norm(x: mx.array, gamma: mx.array, *, eps: float = 1e-12) -> mx.array:
    """Match upstream ``F.normalize(..., dim=1) * sqrt(channels) * gamma``."""

    if x.ndim not in (4, 5):
        raise ValueError("VAE RMS norm expects NCHW or NCTHW input")
    channels = x.shape[1]
    if gamma.size != channels:
        raise ValueError("VAE RMS gamma size must equal the input channel count")
    compute = x.astype(mx.float32)
    norm = mx.sqrt(mx.sum(mx.square(compute), axis=1, keepdims=True))
    normalized = compute / mx.maximum(norm, mx.array(eps, dtype=mx.float32))
    shape = (1, channels, *(1 for _ in range(x.ndim - 2)))
    return (normalized * math.sqrt(channels) * mx.reshape(gamma, shape)).astype(x.dtype)


def causal_conv3d(
    x: mx.array,
    parameters: VaeConvParameters,
    *,
    stride: tuple[int, int, int] = (1, 1, 1),
    padding: tuple[int, int, int] = (0, 0, 0),
    cache: mx.array | None = None,
) -> mx.array:
    """Run upstream left-causal temporal and symmetric spatial Conv3D on NCTHW tensors."""

    if x.ndim != 5 or parameters.weight.ndim != 5:
        raise ValueError("causal Conv3D input and weight must be rank five")
    if x.shape[1] != parameters.weight.shape[1]:
        raise ValueError("causal Conv3D input channels disagree with its weight")
    if parameters.bias.shape != (parameters.weight.shape[0],):
        raise ValueError("causal Conv3D bias shape disagrees with its weight")
    if any(value <= 0 for value in stride) or any(value < 0 for value in padding):
        raise ValueError("causal Conv3D stride and padding are invalid")

    temporal_left = 2 * padding[0]
    if cache is not None:
        if cache.ndim != 5 or cache.shape[:2] != x.shape[:2] or cache.shape[3:] != x.shape[3:]:
            raise ValueError("causal Conv3D cache geometry disagrees with the input")
        x = mx.concatenate([cache.astype(x.dtype), x], axis=2)
        temporal_left -= cache.shape[2]
    if temporal_left < 0:
        raise ValueError("causal Conv3D cache is longer than the temporal padding")
    x = mx.pad(
        x,
        [
            (0, 0),
            (0, 0),
            (temporal_left, 0),
            (padding[1], padding[1]),
            (padding[2], padding[2]),
        ],
    )
    channels_last = mx.transpose(x, (0, 2, 3, 4, 1))
    weight = mx.transpose(parameters.weight, (0, 2, 3, 4, 1))
    output = mx.conv3d(channels_last, weight, stride=stride)
    return mx.transpose(output, (0, 4, 1, 2, 3)) + parameters.bias[None, :, None, None, None]


def vae_residual_block(
    x: mx.array,
    parameters: VaeResidualParameters,
    *,
    eps: float = 1e-12,
) -> mx.array:
    """Run a non-streaming Wan VAE residual block in exact upstream order."""

    shortcut = x if parameters.shortcut is None else causal_conv3d(x, parameters.shortcut)
    hidden = vae_rms_norm(x, parameters.norm1, eps=eps)
    hidden = hidden * mx.sigmoid(hidden)
    hidden = causal_conv3d(hidden, parameters.conv1, padding=(1, 1, 1))
    hidden = vae_rms_norm(hidden, parameters.norm2, eps=eps)
    hidden = hidden * mx.sigmoid(hidden)
    hidden = causal_conv3d(hidden, parameters.conv2, padding=(1, 1, 1))
    return hidden + shortcut


def vae_conv2d(
    x: mx.array,
    parameters: VaeConv2dParameters,
    *,
    stride: tuple[int, int] = (1, 1),
    padding: tuple[int, int] = (0, 0),
) -> mx.array:
    """Run a PyTorch-layout Conv2D over every NCTHW frame."""

    if x.ndim != 5 or parameters.weight.ndim != 4:
        raise ValueError("VAE Conv2D expects NCTHW input and OIHW weight")
    if x.shape[1] != parameters.weight.shape[1]:
        raise ValueError("VAE Conv2D input channels disagree with its weight")
    batch, _, frames, height, width = x.shape
    value = mx.transpose(x, (0, 2, 3, 4, 1))
    value = mx.reshape(value, (batch * frames, height, width, x.shape[1]))
    weight = mx.transpose(parameters.weight, (0, 2, 3, 1))
    output = mx.conv2d(value, weight, stride=stride, padding=padding)
    output = output + parameters.bias[None, None, None, :]
    output = mx.reshape(
        output,
        (batch, frames, output.shape[1], output.shape[2], output.shape[3]),
    )
    return mx.transpose(output, (0, 4, 1, 2, 3))


def vae_upsample2d(x: mx.array, parameters: VaeConv2dParameters) -> mx.array:
    """Match nearest-exact 2x spatial interpolation followed by padded Conv2D."""

    x = mx.repeat(mx.repeat(x.astype(mx.float32), 2, axis=3), 2, axis=4).astype(x.dtype)
    return vae_conv2d(x, parameters, padding=(1, 1))


def vae_downsample2d(x: mx.array, parameters: VaeConv2dParameters) -> mx.array:
    """Match upstream right/bottom zero padding followed by stride-two Conv2D."""

    x = mx.pad(x, [(0, 0), (0, 0), (0, 0), (0, 1), (0, 1)])
    return vae_conv2d(x, parameters, stride=(2, 2))


def vae_attention_block(
    x: mx.array,
    parameters: VaeAttentionParameters,
    *,
    fast_attention: bool = True,
) -> mx.array:
    """Run the upstream per-frame single-head spatial attention block."""

    identity = x
    batch, channels, frames, height, width = x.shape
    hidden = vae_rms_norm(x, parameters.norm)
    qkv = vae_conv2d(hidden, parameters.qkv)
    qkv = mx.transpose(qkv, (0, 2, 3, 4, 1))
    qkv = mx.reshape(qkv, (batch * frames, height * width, 3, channels))
    query, key, value = mx.split(qkv, 3, axis=2)
    attended = scaled_dot_product_attention(query, key, value, fast=fast_attention)
    attended = mx.reshape(attended, (batch, frames, height, width, channels))
    attended = mx.transpose(attended, (0, 4, 1, 2, 3))
    return vae_conv2d(attended, parameters.projection) + identity


def _updated_cache(x: mx.array, previous: mx.array | None) -> mx.array:
    current = x[:, :, -2:]
    if current.shape[2] < 2 and previous is not None:
        current = mx.concatenate([previous[:, :, -1:], current], axis=2)
    return current


def _streaming_conv3d(
    name: str,
    x: mx.array,
    parameters: VaeConvParameters,
    state: WanVaeDecoderState,
    *,
    padding: tuple[int, int, int] = (1, 1, 1),
) -> mx.array:
    previous = state.conv_cache.get(name)
    state.conv_cache[name] = _updated_cache(x, previous)
    return causal_conv3d(x, parameters, padding=padding, cache=previous)


def _streaming_residual(
    name: str,
    x: mx.array,
    parameters: VaeResidualParameters,
    state: WanVaeDecoderState,
) -> mx.array:
    shortcut = x if parameters.shortcut is None else causal_conv3d(x, parameters.shortcut)
    hidden = vae_rms_norm(x, parameters.norm1)
    hidden = hidden * mx.sigmoid(hidden)
    hidden = _streaming_conv3d(f"{name}.conv1", hidden, parameters.conv1, state)
    hidden = vae_rms_norm(hidden, parameters.norm2)
    hidden = hidden * mx.sigmoid(hidden)
    hidden = _streaming_conv3d(f"{name}.conv2", hidden, parameters.conv2, state)
    return hidden + shortcut


def _streaming_resample(
    name: str,
    x: mx.array,
    parameters: VaeResampleParameters,
    state: WanVaeDecoderState,
) -> mx.array:
    if parameters.mode == "upsample3d":
        if parameters.temporal is None:
            raise ValueError("3D VAE upsample is missing its temporal convolution")
        if name not in state.temporal_started:
            state.temporal_started.add(name)
        else:
            previous = state.conv_cache.get(f"{name}.temporal")
            state.conv_cache[f"{name}.temporal"] = _updated_cache(x, previous)
            x = causal_conv3d(
                x,
                parameters.temporal,
                padding=(1, 0, 0),
                cache=previous,
            )
            batch, doubled_channels, frames, height, width = x.shape
            channels = doubled_channels // 2
            x = mx.reshape(x, (batch, 2, channels, frames, height, width))
            x = mx.transpose(x, (0, 2, 3, 1, 4, 5))
            x = mx.reshape(x, (batch, channels, frames * 2, height, width))
    elif parameters.mode != "upsample2d":
        raise ValueError(f"unsupported VAE decoder resample mode: {parameters.mode}")
    return vae_upsample2d(x, parameters.spatial)


def _streaming_downsample(
    name: str,
    x: mx.array,
    parameters: VaeResampleParameters,
    state: WanVaeDecoderState,
) -> mx.array:
    x = vae_downsample2d(x, parameters.spatial)
    if parameters.mode == "downsample2d":
        return x
    if parameters.mode != "downsample3d" or parameters.temporal is None:
        raise ValueError(f"unsupported VAE encoder resample mode: {parameters.mode}")
    cache_name = f"{name}.temporal"
    previous = state.conv_cache.get(cache_name)
    state.conv_cache[cache_name] = x[:, :, -1:]
    if previous is None:
        return x
    return causal_conv3d(
        mx.concatenate([previous[:, :, -1:].astype(x.dtype), x], axis=2),
        parameters.temporal,
        stride=(2, 1, 1),
    )


_VAE_MEAN = (
    -0.7571,
    -0.7089,
    -0.9113,
    0.1075,
    -0.1745,
    0.9653,
    -0.1517,
    1.5508,
    0.4134,
    -0.0715,
    0.5517,
    -0.3632,
    -0.1922,
    -0.9497,
    0.2503,
    -0.2921,
)
_VAE_STD = (
    2.8184,
    1.4541,
    2.3275,
    2.6558,
    1.2196,
    1.7708,
    2.6052,
    2.0743,
    3.2687,
    2.1526,
    2.8652,
    1.5579,
    1.6382,
    1.1253,
    2.8251,
    1.9160,
)


def wan_vae_encode(
    video: mx.array,
    parameters: WanVaeEncoderParameters,
    *,
    fast_attention: bool = True,
    evaluation_interval: int = 1,
    trace: dict[str, mx.array] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> mx.array:
    """Encode an NCTHW video to the pinned Wan diagonal-Gaussian parameters."""

    if video.ndim != 5 or video.shape[1] != 3:
        raise ValueError("Wan VAE video must have shape [batch, 3, frames, height, width]")
    if (video.shape[2] - 1) % 4:
        raise ValueError("Wan VAE video frame count must equal 1 + 4 * n")
    if evaluation_interval < 0:
        raise ValueError("VAE evaluation interval must be non-negative")
    state = WanVaeDecoderState()
    outputs: list[mx.array] = []
    chunk_count = 1 + (video.shape[2] - 1) // 4
    for chunk_index in range(chunk_count):
        if cancel_check is not None:
            cancel_check()
        start = 0 if chunk_index == 0 else 1 + 4 * (chunk_index - 1)
        end = 1 if chunk_index == 0 else min(1 + 4 * chunk_index, video.shape[2])
        hidden = _streaming_conv3d(
            "encoder.input", video[:, :, start:end], parameters.input_projection, state
        )
        for layer_index, layer in enumerate(parameters.downsample_layers):
            name = f"encoder.downsamples.{layer_index}"
            if isinstance(layer, VaeResidualParameters):
                hidden = _streaming_residual(name, hidden, layer, state)
            else:
                hidden = _streaming_downsample(name, hidden, layer, state)
        hidden = _streaming_residual(
            "encoder.middle.0", hidden, parameters.middle_residual_0, state
        )
        hidden = vae_attention_block(
            hidden, parameters.middle_attention, fast_attention=fast_attention
        )
        hidden = _streaming_residual(
            "encoder.middle.2", hidden, parameters.middle_residual_1, state
        )
        hidden = vae_rms_norm(hidden, parameters.output_norm)
        hidden = hidden * mx.sigmoid(hidden)
        hidden = _streaming_conv3d("encoder.output", hidden, parameters.output_projection, state)
        outputs.append(hidden)
        if evaluation_interval and (chunk_index + 1) % evaluation_interval == 0:
            mx.eval(outputs[-1])
    encoded = mx.concatenate(outputs, axis=2)
    distribution = causal_conv3d(encoded, parameters.distribution_projection)
    mean, log_variance = mx.split(distribution, 2, axis=1)
    offset = mx.array(_VAE_MEAN, dtype=mean.dtype)[None, :, None, None, None]
    inverse_scale = (1.0 / mx.array(_VAE_STD, dtype=mean.dtype))[None, :, None, None, None]
    distribution = mx.concatenate([(mean - offset) * inverse_scale, log_variance], axis=1)
    if trace is not None:
        trace["vae.encoder.output"] = encoded
        trace["vae.distribution"] = distribution
    return distribution


def wan_vae_encode_mode(
    video: mx.array,
    parameters: WanVaeEncoderParameters,
    *,
    fast_attention: bool = True,
    evaluation_interval: int = 1,
    trace: dict[str, mx.array] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> mx.array:
    """Encode a video and return the deterministic posterior mode used by inference."""

    return wan_vae_encode(
        video,
        parameters,
        fast_attention=fast_attention,
        evaluation_interval=evaluation_interval,
        trace=trace,
        cancel_check=cancel_check,
    )[:, :16]


def wan_vae_decode_chunks(
    latent: mx.array,
    parameters: WanVaeDecoderParameters,
    *,
    fast_attention: bool = True,
    evaluation_interval: int = 0,
    trace: dict[str, mx.array] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> Iterator[mx.array]:
    """Yield decoded NCTHW chunks from the pinned frame-streaming Wan VAE path."""

    if latent.ndim != 5 or latent.shape[1] != 16:
        raise ValueError("Wan VAE latent must have shape [batch, 16, frames, height, width]")
    if evaluation_interval < 0:
        raise ValueError("VAE evaluation interval must be non-negative")
    mean = mx.array(_VAE_MEAN, dtype=latent.dtype)[None, :, None, None, None]
    std = mx.array(_VAE_STD, dtype=latent.dtype)[None, :, None, None, None]
    latent = latent * std + mean
    if trace is not None:
        trace["vae.scaled_latent"] = latent
    latent = causal_conv3d(latent, parameters.latent_projection)
    if trace is not None:
        trace["vae.conv2"] = latent
    state = WanVaeDecoderState()
    for frame_index in range(latent.shape[2]):
        if cancel_check is not None:
            cancel_check()
        hidden = _streaming_conv3d(
            "decoder.input",
            latent[:, :, frame_index : frame_index + 1],
            parameters.input_projection,
            state,
        )
        if trace is not None and frame_index == 0:
            trace["vae.decoder.conv1"] = hidden
        hidden = _streaming_residual(
            "decoder.middle.0", hidden, parameters.middle_residual_0, state
        )
        if trace is not None and frame_index == 0:
            trace["vae.decoder.middle.residual_0"] = hidden
        hidden = vae_attention_block(
            hidden, parameters.middle_attention, fast_attention=fast_attention
        )
        if trace is not None and frame_index == 0:
            trace["vae.decoder.middle.attention"] = hidden
        hidden = _streaming_residual(
            "decoder.middle.2", hidden, parameters.middle_residual_1, state
        )
        if trace is not None and frame_index == 0:
            trace["vae.decoder.middle.residual_1"] = hidden
        for layer_index, layer in enumerate(parameters.upsample_layers):
            name = f"decoder.upsamples.{layer_index}"
            if isinstance(layer, VaeResidualParameters):
                hidden = _streaming_residual(name, hidden, layer, state)
            else:
                hidden = _streaming_resample(name, hidden, layer, state)
            if trace is not None and frame_index == 0 and layer_index in (3, 7, 11):
                trace_name = {
                    3: "vae.decoder.upsample_3d_0",
                    7: "vae.decoder.upsample_3d_1",
                    11: "vae.decoder.upsample_2d",
                }[layer_index]
                trace[trace_name] = hidden
        hidden = vae_rms_norm(hidden, parameters.output_norm)
        hidden = hidden * mx.sigmoid(hidden)
        hidden = _streaming_conv3d("decoder.output", hidden, parameters.output_projection, state)
        output = mx.clip(hidden, -1.0, 1.0)
        if evaluation_interval and (frame_index + 1) % evaluation_interval == 0:
            mx.eval(output)
        yield output


def wan_vae_decode(
    latent: mx.array,
    parameters: WanVaeDecoderParameters,
    *,
    fast_attention: bool = True,
    evaluation_interval: int = 0,
    trace: dict[str, mx.array] | None = None,
    cancel_check: Callable[[], None] | None = None,
) -> mx.array:
    """Decode an NCTHW latent and concatenate all streaming output chunks."""

    outputs = list(
        wan_vae_decode_chunks(
            latent,
            parameters,
            fast_attention=fast_attention,
            evaluation_interval=evaluation_interval,
            trace=trace,
            cancel_check=cancel_check,
        )
    )
    output = mx.concatenate(outputs, axis=2)
    if trace is not None:
        trace["vae.output"] = output
    return output
