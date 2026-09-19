"""RVC-compatible continuous-to-coarse pitch conversion."""

from __future__ import annotations

import numpy as np

F0_MIN = 50.0
F0_MAX = 1100.0
COARSE_MIN = 1
COARSE_MAX = 255


def interpolate_unvoiced(f0: np.ndarray) -> np.ndarray:
    values = np.asarray(f0, dtype=np.float32).copy()
    if values.ndim != 1:
        raise ValueError("f0 must be one-dimensional")
    voiced = np.isfinite(values) & (values > 0)
    if voiced.any() and not voiced.all():
        positions = np.arange(values.size)
        values[~voiced] = np.interp(
            positions[~voiced], positions[voiced], values[voiced]
        )
    elif not voiced.any():
        values.fill(0)
    return values


def coarse_f0(f0: np.ndarray, semitones: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Return the 1..255 RVC pitch bins and shifted continuous F0."""

    continuous = interpolate_unvoiced(f0)
    continuous *= np.float32(2.0 ** (float(semitones) / 12.0))
    mel = 1127.0 * np.log1p(continuous / 700.0)
    mel_min = 1127.0 * np.log1p(F0_MIN / 700.0)
    mel_max = 1127.0 * np.log1p(F0_MAX / 700.0)
    positive = mel > 0
    mel[positive] = (mel[positive] - mel_min) * 254.0 / (mel_max - mel_min) + 1.0
    coarse = np.rint(np.clip(mel, COARSE_MIN, COARSE_MAX)).astype(np.int32)
    return coarse, continuous
