# SPDX-License-Identifier: Apache-2.0
"""Validated, signed capability declarations for audio Model Packages."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

AUDIO_CAPABILITIES_SCHEMA = "ai2apps.audio-capabilities/v1"
FEATURE_MODES = frozenset({"native", "pipeline", "fallback", "unsupported"})
FEATURE_STATUSES = frozenset({"native", "pipeline", "fallback", "ignored", "rejected"})
_OPERATIONS_BY_MODEL_TYPE = {
    "audio_stt": "audio_transcription",
    "audio_tts": "audio_speech",
    "audio_processing": "audio_process",
    "audio_detailed_transcription": "audio_detailed_transcription",
}
_CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$")


class AudioCapabilitiesError(ValueError):
    pass


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise AudioCapabilitiesError(
            "audio_capabilities must contain JSON values"
        ) from exc


def _feature(value: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AudioCapabilitiesError(f"{field} must be an object")
    normalized = _json_copy(dict(value))
    mode = normalized.get("mode", "unsupported")
    if mode not in FEATURE_MODES:
        raise AudioCapabilitiesError(f"{field}.mode is invalid")
    normalized["mode"] = mode
    return normalized


def default_audio_capabilities(model_type: str) -> dict[str, Any] | None:
    operation = _OPERATIONS_BY_MODEL_TYPE.get(model_type)
    if operation is None:
        return None
    value: dict[str, Any] = {
        "schema": AUDIO_CAPABILITIES_SCHEMA,
        "operations": [operation],
        "formats": {
            "input": ["wav"] if model_type != "audio_tts" else [],
            "output": ["wav"],
        },
        "streaming": {"mode": "unsupported", "formats": []},
    }
    if model_type in {"audio_stt", "audio_detailed_transcription"}:
        value["stt"] = {
            "timestamps": {"mode": "unsupported"},
            "diarization": {"mode": "unsupported"},
            "speaker_recognition": {"mode": "unsupported"},
            "speech_rate": {"mode": "unsupported"},
            "emotion": {"mode": "unsupported"},
        }
    elif model_type == "audio_tts":
        value["tts"] = {
            "named_voices": {"mode": "unsupported", "voices": []},
            "speed": {"mode": "unsupported"},
            "emotion": {"mode": "unsupported"},
            "instructions": {"mode": "unsupported"},
            "voice_profiles": {"mode": "unsupported"},
        }
    elif model_type == "audio_processing":
        value["processing"] = {
            "separation": {
                "mode": "unsupported",
                "native_stems": [],
                "profiles": [],
            },
            "voice_conversion": {
                "mode": "unsupported",
                "target_sources": [],
                "profiles": [],
                "controls": [],
            },
            "voice_training": {
                "mode": "unsupported",
                "input_sources": [],
                "controls": [],
                "output": None,
            },
        }
    return value


def _capability_ids(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise AudioCapabilitiesError(f"{field} must be a list")
    if not all(
        isinstance(item, str) and _CAPABILITY_ID.fullmatch(item) for item in value
    ):
        raise AudioCapabilitiesError(f"{field} contains an invalid identifier")
    if len(value) != len(set(value)):
        raise AudioCapabilitiesError(f"{field} must not contain duplicates")
    return list(value)


def _validate_separation(value: dict[str, Any]) -> dict[str, Any]:
    field = "audio_capabilities.processing.separation"
    native_stems = _capability_ids(
        value.get("native_stems", []), field=f"{field}.native_stems"
    )
    profiles = value.get("profiles", [])
    if not isinstance(profiles, list):
        raise AudioCapabilitiesError(f"{field}.profiles must be a list")
    normalized_profiles: list[dict[str, Any]] = []
    profile_ids: set[str] = set()
    for index, profile in enumerate(profiles):
        profile_field = f"{field}.profiles[{index}]"
        if not isinstance(profile, Mapping):
            raise AudioCapabilitiesError(f"{profile_field} must be an object")
        normalized = _json_copy(dict(profile))
        profile_id = normalized.get("id")
        if not isinstance(profile_id, str) or not _CAPABILITY_ID.fullmatch(profile_id):
            raise AudioCapabilitiesError(f"{profile_field}.id is invalid")
        if profile_id in profile_ids:
            raise AudioCapabilitiesError(f"{field}.profiles ids must be unique")
        profile_ids.add(profile_id)
        mode = normalized.get("mode")
        if mode not in {"native", "pipeline", "fallback"}:
            raise AudioCapabilitiesError(f"{profile_field}.mode is invalid")
        normalized["stems"] = _capability_ids(
            normalized.get("stems"), field=f"{profile_field}.stems", allow_empty=False
        )
        derivation = normalized.get("derivation", {})
        if not isinstance(derivation, Mapping) or not all(
            isinstance(key, str)
            and key in normalized["stems"]
            and isinstance(source, str)
            and source
            for key, source in derivation.items()
        ):
            raise AudioCapabilitiesError(f"{profile_field}.derivation is invalid")
        normalized_profiles.append(normalized)
    default_profile = value.get("default_profile")
    if default_profile is not None and default_profile not in profile_ids:
        raise AudioCapabilitiesError(f"{field}.default_profile is not declared")
    unsupported_policy = value.get("unsupported_profile_policy", "reject")
    if unsupported_policy not in {"reject", "default_profile"}:
        raise AudioCapabilitiesError(f"{field}.unsupported_profile_policy is invalid")
    if unsupported_policy == "default_profile" and default_profile is None:
        raise AudioCapabilitiesError(
            f"{field}.default_profile is required by fallback policy"
        )
    if value["mode"] != "unsupported" and not normalized_profiles:
        raise AudioCapabilitiesError(f"{field}.profiles cannot be empty when supported")
    preserves_timeline = value.get("preserves_timeline", True)
    if not isinstance(preserves_timeline, bool):
        raise AudioCapabilitiesError(f"{field}.preserves_timeline must be boolean")
    max_input_channels = value.get("max_input_channels")
    if max_input_channels is not None and (
        not isinstance(max_input_channels, int)
        or isinstance(max_input_channels, bool)
        or not 1 <= max_input_channels <= 64
    ):
        raise AudioCapabilitiesError(f"{field}.max_input_channels is invalid")
    value["native_stems"] = native_stems
    value["profiles"] = normalized_profiles
    value["preserves_timeline"] = preserves_timeline
    value["unsupported_profile_policy"] = unsupported_policy
    return value


def _validate_voice_conversion(value: dict[str, Any]) -> dict[str, Any]:
    field = "audio_capabilities.processing.voice_conversion"
    target_sources = _capability_ids(
        value.get("target_sources", []), field=f"{field}.target_sources"
    )
    controls = _capability_ids(value.get("controls", []), field=f"{field}.controls")
    profiles = value.get("profiles", [])
    if not isinstance(profiles, list):
        raise AudioCapabilitiesError(f"{field}.profiles must be a list")
    normalized_profiles = []
    profile_ids = set()
    for index, profile in enumerate(profiles):
        profile_field = f"{field}.profiles[{index}]"
        if not isinstance(profile, Mapping):
            raise AudioCapabilitiesError(f"{profile_field} must be an object")
        normalized = _json_copy(dict(profile))
        profile_id = normalized.get("id")
        if not isinstance(profile_id, str) or not _CAPABILITY_ID.fullmatch(profile_id):
            raise AudioCapabilitiesError(f"{profile_field}.id is invalid")
        if profile_id in profile_ids:
            raise AudioCapabilitiesError(f"{field}.profiles ids must be unique")
        profile_ids.add(profile_id)
        if normalized.get("mode") not in {"native", "pipeline", "fallback"}:
            raise AudioCapabilitiesError(f"{profile_field}.mode is invalid")
        normalized_profiles.append(normalized)
    if value["mode"] != "unsupported" and (
        not target_sources or not normalized_profiles
    ):
        raise AudioCapabilitiesError(
            f"{field} requires target_sources and profiles when supported"
        )
    value["target_sources"] = target_sources
    value["controls"] = controls
    value["profiles"] = normalized_profiles
    return value


def validate_audio_capabilities(value: Any, *, model_type: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AudioCapabilitiesError("audio_capabilities must be an object")
    normalized = _json_copy(dict(value))
    if normalized.get("schema") != AUDIO_CAPABILITIES_SCHEMA:
        raise AudioCapabilitiesError(
            f"audio_capabilities.schema must be {AUDIO_CAPABILITIES_SCHEMA!r}"
        )
    operation = _OPERATIONS_BY_MODEL_TYPE.get(model_type)
    operations = normalized.get("operations")
    expected_operations = [operation]
    if (
        model_type == "audio_processing"
        and isinstance(operations, list)
        and operations
        == [
            operation,
            "audio_voice_training",
        ]
    ):
        expected_operations = operations
    if (
        operation is None
        or not isinstance(operations, list)
        or operations != expected_operations
    ):
        raise AudioCapabilitiesError(
            "audio_capabilities.operations must contain the model type operation"
        )
    languages = normalized.get("languages", [])
    if not isinstance(languages, list) or not all(
        isinstance(item, str) and 1 <= len(item) <= 32 for item in languages
    ):
        raise AudioCapabilitiesError("audio_capabilities.languages is invalid")
    formats = normalized.get("formats", {})
    if not isinstance(formats, Mapping):
        raise AudioCapabilitiesError("audio_capabilities.formats must be an object")
    for direction in ("input", "output"):
        declared = formats.get(direction, [])
        if not isinstance(declared, list) or not all(
            item
            in {
                "wav",
                "pcm",
                "mp3",
                "m4a",
                "aac",
                "flac",
                "ogg",
                "opus",
                "webm",
            }
            for item in declared
        ):
            raise AudioCapabilitiesError(
                f"audio_capabilities.formats.{direction} contains an unsupported format"
            )
    streaming = normalized.get("streaming", {"mode": "unsupported", "formats": []})
    normalized["streaming"] = _feature(streaming, field="audio_capabilities.streaming")
    stream_formats = normalized["streaming"].get("formats", [])
    if not isinstance(stream_formats, list) or not all(
        item in {"wav", "pcm"} for item in stream_formats
    ):
        raise AudioCapabilitiesError("audio_capabilities.streaming.formats is invalid")
    section_name = (
        "stt"
        if model_type in {"audio_stt", "audio_detailed_transcription"}
        else "tts"
        if model_type == "audio_tts"
        else "processing"
        if model_type == "audio_processing"
        else None
    )
    if section_name is not None:
        section = normalized.get(section_name, {})
        if not isinstance(section, Mapping):
            raise AudioCapabilitiesError(
                f"audio_capabilities.{section_name} must be an object"
            )
        normalized[section_name] = dict(section)
        for name, feature in section.items():
            normalized[section_name][name] = _feature(
                feature, field=f"audio_capabilities.{section_name}.{name}"
            )
        if section_name == "processing" and "separation" in normalized[section_name]:
            normalized[section_name]["separation"] = _validate_separation(
                normalized[section_name]["separation"]
            )
        if (
            section_name == "processing"
            and "voice_conversion" in normalized[section_name]
        ):
            normalized[section_name]["voice_conversion"] = _validate_voice_conversion(
                normalized[section_name]["voice_conversion"]
            )
        if (
            section_name == "processing"
            and "voice_training" in normalized[section_name]
        ):
            training = normalized[section_name]["voice_training"]
            training["input_sources"] = _capability_ids(
                training.get("input_sources", []),
                field="audio_capabilities.processing.voice_training.input_sources",
            )
            training["controls"] = _capability_ids(
                training.get("controls", []),
                field="audio_capabilities.processing.voice_training.controls",
            )
            output = training.get("output")
            if training["mode"] != "unsupported" and output != "voice_bundle":
                raise AudioCapabilitiesError(
                    "audio_capabilities.processing.voice_training.output must be voice_bundle"
                )
    if model_type == "audio_tts":
        named = normalized.get("tts", {}).get("named_voices", {})
        voices = named.get("voices", [])
        if not isinstance(voices, list) or not all(
            isinstance(item, str) and 1 <= len(item) <= 128 for item in voices
        ):
            raise AudioCapabilitiesError(
                "audio_capabilities.tts.named_voices.voices is invalid"
            )
    normalized["languages"] = sorted(set(languages))
    normalized["formats"] = {
        "input": sorted(set(formats.get("input", []))),
        "output": sorted(set(formats.get("output", []))),
    }
    return normalized


def feature_execution(
    feature: str,
    *,
    requested: Any,
    effective: Any,
    status: str,
    reason: str | None = None,
    provider: str | None = None,
    revision: str | None = None,
) -> dict[str, Any]:
    if status not in FEATURE_STATUSES:
        raise AudioCapabilitiesError(f"Invalid feature execution status: {status}")
    result = {
        "feature": feature,
        "requested": requested,
        "effective": effective,
        "status": status,
    }
    if reason:
        result["reason"] = reason
    if provider:
        result["provider"] = provider
    if revision:
        result["revision"] = revision
    return result
