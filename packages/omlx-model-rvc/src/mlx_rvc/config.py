"""Validated inference configuration for legacy RVC v1/v2 checkpoints."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

_SAMPLE_RATES = {"32k": 32_000, "40k": 40_000, "48k": 48_000}


@dataclass(frozen=True)
class RVCConfig:
    spec_channels: int
    segment_size: int
    inter_channels: int
    hidden_channels: int
    filter_channels: int
    heads: int
    layers: int
    kernel_size: int
    dropout: float
    resblock: str
    resblock_kernel_sizes: tuple[int, ...]
    resblock_dilation_sizes: tuple[tuple[int, ...], ...]
    upsample_rates: tuple[int, ...]
    upsample_initial_channels: int
    upsample_kernel_sizes: tuple[int, ...]
    speaker_count: int
    speaker_embedding_channels: int
    sample_rate: int
    feature_version: str
    uses_f0: bool

    @property
    def feature_channels(self) -> int:
        return 768 if self.feature_version == "v2" else 256

    @property
    def hop_length(self) -> int:
        value = 1
        for rate in self.upsample_rates:
            value *= rate
        return value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_legacy(
        cls,
        values: Sequence[Any],
        *,
        version: str,
        uses_f0: bool,
        speaker_count: int | None = None,
    ) -> RVCConfig:
        if len(values) < 18:
            raise ValueError("RVC checkpoint config must contain at least 18 values")
        if version not in {"v1", "v2"}:
            raise ValueError("RVC feature version must be v1 or v2")
        rate_value = values[17]
        if isinstance(rate_value, str):
            try:
                sample_rate = _SAMPLE_RATES[rate_value]
            except KeyError as error:
                raise ValueError(
                    f"unsupported RVC sample rate: {rate_value}"
                ) from error
        else:
            sample_rate = int(rate_value)
        if sample_rate not in _SAMPLE_RATES.values():
            raise ValueError(f"unsupported RVC sample rate: {sample_rate}")

        declared_speakers = int(values[15])
        actual_speakers = (
            declared_speakers if speaker_count is None else int(speaker_count)
        )
        if actual_speakers < 1:
            raise ValueError("RVC checkpoint must contain at least one speaker")
        upsample_rates = tuple(int(item) for item in values[12])
        upsample_kernels = tuple(int(item) for item in values[14])
        if len(upsample_rates) != len(upsample_kernels) or not upsample_rates:
            raise ValueError(
                "RVC upsample rates and kernels must have equal non-zero length"
            )
        if any(item <= 0 for item in upsample_rates + upsample_kernels):
            raise ValueError("RVC upsample values must be positive")
        if sample_rate % _product(upsample_rates):
            raise ValueError(
                "RVC sample rate must be divisible by the decoder hop length"
            )

        return cls(
            spec_channels=int(values[0]),
            segment_size=int(values[1]),
            inter_channels=int(values[2]),
            hidden_channels=int(values[3]),
            filter_channels=int(values[4]),
            heads=int(values[5]),
            layers=int(values[6]),
            kernel_size=int(values[7]),
            dropout=float(values[8]),
            resblock=str(values[9]),
            resblock_kernel_sizes=tuple(int(item) for item in values[10]),
            resblock_dilation_sizes=tuple(
                tuple(int(item) for item in group) for group in values[11]
            ),
            upsample_rates=upsample_rates,
            upsample_initial_channels=int(values[13]),
            upsample_kernel_sizes=upsample_kernels,
            speaker_count=actual_speakers,
            speaker_embedding_channels=int(values[16]),
            sample_rate=sample_rate,
            feature_version=version,
            uses_f0=bool(uses_f0),
        )


def _product(values: Sequence[int]) -> int:
    result = 1
    for value in values:
        result *= value
    return result
