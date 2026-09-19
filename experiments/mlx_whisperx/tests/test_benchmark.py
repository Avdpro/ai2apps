from __future__ import annotations

import numpy as np
import pytest

from experiments.mlx_whisperx.audio import AudioBuffer
from experiments.mlx_whisperx.backends import (
    MLXQwen3ASRBackend,
    _primary_language,
    _qwen_language,
)
from experiments.mlx_whisperx.benchmark import (
    edit_distance,
    file_sha256,
    load_cases,
    normalize_units,
)
from experiments.mlx_whisperx.compose_long_audio import compose


def test_english_normalization_produces_word_units():
    assert normalize_units("Hello, WORLD! It's ready.", "en-US") == [
        "hello",
        "world",
        "it's",
        "ready",
    ]


def test_chinese_normalization_produces_character_units():
    assert normalize_units("“这 并不是，告别。”", "zh-CN") == list(
        "这并不是告别"
    )


def test_edit_distance_handles_insert_delete_and_substitute():
    assert edit_distance(list("kitten"), list("sitting")) == 3
    assert edit_distance([], ["extra"]) == 1
    assert edit_distance(["missing"], []) == 1


def test_benchmark_normalization_rejects_unconfigured_language():
    with pytest.raises(ValueError, match="Unsupported benchmark language"):
        normalize_units("bonjour", "fr")


def test_file_sha256_is_stable(tmp_path):
    fixture = tmp_path / "fixture.bin"
    fixture.write_bytes(b"mlx-whisperx")
    assert file_sha256(fixture) == (
        "d9d207eb5f82a95117c5f644a9d7ba63759589a11887d44f8a08e0873eb22831"
    )


@pytest.mark.parametrize(
    ("provided", "expected"),
    [("zh-CN", "zh"), ("en_US", "en"), (" EN ", "en")],
)
def test_backend_normalizes_bcp47_language_to_whisper_primary_code(
    provided, expected
):
    assert _primary_language(provided) == expected


@pytest.mark.parametrize(
    ("provided", "expected"),
    [("zh-CN", "Chinese"), ("en_US", "English"), ("yue-HK", "Cantonese")],
)
def test_backend_normalizes_bcp47_language_for_qwen(provided, expected):
    assert _qwen_language(provided) == expected


def test_qwen_backend_maps_prompt_and_flattens_result_language():
    from types import SimpleNamespace

    class FakeQwen:
        def __init__(self):
            self.kwargs = None

        def generate(self, _path, **kwargs):
            self.kwargs = kwargs
            return SimpleNamespace(
                text="你好。",
                language=["Chinese"],
                segments=[{"start": 0.0, "end": 1.0, "text": "你好。"}],
            )

    model = FakeQwen()
    backend = MLXQwen3ASRBackend("unused")
    backend._model = model
    result = backend.transcribe(
        "unused.wav",
        language="zh-CN",
        prompt="术语：通义千问",
        word_timestamps=False,
    )
    assert result["text"] == "你好。"
    assert result["language"] == "Chinese"
    assert model.kwargs == {
        "verbose": False,
        "temperature": 0.0,
        "language": "Chinese",
        "system_prompt": "术语：通义千问",
    }


def test_load_cases_expands_and_verifies_transcript_manifest(tmp_path):
    transcript = tmp_path / "zh.trans.txt"
    transcript.write_text("sample_0000 你 好 世 界\n", encoding="utf-8")
    manifest = {
        "language": "zh-CN",
        "expected_cases": 1,
        "transcript": {
            "path": "zh.trans.txt",
            "sha256": file_sha256(transcript),
            "audio_directory": "zh",
        },
    }
    assert load_cases(manifest, tmp_path) == [
        {
            "id": "sample_0000",
            "language": "zh-CN",
            "audio": "zh/sample_0000.wav",
            "reference": "你 好 世 界",
        }
    ]


def test_compose_long_audio_repeats_whole_cases_with_silence(tmp_path):
    audio_path = tmp_path / "sample.wav"
    AudioBuffer(np.ones(1600, dtype=np.float32) * 0.25, 16000).write_wav(audio_path)
    audio, sequence = compose(
        cases=[{"id": "sample", "audio": "sample.wav", "reference": "hello"}],
        audio_root=tmp_path,
        duration_seconds=0.25,
        silence_seconds=0.05,
    )
    assert audio.duration == pytest.approx(0.3)
    assert [item["id"] for item in sequence] == ["sample", "sample"]
    assert sequence[1]["start"] == pytest.approx(0.15)
