# SPDX-License-Identifier: Apache-2.0
"""Trusted Host audio container and codec normalization.

Model Workers intentionally receive PCM WAV only.  The Host uses the PyAV
wheel bundled in the inference Runtime to decode untrusted uploads and encode
non-streaming speech responses without invoking an external executable.
"""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Final


INPUT_FORMATS: Final[tuple[str, ...]] = (
    "wav",
    "pcm",
    "mp3",
    "m4a",
    "aac",
    "flac",
    "ogg",
    "opus",
    "webm",
)
OUTPUT_FORMATS: Final[tuple[str, ...]] = (
    "wav",
    "pcm",
    "mp3",
    "m4a",
    "aac",
    "flac",
    "ogg",
    "opus",
    "webm",
)
OUTPUT_MEDIA_TYPES: Final[dict[str, str]] = {
    "wav": "audio/wav",
    "pcm": "audio/pcm",
    "mp3": "audio/mpeg",
    "m4a": "audio/mp4",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "ogg": "audio/ogg",
    "opus": "audio/ogg",
    "webm": "audio/webm",
}

_ENCODERS: Final[dict[str, tuple[str, str, str, int | None]]] = {
    "mp3": ("mp3", "libmp3lame", "fltp", None),
    "m4a": ("ipod", "aac", "fltp", None),
    "aac": ("adts", "aac", "fltp", None),
    "flac": ("flac", "flac", "s16", None),
    "ogg": ("ogg", "libopus", "fltp", 48_000),
    "opus": ("ogg", "libopus", "fltp", 48_000),
    "webm": ("webm", "libopus", "fltp", 48_000),
}
_MEDIA_TYPE_FORMATS: Final[dict[str, str]] = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/vnd.wave": "wav",
    "audio/pcm": "pcm",
    "audio/l16": "pcm",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/webm": "webm",
}


class AudioCodecError(ValueError):
    """Raised when an upload or requested output cannot be converted."""


def infer_audio_format(filename: str | None, media_type: str | None) -> str | None:
    """Resolve a supported format hint without trusting it as validation."""

    suffix = Path(filename or "").suffix.lower().lstrip(".")
    if suffix in INPUT_FORMATS:
        return suffix
    return _MEDIA_TYPE_FORMATS.get((media_type or "").split(";", 1)[0].lower())


def _pcm_to_wav(
    content: bytes,
    *,
    sample_rate: int,
    max_duration_seconds: float,
) -> bytes:
    if len(content) % 2:
        raise AudioCodecError("PCM input must contain complete signed 16-bit samples")
    if len(content) // 2 > sample_rate * max_duration_seconds:
        raise AudioCodecError("decoded audio exceeds the duration limit")
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(content)
    return output.getvalue()


def decode_audio_to_wav(
    content: bytes,
    *,
    input_format: str | None = None,
    sample_rate: int = 16_000,
    max_duration_seconds: float = 7_200,
) -> bytes:
    """Decode one supported upload to mono signed-16-bit PCM WAV."""

    normalized = (input_format or "").lower().lstrip(".")
    if normalized and normalized not in INPUT_FORMATS:
        raise AudioCodecError(f"unsupported input audio format: {normalized}")
    if normalized == "pcm":
        return _pcm_to_wav(
            content,
            sample_rate=sample_rate,
            max_duration_seconds=max_duration_seconds,
        )
    try:
        import av

        source = av.open(io.BytesIO(content), mode="r")
        stream = next((item for item in source.streams if item.type == "audio"), None)
        if stream is None:
            raise AudioCodecError("uploaded file contains no audio stream")
        resampler = av.AudioResampler(
            format="s16",
            layout="mono",
            rate=sample_rate,
        )
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setnchannels(1)
            target.setsampwidth(2)
            target.setframerate(sample_rate)
            decoded_samples = 0
            for frame in source.decode(stream):
                for converted in resampler.resample(frame):
                    decoded_samples += converted.samples
                    if decoded_samples > sample_rate * max_duration_seconds:
                        raise AudioCodecError(
                            "decoded audio exceeds the duration limit"
                        )
                    target.writeframesraw(
                        bytes(converted.planes[0])[: converted.samples * 2]
                    )
            for converted in resampler.resample(None):
                decoded_samples += converted.samples
                if decoded_samples > sample_rate * max_duration_seconds:
                    raise AudioCodecError("decoded audio exceeds the duration limit")
                target.writeframesraw(
                    bytes(converted.planes[0])[: converted.samples * 2]
                )
        source.close()
        result = output.getvalue()
        if len(result) <= 44:
            raise AudioCodecError("uploaded audio contains no decodable samples")
        return result
    except AudioCodecError:
        raise
    except Exception as exc:
        raise AudioCodecError(f"could not decode uploaded audio: {exc}") from exc


def encode_wav_audio(wav_bytes: bytes, response_format: str) -> bytes:
    """Encode native Worker WAV output into a supported response format."""

    normalized = response_format.lower()
    if normalized not in OUTPUT_FORMATS:
        raise AudioCodecError(f"unsupported output audio format: {normalized}")
    if normalized == "wav":
        return wav_bytes
    if normalized == "pcm":
        with wave.open(io.BytesIO(wav_bytes), "rb") as source:
            return source.readframes(source.getnframes())
    container_format, codec, sample_format, forced_rate = _ENCODERS[normalized]
    try:
        import av

        source = av.open(io.BytesIO(wav_bytes), mode="r")
        input_stream = next(
            (item for item in source.streams if item.type == "audio"), None
        )
        if input_stream is None:
            raise AudioCodecError("speech backend returned no audio stream")
        rate = forced_rate or input_stream.codec_context.sample_rate or 24_000
        output_buffer = io.BytesIO()
        output = av.open(output_buffer, mode="w", format=container_format)
        output_stream = output.add_stream(codec, rate=rate)
        output_stream.layout = "mono"
        resampler = av.AudioResampler(
            format=sample_format,
            layout="mono",
            rate=rate,
        )
        for frame in source.decode(input_stream):
            for converted in resampler.resample(frame):
                for packet in output_stream.encode(converted):
                    output.mux(packet)
        for converted in resampler.resample(None):
            for packet in output_stream.encode(converted):
                output.mux(packet)
        for packet in output_stream.encode(None):
            output.mux(packet)
        output.close()
        source.close()
        return output_buffer.getvalue()
    except AudioCodecError:
        raise
    except Exception as exc:
        raise AudioCodecError(f"could not encode {normalized} audio: {exc}") from exc
