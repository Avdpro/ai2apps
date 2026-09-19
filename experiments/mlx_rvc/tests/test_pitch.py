from __future__ import annotations

import numpy as np

from experiments.mlx_rvc.pitch import coarse_f0, interpolate_unvoiced


def test_unvoiced_frames_are_interpolated_like_rvc_pipeline():
    result = interpolate_unvoiced(np.array([100.0, 0.0, 0.0, 400.0], dtype=np.float32))
    np.testing.assert_allclose(result, [100.0, 200.0, 300.0, 400.0])


def test_coarse_pitch_is_bounded_and_semitone_shift_is_exact():
    coarse, continuous = coarse_f0(
        np.array([50.0, 100.0, 1100.0], dtype=np.float32), semitones=12
    )
    np.testing.assert_allclose(continuous, [100.0, 200.0, 2200.0])
    assert coarse.dtype == np.int32
    assert coarse.min() >= 1
    assert coarse.max() <= 255


def test_all_unvoiced_input_remains_finite():
    coarse, continuous = coarse_f0(np.zeros(5, dtype=np.float32))
    np.testing.assert_array_equal(coarse, np.ones(5, dtype=np.int32))
    np.testing.assert_array_equal(continuous, np.zeros(5, dtype=np.float32))
