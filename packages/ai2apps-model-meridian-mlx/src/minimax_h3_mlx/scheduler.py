"""MLX port of ``MiniMaxH3Scheduler`` — rectified-flow Euler with an exponential sigma shift.

The released checkpoints use ``shift = 12.0`` for video latents and ``3.0`` for audio, so a run
drives two independent schedules over one shared transformer forward.
"""

from __future__ import annotations

import mlx.core as mx
import numpy as np


def _linspace_1_to_0(n: int) -> np.ndarray:
    """``linspace(1, 0, n)`` in float32, bit-identical to ``torch.linspace``.

    The rectified-flow sigma grid is collapsed with a consecutive-duplicate check, so a one-ulp
    difference can change how many sigmas survive and therefore the number of model evaluations.
    Reproducing torch's grid exactly keeps the step count identical to the reference.

    ATen's kernel takes a **float32** step, splits the range at the halfway point to keep the two
    ends symmetric, and evaluates ``start + step*i`` with a fused multiply-add — a single rounding.
    Computing in float64 from the float32 step and rounding once reproduces that FMA exactly
    (verified over n = 2..399).
    """
    start, end = 1.0, 0.0
    step = float(np.float32((end - start) / np.float32(n - 1)))
    half = n // 2
    i = np.arange(n, dtype=np.float64)
    out = np.empty(n, dtype=np.float64)
    out[:half] = start + step * i[:half]
    out[half:] = end - step * (n - 1 - i[half:])
    return out.astype(np.float32)


class MiniMaxH3Scheduler:
    """Rectified-flow Euler scheduler (``eta = 0``) with exponential sigma shift.

    ``sigma' = s*sigma / (1 + (s-1)*sigma)`` over a ``linspace(1, 0, N + 1)`` grid. The terminal
    ``0`` is part of the grid (the shift maps ``0`` to exactly ``0``), so the user-facing
    ``num_inference_steps=N`` drives exactly ``N`` model evaluations and
    ``timesteps = 1 - sigmas[:-1]``.
    """

    order = 1

    def __init__(self, shift: float = 12.0):
        if shift <= 0:
            raise ValueError(f"`shift` must be positive, got {shift}.")
        self._shift = float(shift)
        self.sigmas: mx.array | None = None
        self.timesteps: mx.array | None = None
        self.num_inference_steps: int | None = None
        self._step_index: int | None = None

    @property
    def shift(self) -> float:
        return self._shift

    @property
    def step_index(self) -> int | None:
        return self._step_index

    def set_shift(self, shift: float) -> None:
        """Override the sigma shift; call before :meth:`set_timesteps`."""
        if shift <= 0:
            raise ValueError(f"`shift` must be positive, got {shift}.")
        self._shift = float(shift)

    def set_timesteps(
        self,
        num_inference_steps: int | None = None,
        sigmas: list[float] | mx.array | None = None,
    ) -> None:
        """Build the sigma / timestep schedule.

        The grid is always built in float32 on the host so the schedule never depends on the
        accelerator, matching the reference.
        """
        if sigmas is None:
            if num_inference_steps is None or num_inference_steps < 1:
                raise ValueError(
                    "`set_timesteps` requires either an explicit `sigmas` schedule or "
                    f"`num_inference_steps` >= 1, got {num_inference_steps}."
                )
            # N Euler updates require N + 1 sigma boundaries.  The previous implementation built
            # N boundaries and silently ran only N - 1 transformer forwards.
            base = _linspace_1_to_0(int(num_inference_steps) + 1)
            shift32 = np.float32(self._shift)
            shifted = (shift32 * base) / (np.float32(1.0) + np.float32(self._shift - 1.0) * base)
            # The shift compresses the grid near sigma = 1; collapse float32 collisions it creates.
            values: list[float] = []
            for v in shifted.tolist():
                if not values or v != values[-1]:
                    values.append(v)
        else:
            values = [float(v) for v in (sigmas.tolist() if isinstance(sigmas, mx.array) else sigmas)]
            decreasing = all(b < a for a, b in zip(values, values[1:]))
            if len(values) < 2 or not decreasing or values[-1] != 0.0:
                raise ValueError(
                    "`sigmas` must hold at least two strictly decreasing values ending at 0.0."
                )

        self.sigmas = mx.array(values, dtype=mx.float32)
        self.timesteps = mx.array([1.0 - s for s in values[:-1]], dtype=mx.float32)
        self.num_inference_steps = len(values) - 1
        self._step_index = None

    def index_for_timestep(self, timestep: float) -> int:
        """Map a timestep value to its schedule index. The schedule is strictly increasing in t."""
        target = float(timestep)
        for i, t in enumerate(self.timesteps.tolist()):
            if t == target:
                return i
        raise ValueError(
            "Passed `timestep` is not in `self.timesteps`. Use values from `scheduler.timesteps`."
        )

    def scale_noise(self, sample: mx.array, timestep: float, noise: mx.array) -> mx.array:
        """Rectified-flow forward process in MiniMax-H3's ``t`` convention: ``x_t = t*x0 + (1-t)*noise``.

        Used to noise conditioning anchors, where ``t`` is a ``noise_aug`` level rather than a
        schedule entry, so it is taken at face value and never looked up in ``self.timesteps``.
        """
        t32 = np.float32(timestep)
        return float(t32) * sample + float(np.float32(1.0) - t32) * noise

    def step(self, model_output: mx.array, timestep: float, sample: mx.array) -> mx.array:
        """One Euler (``eta = 0``) step.

        The model output is a **data-ward** velocity, so the denoised estimate is
        ``x0 = x_t + (1 - t) * v`` — note the ``+``, the opposite of the usual flow-match sign.
        The update is the blend ``x_next = r*x_t + (1 - r)*x0`` with ``r = sigma_next / sigma``,
        evaluated in float32.
        """
        if isinstance(timestep, int):
            raise ValueError(
                "Passing integer indices as timesteps is not supported; pass one of the "
                "`scheduler.timesteps` values."
            )
        if self._step_index is None:
            self._step_index = self.index_for_timestep(timestep)

        # The sigma used for x0 is recovered from the *timestep* the transformer was conditioned
        # on, while the Euler ratio below uses the sigma grid: for sigma < 0.5 the float32 round
        # trip `1 - (1 - sigma)` is not exact, and the reference keeps the two sources apart.
        # Every scalar here is evaluated in float32, matching the reference's tensor arithmetic —
        # doing it in Python floats would round twice and drift by an ulp per step.
        sigma_from_timestep = float(np.float32(1.0) - np.float32(timestep))
        denoised = sample + sigma_from_timestep * model_output

        sigma = np.float32(self.sigmas[self._step_index].item())
        sigma_next = np.float32(self.sigmas[self._step_index + 1].item())
        ratio = sigma_next / sigma
        one_minus_ratio = float(np.float32(1.0) - ratio)

        prev = float(ratio) * sample.astype(mx.float32) + one_minus_ratio * denoised.astype(mx.float32)
        self._step_index += 1
        return prev.astype(sample.dtype)
