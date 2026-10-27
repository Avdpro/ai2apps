import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import sys, json, time
from pathlib import Path

import mlx.core as mx
from mlx.utils import tree_map
from flashhead_mlx.model import WanModelAudioProject, convert_weights

root = Path(CHECKPOINT_ROOT / "flashhead/Model_Lite")
start = time.perf_counter()
model = WanModelAudioProject(**json.loads((root / "config.json").read_text()))
raw = mx.load(str(root / "diffusion_pytorch_model.safetensors"))
model.load_weights(list(convert_weights(raw).items()), strict=True)
model.update(tree_map(lambda x: x.astype(mx.bfloat16), model.parameters()))
model.eval()
mx.eval(model.parameters())
del raw
loaded = time.perf_counter()
x = mx.zeros((1, 128, 5, 2, 2), dtype=mx.bfloat16)
audio = mx.zeros((1, 33, 5, 12, 768), dtype=mx.bfloat16)
y = model(x, mx.array([1000], dtype=mx.bfloat16), audio, x)
mx.eval(y)
assert y.shape == x.shape and mx.all(mx.isfinite(y)).item()
print(
    json.dumps(
        {
            "model": "FlashHead Lite",
            "load_seconds": loaded - start,
            "forward_seconds": time.perf_counter() - loaded,
            "shape": list(y.shape),
            "peak_bytes": mx.get_peak_memory(),
            "strict_weight_load": True,
        }
    )
)
