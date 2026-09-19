"""Validation harness for the Package-owned MLX Seed-VC v2 implementation."""

import sys
from pathlib import Path

_PACKAGE_SOURCE = Path(__file__).resolve().parents[2] / "packages/omlx-model-seed-vc-v2/src"
if str(_PACKAGE_SOURCE) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_SOURCE))
