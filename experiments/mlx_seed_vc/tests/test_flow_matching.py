import mlx.core as mx
import numpy as np
import pytest

from experiments.mlx_seed_vc.flow_matching import solve_euler


def _estimator(x, prompt, lengths, time, style, condition):
    del lengths
    return (
        0.2 * x
        + 0.1 * prompt
        + 0.3 * condition.transpose(0, 2, 1)
        + style[:, :, None]
        + time[:, None, None]
    )


def test_euler_solver_is_deterministic_and_preserves_prompt_silence():
    noise = mx.ones((1, 2, 6))
    prompt = mx.ones((1, 2, 2))
    output = solve_euler(
        _estimator,
        noise,
        mx.array([6]),
        prompt,
        mx.ones((1, 6, 2)),
        mx.ones((1, 2)),
        steps=4,
        cfg_rate=0.7,
    )
    actual = np.asarray(output)
    np.testing.assert_array_equal(actual[..., :2], 0)
    assert np.isfinite(actual).all()
    assert np.any(actual[..., 2:] != 0)


def test_euler_solver_rejects_invalid_steps():
    with pytest.raises(ValueError, match="steps must be positive"):
        solve_euler(
            _estimator,
            mx.ones((1, 2, 1)),
            mx.array([2]),
            mx.zeros((1, 1, 0)),
            mx.ones((1, 1, 2)),
            mx.ones((1, 1)),
            steps=0,
        )


@pytest.mark.parametrize("rates", [(0.0, 0.0), (0.0, 0.6), (0.7, 0.0), (0.7, 0.6)])
def test_v2_guidance_branches_are_finite_and_preserve_prompt(rates):
    output = solve_euler(
        _estimator,
        mx.ones((1, 2, 6)),
        mx.array([6]),
        mx.ones((1, 2, 2)),
        mx.ones((1, 6, 2)),
        mx.ones((1, 2)),
        steps=4,
        cfg_rate=rates,
        sway_sampling=True,
    )
    actual = np.asarray(output)
    np.testing.assert_array_equal(actual[..., :2], 0)
    assert np.isfinite(actual).all()


def test_v2_cfg_requires_two_rates():
    with pytest.raises(ValueError, match="two values"):
        solve_euler(
            _estimator,
            mx.ones((1, 2, 2)),
            mx.array([2]),
            mx.zeros((1, 2, 0)),
            mx.ones((1, 2, 2)),
            mx.ones((1, 2)),
            steps=2,
            cfg_rate=(0.5,),
        )
