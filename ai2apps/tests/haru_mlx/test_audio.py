import io

import numpy as np
import pytest
import soundfile as sf

from ai2apps.model_worker.haru_mlx.audio import SAMPLE_RATE, decode_audio, load_audio, prepare_reference, save_audio, trim_silence


def tone(seconds: float, rate: int = SAMPLE_RATE, hz: float = 220.0) -> np.ndarray:
    t = np.arange(int(seconds * rate)) / rate
    return (0.3 * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def wav_bytes(audio: np.ndarray, rate: int) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, audio, rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


def test_decode_resamples_and_mixes_down():
    stereo = np.stack([tone(1.0, 48_000), tone(1.0, 48_000)], axis=1)
    audio = decode_audio(wav_bytes(stereo, 48_000))
    assert audio.dtype == np.float32 and audio.ndim == 1
    assert len(audio) == SAMPLE_RATE
    assert np.abs(audio).max() == pytest.approx(0.3, abs=0.02)


def test_decode_rejects_garbage():
    with pytest.raises(ValueError):
        decode_audio(b"this is not audio")


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "clip.wav"
    save_audio(path, tone(0.5))
    assert np.allclose(load_audio(path), tone(0.5), atol=1e-3)


def test_trim_silence_keeps_a_margin_around_speech():
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    audio = np.concatenate([silence, tone(1.0), silence])
    trimmed = trim_silence(audio)
    assert 1.0 <= len(trimmed) / SAMPLE_RATE <= 1.45
    assert len(trim_silence(silence)) == 0
    assert len(trim_silence(silence[:100])) == 100  # shorter than one analysis window


def test_prepare_reference_keeps_the_end():
    audio = np.concatenate([tone(2.0, hz=220.0), tone(2.0, hz=440.0)])
    reference = prepare_reference(audio, max_seconds=1.0)
    assert len(reference) == SAMPLE_RATE
    assert np.array_equal(reference, trim_silence(audio)[-SAMPLE_RATE:])
