"""Independent MLX inference for NVIDIA SoL-Refiner LTX-2.3 One-Step."""

# M5 otherwise defaults float32 GEMMs to TF32-class precision. Keep the
# numerical reference deterministic; callers may explicitly opt into TF32.
import os

os.environ.setdefault("MLX_ENABLE_TF32", "0")
