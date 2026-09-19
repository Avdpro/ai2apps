"""Validation harness for the Package-owned MLX-RVC implementation."""

import sys
from pathlib import Path

_PACKAGE_SOURCE = Path(__file__).resolve().parents[2] / "packages/omlx-model-rvc/src"
if str(_PACKAGE_SOURCE) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_SOURCE))

from .config import RVCConfig  # noqa: E402
from .pitch import coarse_f0  # noqa: E402

__all__ = ["RVCConfig", "coarse_f0"]
