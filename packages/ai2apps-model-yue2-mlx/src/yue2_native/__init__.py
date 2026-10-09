"""Independent YuE2 MLX inference. No torch, Transformers or AI2Apps imports."""

import os

os.environ["MLX_ENABLE_TF32"] = "0"
