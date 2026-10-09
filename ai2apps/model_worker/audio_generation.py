"""Versioned text-to-music / text-to-sound Worker request contracts."""
from __future__ import annotations

import math
from collections.abc import Mapping

from .protocol import ModelWorkerError

AUDIO_GENERATION_SCHEMA = "ai2apps.audio-generation/v1"
AUDIO_WORKFLOW_SCHEMA = "ai2apps.audio-generation/v2"


def validate_audio_generation(payload: Mapping, *, has_parts: bool = False) -> dict:
    """Validate text-only generation before admission to the adapter queue.

    Providers enforce their own narrower duration and feature limits. Reference
    audio, continuation and streaming require a future capability revision.
    """
    def fail(message):
        raise ModelWorkerError(message, code="invalid_audio_generation", status_code=400)

    schema = payload.get("schema", AUDIO_GENERATION_SCHEMA)
    if not isinstance(schema, str) or schema not in (AUDIO_GENERATION_SCHEMA, AUDIO_WORKFLOW_SCHEMA):
        fail("Unsupported audio generation schema")
    workflow = schema == AUDIO_WORKFLOW_SCHEMA
    allowed = {"model", "task", "prompt", "lyrics", "duration", "steps", "seed",
               "language", "output_format", "stream", "schema"}
    if workflow:
        allowed |= {"duration_mode", "generation"}
    if has_parts or set(payload) - allowed:
        fail("Unsupported audio generation fields or file inputs")
    result = dict(payload)
    for key, limit in (("model", 512), ("prompt", 2000)):
        value = result.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            fail(f"{key} must contain 1–{limit} characters")
    if not isinstance(result.get("task"), str) or result["task"] not in {"music", "sound_effects"}:
        fail("task must be music or sound_effects")
    lyrics = result.get("lyrics", "")
    if not isinstance(lyrics, str) or len(lyrics) > 4096:
        fail("lyrics must be a string of at most 4096 characters")
    if lyrics and result["task"] != "music":
        fail("Lyrics are only supported for music")
    duration_mode = result.get("duration_mode", "fixed")
    if not isinstance(duration_mode, str) or duration_mode not in {"fixed", "auto"}:
        fail("duration_mode must be fixed or auto")
    if duration_mode == "auto":
        if "duration" in result or result["task"] != "music":
            fail("Automatic duration requires music and an omitted duration")
    duration = result.get("duration")
    if duration_mode == "fixed" and (type(duration) not in (int, float) or not math.isfinite(duration) or not 1 <= duration <= 600):
        fail("duration must be a finite number in [1,600] seconds")
    for key, default, low, high in (("seed", 42, 0, 2**32 - 1), ("steps", 32 if workflow else 8, 1, 100)):
        value = result.get(key, default)
        if type(value) is not int or not low <= value <= high:
            fail(f"{key} must be an integer in [{low},{high}]")
        result[key] = value
    language = result.get("language", "unknown")
    if not isinstance(language, str) or not language or len(language) > 16 or not all(c.isascii() and (c.isalpha() or c == '-') for c in language):
        fail("language must be a short language tag")
    if result.get("stream", False) is not False:
        fail("Audio generation streaming is not supported")
    if result.get("output_format", "wav") != "wav":
        fail("Audio generation output_format must be wav")
    if workflow:
        generation = result.get("generation", {})
        if not isinstance(generation, dict) or set(generation) - {
            "planning_mode", "abc", "max_abc_tokens", "max_semantic_tokens", "guidance_scale"
        }:
            fail("Unsupported generation parameters")
        generation = dict(generation)
        mode = generation.get("planning_mode", "full")
        if not isinstance(mode, str) or mode not in {"full", "melody", "off"}:
            fail("planning_mode must be full, melody or off")
        if "abc" in generation:
            abc = generation["abc"]
            if not isinstance(abc, str) or not abc.strip() or len(abc.encode("utf-8")) > 131072 or mode == "off":
                fail("abc must be nonempty inline notation up to 128 KiB with planning enabled")
        for key, high in (("max_abc_tokens", 4096), ("max_semantic_tokens", 15000)):
            if key in generation and (type(generation[key]) is not int or not 1 <= generation[key] <= high):
                fail(f"{key} must be an integer in [1,{high}]")
        if "guidance_scale" in generation:
            scale = generation["guidance_scale"]
            if type(scale) not in (int, float) or not math.isfinite(scale) or not 1 <= scale <= 10:
                fail("guidance_scale must be a finite number in [1,10]")
        if result["task"] != "music" and generation:
            fail("Planning parameters require music")
        result.update(duration_mode=duration_mode, generation=generation)
    result.update(lyrics=lyrics, language=language, output_format="wav", stream=False)
    return result
