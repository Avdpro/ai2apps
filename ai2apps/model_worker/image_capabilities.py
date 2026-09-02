# SPDX-License-Identifier: Apache-2.0
"""Validated capability declarations for image Model Packages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

IMAGE_CAPABILITIES_SCHEMA = "ai2apps.image-capabilities/v1"
_OPERATIONS = frozenset({"image_generation", "image_edit"})
_FORMATS = frozenset({"png", "jpeg", "webp"})


class ImageCapabilitiesError(ValueError):
    pass


def default_image_capabilities() -> dict[str, Any]:
    """Conservative compatibility declaration for pre-1.5 image Packages."""
    return {
        "schema": IMAGE_CAPABILITIES_SCHEMA,
        "operations": ["image_generation"],
        "formats": {"input": ["png", "jpeg", "webp"], "output": ["png"]},
        "geometry": {
            "minimum": {"width": 64, "height": 64},
            "maximum": {"width": 2048, "height": 2048},
            "multiple_of": 1,
            "ratios": ["1:1"],
        },
        "defaults": {"width": 1024, "height": 1024, "steps": 20, "guidance": 1.0, "output_format": "png"},
        "execution": {
            "quantizations": ["bf16"],
            "compiled_denoiser": False,
            "persistent_quantized_cache": False,
            "single_pass_guidance_one": False,
            "metal_rms_adaln_fusion": False,
            "edit_kv_cache": False,
            "max_concurrency_per_device": 1,
        },
    }


def _strings(value: Any, *, field: str, allowed: frozenset[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not value or not all(
        isinstance(item, str) and 1 <= len(item) <= 128 for item in value
    ):
        raise ImageCapabilitiesError(f"{field} is invalid")
    if allowed is not None and any(item not in allowed for item in value):
        raise ImageCapabilitiesError(f"{field} contains an unsupported value")
    return list(dict.fromkeys(value))


def _positive_int(value: Any, *, field: str, maximum: int = 16384) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= maximum:
        raise ImageCapabilitiesError(f"{field} is invalid")
    return value


def validate_image_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ImageCapabilitiesError("image_capabilities must be an object")
    try:
        normalized = json.loads(json.dumps(dict(value)))
    except (TypeError, ValueError) as exc:
        raise ImageCapabilitiesError("image_capabilities must contain JSON values") from exc
    if normalized.get("schema") != IMAGE_CAPABILITIES_SCHEMA:
        raise ImageCapabilitiesError(
            f"image_capabilities.schema must be {IMAGE_CAPABILITIES_SCHEMA!r}"
        )
    operations = _strings(
        normalized.get("operations"), field="image_capabilities.operations", allowed=_OPERATIONS
    )
    if operations[0] != "image_generation":
        raise ImageCapabilitiesError("image_generation must be the first operation")
    normalized["operations"] = operations

    formats = normalized.get("formats")
    if not isinstance(formats, Mapping):
        raise ImageCapabilitiesError("image_capabilities.formats must be an object")
    normalized["formats"] = {
        "input": _strings(formats.get("input", ["png"]), field="image_capabilities.formats.input", allowed=_FORMATS),
        "output": _strings(formats.get("output"), field="image_capabilities.formats.output", allowed=_FORMATS),
    }

    geometry = normalized.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ImageCapabilitiesError("image_capabilities.geometry must be an object")
    minimum = geometry.get("minimum", {})
    maximum = geometry.get("maximum", {})
    if not isinstance(minimum, Mapping) or not isinstance(maximum, Mapping):
        raise ImageCapabilitiesError("image_capabilities.geometry bounds are invalid")
    min_width = _positive_int(minimum.get("width"), field="image_capabilities.geometry.minimum.width")
    min_height = _positive_int(minimum.get("height"), field="image_capabilities.geometry.minimum.height")
    max_width = _positive_int(maximum.get("width"), field="image_capabilities.geometry.maximum.width")
    max_height = _positive_int(maximum.get("height"), field="image_capabilities.geometry.maximum.height")
    multiple = _positive_int(geometry.get("multiple_of", 1), field="image_capabilities.geometry.multiple_of", maximum=1024)
    if min_width > max_width or min_height > max_height:
        raise ImageCapabilitiesError("image_capabilities.geometry minimum exceeds maximum")
    normalized["geometry"] = {
        "minimum": {"width": min_width, "height": min_height},
        "maximum": {"width": max_width, "height": max_height},
        "multiple_of": multiple,
        "ratios": _strings(geometry.get("ratios", ["1:1"]), field="image_capabilities.geometry.ratios"),
    }

    defaults = normalized.get("defaults", {})
    if not isinstance(defaults, Mapping):
        raise ImageCapabilitiesError("image_capabilities.defaults must be an object")
    width = _positive_int(defaults.get("width"), field="image_capabilities.defaults.width")
    height = _positive_int(defaults.get("height"), field="image_capabilities.defaults.height")
    steps = _positive_int(defaults.get("steps"), field="image_capabilities.defaults.steps", maximum=1000)
    output_format = defaults.get("output_format")
    if output_format not in normalized["formats"]["output"]:
        raise ImageCapabilitiesError("image_capabilities.defaults.output_format is invalid")
    if not (min_width <= width <= max_width and min_height <= height <= max_height):
        raise ImageCapabilitiesError("image_capabilities.defaults geometry is out of range")
    normalized["defaults"] = {
        "width": width,
        "height": height,
        "steps": steps,
        "guidance": float(defaults.get("guidance", 1.0)),
        "output_format": output_format,
    }

    execution = normalized.get("execution", {})
    if not isinstance(execution, Mapping):
        raise ImageCapabilitiesError("image_capabilities.execution must be an object")
    normalized["execution"] = {
        "quantizations": _strings(execution.get("quantizations", ["bf16"]), field="image_capabilities.execution.quantizations"),
        "compiled_denoiser": execution.get("compiled_denoiser", False) is True,
        "persistent_quantized_cache": execution.get("persistent_quantized_cache", False) is True,
        "single_pass_guidance_one": execution.get("single_pass_guidance_one", False) is True,
        "metal_rms_adaln_fusion": execution.get("metal_rms_adaln_fusion", False) is True,
        "edit_kv_cache": execution.get("edit_kv_cache", False) is True,
        "max_concurrency_per_device": _positive_int(
            execution.get("max_concurrency_per_device", 1),
            field="image_capabilities.execution.max_concurrency_per_device",
            maximum=64,
        ),
    }
    return normalized
