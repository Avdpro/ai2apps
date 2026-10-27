import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import sys, time, json
from pathlib import Path

import mlx.core as mx
from infinitetalk_mlx.checkpoint import load_model

root = Path(CHECKPOINT_ROOT)
start = time.perf_counter()
model = load_model(
    root / "wan14b", root / "infinitetalk/single/infinitetalk.safetensors"
)
loaded = time.perf_counter()
y = model(
    mx.zeros((1, 16, 2, 4, 4), dtype=mx.bfloat16),
    mx.array([750.0], dtype=mx.bfloat16),
    mx.zeros((1, 4, 4096), dtype=mx.bfloat16),
    mx.zeros((1, 257, 1280), dtype=mx.bfloat16),
    mx.zeros((1, 20, 2, 4, 4), dtype=mx.bfloat16),
    mx.zeros((1, 5, 5, 12, 768), dtype=mx.bfloat16),
)
mx.eval(y)
assert y.shape == (1, 16, 2, 4, 4) and bool(mx.all(mx.isfinite(y)).item())
assert "torch" not in sys.modules
print(
    json.dumps(
        {
            "strict_load": True,
            "shape": list(y.shape),
            "load_seconds": loaded - start,
            "forward_seconds": time.perf_counter() - loaded,
            "peak_bytes": mx.get_peak_memory(),
        }
    )
)
