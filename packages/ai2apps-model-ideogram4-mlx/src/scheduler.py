"""Torch-free Ideogram 4 logit-normal inference schedule."""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np


def schedule_for_resolution(
    num_steps: int,
    height: int,
    width: int,
    *,
    known_mean: float,
    std: float = 1.0,
) -> np.ndarray:
    if num_steps <= 0:
        raise ValueError("num_steps must be positive")
    mean = known_mean + 0.5 * math.log((height * width) / (512 * 512))
    probabilities = np.linspace(0.0, 1.0, num_steps + 1, dtype=np.float64)
    probabilities = np.clip(probabilities, 1e-12, 1.0 - 1e-12)
    normal = NormalDist()
    z = np.fromiter((normal.inv_cdf(float(p)) for p in probabilities), dtype=np.float64)
    transformed = 1.0 / (1.0 + np.exp(mean + std * z))
    t_min = 1.0 / (1.0 + math.exp(0.5 * 18.0))
    t_max = 1.0 / (1.0 + math.exp(0.5 * -15.0))
    return np.clip(transformed, t_min, t_max).astype(np.float32)


def steps_for_strength(num_steps: int, strength: float) -> int:
    if num_steps <= 0:
        raise ValueError("num_steps must be positive")
    if not 0.0 < strength <= 1.0:
        raise ValueError("strength must be greater than 0 and at most 1")
    return max(1, min(num_steps, math.ceil(num_steps * strength)))
