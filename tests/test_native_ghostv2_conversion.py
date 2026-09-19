from __future__ import annotations

import numpy as np

from experiments.mlx_faceswap.native_ghostv2.convert import _fold_batch_norm


def test_fold_batch_norm_for_conv_output_channels() -> None:
    weight = np.arange(2 * 3 * 2 * 2, dtype=np.float32).reshape(2, 3, 2, 2)
    gamma = np.array([1.5, 0.5], dtype=np.float32)
    beta = np.array([-0.25, 0.75], dtype=np.float32)
    mean = np.array([0.2, -0.4], dtype=np.float32)
    variance = np.array([0.8, 1.2], dtype=np.float32)
    fused, bias = _fold_batch_norm(
        weight, gamma, beta, mean, variance, transposed=False
    )
    scale = gamma / np.sqrt(variance + 1e-5)
    np.testing.assert_allclose(fused, weight * scale[:, None, None, None])
    np.testing.assert_allclose(bias, beta - mean * scale)


def test_fold_batch_norm_for_transposed_conv_output_channels() -> None:
    weight = np.arange(3 * 2 * 2 * 2, dtype=np.float32).reshape(3, 2, 2, 2)
    gamma = np.array([1.5, 0.5], dtype=np.float32)
    beta = np.array([-0.25, 0.75], dtype=np.float32)
    mean = np.array([0.2, -0.4], dtype=np.float32)
    variance = np.array([0.8, 1.2], dtype=np.float32)
    fused, bias = _fold_batch_norm(
        weight, gamma, beta, mean, variance, transposed=True
    )
    scale = gamma / np.sqrt(variance + 1e-5)
    np.testing.assert_allclose(fused, weight * scale[None, :, None, None])
    np.testing.assert_allclose(bias, beta - mean * scale)
