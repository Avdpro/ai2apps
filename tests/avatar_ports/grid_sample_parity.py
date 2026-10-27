import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
from pathlib import Path
import sys

import mlx.core as mx
import numpy as np
import torch
from avtr_mlx.sampling import grid_sample_3d

rng = np.random.default_rng(17)
worst = 0
for depth in [1, 3]:
    x = rng.normal(size=(2, 4, depth, 5, 6)).astype("float32")
    grid = rng.uniform(-3, 3, size=(2, 2, 4, 7, 3)).astype("float32")
    for align in [True, False]:
        for mode in ["zeros", "border", "reflection"]:
            expected = torch.nn.functional.grid_sample(
                torch.from_numpy(x),
                torch.from_numpy(grid),
                padding_mode=mode,
                align_corners=align,
            ).numpy()
            actual = np.array(
                grid_sample_3d(
                    mx.array(x), mx.array(grid), padding_mode=mode, align_corners=align
                )
            )
            error = float(np.max(np.abs(expected - actual)))
            worst = max(error, worst)
            np.testing.assert_allclose(actual, expected, atol=3e-6, rtol=3e-6)
print({"cases": 12, "max_abs_error": worst})
