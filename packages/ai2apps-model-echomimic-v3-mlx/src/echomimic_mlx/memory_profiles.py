"""Evidence-based unified-memory deployment profiles."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import GenerationRequest

GIB = 1024**3


@dataclass(frozen=True, slots=True)
class MemoryProfile:
    name: str
    minimum_bytes: int
    maximum_resolution: int
    cache_conditions: bool

    def validate(self, request: GenerationRequest) -> None:
        if max(request.width, request.height) > self.maximum_resolution:
            raise ValueError(
                f"the {self.name} memory profile supports at most "
                f"{self.maximum_resolution}x{self.maximum_resolution}"
            )


COMPACT_MEMORY_PROFILE = MemoryProfile("compact", 32 * GIB, 512, False)
STANDARD_MEMORY_PROFILE = MemoryProfile("standard", 64 * GIB, 768, False)
PERFORMANCE_MEMORY_PROFILE = MemoryProfile("performance", 96 * GIB, 768, True)


def physical_memory_bytes() -> int:
    """Return physical memory without platform-specific subprocesses or dependencies."""

    return int(os.sysconf("SC_PHYS_PAGES")) * int(os.sysconf("SC_PAGE_SIZE"))


def select_memory_profile(total_bytes: int | None = None) -> MemoryProfile:
    """Select the safest supported profile for the available unified memory."""

    available = physical_memory_bytes() if total_bytes is None else total_bytes
    if available < COMPACT_MEMORY_PROFILE.minimum_bytes:
        raise RuntimeError("EchoMimicV3 MLX requires at least 32 GiB of unified memory")
    if available < STANDARD_MEMORY_PROFILE.minimum_bytes:
        return COMPACT_MEMORY_PROFILE
    if available < PERFORMANCE_MEMORY_PROFILE.minimum_bytes:
        return STANDARD_MEMORY_PROFILE
    return PERFORMANCE_MEMORY_PROFILE
