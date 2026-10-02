# SPDX-License-Identifier: Apache-2.0
"""Validated capability declarations for video segmentation Model Packages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

VIDEO_SEGMENTATION_CAPABILITIES_SCHEMA = (
    "ai2apps.video-segmentation-capabilities/v1"
)
PROMPT_TYPES = frozenset({"point", "box", "mask"})
OUTPUT_FORMATS = frozenset({"mp4", "mov", "webm", "png-sequence", "npz"})


class VideoSegmentationCapabilitiesError(ValueError):
    pass


def _strings(value: Any, *, field: str, allowed: frozenset[str]) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item in allowed for item in value)
    ):
        raise VideoSegmentationCapabilitiesError(f"{field} is invalid")
    return sorted(set(value))


def validate_video_segmentation_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoSegmentationCapabilitiesError(
            "video_segmentation_capabilities must be an object"
        )
    try:
        normalized = json.loads(json.dumps(dict(value)))
    except (TypeError, ValueError) as exc:
        raise VideoSegmentationCapabilitiesError(
            "video_segmentation_capabilities must contain JSON values"
        ) from exc
    if normalized.get("schema") != VIDEO_SEGMENTATION_CAPABILITIES_SCHEMA:
        raise VideoSegmentationCapabilitiesError(
            f"schema must be {VIDEO_SEGMENTATION_CAPABILITIES_SCHEMA!r}"
        )
    if normalized.get("operations") != ["video_segmentation"]:
        raise VideoSegmentationCapabilitiesError(
            "operations must be ['video_segmentation']"
        )
    normalized["prompt_types"] = _strings(
        normalized.get("prompt_types"), field="prompt_types", allowed=PROMPT_TYPES
    )
    normalized["output_formats"] = _strings(
        normalized.get("output_formats"),
        field="output_formats",
        allowed=OUTPUT_FORMATS,
    )
    maximum_seconds = normalized.get("maximum_seconds")
    if (
        not isinstance(maximum_seconds, (int, float))
        or isinstance(maximum_seconds, bool)
        or not 0 < maximum_seconds <= 3600
    ):
        raise VideoSegmentationCapabilitiesError("maximum_seconds is invalid")
    normalized["maximum_seconds"] = float(maximum_seconds)
    normalized["multi_object"] = normalized.get("multi_object") is True
    normalized["bidirectional"] = normalized.get("bidirectional") is True
    normalized["soft_masks"] = normalized.get("soft_masks") is True
    return normalized
