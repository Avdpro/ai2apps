"""Versioned result schema for two-stem audio separation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Stem:
    type: str
    path: str
    channels: int
    sample_rate: int
    frames: int
    duration: float
    rms: float


@dataclass
class SeparationResult:
    duration: float
    sample_rate: int
    channels: int
    stems: list[Stem]
    model: dict[str, Any]
    metrics: dict[str, float]
    features: dict[str, dict[str, Any]] = field(default_factory=dict)
    schema: str = "ai2apps.audio-separation-result/v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
