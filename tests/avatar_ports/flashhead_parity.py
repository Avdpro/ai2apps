import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Compare MLX against the pinned upstream's unmodified model classes on CPU."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace
import math
from typing import Tuple, Optional
import numpy as np
import torch
from einops import rearrange
import mlx.core as mx

from flashhead_mlx.model import WanModelAudioProject, AudioProjModel, convert_weights

source = Path(UPSTREAM_ROOT / "flashhead/flash_head/src/modules/flash_head_model.py")
parsed = ast.parse(source.read_text())
# Omit packaging and optional CUDA imports; execute the actual upstream class/function bodies.
parsed.body = [
    node for node in parsed.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
]


class ConfigMixin:
    pass


ns = dict(
    torch=torch,
    nn=torch.nn,
    F=torch.nn.functional,
    math=math,
    Tuple=Tuple,
    Optional=Optional,
    rearrange=rearrange,
    ModelMixin=torch.nn.Module,
    ConfigMixin=ConfigMixin,
    register_to_config=lambda f: f,
    dist=SimpleNamespace(is_initialized=lambda: False),
    FLASH_ATTN_3_AVAILABLE=False,
    FLASH_ATTN_2_AVAILABLE=False,
    SAGE_ATTN_AVAILABLE=False,
    amp=torch.cuda.amp,
)
exec(compile(parsed, str(source), "exec"), ns)
torch.manual_seed(11)
config = dict(
    dim=24,
    in_dim=4,
    ffn_dim=48,
    out_dim=2,
    text_dim=8,
    freq_dim=8,
    eps=1e-6,
    vae_stride=(4, 8, 8),
    patch_size=(1, 2, 2),
    num_heads=2,
    num_layers=2,
    has_image_input=False,
)
ref = ns["WanModelAudioProject"](**config).eval()
args = dict(
    seq_len=5,
    seq_len_vf=8,
    blocks=2,
    channels=3,
    intermediate_dim=64,
    output_dim=24,
    context_tokens=4,
    norm_output_audio=True,
)
ref.audio_proj = ns["AudioProjModel"](**args).eval()
model = WanModelAudioProject(**config)
model.audio_proj = AudioProjModel(**args)
weights = convert_weights({k: v.detach().numpy() for k, v in ref.state_dict().items()})
model.load_weights(list(weights.items()), strict=True)
model.eval()
rng = np.random.default_rng(3)
x = rng.normal(size=(1, 2, 2, 4, 4)).astype("float32")
y = rng.normal(size=x.shape).astype("float32")
audio = rng.normal(size=(1, 5, 5, 2, 3)).astype("float32")
t = np.array([750], dtype="float32")
with torch.no_grad():
    expected = ref(
        torch.from_numpy(x),
        torch.from_numpy(t),
        torch.from_numpy(audio),
        torch.from_numpy(y),
    ).numpy()
actual = np.array(model(mx.array(x), mx.array(t), mx.array(audio), mx.array(y)))
error = float(np.max(np.abs(expected - actual)))
print({"shape": actual.shape, "max_abs_error": error})
np.testing.assert_allclose(actual, expected, atol=3e-5, rtol=3e-5)
print("PASS: full reduced FlashHead model matches upstream CPU reference")
