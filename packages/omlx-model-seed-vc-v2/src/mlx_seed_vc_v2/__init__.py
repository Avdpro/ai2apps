"""Native MLX implementation of Seed-VC v2."""

import os

# Standalone inference must set this before the first MLX operation too.
# Reduced-precision matmul can flip ASTRAL bits close to zero.
os.environ["MLX_ENABLE_TF32"] = "0"

from .pipeline import SeedVCV2

__all__ = ["SeedVCV2"]
