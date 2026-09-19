import mlx.core as mx
import numpy as np
import pytest

from experiments.mlx_rvc.contentvec import normalize_audio


def test_normalize_audio_matches_expected_statistics():
    output = np.asarray(normalize_audio(mx.array([[1.0, 2.0, 3.0]], dtype=mx.float32)))
    np.testing.assert_allclose(output.mean(axis=-1), 0.0, atol=1e-6)
    np.testing.assert_allclose(np.mean(output**2, axis=-1), 1.0, atol=1e-6)


def test_normalize_audio_rejects_invalid_shape():
    with pytest.raises(ValueError, match="audio must have shape"):
        normalize_audio(mx.zeros((1, 2, 3)))
