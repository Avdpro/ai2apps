"""Deterministic MLX Euler sampler matching Seed-VC's conditional flow loop."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import mlx.core as mx

Estimator = Callable[[mx.array, mx.array, mx.array, mx.array, mx.array, mx.array], mx.array]


def solve_euler(
    estimator: Estimator,
    noise: mx.array,
    lengths: mx.array,
    prompt: mx.array,
    condition: mx.array,
    style: mx.array,
    *,
    steps: int,
    cfg_rate: float | Sequence[float] = 0.5,
    zero_prompt_condition: bool = False,
    random_voice: bool = False,
    sway_sampling: bool = False,
) -> mx.array:
    """Run the Seed-VC v1/v2 CFM Euler loop without Torch.

    A scalar ``cfg_rate`` preserves the v1 speaker/content CFG contract.  A
    two-item value selects Seed-VC v2's independent intelligibility and speaker
    guidance.  ``sway_sampling`` uses v2's cosine-warped time grid.
    """

    if steps < 1:
        raise ValueError("steps must be positive")
    if isinstance(cfg_rate, Sequence):
        if len(cfg_rate) != 2:
            raise ValueError("v2 cfg_rate must contain two values")
        text_rate, speaker_rate = (float(value) for value in cfg_rate)
        legacy_rate = None
        if text_rate < 0 or speaker_rate < 0:
            raise ValueError("cfg_rate values must be non-negative")
    else:
        legacy_rate = float(cfg_rate)
        text_rate = speaker_rate = legacy_rate
        if legacy_rate < 0:
            raise ValueError("cfg_rate must be non-negative")
    x = noise
    prompt_length = prompt.shape[-1]
    prompt_x = mx.zeros_like(x)
    prompt_x = mx.concatenate(
        (prompt[..., :prompt_length], prompt_x[..., prompt_length:]), axis=-1
    )
    x = mx.concatenate((mx.zeros_like(x[..., :prompt_length]), x[..., prompt_length:]), axis=-1)
    if zero_prompt_condition:
        condition = mx.concatenate(
            (
                mx.zeros_like(condition[:, :prompt_length]),
                condition[:, prompt_length:],
            ),
            axis=1,
        )
    times = mx.linspace(0.0, 1.0, steps + 1)
    if sway_sampling:
        times = 1.0 - mx.cos(mx.pi * 0.5 * times)
    for index in range(1, steps + 1):
        time = times[index - 1]
        delta = times[index] - time
        if legacy_rate is not None and legacy_rate > 0:
            batch = x.shape[0]
            derivative = estimator(
                mx.concatenate((x, x), axis=0),
                mx.concatenate((prompt_x, mx.zeros_like(prompt_x)), axis=0),
                mx.concatenate((lengths, lengths), axis=0),
                mx.full((batch * 2,), time),
                mx.concatenate((style, mx.zeros_like(style)), axis=0),
                mx.concatenate((condition, mx.zeros_like(condition)), axis=0),
            )
            conditional, unconditional = mx.split(derivative, 2, axis=0)
            derivative = (1 + legacy_rate) * conditional - legacy_rate * unconditional
        elif legacy_rate is not None:
            derivative = estimator(
                x, prompt_x, lengths, mx.full((x.shape[0],), time), style, condition
            )
        elif random_voice:
            derivative = estimator(
                mx.concatenate((x, x), axis=0),
                mx.concatenate((mx.zeros_like(prompt_x), mx.zeros_like(prompt_x)), axis=0),
                mx.concatenate((lengths, lengths), axis=0),
                mx.full((x.shape[0] * 2,), time),
                mx.concatenate((mx.zeros_like(style), mx.zeros_like(style)), axis=0),
                mx.concatenate((condition, mx.zeros_like(condition)), axis=0),
            )
            conditional, unconditional = mx.split(derivative, 2, axis=0)
            derivative = (1 + text_rate) * conditional - text_rate * unconditional
        elif text_rate == 0 and speaker_rate == 0:
            derivative = estimator(
                x, prompt_x, lengths, mx.full((x.shape[0],), time), style, condition
            )
        elif text_rate == 0:
            derivative = estimator(
                mx.concatenate((x, x), axis=0),
                mx.concatenate((prompt_x, mx.zeros_like(prompt_x)), axis=0),
                mx.concatenate((lengths, lengths), axis=0),
                mx.full((x.shape[0] * 2,), time),
                mx.concatenate((style, mx.zeros_like(style)), axis=0),
                mx.concatenate((condition, condition), axis=0),
            )
            conditional, content_only = mx.split(derivative, 2, axis=0)
            derivative = (1 + speaker_rate) * conditional - speaker_rate * content_only
        elif speaker_rate == 0:
            derivative = estimator(
                mx.concatenate((x, x), axis=0),
                mx.concatenate((prompt_x, mx.zeros_like(prompt_x)), axis=0),
                mx.concatenate((lengths, lengths), axis=0),
                mx.full((x.shape[0] * 2,), time),
                mx.concatenate((style, mx.zeros_like(style)), axis=0),
                mx.concatenate((condition, mx.zeros_like(condition)), axis=0),
            )
            conditional, unconditional = mx.split(derivative, 2, axis=0)
            derivative = (1 + text_rate) * conditional - text_rate * unconditional
        else:
            derivative = estimator(
                mx.concatenate((x, x, x), axis=0),
                mx.concatenate((prompt_x, mx.zeros_like(prompt_x), mx.zeros_like(prompt_x)), axis=0),
                mx.concatenate((lengths, lengths, lengths), axis=0),
                mx.full((x.shape[0] * 3,), time),
                mx.concatenate((style, mx.zeros_like(style), mx.zeros_like(style)), axis=0),
                mx.concatenate((condition, condition, mx.zeros_like(condition)), axis=0),
            )
            conditional, content_only, unconditional = mx.split(derivative, 3, axis=0)
            derivative = (
                (1 + text_rate + speaker_rate) * conditional
                - text_rate * unconditional
                - speaker_rate * content_only
            )
        x = x + delta * derivative
        x = mx.concatenate(
            (mx.zeros_like(x[..., :prompt_length]), x[..., prompt_length:]), axis=-1
        )
    return x
