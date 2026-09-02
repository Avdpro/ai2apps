"""Host-side safety and compatibility policy for video model variants."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

H3_RESOLUTIONS = (
    "512x512",
    "512x288",
    "288x512",
    "768x768",
    "1024x768",
    "768x1024",
    "1152x768",
    "768x1152",
    "1344x768",
    "768x1344",
)
H3_RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3")


def _model_identity(model: Any) -> tuple[str, Mapping[str, Any]]:
    if isinstance(model, Mapping):
        model_id = str(model.get("id", "")).lower()
        metadata = model.get("metadata", {})
    else:
        model_id = str(getattr(model, "id", "")).lower()
        metadata = getattr(model, "metadata", {})
    return model_id, metadata if isinstance(metadata, Mapping) else {}


def is_h3_video_model(model: Any) -> bool:
    model_id, metadata = _model_identity(model)
    family = str(metadata.get("family", "")).lower().replace("_", "-")
    return (
        family in {"minimax-h3", "h3"}
        or "minimax-h3" in model_id
        or model_id.startswith("h3/")
    )


def effective_video_capabilities(model: Any) -> dict[str, Any]:
    """Return capabilities corrected for compatibility known by this Host build."""

    if isinstance(model, Mapping):
        raw = model.get("video_capabilities", {})
    else:
        raw = getattr(model, "video_capabilities", {})
    capabilities = deepcopy(dict(raw or {}))
    if is_h3_video_model(model):
        geometry = dict(capabilities.get("geometry") or {})
        geometry["resolutions"] = list(H3_RESOLUTIONS)
        geometry["ratios"] = list(H3_RATIOS)
        capabilities["geometry"] = geometry
    return capabilities


def is_temporarily_disabled_video_model(model: Any) -> bool:
    """Block H3 full-precision variants while their output quality is investigated."""

    model_id, metadata = _model_identity(model)
    precision = str(metadata.get("precision", "")).lower().replace("_", "-")
    is_16_bit = precision in {"bf16", "fp16", "f16", "16bit", "16-bit"} or any(
        token in model_id
        for token in ("/fl2va-bf16", "/fl2va-fp16", "/bf16", "/fp16")
    )
    return is_h3_video_model(model) and is_16_bit
