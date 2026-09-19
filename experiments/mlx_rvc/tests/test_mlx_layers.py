from __future__ import annotations

import numpy as np
import pytest

from experiments.mlx_rvc.mlx_layers import (
    conv1d_nct,
    conv_transpose1d_nct,
    linear,
    weight_norm,
)


def test_weight_norm_materializes_pytorch_dim_zero_semantics():
    direction = np.arange(1, 13, dtype=np.float32).reshape(2, 2, 3)
    gain = np.array([[[2.0]], [[4.0]]], dtype=np.float32)
    result = weight_norm(gain, direction)
    norms = np.sqrt(np.sum(np.square(result), axis=(1, 2)))
    np.testing.assert_allclose(norms, [2.0, 4.0], rtol=1e-6)


def test_mlx_linear_and_convolutions_match_torch():
    torch = pytest.importorskip("torch")
    torch_f = pytest.importorskip("torch.nn.functional")
    mx = pytest.importorskip("mlx.core")
    rng = np.random.default_rng(9)

    values = rng.normal(size=(2, 5, 4)).astype(np.float32)
    linear_weight = rng.normal(size=(3, 4)).astype(np.float32)
    linear_bias = rng.normal(size=(3,)).astype(np.float32)
    expected_linear = torch_f.linear(
        torch.from_numpy(values),
        torch.from_numpy(linear_weight),
        torch.from_numpy(linear_bias),
    ).numpy()
    actual_linear = linear(
        mx.array(values), mx.array(linear_weight), mx.array(linear_bias)
    )

    signal = rng.normal(size=(1, 3, 13)).astype(np.float32)
    conv_weight = rng.normal(size=(5, 3, 3)).astype(np.float32)
    conv_bias = rng.normal(size=(5,)).astype(np.float32)
    expected_conv = torch_f.conv1d(
        torch.from_numpy(signal),
        torch.from_numpy(conv_weight),
        torch.from_numpy(conv_bias),
        padding=2,
        dilation=2,
    ).numpy()
    actual_conv = conv1d_nct(
        mx.array(signal),
        mx.array(conv_weight),
        mx.array(conv_bias),
        padding=2,
        dilation=2,
    )

    transpose_weight = rng.normal(size=(3, 2, 4)).astype(np.float32)
    transpose_bias = rng.normal(size=(2,)).astype(np.float32)
    expected_transpose = torch_f.conv_transpose1d(
        torch.from_numpy(signal),
        torch.from_numpy(transpose_weight),
        torch.from_numpy(transpose_bias),
        stride=2,
        padding=1,
    ).numpy()
    actual_transpose = conv_transpose1d_nct(
        mx.array(signal),
        mx.array(transpose_weight),
        mx.array(transpose_bias),
        stride=2,
        padding=1,
    )
    mx.eval(actual_linear, actual_conv, actual_transpose)

    for actual, expected in (
        (actual_linear, expected_linear),
        (actual_conv, expected_conv),
        (actual_transpose, expected_transpose),
    ):
        difference = np.asarray(actual) - expected
        peak_error = np.max(np.abs(difference)) / max(np.max(np.abs(expected)), 1e-12)
        relative_rmse = np.sqrt(np.mean(np.square(difference))) / max(
            np.sqrt(np.mean(np.square(expected))), 1e-12
        )
        assert peak_error < 0.01
        assert relative_rmse < 0.01
