"""Checkpoint tensors -> model parameters, as a function of names and shapes.

``model.safetensors`` stores every tensor in the PyTorch layout. The MLX model
keeps most of them as they are and changes a few:

- projections that read the same input are stacked into one matrix (the Gated
  DeltaNet input projections, attention ``q/k/v``, MLP ``gate/up`` and every
  AdaLN projection of the head), so a frame issues fewer, larger matmuls;
- the backbone's RMSNorm gains are zero-centred (``y = norm(x) * (1 + w)``) and
  are stored as ``1 + w`` in float32, because bfloat16 only resolves 1/128
  near 1;
- convolutions are stored channel-last, and the codec's as the matrix of the
  single matmul that evaluates them.

Nothing here imports MLX: :func:`conversion_plan` and :func:`parameter_shapes`
describe the conversion, :mod:`haru_mlx.models.loaders` applies it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

from .config import HaruConfig
from .lm_config import LINEAR, TextConfig

Shape = tuple[int, ...]

COPY = "copy"  # unchanged; several sources are concatenated along axis 0
GAMMA = "gamma"  # zero-centred norm gain -> float32 ``1 + w``
SCALAR = "scalar"  # float32 scalar
CHANNELS_LAST = "channels_last"  # Conv1d [out, in, k] -> [out, k, in]
CONV_MATRIX = "conv_matrix"  # Conv1d [out, in, k] -> [out, k * in]
CONV_TRANSPOSE_MATRIX = "conv_transpose_matrix"  # ConvTranspose1d [in, out, k] -> [out * k, in]


@dataclass(frozen=True)
class Conversion:
    """How one model parameter is built from checkpoint tensors."""

    sources: tuple[str, ...]
    layout: str
    shape: Shape


# Fused backbone projections: parameter -> checkpoint projections, in row order.
_FUSED = {
    "linear_attn.in_proj": ("in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a"),
    "self_attn.qkv": ("q_proj", "k_proj", "v_proj"),
    "mlp.gate_up": ("gate_proj", "up_proj"),
}
_FUSED_TARGET = {
    f"{target.split('.')[0]}.{part}": (target, index)
    for target, parts in _FUSED.items()
    for index, part in enumerate(parts)
}
_PROJECTION = re.compile(r"(lm\.layers\.\d+)\.(\w+\.\w+)\.weight")
_HEAD_ADA = re.compile(r"head\.(?:layers\.(\d+)|final)\.ada\.weight")
_GAMMA = re.compile(r"lm\.(?:norm|layers\.\d+\.(?:\w+_layernorm|self_attn\.[qk]_norm))\.weight")
_LM_CONV = re.compile(r"lm\.layers\.\d+\.linear_attn\.conv1d\.weight")
_CODEC_CONV = re.compile(r"codec\.(?:encoder|decoder)\.(?:stem|head|down\.\d+|stages\.\d+\.\d+\.conv)\.weight")
_CODEC_CONV_TRANSPOSE = re.compile(r"codec\.decoder\.up\.\d+\.weight")


def _target(name: str) -> tuple[str, int]:
    """``(parameter, row block)`` that checkpoint tensor ``name`` goes to."""
    match = _PROJECTION.fullmatch(name)
    if match and match.group(2) in _FUSED_TARGET:
        target, index = _FUSED_TARGET[match.group(2)]
        return f"{match.group(1)}.{target}.weight", index
    match = _HEAD_ADA.fullmatch(name)
    if match:  # layers in order, then the final layer
        return "head.ada.weight", int(match.group(1)) if match.group(1) else 1 << 30
    return name, 0


def _layout(name: str) -> str:
    if name in ("latent_scale", "latent_bias"):
        return SCALAR
    for pattern, layout in (
        (_GAMMA, GAMMA),
        (_LM_CONV, CHANNELS_LAST),
        (_CODEC_CONV, CONV_MATRIX),
        (_CODEC_CONV_TRANSPOSE, CONV_TRANSPOSE_MATRIX),
    ):
        if pattern.fullmatch(name):
            return layout
    return COPY


def _converted_shape(layout: str, shapes: list[Shape]) -> Shape:
    first = shapes[0]
    if layout == SCALAR:
        return ()
    if layout == CHANNELS_LAST:
        return (first[0], first[2], first[1])
    if layout == CONV_MATRIX:
        return (first[0], first[2] * first[1])
    if layout == CONV_TRANSPOSE_MATRIX:
        return (first[1] * first[2], first[0])
    if len(shapes) == 1:
        return first
    if any(shape[1:] != first[1:] for shape in shapes):
        raise ValueError(f"cannot stack tensors of shapes {shapes}")
    return (sum(shape[0] for shape in shapes), *first[1:])


def conversion_plan(shapes: Mapping[str, Shape]) -> dict[str, Conversion]:
    """``{parameter: Conversion}`` for a checkpoint's ``{tensor name: shape}``.

    Every checkpoint tensor is a source of exactly one parameter.
    """
    blocks: dict[str, dict[int, str]] = {}
    for name in shapes:
        target, index = _target(name)
        blocks.setdefault(target, {})[index] = name
    plan = {}
    for target, parts in blocks.items():
        sources = tuple(parts[index] for index in sorted(parts))
        layout = _layout(sources[0])
        plan[target] = Conversion(sources, layout, _converted_shape(layout, [tuple(shapes[s]) for s in sources]))
    return plan


def parameter_shapes(config: HaruConfig) -> dict[str, Shape]:
    """Every parameter of :class:`haru_mlx.HaruModel` and its shape."""
    lm = TextConfig.from_dict(config.lm)
    hidden, latent = lm.hidden_size, config.latent_dim
    shapes: dict[str, Shape] = {
        "lm.embed_tokens.weight": (lm.vocab_size, hidden),
        "lm.norm.weight": (hidden,),
        "latent_scale": (),
        "latent_bias": (),
    }
    for i, kind in enumerate(lm.layer_types):
        layer = f"lm.layers.{i}"
        shapes[f"{layer}.input_layernorm.weight"] = (hidden,)
        shapes[f"{layer}.post_attention_layernorm.weight"] = (hidden,)
        shapes[f"{layer}.mlp.gate_up.weight"] = (2 * lm.intermediate_size, hidden)
        shapes[f"{layer}.mlp.down_proj.weight"] = (hidden, lm.intermediate_size)
        if kind == LINEAR:
            block = f"{layer}.linear_attn"
            heads = lm.linear_num_value_heads
            shapes[f"{block}.in_proj.weight"] = (lm.conv_dim + lm.value_dim + 2 * heads, hidden)
            shapes[f"{block}.conv1d.weight"] = (lm.conv_dim, lm.linear_conv_kernel_dim, 1)
            shapes[f"{block}.A_log"] = (heads,)
            shapes[f"{block}.dt_bias"] = (heads,)
            shapes[f"{block}.norm.weight"] = (lm.linear_value_head_dim,)
            shapes[f"{block}.out_proj.weight"] = (hidden, lm.value_dim)
        else:
            block = f"{layer}.self_attn"
            query_dim = lm.num_attention_heads * lm.head_dim
            key_dim = lm.num_key_value_heads * lm.head_dim
            shapes[f"{block}.qkv.weight"] = (2 * query_dim + 2 * key_dim, hidden)  # queries carry the output gate
            shapes[f"{block}.q_norm.weight"] = (lm.head_dim,)
            shapes[f"{block}.k_norm.weight"] = (lm.head_dim,)
            shapes[f"{block}.o_proj.weight"] = (hidden, query_dim)

    for proj in ("model_audio_proj", "user_audio_proj"):
        shapes[f"{proj}.fc1.weight"] = (hidden, latent)
        shapes[f"{proj}.fc1.bias"] = (hidden,)
        shapes[f"{proj}.norm.weight"] = (hidden,)
        shapes[f"{proj}.fc2.weight"] = (hidden, hidden)
        shapes[f"{proj}.fc2.bias"] = (hidden,)

    head = config.head
    width, ffn = head.hidden_size, int(head.hidden_size * head.ffn_ratio)
    shapes["head.latent_proj.weight"] = (width, head.latent_dim)
    shapes["head.cond_proj.weight"] = (width, width)
    for embed in ("t_embed", "dt_embed", "h_embed", "omega_embed"):
        shapes[f"head.{embed}.fc1.weight"] = (width, 256)
        shapes[f"head.{embed}.fc2.weight"] = (width, width)
    shapes["head.ada.weight"] = ((3 * head.num_layers + 2) * width, width)
    for i in range(head.num_layers):
        shapes[f"head.layers.{i}.norm.weight"] = (width,)
        shapes[f"head.layers.{i}.ffn.gate_proj.weight"] = (ffn, width)
        shapes[f"head.layers.{i}.ffn.up_proj.weight"] = (ffn, width)
        shapes[f"head.layers.{i}.ffn.down_proj.weight"] = (width, ffn)
    shapes["head.final.proj.weight"] = (head.latent_dim, width)

    codec = config.codec
    base, stages = codec.base_channels, len(codec.ratios)

    def conv(name: str, in_channels: int, out_channels: int, kernel: int) -> None:
        shapes[f"{name}.weight"] = (out_channels, kernel * in_channels)
        shapes[f"{name}.bias"] = (out_channels,)

    def stage(name: str, channels: int, depth: int) -> None:
        for b in range(depth):
            block = f"{name}.{b}"
            shapes[f"{block}.norm.weight"] = (channels,)
            shapes[f"{block}.conv.weight"] = (channels, 7)
            shapes[f"{block}.conv.bias"] = (channels,)
            shapes[f"{block}.gamma"] = (channels,)
            shapes[f"{block}.ffn_norm.weight"] = (channels,)
            shapes[f"{block}.fc1.weight"] = (4 * channels, channels)
            shapes[f"{block}.fc1.bias"] = (4 * channels,)
            shapes[f"{block}.fc2.weight"] = (channels, 4 * channels)
            shapes[f"{block}.fc2.bias"] = (channels,)
            shapes[f"{block}.ffn_gamma"] = (channels,)

    conv("codec.encoder.stem", 1, base, 7)
    for i, stride in enumerate(codec.ratios[::-1]):
        conv(f"codec.encoder.down.{i}", base << i, base << (i + 1), 2 * stride)
    for i, depth in enumerate(codec.encoder_depths):
        stage(f"codec.encoder.stages.{i}", base << i, depth)
    conv("codec.encoder.head", base << stages, codec.latent_dim, 7)

    conv("codec.decoder.stem", codec.latent_dim, base << stages, 7)
    for i, stride in enumerate(codec.ratios):
        out_channels = base << (stages - i - 1)
        shapes[f"codec.decoder.up.{i}.weight"] = (out_channels * 2 * stride, base << (stages - i))
        shapes[f"codec.decoder.up.{i}.bias"] = (out_channels,)
    for i, depth in enumerate(codec.decoder_depths):
        stage(f"codec.decoder.stages.{i}", base << (stages - i), depth)
    conv("codec.decoder.head", base, 1, 7)
    return shapes


def check_plan(plan: Mapping[str, Conversion], expected: Mapping[str, Shape]) -> None:
    """Raise unless ``plan`` produces exactly the parameters in ``expected``."""
    problems = [f"missing from the checkpoint: {name}" for name in sorted(set(expected) - set(plan))]
    problems += [
        f"not a model parameter: {name} (from {', '.join(plan[name].sources)})"
        for name in sorted(set(plan) - set(expected))
    ]
    problems += [
        f"{name}: checkpoint gives {plan[name].shape}, the model needs {tuple(expected[name])}"
        for name in sorted(set(plan) & set(expected))
        if tuple(plan[name].shape) != tuple(expected[name])
    ]
    if problems:
        shown = "\n  ".join(problems[:20])
        more = f"\n  ... and {len(problems) - 20} more" if len(problems) > 20 else ""
        raise ValueError(f"checkpoint does not match the model:\n  {shown}{more}")
