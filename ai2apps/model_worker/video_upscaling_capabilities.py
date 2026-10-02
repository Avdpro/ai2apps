# SPDX-License-Identifier: Apache-2.0
"""Separate, bounded video upscaling contract for Model Workers."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any

VIDEO_UPSCALING_CAPABILITIES_SCHEMA = "ai2apps.video-upscaling-capabilities/v1"


class VideoUpscalingCapabilitiesError(ValueError):
    pass


def validate_video_upscaling_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoUpscalingCapabilitiesError(
            "video_upscaling_capabilities must be an object"
        )
    try:
        result = json.loads(json.dumps(dict(value), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise VideoUpscalingCapabilitiesError(
            "capabilities must contain finite JSON values"
        ) from exc
    if result.get("schema") != VIDEO_UPSCALING_CAPABILITIES_SCHEMA:
        raise VideoUpscalingCapabilitiesError("Unsupported video upscaling schema")
    if result.get("operations") != ["video_upscaling"]:
        raise VideoUpscalingCapabilitiesError("operations must be ['video_upscaling']")
    scales = result.get("scale_factors")
    if (
        not isinstance(scales, list)
        or not scales
        or any(type(v) is not int or not 2 <= v <= 8 for v in scales)
    ):
        raise VideoUpscalingCapabilitiesError(
            "scale_factors must contain integer factors 2..8"
        )
    result["scale_factors"] = sorted(set(scales))
    resource_limited = result.get("resolution_policy") == "resource_limited"
    if result.get("maximum_output_pixels") is None:
        if not resource_limited or "maximum_output_pixels" not in result:
            raise VideoUpscalingCapabilitiesError(
                "An unbounded pixel limit requires resolution_policy=resource_limited"
            )
    elif (
        type(result["maximum_output_pixels"]) is not int
        or result["maximum_output_pixels"] < 1
    ):
        raise VideoUpscalingCapabilitiesError("maximum_output_pixels is invalid")
    for key, upper in (("maximum_frames", 108000),):
        if type(result.get(key)) is not int or not 1 <= result[key] <= upper:
            raise VideoUpscalingCapabilitiesError(f"{key} is invalid")
    seconds = result.get("maximum_seconds")
    if (
        type(seconds) not in (int, float)
        or not math.isfinite(seconds)
        or not 0 < seconds <= 3600
    ):
        raise VideoUpscalingCapabilitiesError("maximum_seconds is invalid")
    if result.get("output_formats") != ["mp4"]:
        raise VideoUpscalingCapabilitiesError("output_formats must be ['mp4']")
    for key in (
        "preserves_frame_count",
        "preserves_audio",
        "segmented",
        "prompt_required",
    ):
        if type(result.get(key)) is not bool:
            raise VideoUpscalingCapabilitiesError(f"{key} must be boolean")
    return result
