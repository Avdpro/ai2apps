"""Native MLX implementation of the pinned Wan UMT5-XXL text encoder."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import mlx.core as mx


@dataclass(frozen=True, slots=True)
class WanT5Configuration:
    vocab_size: int = 256384
    dimension: int = 4096
    attention_dimension: int = 4096
    feed_forward_dimension: int = 10240
    num_heads: int = 64
    num_layers: int = 24
    num_buckets: int = 32
    max_distance: int = 128
    norm_epsilon: float = 1e-6

    @property
    def head_dimension(self) -> int:
        if self.attention_dimension % self.num_heads:
            raise ValueError("T5 attention dimension must be divisible by its head count")
        return self.attention_dimension // self.num_heads


DEFAULT_WAN_T5_CONFIGURATION = WanT5Configuration()


@dataclass(frozen=True, slots=True)
class WanT5BlockParameters:
    norm1: mx.array
    query: mx.array
    key: mx.array
    value: mx.array
    attention_output: mx.array
    norm2: mx.array
    gate: mx.array
    feed_forward_input: mx.array
    feed_forward_output: mx.array
    position_embedding: mx.array


@dataclass(frozen=True, slots=True)
class WanT5EncoderParameters:
    token_embedding: mx.array
    blocks: tuple[WanT5BlockParameters, ...]
    output_norm: mx.array


def load_wan_t5_tokenizer(path: Path) -> Any:
    """Load the pinned fast UMT5 tokenizer without Transformers or PyTorch."""

    try:
        from tokenizers import Tokenizer  # type: ignore[import-untyped]
    except ImportError as error:
        raise RuntimeError("install the tokenizers runtime dependency") from error
    tokenizer_file = path.expanduser().resolve()
    if tokenizer_file.is_dir():
        tokenizer_file = tokenizer_file / "tokenizer.json"
    if not tokenizer_file.is_file():
        raise FileNotFoundError(f"UMT5 tokenizer does not exist: {tokenizer_file}")
    return Tokenizer.from_file(str(tokenizer_file))


def wan_t5_tokenize(
    prompts: list[str],
    tokenizer: Any,
    *,
    max_length: int = 512,
) -> tuple[mx.array, mx.array]:
    """Match production AutoTokenizer max-length padding and truncation."""

    if not prompts or not all(isinstance(prompt, str) for prompt in prompts):
        raise ValueError("T5 prompts must be a non-empty string list")
    if max_length <= 0:
        raise ValueError("T5 maximum token length must be positive")
    tokenizer.enable_truncation(max_length=max_length)
    tokenizer.enable_padding(length=max_length, pad_id=0, pad_token="<pad>")
    encodings = tokenizer.encode_batch(prompts, add_special_tokens=True)
    input_ids = mx.array([encoding.ids for encoding in encodings], dtype=mx.int32)
    attention_mask = mx.array([encoding.attention_mask for encoding in encodings], dtype=mx.int32)
    return input_ids, attention_mask


def wan_t5_tensor_names(
    configuration: WanT5Configuration = DEFAULT_WAN_T5_CONFIGURATION,
) -> tuple[str, ...]:
    """Return the exact 242 tensors required by the pinned UMT5-XXL encoder."""

    names = ["token_embedding.weight", "norm.weight"]
    suffixes = (
        "attn.k.weight",
        "attn.o.weight",
        "attn.q.weight",
        "attn.v.weight",
        "ffn.fc1.weight",
        "ffn.fc2.weight",
        "ffn.gate.0.weight",
        "norm1.weight",
        "norm2.weight",
        "pos_embedding.embedding.weight",
    )
    names.extend(
        f"blocks.{layer}.{suffix}"
        for layer in range(configuration.num_layers)
        for suffix in suffixes
    )
    return tuple(sorted(names))


def _require(tensors: Mapping[str, mx.array], name: str) -> mx.array:
    try:
        return tensors[name]
    except KeyError as error:
        raise KeyError(f"required T5 tensor is missing: {name}") from error


def _validate_shape(value: mx.array, expected: tuple[int, ...], name: str) -> mx.array:
    if value.shape != expected:
        raise ValueError(f"T5 tensor {name} has shape {value.shape}, expected {expected}")
    return value


def wan_t5_parameters_from_tensors(
    tensors: Mapping[str, mx.array],
    configuration: WanT5Configuration = DEFAULT_WAN_T5_CONFIGURATION,
) -> WanT5EncoderParameters:
    """Strictly validate and map a complete pinned Wan UMT5 checkpoint."""

    expected = set(wan_t5_tensor_names(configuration))
    actual = set(tensors)
    if actual != expected:
        raise ValueError(
            "T5 tensor set mismatch: "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    dimension = configuration.dimension
    attention = configuration.attention_dimension
    feed_forward = configuration.feed_forward_dimension
    blocks = []
    for index in range(configuration.num_layers):
        prefix = f"blocks.{index}"
        blocks.append(
            WanT5BlockParameters(
                norm1=_validate_shape(
                    _require(tensors, f"{prefix}.norm1.weight"), (dimension,), "norm1"
                ),
                query=_validate_shape(
                    _require(tensors, f"{prefix}.attn.q.weight"), (attention, dimension), "query"
                ),
                key=_validate_shape(
                    _require(tensors, f"{prefix}.attn.k.weight"), (attention, dimension), "key"
                ),
                value=_validate_shape(
                    _require(tensors, f"{prefix}.attn.v.weight"), (attention, dimension), "value"
                ),
                attention_output=_validate_shape(
                    _require(tensors, f"{prefix}.attn.o.weight"),
                    (dimension, attention),
                    "attention output",
                ),
                norm2=_validate_shape(
                    _require(tensors, f"{prefix}.norm2.weight"), (dimension,), "norm2"
                ),
                gate=_validate_shape(
                    _require(tensors, f"{prefix}.ffn.gate.0.weight"),
                    (feed_forward, dimension),
                    "feed-forward gate",
                ),
                feed_forward_input=_validate_shape(
                    _require(tensors, f"{prefix}.ffn.fc1.weight"),
                    (feed_forward, dimension),
                    "feed-forward input",
                ),
                feed_forward_output=_validate_shape(
                    _require(tensors, f"{prefix}.ffn.fc2.weight"),
                    (dimension, feed_forward),
                    "feed-forward output",
                ),
                position_embedding=_validate_shape(
                    _require(tensors, f"{prefix}.pos_embedding.embedding.weight"),
                    (configuration.num_buckets, configuration.num_heads),
                    "position embedding",
                ),
            )
        )
    return WanT5EncoderParameters(
        token_embedding=_validate_shape(
            _require(tensors, "token_embedding.weight"),
            (configuration.vocab_size, dimension),
            "token embedding",
        ),
        blocks=tuple(blocks),
        output_norm=_validate_shape(_require(tensors, "norm.weight"), (dimension,), "output norm"),
    )


def t5_rms_norm(x: mx.array, weight: mx.array, *, epsilon: float = 1e-6) -> mx.array:
    """Match upstream T5LayerNorm's FP32 variance and parameter-dtype output."""

    variance = mx.mean(mx.square(x.astype(mx.float32)), axis=-1, keepdims=True)
    normalized = x.astype(mx.float32) * mx.rsqrt(variance + epsilon)
    return normalized.astype(weight.dtype) * weight


def relative_position_buckets(
    query_length: int,
    key_length: int,
    *,
    num_buckets: int,
    max_distance: int,
    bidirectional: bool = True,
) -> mx.array:
    """Compute upstream T5 relative-position bucket indices."""

    if query_length <= 0 or key_length <= 0 or num_buckets <= 0:
        raise ValueError("T5 relative-position dimensions must be positive")
    relative = mx.arange(key_length)[None, :] - mx.arange(query_length)[:, None]
    if bidirectional:
        half = num_buckets // 2
        buckets = (relative > 0).astype(mx.int32) * half
        distance = mx.abs(relative)
        available = half
    else:
        buckets = mx.zeros_like(relative)
        distance = -mx.minimum(relative, mx.zeros_like(relative))
        available = num_buckets
    exact = available // 2
    safe_distance = mx.maximum(distance, exact)
    large = exact + mx.floor(
        mx.log(safe_distance.astype(mx.float32) / exact)
        / math.log(max_distance / exact)
        * (available - exact)
    ).astype(mx.int32)
    large = mx.minimum(large, available - 1)
    return buckets + mx.where(distance < exact, distance, large)


def _linear(x: mx.array, weight: mx.array) -> mx.array:
    return mx.matmul(x, mx.transpose(weight))


def _gelu_tanh(x: mx.array) -> mx.array:
    return 0.5 * x * (1.0 + mx.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * mx.power(x, 3.0))))


def wan_t5_block(
    x: mx.array,
    attention_mask: mx.array | None,
    parameters: WanT5BlockParameters,
    configuration: WanT5Configuration,
    *,
    fast_attention: bool = False,
) -> mx.array:
    """Run one bidirectional Wan UMT5 encoder block."""

    batch, length, _ = x.shape
    hidden = t5_rms_norm(x, parameters.norm1, epsilon=configuration.norm_epsilon)
    shape = (batch, length, configuration.num_heads, configuration.head_dimension)
    query = mx.reshape(_linear(hidden, parameters.query), shape)
    key = mx.reshape(_linear(hidden, parameters.key), shape)
    value = mx.reshape(_linear(hidden, parameters.value), shape)
    buckets = relative_position_buckets(
        length,
        length,
        num_buckets=configuration.num_buckets,
        max_distance=configuration.max_distance,
    )
    bias = mx.transpose(parameters.position_embedding[buckets], (2, 0, 1))[None]
    if attention_mask is not None:
        if attention_mask.shape != (batch, length):
            raise ValueError("T5 attention mask must have shape [batch, sequence]")
        minimum = mx.array(mx.finfo(x.dtype).min, dtype=x.dtype)
        bias = bias + mx.where(attention_mask[:, None, None, :] != 0, 0.0, minimum)
    query = mx.transpose(query, (0, 2, 1, 3))
    key = mx.transpose(key, (0, 2, 1, 3))
    value = mx.transpose(value, (0, 2, 1, 3))
    if fast_attention:
        attended = mx.fast.scaled_dot_product_attention(query, key, value, scale=1.0, mask=bias)
    else:
        scores = mx.matmul(query, mx.swapaxes(key, -1, -2)) + bias
        probabilities = mx.softmax(scores.astype(mx.float32), axis=-1).astype(scores.dtype)
        attended = mx.matmul(probabilities, value)
    attended = mx.reshape(mx.transpose(attended, (0, 2, 1, 3)), (batch, length, -1))
    x = x + _linear(attended, parameters.attention_output)
    hidden = t5_rms_norm(x, parameters.norm2, epsilon=configuration.norm_epsilon)
    gated = _linear(hidden, parameters.feed_forward_input) * _gelu_tanh(
        _linear(hidden, parameters.gate)
    )
    return x + _linear(gated, parameters.feed_forward_output)


def wan_t5_encode(
    input_ids: mx.array,
    attention_mask: mx.array,
    parameters: WanT5EncoderParameters,
    configuration: WanT5Configuration = DEFAULT_WAN_T5_CONFIGURATION,
    *,
    fast_attention: bool = False,
    evaluation_interval: int = 1,
    trace: dict[str, mx.array] | None = None,
) -> mx.array:
    """Encode token ids with the complete pinned Wan UMT5 encoder."""

    if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
        raise ValueError("T5 ids and mask must have matching [batch, sequence] shapes")
    if len(parameters.blocks) != configuration.num_layers:
        raise ValueError("T5 parameter layer count disagrees with configuration")
    x = parameters.token_embedding[input_ids]
    for index, block in enumerate(parameters.blocks):
        x = wan_t5_block(x, attention_mask, block, configuration, fast_attention=fast_attention)
        if trace is not None:
            trace[f"text.blocks.{index}"] = x
        if evaluation_interval and (index + 1) % evaluation_interval == 0:
            mx.eval(x)
    output = t5_rms_norm(x, parameters.output_norm, epsilon=configuration.norm_epsilon)
    if trace is not None:
        trace["text.output"] = output
    return output


def wan_t5_encode_trimmed(
    input_ids: mx.array,
    attention_mask: mx.array,
    parameters: WanT5EncoderParameters,
    configuration: WanT5Configuration = DEFAULT_WAN_T5_CONFIGURATION,
    *,
    fast_attention: bool = False,
    evaluation_interval: int = 1,
    minimum_length: int = 64,
) -> tuple[mx.array, mx.array]:
    """Encode only the non-padding prefix while preserving a dense batch result."""

    if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
        raise ValueError("T5 ids and mask must have matching [batch, sequence] shapes")
    lengths = mx.sum(attention_mask, axis=1)
    mx.eval(lengths)
    maximum = max(int(cast(int, mx.max(lengths).item())), minimum_length)
    maximum = min(maximum, input_ids.shape[1])
    if maximum <= 0:
        raise ValueError("T5 input must contain at least one non-padding token")
    trimmed_mask = attention_mask[:, :maximum]
    output = wan_t5_encode(
        input_ids[:, :maximum],
        trimmed_mask,
        parameters,
        configuration,
        fast_attention=fast_attention,
        evaluation_interval=evaluation_interval,
    )
    return output, lengths
