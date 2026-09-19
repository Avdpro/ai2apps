from __future__ import annotations

import mlx.core as mx
import pytest
from mlx_rvc.training import (
    adversarial_generator_loss,
    discriminator_loss,
    feature_matching_loss,
    log_mel_l1_loss,
    mel_filterbank,
    multi_resolution_spectral_loss,
)
from mlx_rvc.voice_training import (
    VoiceTrainingConfig,
    _extract_tree,
    _prefixed_arrays,
    _spectrogram,
)


def test_training_losses_have_expected_zero_and_positive_cases():
    waveform = mx.linspace(-0.5, 0.5, 4096)[None, None]
    spectral = multi_resolution_spectral_loss(waveform, waveform)
    discriminator = discriminator_loss([mx.ones((1, 4))], [mx.zeros((1, 4))])
    generator = adversarial_generator_loss([mx.zeros((1, 4))])
    features = feature_matching_loss([[mx.ones((1, 2))]], [[mx.zeros((1, 2))]])
    mx.eval(spectral, discriminator, generator, features)
    assert float(spectral.item()) == pytest.approx(0.0, abs=1e-7)
    assert float(discriminator.item()) == pytest.approx(0.0)
    assert float(generator.item()) == pytest.approx(1.0)
    assert float(features.item()) == pytest.approx(2.0)


def test_rvc_mel_filterbank_has_expected_shape_and_energy():
    basis = mel_filterbank()
    mx.eval(basis)
    assert basis.shape == (128, 1025)
    assert float(mx.min(basis).item()) >= 0.0
    assert float(mx.max(basis).item()) > 0.0


def test_log_mel_loss_is_zero_for_matching_spectrogram_and_waveform():
    waveform = mx.sin(mx.arange(17_280, dtype=mx.float32) * 0.031)[None, None]
    spectrogram = _spectrogram(waveform.reshape((-1,)))[None]
    loss = log_mel_l1_loss(spectrogram, waveform)
    mx.eval(loss)
    assert float(loss.item()) == pytest.approx(0.0, abs=2e-5)


def test_native_spectrogram_keeps_one_frame_per_10ms():
    result = _spectrogram(mx.zeros((48_000,), dtype=mx.float32))
    assert result.shape == (1025, 100)


def test_voice_training_config_rejects_invalid_precision():
    with pytest.raises(ValueError, match="optimizer"):
        VoiceTrainingConfig(precision="float64").validate()


def test_voice_training_config_accepts_float16():
    VoiceTrainingConfig(precision="float16").validate()


def test_resume_state_round_trips_parameter_names_containing_dots():
    state = {
        "decoder_weights": {
            "dec.conv_pre.weight": mx.array([1.0, 2.0]),
        },
        "step": mx.array(7, dtype=mx.uint64),
    }
    encoded = _prefixed_arrays("optimizer", state)
    restored = _extract_tree(encoded, "optimizer")
    assert set(encoded) == {
        "optimizer/decoder_weights/dec.conv_pre.weight",
        "optimizer/step",
    }
    assert mx.array_equal(
        restored["decoder_weights"]["dec.conv_pre.weight"],
        state["decoder_weights"]["dec.conv_pre.weight"],
    )
    assert int(restored["step"].item()) == 7
