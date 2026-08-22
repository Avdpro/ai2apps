# SPDX-License-Identifier: Apache-2.0
"""MLX-free config gate for the supported mixed ModelOpt contract."""

from __future__ import annotations

from typing import Any

_FP8_TARGETS = (
    r"re:.*self_attn\.(q|k|v|o)_proj$",
    r"re:.*linear_attn\.(in_proj_qkv|in_proj_z|out_proj)$",
    r"re:.*lm_head",
    r"re:.*layers\.(56|57|58|59|60|61|62|63)\.mlp\.(gate|up|down)_proj$",
)
_NVFP4_TARGETS = (r"re:.*mlp\.(gate|up|down)_proj$",)


def _group_matches(
    group: Any,
    *,
    fmt: str,
    targets: tuple[str, ...],
    bits: int,
    strategy: str,
    group_size: int | None,
) -> bool:
    if not isinstance(group, dict) or group.get("format") != fmt:
        return False
    if tuple(group.get("targets") or ()) != targets:
        return False
    weights = group.get("weights")
    if not isinstance(weights, dict):
        return False
    return (
        weights.get("type") == "float"
        and weights.get("num_bits") == bits
        and weights.get("strategy") == strategy
        and weights.get("group_size") == group_size
        and weights.get("dynamic") is False
        and weights.get("symmetric") is True
    )


def is_supported_config(config: dict[str, Any]) -> bool:
    """Return whether *config* matches the supported Qwen3.8 contract."""
    if config.get("model_type") != "qwen3_5":
        return False
    if config.get("architectures") != ["Qwen3_5ForConditionalGeneration"]:
        return False
    text = config.get("text_config")
    vision = config.get("vision_config")
    if not isinstance(text, dict) or not isinstance(vision, dict):
        return False
    if (
        text.get("num_hidden_layers") != 64
        or text.get("hidden_size") != 5120
        or text.get("num_experts") is not None
    ):
        return False
    if (
        vision.get("model_type") != "qwen3_5_vision"
        or vision.get("hidden_size") != 1152
        or vision.get("out_hidden_size") != 5120
    ):
        return False

    quant = config.get("quantization_config")
    if not isinstance(quant, dict):
        return False
    if (
        quant.get("quant_method") != "compressed-tensors"
        or quant.get("format") != "mixed-precision"
    ):
        return False
    groups = quant.get("config_groups")
    if not isinstance(groups, dict) or set(groups) != {"group_0", "group_1"}:
        return False
    return _group_matches(
        groups["group_0"],
        fmt="float-quantized",
        targets=_FP8_TARGETS,
        bits=8,
        strategy="channel",
        group_size=None,
    ) and _group_matches(
        groups["group_1"],
        fmt="nvfp4-pack-quantized",
        targets=_NVFP4_TARGETS,
        bits=4,
        strategy="tensor_group",
        group_size=16,
    )
