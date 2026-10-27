import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Compare full official Wan VAE weights on a small spatiotemporal fixture."""
import ast, sys
from pathlib import Path
import numpy as np, torch, mlx.core as mx
from einops import rearrange

from flashhead_mlx.wan_vae import WanVAE
from flashhead_mlx.wan_vae_ops import _VAE_MEAN, _VAE_STD

source = Path(UPSTREAM_ROOT / "flashhead/flash_head/wan/modules/vae.py")
tree = ast.parse(source.read_text())
tree.body = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
ns = dict(
    torch=torch, nn=torch.nn, F=torch.nn.functional, CACHE_T=2, rearrange=rearrange
)
exec(compile(tree, str(source), "exec"), ns)
root = Path(CHECKPOINT_ROOT / "flashhead/VAE_Wan")
ref = ns["WanVAE_"](dim=96, z_dim=16, temperal_downsample=[False, True, True]).eval()
ref.load_state_dict(
    torch.load(root / "Wan2.1_VAE.pth", weights_only=True, map_location="cpu"),
    strict=True,
)
model = WanVAE(root / "Wan2.1_VAE.safetensors", dtype=mx.float32)
rng = np.random.default_rng(2)
video = rng.uniform(-1, 1, (1, 3, 5, 16, 16)).astype("float32")
scale = [torch.tensor(_VAE_MEAN), 1 / torch.tensor(_VAE_STD)]
with torch.no_grad():
    expected = ref.encode(torch.from_numpy(video), scale).numpy()
actual = np.array(model.encode(mx.array(video)))
error = np.max(np.abs(expected - actual))
print("encoder max_abs", error, flush=True)
np.testing.assert_allclose(actual, expected, atol=4e-4, rtol=4e-4)
with torch.no_grad():
    expected_video = ref.decode(torch.from_numpy(expected), scale).clamp(-1, 1).numpy()
actual_video = np.array(model.decode(mx.array(expected)))
error = np.max(np.abs(expected_video - actual_video))
print("decoder max_abs", error, flush=True)
np.testing.assert_allclose(actual_video, expected_video, atol=4e-4, rtol=4e-4)
print("PASS")
