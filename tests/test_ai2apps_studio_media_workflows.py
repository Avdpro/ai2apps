from __future__ import annotations

import io
from fractions import Fraction

import av
import numpy as np
import pytest
import soundfile as sf
from PIL import Image, ImageDraw

from ai2apps.studio.media_workflows import (
    StudioMediaError,
    _caption_layout,
    _caption_stroke_width,
    _draw_caption,
    audio_duration,
    burn_subtitles,
    mix_dubbed_segments,
    mix_replaced_speaker,
    render_subtitles,
    replace_video_audio,
    select_voice_clone_reference,
    speaker_conversion_source,
    split_subtitle_segments,
    validate_video_media,
)

SEGMENTS = [
    {"start": 0.0, "end": 0.6, "text": "Hello", "speaker": "SPEAKER_00"},
    {"start": 0.6, "end": 1.0, "text": "World", "speaker": "SPEAKER_01"},
]


def _wav48(samples: np.ndarray, rate: int = 48_000) -> bytes:
    output = io.BytesIO()
    sf.write(output, samples, rate, format="WAV", subtype="PCM_16")
    return output.getvalue()


def test_mix_dubbed_segments_preserves_background_and_places_narration_on_timeline():
    background = np.full((48_000, 2), 0.02, dtype=np.float32)
    speech = np.full((4_800, 1), 0.2, dtype=np.float32)

    result = mix_dubbed_segments(
        _wav48(background),
        [_wav48(speech)],
        [{"start": 0.5, "end": 0.8, "text": "你好。"}],
    )
    mixed, rate = sf.read(io.BytesIO(result), dtype="float32", always_2d=True)

    assert rate == 48_000
    assert mixed.shape == background.shape
    assert np.allclose(mixed[:20_000], 0.02, atol=0.002)
    assert float(mixed[25_000:27_000].mean()) > 0.1


def test_voice_clone_reference_prefers_dense_window_near_ten_seconds():
    audio = np.zeros((20_000, 1), dtype=np.float32)
    audio[2_000:12_000] = 0.12
    segments = [
        {"start": 0.0, "end": 1.0, "text": "quiet"},
        {"start": 2.0, "end": 6.5, "text": "clear first sentence"},
        {"start": 6.5, "end": 12.0, "text": "clear second sentence"},
        {"start": 17.0, "end": 18.0, "text": "late"},
    ]

    reference, text, metadata = select_voice_clone_reference(
        _wav(audio), segments, target_seconds=10, min_seconds=2, max_seconds=12
    )

    assert text == "clear first sentence clear second sentence"
    assert metadata["start"] == 2.0
    assert metadata["end"] == 12.0
    assert audio_duration(reference) == pytest.approx(10.0, abs=0.02)


def test_mix_dubbed_segments_rejects_mismatched_counts():
    with pytest.raises(StudioMediaError, match="segment count"):
        mix_dubbed_segments(
            _wav48(np.zeros((4_800, 2), dtype=np.float32)), [], SEGMENTS
        )


def test_mix_dubbed_segments_fits_each_clip_to_its_own_timeline_window():
    background = np.zeros((48_000, 2), dtype=np.float32)
    long_speech = np.full((28_800, 1), 0.2, dtype=np.float32)
    next_speech = np.full((4_800, 1), 0.4, dtype=np.float32)

    result = mix_dubbed_segments(
        _wav48(background),
        [_wav48(long_speech), _wav48(next_speech)],
        [
            {"start": 0.0, "end": 0.25, "text": "第一句"},
            {"start": 0.30, "end": 0.50, "text": "第二句"},
        ],
    )
    mixed, _rate = sf.read(io.BytesIO(result), dtype="float32", always_2d=True)

    assert float(np.max(np.abs(mixed[12_500:14_000]))) < 0.002
    assert float(mixed[15_500:18_000].mean()) > 0.2


def test_mix_dubbed_segments_compresses_overflow_without_raising_pitch():
    rate = 48_000
    timeline = np.arange(rate, dtype=np.float32) / rate
    speech = (0.25 * np.sin(2 * np.pi * 440 * timeline))[:, None]

    result = mix_dubbed_segments(
        _wav48(np.zeros((rate, 2), dtype=np.float32)),
        [_wav48(speech)],
        [{"start": 0.0, "end": 0.5, "text": "A long sentence."}],
    )
    mixed, _rate = sf.read(io.BytesIO(result), dtype="float32", always_2d=True)
    sample = mixed[2_000:22_000, 0]
    frequencies = np.fft.rfftfreq(len(sample), 1 / rate)
    dominant = frequencies[np.argmax(np.abs(np.fft.rfft(sample)))]

    assert dominant == pytest.approx(440, abs=20)
    assert float(np.max(np.abs(mixed[24_500:]))) < 0.002


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


def test_split_subtitle_segments_limits_cue_duration_and_text_size():
    segments = [
        {
            "start": 0.0,
            "end": 12.0,
            "text": "这是一个很长的字幕段落，需要跟随语音拆成容易阅读的短句，而不是一次占满整个画面。",
            "speaker": "SPEAKER_00",
        }
    ]

    cues = split_subtitle_segments(segments)

    assert len(cues) >= 2
    assert all(cue["end"] - cue["start"] <= 5.61 for cue in cues)
    assert all(len(cue["text"]) <= 28 for cue in cues)
    assert all(cue["text"][-1] in "，。！？" for cue in cues)
    assert all(cue["speaker"] == "SPEAKER_00" for cue in cues)
    assert "".join(cue["text"] for cue in cues) == segments[0]["text"]


def test_split_subtitle_segments_uses_word_timestamps_when_available():
    words = [
        {"word": word, "start": index * 0.7, "end": (index + 1) * 0.7}
        for index, word in enumerate(
            [
                "You",
                "should",
                "only",
                "see",
                "a",
                "few",
                "seconds",
                "of",
                "dialogue",
                "in",
                "each",
                "subtitle",
                "cue",
            ]
        )
    ]
    cues = split_subtitle_segments(
        [
            {
                "start": 0.0,
                "end": 9.1,
                "text": (
                    "You should only see a few seconds of dialogue. "
                    "Each subtitle cue should feel complete."
                ),
                "words": words,
            }
        ]
    )

    assert len(cues) >= 2
    assert all(cue["end"] - cue["start"] <= 5.61 for cue in cues)
    assert all(cue["text"][-1] in ".!?" for cue in cues)
    assert [word for cue in cues for word in cue["words"]] == words


def test_caption_layout_stays_inside_safe_frame_and_uses_two_lines():
    image = Image.new("RGB", (640, 360))
    draw = ImageDraw.Draw(image)
    caption, font, box, x, y, padding = _caption_layout(
        draw,
        "A readable subtitle should wrap without crossing either edge of the video frame.",
        width=640,
        height=360,
    )
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]

    assert caption.count("\n") <= 1
    assert x - padding >= 0
    assert x + text_width + padding <= 640
    assert y - padding >= 0
    assert y + text_height + padding <= 360
    assert font is not None


def test_caption_uses_white_text_with_thick_black_outline_and_no_backdrop():
    background = (73, 109, 151)
    image = Image.new("RGB", (640, 360), background)
    draw = ImageDraw.Draw(image)
    caption, font, box, x, y, stroke_width = _caption_layout(
        draw, "Outlined subtitle", width=640, height=360
    )

    assert stroke_width == _caption_stroke_width(font)
    assert stroke_width >= 3
    _draw_caption(image, caption, width=640, height=360)

    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    pixels = np.asarray(
        image.crop(
            (
                max(0, x - stroke_width),
                max(0, y - stroke_width),
                min(640, x + text_width + stroke_width),
                min(360, y + text_height + stroke_width),
            )
        )
    )
    assert np.any(np.all(pixels >= 245, axis=2))
    assert np.any(np.all(pixels <= 10, axis=2))
    assert image.getpixel((x - stroke_width, y - stroke_width)) == background


@pytest.mark.parametrize("font_size", ["small", "medium", "large", "extra_large"])
@pytest.mark.parametrize("background_style", ["outline", "box"])
def test_caption_size_and_background_options_stay_inside_safe_frame(
    font_size, background_style
):
    image = Image.new("RGB", (640, 360), (73, 109, 151))
    draw = ImageDraw.Draw(image)
    caption, font, box, x, y, padding = _caption_layout(
        draw,
        "字幕字号变化后仍然需要在安全区域内正确换行。",
        width=640,
        height=360,
        font_size=font_size,
        background_style=background_style,
    )

    assert caption.count("\n") <= 1
    assert x - padding >= 0
    assert x + (box[2] - box[0]) + padding <= 640
    assert y - padding >= 0
    assert y + (box[3] - box[1]) + padding <= 360
    assert font is not None


def test_extra_large_caption_is_larger_than_small_caption():
    image = Image.new("RGB", (1280, 720))
    draw = ImageDraw.Draw(image)

    small = _caption_layout(
        draw, "Short caption", width=1280, height=720, font_size="small"
    )[1]
    extra_large = _caption_layout(
        draw, "Short caption", width=1280, height=720, font_size="extra_large"
    )[1]

    assert extra_large.size > small.size


def test_caption_box_uses_a_translucent_backdrop():
    background = (80, 120, 160)
    image = Image.new("RGB", (640, 360), background)
    draw = ImageDraw.Draw(image)
    _caption, _font_value, box, x, y, padding = _caption_layout(
        draw,
        "Box subtitle",
        width=640,
        height=360,
        background_style="box",
    )

    _draw_caption(
        image,
        "Box subtitle",
        width=640,
        height=360,
        background_style="box",
    )

    sample = image.getpixel((x - max(1, padding // 2), y + (box[3] - box[1]) // 2))
    assert sample != background
    assert sample != (0, 0, 0)
    assert all(sample[index] < background[index] for index in range(3))


def test_validate_video_media_requires_video_and_audio_tracks():
    validate_video_media(_video())

    with pytest.raises(StudioMediaError) as error:
        validate_video_media(_video(audio=False))
    assert error.value.code == "audio_track_not_found"


def test_burn_subtitles_outputs_playable_mp4_with_audio():
    progress = []
    result = burn_subtitles(_video(), SEGMENTS, progress=progress.append)

    with av.open(io.BytesIO(result), mode="r") as container:
        assert len(container.streams.video) == 1
        assert len(container.streams.audio) == 1
        assert sum(1 for _frame in container.decode(video=0)) == 10
    assert progress[0] == 0
    assert progress[-1] == 100
    assert progress == sorted(progress)
    assert any(0 < value < 95 for value in progress)


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
            speaker_conversion_source(dialogue, segments, target_speaker="SPEAKER_00")
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
