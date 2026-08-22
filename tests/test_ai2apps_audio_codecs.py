# SPDX-License-Identifier: Apache-2.0
"""Real in-memory codec coverage for the inference Runtime."""

from __future__ import annotations

import io
import math
import struct
import wave

import av
import pytest

from ai2apps.audio_codecs import (
    AudioCodecError,
    decode_audio_to_wav,
    encode_wav_audio,
)


def _tone_wav(sample_rate: int = 24_000) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(
            b"".join(
                struct.pack(
                    "<h",
                    int(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate)),
                )
                for index in range(sample_rate // 10)
            )
        )
    return output.getvalue()


@pytest.mark.parametrize(
    "response_format", ["mp3", "m4a", "aac", "flac", "ogg", "opus", "webm"]
)
def test_compressed_outputs_decode_back_to_audio(response_format):
    encoded = encode_wav_audio(_tone_wav(), response_format)

    assert encoded
    container = av.open(io.BytesIO(encoded))
    frames = list(container.decode(audio=0))
    assert sum(frame.samples for frame in frames) > 0


@pytest.mark.parametrize(
    "input_format", ["mp3", "m4a", "aac", "flac", "ogg", "opus", "webm"]
)
def test_compressed_inputs_normalize_to_pcm_wav(input_format):
    encoded = encode_wav_audio(_tone_wav(), input_format)
    normalized = decode_audio_to_wav(
        encoded,
        input_format=input_format,
        sample_rate=16_000,
    )

    with wave.open(io.BytesIO(normalized), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 16_000
        assert audio.getnframes() > 0


def test_raw_pcm_is_wrapped_with_explicit_runtime_defaults():
    raw = b"\x01\x00" * 160
    normalized = decode_audio_to_wav(raw, input_format="pcm", sample_rate=16_000)
    with wave.open(io.BytesIO(normalized), "rb") as audio:
        assert audio.readframes(audio.getnframes()) == raw


def test_invalid_audio_is_rejected_before_worker_boundary():
    with pytest.raises(AudioCodecError, match="could not decode"):
        decode_audio_to_wav(b"not audio", input_format="mp3")


def test_decoded_duration_limit_rejects_pcm_expansion():
    with pytest.raises(AudioCodecError, match="duration limit"):
        decode_audio_to_wav(
            b"\x00\x00" * 161,
            input_format="pcm",
            sample_rate=160,
            max_duration_seconds=1,
        )
