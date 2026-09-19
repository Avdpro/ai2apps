from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.mlx_demucs.audio import AudioBuffer, read_audio
from experiments.mlx_demucs.backends import (
    OracleMaskBackend,
    _centered_chunk,
    _triangle_weight,
)
from experiments.mlx_demucs.benchmark import compose_fixture
from experiments.mlx_demucs.pipeline import SeparationConfig, separate_audio


def _audio(*, channels: int = 2, sample_rate: int = 8000, seconds: float = 1.0):
    times = np.arange(round(sample_rate * seconds), dtype=np.float32) / sample_rate
    mono = 0.2 * np.sin(2 * np.pi * 220 * times)
    return AudioBuffer(np.repeat(mono[None, :], channels, axis=0), sample_rate)


def test_two_stems_are_equal_length_and_reconstruct_exactly(tmp_path):
    audio = _audio()
    mask = np.linspace(0, 1, audio.frames, dtype=np.float32)
    backend = OracleMaskBackend(mask, audio.sample_rate, audio.channels)

    result = separate_audio(audio, tmp_path, backend=backend)

    assert [stem.type for stem in result.stems] == ["dialogue", "background"]
    assert all(stem.frames == audio.frames for stem in result.stems)
    assert result.metrics["reconstruction_max_error"] <= np.finfo(np.float32).eps
    payload = json.loads((tmp_path / "separation.json").read_text())
    assert payload["schema"] == "ai2apps.audio-separation-result/v1"
    feature = payload["features"]["source_separation"]
    assert feature["status"] == "pipeline"
    assert feature["requested"]["profile"] == "dialogue_background"
    assert feature["effective"]["derivation"]["background"] == (
        "mixture_minus_dialogue"
    )
    assert feature["preserves_timeline"] is True


def test_pipeline_adapts_mono_sample_rate_to_backend(tmp_path):
    audio = _audio(channels=1, sample_rate=8000, seconds=0.2)
    target_frames = round(audio.frames * 16000 / audio.sample_rate)
    backend = OracleMaskBackend(np.ones(target_frames), 16000, 2)

    result = separate_audio(audio, tmp_path, backend=backend)

    assert result.sample_rate == 16000
    assert result.channels == 2
    assert all(stem.frames == target_frames for stem in result.stems)


def test_backend_shape_change_fails_closed(tmp_path):
    audio = _audio()

    class BadBackend:
        name = "bad"
        model_name = "bad"
        sample_rate = audio.sample_rate
        channels = audio.channels

        def extract_vocals(self, value):
            return AudioBuffer(value.samples[:, :-1], value.sample_rate)

    with pytest.raises(ValueError, match="changed the audio shape"):
        separate_audio(audio, tmp_path, backend=BadBackend())


def test_pcm16_wav_round_trip_preserves_channels(tmp_path):
    audio = _audio(seconds=0.1)
    path = tmp_path / "stereo.wav"
    audio.write_wav(path, float32=False)

    decoded = read_audio(path)

    assert decoded.channels == 2
    assert decoded.sample_rate == audio.sample_rate
    assert decoded.samples.shape == audio.samples.shape
    assert np.max(np.abs(decoded.samples - audio.samples)) < 1e-4


def test_multichannel_input_is_rejected(tmp_path):
    audio = _audio(channels=3)
    backend = OracleMaskBackend(np.ones(audio.frames), audio.sample_rate, 2)

    with pytest.raises(ValueError, match="mono or stereo"):
        separate_audio(audio, tmp_path, backend=backend)


def test_synthetic_benchmark_fixture_is_deterministic_and_equal_length():
    clean = _audio(channels=1, seconds=0.3)
    target_frames = round(clean.frames * 16000 / clean.sample_rate)

    first = compose_fixture(clean, sample_rate=16000)
    second = compose_fixture(clean, sample_rate=16000)

    assert all(item.samples.shape == (2, target_frames) for item in first)
    assert np.array_equal(first[0].samples, second[0].samples)
    assert np.allclose(first[0].samples, first[1].samples + first[2].samples)


def test_triangle_weight_and_centered_tail_match_chunk_contract():
    weight = _triangle_weight(8)
    np.testing.assert_allclose(weight, [0.25, 0.5, 0.75, 1, 1, 0.75, 0.5, 0.25])
    values = np.arange(12, dtype=np.float32)[None, :]
    chunk, retained, available = _centered_chunk(values, 8, 8)
    assert available == 4
    np.testing.assert_array_equal(chunk, [[6, 7, 8, 9, 10, 11, 0, 0]])
    np.testing.assert_array_equal(chunk[..., retained], [[8, 9, 10, 11]])


def test_vocals_instrumental_profile_uses_stable_stem_names(tmp_path):
    audio = _audio()
    backend = OracleMaskBackend(np.full(audio.frames, 0.25), audio.sample_rate, 2)

    result = separate_audio(
        audio,
        tmp_path,
        backend=backend,
        config=SeparationConfig(profile="vocals_instrumental"),
    )

    assert [stem.type for stem in result.stems] == ["vocals", "instrumental"]
    assert result.features["source_separation"]["status"] == "pipeline"
    assert result.metrics["reconstruction_max_error"] <= np.finfo(np.float32).eps


def test_native_four_stem_profile_requires_exact_backend_sources(tmp_path):
    audio = _audio()
    backend = OracleMaskBackend(np.ones(audio.frames), audio.sample_rate, 2)

    with pytest.raises(ValueError, match="Backend sources"):
        separate_audio(
            audio,
            tmp_path,
            backend=backend,
            config=SeparationConfig(profile="music_4stem"),
        )
