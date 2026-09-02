"""Optional timestep-embedding-aware residual cache for fast approximate inference."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

import mlx.core as mx

WAN_1_3B_COEFFICIENTS = (
    -5.21862437e4,
    9.23041404e3,
    -5.28275948e2,
    1.36987616e1,
    -4.99875664e-2,
)


@dataclass(slots=True)
class TeaCacheState:
    """Make one cache decision per timestep and retain a residual for each CFG branch."""

    num_steps: int
    threshold: float
    skip_start_steps: int = 5
    coefficients: tuple[float, ...] = WAN_1_3B_COEFFICIENTS
    accumulated_distance: float = 0.0
    previous_modulation: mx.array | None = None
    residuals: dict[str, mx.array] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.num_steps <= 0:
            raise ValueError("TeaCache num_steps must be positive")
        if self.threshold <= 0:
            raise ValueError("TeaCache threshold must be positive")
        if not 0 <= self.skip_start_steps <= self.num_steps:
            raise ValueError("TeaCache skip_start_steps must be within the denoising schedule")
        if not self.coefficients:
            raise ValueError("TeaCache requires polynomial coefficients")

    def _rescale(self, relative_l1: float) -> float:
        result = 0.0
        for coefficient in self.coefficients:
            result = result * relative_l1 + coefficient
        return result

    def should_compute(self, step: int, modulation: mx.array) -> bool:
        """Return whether both CFG branches should execute their block stacks at this step."""

        if not 0 <= step < self.num_steps:
            raise ValueError("TeaCache step is outside the denoising schedule")
        compute = True
        if step < self.skip_start_steps or self.previous_modulation is None:
            self.accumulated_distance = 0.0
        else:
            previous = self.previous_modulation.astype(mx.float32)
            current = modulation.astype(mx.float32)
            denominator = mx.mean(mx.abs(previous))
            relative_l1 = cast(float, (mx.mean(mx.abs(current - previous)) / denominator).item())
            self.accumulated_distance += self._rescale(relative_l1)
            if self.accumulated_distance < self.threshold and len(self.residuals) == 2:
                compute = False
            else:
                self.accumulated_distance = 0.0
        self.previous_modulation = modulation
        return compute

    def store_residual(self, branch: str, residual: mx.array) -> None:
        if branch not in ("conditional", "unconditional"):
            raise ValueError("TeaCache branch must be conditional or unconditional")
        self.residuals[branch] = residual

    def residual(self, branch: str) -> mx.array:
        try:
            return self.residuals[branch]
        except KeyError as error:
            raise RuntimeError(f"TeaCache has no residual for {branch}") from error
