# SPDX-License-Identifier: Apache-2.0
"""Validated, signed capability declarations for audio Model Packages."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

AUDIO_CAPABILITIES_SCHEMA = "ai2apps.audio-capabilities/v1"
FEATURE_MODES = frozenset({"native", "pipeline", "fallback", "unsupported"})
FEATURE_STATUSES = frozenset(
    {"native", "pipeline", "fallback", "ignored", "rejected"}
)
_OPERATIONS_BY_MODEL_TYPE = {
    "audio_stt": "audio_transcription",
    "audio_tts": "audio_speech",
    "audio_processing": "audio_process",
}


class AudioCapabilitiesError(ValueError):
    pass


def _json_copy(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value))
    except (TypeError, ValueError) as exc:
        raise AudioCapabilitiesError("audio_capabilities must contain JSON values") from exc


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
        "formats": {"input": ["wav"] if model_type != "audio_tts" else [], "output": ["wav"]},
        "streaming": {"mode": "unsupported", "formats": []},
    }
    if model_type == "audio_stt":
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
    if (
        operation is None
        or not isinstance(operations, list)
        or operations != [operation]
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
    section_name = "stt" if model_type == "audio_stt" else "tts" if model_type == "audio_tts" else None
    if section_name is not None:
        section = normalized.get(section_name, {})
        if not isinstance(section, Mapping):
            raise AudioCapabilitiesError(f"audio_capabilities.{section_name} must be an object")
        normalized[section_name] = dict(section)
        for name, feature in section.items():
            normalized[section_name][name] = _feature(
                feature, field=f"audio_capabilities.{section_name}.{name}"
            )
    if model_type == "audio_tts":
        named = normalized.get("tts", {}).get("named_voices", {})
        voices = named.get("voices", [])
        if not isinstance(voices, list) or not all(
            isinstance(item, str) and 1 <= len(item) <= 128 for item in voices
        ):
            raise AudioCapabilitiesError("audio_capabilities.tts.named_voices.voices is invalid")
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
