"""Local, model-free media utilities used by Video Studio Mini-Apps."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import av

from ai2apps.video.tasks import VideoGenerationError

OUTPUT_SAMPLE_RATE = 48_000
OUTPUT_CHANNELS = 2
OUTPUT_SAMPLE_WIDTH = 2


def extract_audio_to_wav(source: Path, destination: Path) -> dict[str, Any]:
    """Decode the first audio stream into a broadly playable stereo PCM WAV."""

    samples_written = 0
    try:
        with av.open(str(source), mode="r") as container:
            if not container.streams.audio:
                raise VideoGenerationError(
                    "audio_track_not_found", "The selected video does not contain an audio track"
                )
            stream = container.streams.audio[0]
            resampler = av.AudioResampler(
                format="s16", layout="stereo", rate=OUTPUT_SAMPLE_RATE
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(destination), "wb") as output:
                output.setnchannels(OUTPUT_CHANNELS)
                output.setsampwidth(OUTPUT_SAMPLE_WIDTH)
                output.setframerate(OUTPUT_SAMPLE_RATE)
                for frame in container.decode(stream):
                    for converted in resampler.resample(frame):
                        byte_count = (
                            converted.samples * OUTPUT_CHANNELS * OUTPUT_SAMPLE_WIDTH
                        )
                        output.writeframes(bytes(converted.planes[0])[:byte_count])
                        samples_written += converted.samples
                for converted in resampler.resample(None):
                    byte_count = converted.samples * OUTPUT_CHANNELS * OUTPUT_SAMPLE_WIDTH
                    output.writeframes(bytes(converted.planes[0])[:byte_count])
                    samples_written += converted.samples
    except VideoGenerationError:
        raise
    except Exception as error:
        destination.unlink(missing_ok=True)
        raise VideoGenerationError(
            "audio_extraction_failed", "The video audio track could not be decoded"
        ) from error
    if samples_written <= 0:
        destination.unlink(missing_ok=True)
        raise VideoGenerationError(
            "audio_track_empty", "The selected video has an empty audio track"
        )
    return {
        "sampleRate": OUTPUT_SAMPLE_RATE,
        "channels": OUTPUT_CHANNELS,
        "sampleWidth": OUTPUT_SAMPLE_WIDTH,
        "durationSeconds": round(samples_written / OUTPUT_SAMPLE_RATE, 3),
        "samples": samples_written,
    }
