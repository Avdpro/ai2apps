"""Meter final delivered media artifacts for multimodal Compute settlement."""

from __future__ import annotations

import io
import json
import math
import subprocess
import wave
from collections.abc import Iterable
from pathlib import Path

from PIL import Image


def wav_actual_usage(audio: bytes) -> dict[str, int]:
    try:
        with wave.open(io.BytesIO(audio), "rb") as value:
            frames, sample_rate = value.getnframes(), value.getframerate()
    except (EOFError, wave.Error) as error:
        raise ValueError("final TTS artifact is not a playable WAV") from error
    if frames <= 0 or sample_rate <= 0:
        raise ValueError("final TTS artifact is empty")
    return {"outputDurationMs": math.ceil(frames * 1000 / sample_rate)}


def image_actual_usage(images: Iterable[bytes]) -> dict[str, object]:
    count = 0
    pixels = 0
    for raw in images:
        try:
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
                image.verify()
        except (OSError, ValueError) as error:
            raise ValueError("final image artifact is invalid") from error
        if width <= 0 or height <= 0:
            raise ValueError("final image dimensions are invalid")
        count += 1
        pixels += width * height
    if count == 0:
        raise ValueError("at least one final image artifact is required")
    return {"outputPixels": str(pixels), "imageCount": count}


def video_actual_usage(paths: Iterable[Path]) -> dict[str, object]:
    count = 0
    pixel_milliseconds = 0
    audio_milliseconds = 0
    for path in paths:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
            check=False, capture_output=True, text=True, timeout=30,
        )
        if completed.returncode != 0:
            raise ValueError("final video artifact is not playable")
        try:
            probe = json.loads(completed.stdout)
            streams = probe["streams"]
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError("final video metadata is invalid") from error
        video = next((item for item in streams if item.get("codec_type") == "video"), None)
        if not isinstance(video, dict):
            raise ValueError("final artifact has no video track")
        width, height = int(video.get("width", 0)), int(video.get("height", 0))
        duration = video.get("duration") or probe.get("format", {}).get("duration")
        try:
            duration_ms = math.ceil(float(duration) * 1000)
        except (TypeError, ValueError) as error:
            raise ValueError("final video duration is invalid") from error
        if width <= 0 or height <= 0 or duration_ms <= 0:
            raise ValueError("final video dimensions or duration are invalid")
        pixel_milliseconds += width * height * duration_ms
        audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
        if isinstance(audio, dict):
            audio_duration = audio.get("duration") or duration
            audio_milliseconds += math.ceil(float(audio_duration) * 1000)
        count += 1
    if count == 0:
        raise ValueError("at least one final video artifact is required")
    return {
        "outputPixelMilliseconds": str(pixel_milliseconds),
        "videoCount": count,
        "audioDurationMs": str(audio_milliseconds),
    }
