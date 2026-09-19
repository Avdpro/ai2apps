import numpy as np
import pytest

from experiments.mlx_whisperx.audio import AudioBuffer
from experiments.mlx_whisperx.create_noisy_fixture import add_white_noise


def test_white_noise_fixture_is_deterministic_and_has_requested_snr():
    sample_rate = 16000
    time = np.arange(sample_rate, dtype=np.float32) / sample_rate
    source = AudioBuffer(np.sin(2 * np.pi * 440 * time) * 0.1, sample_rate)

    first = add_white_noise(source, snr_db=10.0, seed=7)
    second = add_white_noise(source, snr_db=10.0, seed=7)

    assert np.array_equal(first.samples, second.samples)
    noise = first.samples - source.samples
    measured = 20 * np.log10(
        np.sqrt(np.mean(source.samples**2)) / np.sqrt(np.mean(noise**2))
    )
    assert measured == pytest.approx(10.0, abs=0.05)
