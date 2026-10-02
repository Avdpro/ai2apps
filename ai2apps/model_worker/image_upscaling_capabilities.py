"""Validated core image-upscaling contract, independent of image generation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


class ImageUpscalingCapabilitiesError(ValueError):
    pass


def validate_image_upscaling_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ImageUpscalingCapabilitiesError(
            "image_upscaling_capabilities must be an object"
        )
    try:
        result = json.loads(json.dumps(dict(value), allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ImageUpscalingCapabilitiesError(
            "Capabilities must be finite JSON"
        ) from exc
    if result.get("schema") != "ai2apps.image-upscaling-capabilities/v1":
        raise ImageUpscalingCapabilitiesError("Unsupported image upscaling schema")
    if result.get("operations") != ["image_upscaling"]:
        raise ImageUpscalingCapabilitiesError("operations must be ['image_upscaling']")
    scales = result.get("scale_factors")
    if (
        not isinstance(scales, list)
        or not scales
        or any(type(x) is not int or x < 2 for x in scales)
    ):
        raise ImageUpscalingCapabilitiesError(
            "scale_factors must contain integer factors >=2"
        )
    limit = result.get("maximum_output_pixels")
    if limit is None:
        if (
            "maximum_output_pixels" not in result
            or result.get("resolution_policy") != "resource_limited"
        ):
            raise ImageUpscalingCapabilitiesError(
                "A null pixel limit requires resource_limited policy"
            )
    elif type(limit) is not int or limit < 1:
        raise ImageUpscalingCapabilitiesError("maximum_output_pixels is invalid")
    formats = result.get("input_formats")
    if (
        not isinstance(formats, list)
        or not formats
        or any(x not in {"png", "jpeg", "webp"} for x in formats)
    ):
        raise ImageUpscalingCapabilitiesError("input_formats are invalid")
    if result.get("output_formats") != ["png"]:
        raise ImageUpscalingCapabilitiesError("output_formats must be ['png']")
    for key in ("preserves_alpha", "applies_exif_orientation", "prompt_required"):
        if type(result.get(key)) is not bool:
            raise ImageUpscalingCapabilitiesError(f"{key} must be boolean")
    return result
