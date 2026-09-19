from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import pytest

from experiments.mlx_whisperx.assignment import assign_speakers
from experiments.mlx_whisperx.backends import MLXWhisperBackend
from experiments.mlx_whisperx.pipeline import (
    MLXWhisperXPipeline,
    PipelineConfig,
    clip_segments,
    split_spans,
)
from experiments.mlx_whisperx.schema import DiarizationSpan, Segment, TimeSpan, Word
from experiments.mlx_whisperx.vad import EnergyVAD, FullAudioVAD


def _wav(path: Path, samples: np.ndarray, sample_rate: int = 16000) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(pcm.tobytes())


class FixedVAD:
    name = "fixed_vad"

    def detect(self, _audio):
        return [TimeSpan(1.0, 2.0), TimeSpan(3.0, 4.0)]


class FakeWhisper:
    name = "fake_mlx_whisper"

    def __init__(self):
        self.calls = 0

    def transcribe(self, _path, **_kwargs):
        self.calls += 1
        word = "hello" if self.calls == 1 else "world"
        return {
            "text": word,
            "language": "en",
            "segments": [
                {
                    "start": 0.1,
                    "end": 0.9,
                    "text": word,
                    "words": [
                        {
                            "word": word,
                            "start": 0.1,
                            "end": 0.9,
                            "probability": 0.9,
                        }
                    ],
                }
            ],
        }


class FakeWhisperWithEmptySegments:
    name = "fake_mlx_whisper"

    def transcribe(self, _path, **_kwargs):
        return {
            "text": "hello",
            "language": "en",
            "segments": [
                {"start": 0.1, "end": 0.9, "text": "hello"},
                {"start": 0.9, "end": 0.9, "text": ""},
                {"start": 0.9, "end": 1.0, "text": ""},
            ],
        }


class FakeDiarizer:
    name = "fake_mlx_sortformer"

    def diarize(self, _path):
        return [
            DiarizationSpan(0.5, 2.5, "speaker_0"),
            DiarizationSpan(2.5, 4.5, "speaker_1"),
        ]


class FakeAligner:
    name = "fake_mlx_ctc"
    alignment_method = "ctc_forced_alignment"
    min_word_score = 0.05

    def align(self, _path, segments, *, language):
        assert language == "en"
        for segment in segments:
            for word in segment.words:
                word.start += 0.01
                word.end += 0.01
        return segments


class FailingAligner:
    name = "failing_mlx_ctc"

    def align(self, _path, _segments, *, language):
        raise ValueError(f"unsupported language: {language}")


def test_pipeline_offsets_words_and_assigns_speakers(tmp_path: Path):
    audio = tmp_path / "four-seconds.wav"
    _wav(audio, np.zeros(4 * 16000, dtype=np.float32))
    transcript = MLXWhisperXPipeline(
        FakeWhisper(), vad=FixedVAD(), diarizer=FakeDiarizer()
    ).run(audio, config=PipelineConfig(word_timestamps=True))

    assert transcript.schema == "ai2apps.mlx-whisperx-result/v1"
    assert transcript.text == "hello world"
    assert transcript.language == "en"
    assert transcript.duration == 4.0
    assert [(item.start, item.end) for item in transcript.segments] == [
        (1.1, 1.9),
        (3.1, 3.9),
    ]
    assert transcript.segments[0].words[0].start == 1.1
    assert transcript.segments[0].speaker == "speaker_0"
    assert transcript.segments[1].speaker == "speaker_1"
    assert transcript.features["alignment"]["method"] == "native_attention"
    assert transcript.features["forced_alignment"]["status"] == "rejected"


def test_pipeline_reports_ctc_forced_alignment(tmp_path: Path):
    audio = tmp_path / "four-seconds.wav"
    _wav(audio, np.zeros(4 * 16000, dtype=np.float32))
    transcript = MLXWhisperXPipeline(
        FakeWhisper(), vad=FixedVAD(), aligner=FakeAligner()
    ).run(audio)
    assert transcript.segments[0].words[0].start == 1.11
    assert transcript.features["alignment"] == {
        "status": "pipeline",
        "provider": "fake_mlx_ctc",
        "method": "ctc_forced_alignment",
        "minimum_word_score": 0.05,
    }
    assert transcript.features["forced_alignment"]["status"] == "pipeline"


def test_explicit_native_alignment_fallback_is_reported(tmp_path: Path):
    audio = tmp_path / "four-seconds.wav"
    _wav(audio, np.zeros(4 * 16000, dtype=np.float32))
    transcript = MLXWhisperXPipeline(
        FakeWhisper(), vad=FixedVAD(), aligner=FailingAligner()
    ).run(audio, config=PipelineConfig(alignment_fallback="native"))
    assert transcript.features["alignment"]["status"] == "fallback"
    assert transcript.features["alignment"]["provider"] == "whisper_attention"
    assert transcript.features["forced_alignment"]["status"] == "rejected"


def test_energy_vad_finds_separated_tones(tmp_path: Path):
    sample_rate = 16000
    silence = np.zeros(sample_rate // 2, dtype=np.float32)
    t = np.arange(sample_rate // 2) / sample_rate
    tone = (0.2 * np.sin(2 * math.pi * 440 * t)).astype(np.float32)
    samples = np.concatenate([silence, tone, silence, tone, silence])
    path = tmp_path / "speech.wav"
    _wav(path, samples, sample_rate)

    from experiments.mlx_whisperx.audio import read_audio

    spans = EnergyVAD(pad_seconds=0.0, merge_gap_seconds=0.1).detect(
        read_audio(path)
    )
    assert len(spans) == 2
    assert 0.45 <= spans[0].start <= 0.55
    assert 0.95 <= spans[0].end <= 1.05
    assert 1.45 <= spans[1].start <= 1.55


def test_no_speech_returns_empty_transcript(tmp_path: Path):
    path = tmp_path / "silence.wav"
    _wav(path, np.zeros(16000, dtype=np.float32))
    transcript = MLXWhisperXPipeline(FakeWhisper(), vad=EnergyVAD()).run(path)
    assert transcript.text == ""
    assert transcript.segments == []


def test_pipeline_reads_granted_file_without_canonicalizing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    path = tmp_path / "one-second.wav"
    _wav(path, np.zeros(16000, dtype=np.float32))

    def reject_resolve(*_args, **_kwargs):
        raise PermissionError("parent directory is outside the sandbox grant")

    monkeypatch.setattr(Path, "resolve", reject_resolve)
    transcript = MLXWhisperXPipeline(FakeWhisper(), vad=FullAudioVAD()).run(path)
    assert transcript.text == "hello"


def test_long_vad_spans_are_hard_bounded_before_transcription():
    assert split_spans([TimeSpan(2.0, 67.0)], 30.0) == [
        TimeSpan(2.0, 32.0),
        TimeSpan(32.0, 62.0),
        TimeSpan(62.0, 67.0),
    ]
    with pytest.raises(ValueError, match="must be positive"):
        split_spans([TimeSpan(0.0, 1.0)], 0.0)


def test_pipeline_drops_empty_and_zero_duration_backend_segments(tmp_path: Path):
    path = tmp_path / "one-second.wav"
    _wav(path, np.zeros(16000, dtype=np.float32))
    transcript = MLXWhisperXPipeline(
        FakeWhisperWithEmptySegments(), vad=FullAudioVAD()
    ).run(path)
    assert len(transcript.segments) == 1
    assert transcript.segments[0].text == "hello"


def test_zero_duration_word_inherits_segment_speaker():
    segment = Segment(
        start=3.0,
        end=4.0,
        text="hello world",
        words=[
            Word("hello", start=3.0, end=3.0),
            Word("world", start=3.1, end=3.8),
        ],
    )
    assign_speakers(
        [segment], [DiarizationSpan(3.0, 4.0, speaker="speaker_1")]
    )
    assert segment.speaker == "speaker_1"
    assert [word.speaker for word in segment.words] == ["speaker_1", "speaker_1"]


def test_legacy_whisper_checkpoint_is_rejected_before_loading(tmp_path: Path):
    (tmp_path / "config.json").write_text('{"model_type":"whisper"}')
    backend = MLXWhisperBackend(str(tmp_path))
    with pytest.raises(ValueError, match="legacy mlx-examples"):
        backend._validate_local_checkpoint()


def test_sortformer_speaker_activity_is_unioned_for_vad():
    from experiments.mlx_whisperx.backends import MLXSortformerDiarizer

    spans = MLXSortformerDiarizer.speech_spans(
        [
            DiarizationSpan(0.0, 1.0, "speaker_0"),
            DiarizationSpan(0.8, 1.4, "speaker_1"),
            DiarizationSpan(1.5, 2.0, "speaker_0"),
            DiarizationSpan(3.0, 4.0, "speaker_1"),
        ]
    )
    assert spans == [TimeSpan(0.0, 2.0), TimeSpan(3.0, 4.0)]


def test_sortformer_windows_long_audio_and_scopes_speaker_ids():
    from types import SimpleNamespace

    from experiments.mlx_whisperx.audio import AudioBuffer
    from experiments.mlx_whisperx.backends import MLXSortformerDiarizer

    class FakeSortformer:
        def __init__(self):
            self.durations = []

        def generate(self, samples, *, sample_rate, **_kwargs):
            duration = len(samples) / sample_rate
            self.durations.append(duration)
            return SimpleNamespace(
                segments=[SimpleNamespace(start=0.1, end=duration, speaker=0)]
            )

    model = FakeSortformer()
    diarizer = MLXSortformerDiarizer(
        "unused", window_seconds=2.0, speaker_identity="window_local"
    )
    diarizer._model = model
    spans = diarizer._generate(AudioBuffer(np.zeros(5 * 16000), 16000))
    assert model.durations == [2.0, 2.0, 1.0]
    assert [(span.start, span.end, span.speaker) for span in spans] == [
        (0.1, 2.0, "window_0000_speaker_0"),
        (2.1, 4.0, "window_0001_speaker_0"),
        (4.1, 5.0, "window_0002_speaker_0"),
    ]


def test_global_speaker_spans_merge_across_streaming_chunks():
    from experiments.mlx_whisperx.backends import MLXSortformerDiarizer

    spans = MLXSortformerDiarizer._merge_same_speaker(
        [
            DiarizationSpan(0.0, 1.0, "speaker_0"),
            DiarizationSpan(1.05, 2.0, "speaker_0"),
            DiarizationSpan(0.5, 1.5, "speaker_1"),
        ]
    )
    assert [(span.start, span.end, span.speaker) for span in spans] == [
        (0.0, 2.0, "speaker_0"),
        (0.5, 1.5, "speaker_1"),
    ]


def test_sortformer_rejects_negative_speaker_bridge_gap():
    from experiments.mlx_whisperx.backends import MLXSortformerDiarizer

    with pytest.raises(ValueError, match="must be non-negative"):
        MLXSortformerDiarizer("unused", speaker_bridge_gap_seconds=-0.1)


def test_public_timeline_is_clipped_to_source_duration():
    segments = [
        Segment(
            -0.2,
            1.2,
            "valid",
            words=[Word("valid", start=-0.1, end=1.1)],
        ),
        Segment(1.1, 1.5, "hallucination", words=[Word("late", 1.1, 1.5)]),
    ]
    clipped = clip_segments(segments, duration=1.0)
    assert len(clipped) == 1
    assert (clipped[0].start, clipped[0].end) == (0.0, 1.0)
    assert (clipped[0].words[0].start, clipped[0].words[0].end) == (0.0, 1.0)
