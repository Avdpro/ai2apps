"""Standalone two-stem Demucs/MLX separation experiment.

This package intentionally has no AI2Apps App, Runtime, Registry, or installed
Package integration.  The PyTorch backend is only a reference oracle for the
eventual MLX implementation.
"""

from .audio import AudioBuffer, read_audio
from .pipeline import SeparationConfig, separate_file
from .schema import SeparationResult, Stem

__all__ = [
    "AudioBuffer",
    "SeparationConfig",
    "SeparationResult",
    "Stem",
    "read_audio",
    "separate_file",
]
