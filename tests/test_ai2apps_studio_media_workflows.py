from __future__ import annotations

import io
from fractions import Fraction

import av
import numpy as np
import pytest
import soundfile as sf

from ai2apps.studio.media_workflows import (
    StudioMediaError,
    burn_subtitles,
    mix_replaced_speaker,
    render_subtitles,
    replace_video_audio,
    speaker_conversion_source,
    validate_video_media,
)

SEGMENTS = [
    {"start": 0.0, "end": 0.6, "text": "Hello", "speaker": "SPEAKER_00"},
    {"start": 0.6, "end": 1.0, "text": "World", "speaker": "SPEAKER_01"},
]


def _video(*, audio: bool = True) -> bytes:
    destination = io.BytesIO()
    with av.open(destination, mode="w", format="mp4") as container:
        video = container.add_stream("libx264", rate=10)
        video.width = 160
        video.height = 90
        video.pix_fmt = "yuv420p"
        stream = None
        if audio:
            stream = container.add_stream("aac", rate=16_000)
            stream.layout = "mono"
        for index in range(10):
            pixels = np.full((90, 160, 3), 30 + index, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(pixels, format="rgb24")
            frame.pts = index
            frame.time_base = Fraction(1, 10)
            for packet in video.encode(frame):
                container.mux(packet)
        for packet in video.encode(None):
            container.mux(packet)
        if stream is not None:
            samples = np.zeros((1, 16_000), dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
            frame.sample_rate = 16_000
            frame.pts = 0
            frame.time_base = Fraction(1, 16_000)
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)
    return destination.getvalue()


@pytest.mark.parametrize("output_format", ["srt", "vtt", "ass"])
def test_render_subtitles_preserves_timing_translation_and_speakers(output_format):
    result = render_subtitles(
        SEGMENTS,
        output_format=output_format,
        translations=["你好", "世界"],
        bilingual=True,
        speaker_names={"SPEAKER_00": "Alice"},
    ).decode("utf-8-sig")

    assert "Hello" in result
    assert "你好" in result
    assert "Alice" in result
    assert "00:00:00" in result


def test_validate_video_media_requires_video_and_audio_tracks():
    validate_video_media(_video())

    with pytest.raises(StudioMediaError) as error:
        validate_video_media(_video(audio=False))
    assert error.value.code == "audio_track_not_found"


def test_burn_subtitles_outputs_playable_mp4_with_audio():
    result = burn_subtitles(_video(), SEGMENTS)

    with av.open(io.BytesIO(result), mode="r") as container:
        assert len(container.streams.video) == 1
        assert len(container.streams.audio) == 1
        assert sum(1 for _frame in container.decode(video=0)) == 10


def _wav(values: np.ndarray, rate: int = 1_000) -> bytes:
    output = io.BytesIO()
    sf.write(output, values, rate, format="WAV", subtype="PCM_16")
    return output.getvalue()


def test_speaker_conversion_source_masks_non_target_timeline():
    dialogue = _wav(np.full((1_000, 2), 0.25, dtype=np.float32))
    segments = [
        {"start": 0.2, "end": 0.6, "speaker": "SPEAKER_00"},
        {"start": 0.6, "end": 0.9, "speaker": "SPEAKER_01"},
    ]

    source, rate = sf.read(
        io.BytesIO(
            speaker_conversion_source(
                dialogue, segments, target_speaker="SPEAKER_00"
            )
        ),
        dtype="float32",
    )

    assert rate == 48_000
    assert abs(source[19_200] - 0.25) < 0.01
    assert abs(source[33_600]) < 0.01


def test_mix_replaced_speaker_preserves_background_and_other_speakers():
    dialogue = _wav(np.full((1_000, 2), 0.2, dtype=np.float32))
    background = _wav(np.full((1_000, 2), 0.1, dtype=np.float32))
    converted = _wav(np.full(1_000, 0.6, dtype=np.float32))
    segments = [{"start": 0.2, "end": 0.6, "speaker": "SPEAKER_00"}]

    mixed, rate = sf.read(
        io.BytesIO(
            mix_replaced_speaker(
                dialogue,
                background,
                converted,
                segments,
                target_speaker="SPEAKER_00",
            )
        ),
        dtype="float32",
        always_2d=True,
    )

    assert rate == 48_000
    assert np.allclose(mixed[4_800], 0.3, atol=0.01)
    assert np.all(mixed[19_200] > 0.5)
    assert np.allclose(mixed[38_400], 0.3, atol=0.01)


def test_replace_video_audio_outputs_playable_mp4():
    replacement = _wav(np.zeros((48_000, 1), dtype=np.float32), rate=48_000)
    result = replace_video_audio(_video(), replacement)

    with av.open(io.BytesIO(result), mode="r") as container:
        assert len(container.streams.video) == 1
        assert len(container.streams.audio) == 1
        assert sum(1 for _frame in container.decode(video=0)) == 10
