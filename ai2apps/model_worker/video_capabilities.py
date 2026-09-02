# SPDX-License-Identifier: Apache-2.0
"""Validated capability declarations for video Model Packages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

VIDEO_CAPABILITIES_SCHEMA = "ai2apps.video-capabilities/v1"
CONTENT_TYPES = frozenset({"text", "image_url", "audio_url", "video_url"})
CONTENT_ROLES = frozenset({
    "prompt", "negative_prompt", "reference_image", "first_frame", "last_frame",
    "mask", "driving_audio", "reference_audio", "soundtrack", "reference_video",
    "source_video",
})
AUDIO_MODES = frozenset({"none", "generated", "preserve_driving_audio", "auto"})
RESUMABLE_MODES = frozenset({"unsupported", "single_window", "all"})
PROGRESS_MODES = frozenset({"unsupported", "phase", "step"})


class VideoCapabilitiesError(ValueError):
    pass


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise VideoCapabilitiesError(
            "video_capabilities must contain JSON values"
        ) from exc


def _string_list(value: Any, *, field: str, allowed: frozenset[str] | None = None) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and 1 <= len(item) <= 128 for item in value
    ):
        raise VideoCapabilitiesError(f"{field} is invalid")
    if allowed is not None and any(item not in allowed for item in value):
        raise VideoCapabilitiesError(f"{field} contains an unsupported value")
    return sorted(set(value))


def _content_rule(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoCapabilitiesError(f"{field} must be an object")
    content_type = value.get("type")
    role = value.get("role")
    minimum = value.get("min", 0)
    maximum = value.get("max", 1)
    if content_type not in CONTENT_TYPES or role not in CONTENT_ROLES:
        raise VideoCapabilitiesError(f"{field} has an invalid type or role")
    if (
        not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0
        or not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < minimum
        or maximum > 12
    ):
        raise VideoCapabilitiesError(f"{field} has invalid cardinality")
    return {"type": content_type, "role": role, "min": minimum, "max": maximum}


def validate_video_capabilities(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise VideoCapabilitiesError("video_capabilities must be an object")
    normalized = _json_copy(dict(value))
    if normalized.get("schema") != VIDEO_CAPABILITIES_SCHEMA:
        raise VideoCapabilitiesError(
            f"video_capabilities.schema must be {VIDEO_CAPABILITIES_SCHEMA!r}"
        )
    if normalized.get("operations") != ["video_generation"]:
        raise VideoCapabilitiesError(
            "video_capabilities.operations must be ['video_generation']"
        )

    combinations = normalized.get("content_combinations")
    if not isinstance(combinations, list) or not combinations:
        raise VideoCapabilitiesError(
            "video_capabilities.content_combinations must be a non-empty array"
        )
    seen_ids: set[str] = set()
    normalized_combinations: list[dict[str, Any]] = []
    for index, combination in enumerate(combinations):
        field = f"video_capabilities.content_combinations[{index}]"
        if not isinstance(combination, Mapping):
            raise VideoCapabilitiesError(f"{field} must be an object")
        combination_id = combination.get("id")
        if (
            not isinstance(combination_id, str) or not combination_id
            or len(combination_id) > 128 or combination_id in seen_ids
        ):
            raise VideoCapabilitiesError(f"{field}.id is invalid")
        seen_ids.add(combination_id)
        required = combination.get("required", [])
        optional = combination.get("optional", [])
        if not isinstance(required, list) or not required or not isinstance(optional, list):
            raise VideoCapabilitiesError(f"{field} rules are invalid")
        rules = [
            _content_rule(item, field=f"{field}.required[{rule_index}]")
            for rule_index, item in enumerate(required)
        ]
        optional_rules = [
            _content_rule(item, field=f"{field}.optional[{rule_index}]")
            for rule_index, item in enumerate(optional)
        ]
        pairs = [(item["type"], item["role"]) for item in rules + optional_rules]
        if len(pairs) != len(set(pairs)):
            raise VideoCapabilitiesError(f"{field} contains duplicate rules")
        normalized_combinations.append({
            "id": combination_id,
            "required": rules,
            "optional": optional_rules,
            "unsupported_roles": _string_list(
                combination.get("unsupported_roles", []),
                field=f"{field}.unsupported_roles",
                allowed=CONTENT_ROLES,
            ),
        })
    normalized["content_combinations"] = normalized_combinations

    formats = normalized.get("formats")
    if not isinstance(formats, Mapping):
        raise VideoCapabilitiesError("video_capabilities.formats must be an object")
    allowed_formats = {
        "image_input": frozenset({"png", "jpeg", "webp"}),
        "audio_input": frozenset({"wav", "mp3", "m4a", "aac", "flac"}),
        "video_input": frozenset({"mp4", "mov", "webm"}),
        "video_output": frozenset({"mp4", "mov", "webm"}),
        "video_codecs": frozenset({"h264", "hevc", "vp9", "av1"}),
        "audio_codecs": frozenset({"aac", "opus", "pcm"}),
    }
    normalized["formats"] = {
        name: _string_list(formats.get(name, []), field=f"video_capabilities.formats.{name}",
                           allowed=allowed)
        for name, allowed in allowed_formats.items()
    }
    if not normalized["formats"]["video_output"]:
        raise VideoCapabilitiesError("video_capabilities.formats.video_output is empty")

    geometry = normalized.get("geometry")
    if not isinstance(geometry, Mapping):
        raise VideoCapabilitiesError("video_capabilities.geometry must be an object")
    resolutions = _string_list(
        geometry.get("resolutions", []), field="video_capabilities.geometry.resolutions"
    )
    ratios = _string_list(geometry.get("ratios", []), field="video_capabilities.geometry.ratios")
    fps = geometry.get("framespersecond", [])
    if not isinstance(fps, list) or not fps or not all(
        isinstance(item, int) and not isinstance(item, bool) and 1 <= item <= 240 for item in fps
    ):
        raise VideoCapabilitiesError("video_capabilities.geometry.framespersecond is invalid")
    normalized["geometry"] = {
        "resolutions": resolutions,
        "ratios": ratios,
        "framespersecond": sorted(set(fps)),
        "alpha": geometry.get("alpha", False) is True,
    }

    audio = normalized.get("audio", {})
    if not isinstance(audio, Mapping):
        raise VideoCapabilitiesError("video_capabilities.audio must be an object")
    modes = _string_list(
        audio.get("modes", ["none"]), field="video_capabilities.audio.modes",
        allowed=AUDIO_MODES,
    )
    default_mode = audio.get("default_mode", modes[0] if modes else None)
    if default_mode not in modes:
        raise VideoCapabilitiesError("video_capabilities.audio.default_mode is invalid")
    normalized["audio"] = {
        "modes": modes,
        "default_mode": default_mode,
        "generated_audio": audio.get("generated_audio", False) is True,
    }

    presets = normalized.get("presets")
    if not isinstance(presets, list) or not presets:
        raise VideoCapabilitiesError("video_capabilities.presets must be a non-empty array")
    preset_ids: set[str] = set()
    normalized_presets: list[dict[str, Any]] = []
    for index, preset in enumerate(presets):
        field = f"video_capabilities.presets[{index}]"
        if not isinstance(preset, Mapping):
            raise VideoCapabilitiesError(f"{field} must be an object")
        preset_id = preset.get("id")
        if not isinstance(preset_id, str) or not preset_id or preset_id in preset_ids:
            raise VideoCapabilitiesError(f"{field}.id is invalid")
        preset_ids.add(preset_id)
        resumable = preset.get("resumable", "unsupported")
        if resumable not in RESUMABLE_MODES:
            raise VideoCapabilitiesError(f"{field}.resumable is invalid")
        normalized_presets.append({**dict(preset), "id": preset_id, "resumable": resumable})
    normalized["presets"] = normalized_presets

    execution = normalized.get("execution", {})
    if not isinstance(execution, Mapping):
        raise VideoCapabilitiesError("video_capabilities.execution must be an object")
    progress = execution.get("progress", "unsupported")
    concurrency = execution.get("max_concurrency_per_device", 1)
    if progress not in PROGRESS_MODES:
        raise VideoCapabilitiesError("video_capabilities.execution.progress is invalid")
    if not isinstance(concurrency, int) or isinstance(concurrency, bool) or concurrency < 1:
        raise VideoCapabilitiesError(
            "video_capabilities.execution.max_concurrency_per_device is invalid"
        )
    normalized["execution"] = {
        **dict(execution),
        "asynchronous": execution.get("asynchronous", True) is True,
        "progress": progress,
        "max_concurrency_per_device": concurrency,
    }
    defaults = normalized.get("defaults", {})
    if not isinstance(defaults, Mapping):
        raise VideoCapabilitiesError("video_capabilities.defaults must be an object")
    if defaults.get("preset") not in preset_ids:
        raise VideoCapabilitiesError("video_capabilities.defaults.preset is invalid")
    if defaults.get("audio_output_mode", default_mode) not in modes:
        raise VideoCapabilitiesError("video_capabilities.defaults.audio_output_mode is invalid")
    normalized["defaults"] = dict(defaults)
    return normalized
