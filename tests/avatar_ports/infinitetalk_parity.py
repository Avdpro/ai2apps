import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Small full-network parity against pinned upstream class bodies, no CUDA required."""
import ast, sys, math
from pathlib import Path
from types import SimpleNamespace
from functools import lru_cache
import numpy as np
import torch
from einops import rearrange, repeat
import mlx.core as mx

from infinitetalk_mlx.model import WanModel, convert_weights
from infinitetalk_mlx.primitives import AudioProjModel

root = Path(UPSTREAM_ROOT / "infinitetalk")


def flash(q, k, v, **kwargs):
    return torch.nn.functional.scaled_dot_product_attention(
        q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2)
    ).transpose(1, 2)


ns = dict(
    torch=torch,
    nn=torch.nn,
    F=torch.nn.functional,
    amp=torch.cuda.amp,
    math=math,
    np=np,
    rearrange=rearrange,
    repeat=repeat,
    lru_cache=lru_cache,
    torch_gc=lambda: None,
    USE_SAGEATTN=False,
    ModelMixin=torch.nn.Module,
    ConfigMixin=type("ConfigMixin", (), {}),
    register_to_config=lambda f: f,
    flash_attention=flash,
    xformers=SimpleNamespace(
        ops=SimpleNamespace(
            memory_efficient_attention=lambda q, k, v, **kw: flash(q, k, v)
        )
    ),
)
for name, keep in [
    (
        "wan/utils/multitalk_utils.py",
        {
            "normalize_and_scale",
            "calculate_x_ref_attn_map",
            "get_attn_map_with_target",
            "rotate_half",
            "RotaryPositionalEmbedding1D",
        },
    ),
    (
        "wan/modules/attention.py",
        {"SingleStreamAttention", "SingleStreamMutiAttention"},
    ),
    ("wan/modules/multitalk_model.py", None),
]:
    parsed = ast.parse((root / name).read_text())
    parsed.body = [
        n
        for n in parsed.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef))
        and (keep is None or n.name in keep)
    ]
    for n in parsed.body:
        if isinstance(n, ast.FunctionDef):
            n.decorator_list = []
    exec(compile(parsed, str(root / name), "exec"), ns)
torch.manual_seed(11)
config = dict(
    dim=24,
    in_dim=6,
    ffn_dim=48,
    out_dim=2,
    text_dim=8,
    text_len=4,
    freq_dim=8,
    num_heads=2,
    num_layers=2,
    output_dim=6,
    intermediate_dim=8,
    context_tokens=4,
)
ref = ns["WanModel"](**config).eval()
ref.disable_teacache()
model = WanModel(**config)
args = dict(
    seq_len=5,
    seq_len_vf=8,
    blocks=2,
    channels=3,
    intermediate_dim=8,
    output_dim=6,
    context_tokens=4,
    norm_output_audio=True,
)
ref.audio_proj = ns["AudioProjModel"](**args)
model.audio_proj = AudioProjModel(**args)
# Upstream initializes the output head to zero; randomize it for a non-vacuous parity gate.
with torch.no_grad():
    ref.head.head.weight.normal_(0, 0.1)
    ref.head.head.bias.normal_(0, 0.1)
model.load_weights(
    list(
        convert_weights(
            {k: v.detach().numpy() for k, v in ref.state_dict().items()}
        ).items()
    ),
    strict=True,
)
model.eval()
rng = np.random.default_rng(3)
x = rng.normal(size=(1, 2, 2, 4, 4)).astype("float32")
y = rng.normal(size=(1, 4, 2, 4, 4)).astype("float32")
context = rng.normal(size=(1, 3, 8)).astype("float32")
clip = rng.normal(size=(1, 257, 1280)).astype("float32")
t = np.array([750], dtype="float32")
for speakers in [1, 2]:
    audio = rng.normal(size=(speakers, 5, 5, 2, 3)).astype("float32")
    masks = (
        np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 1]], dtype="float32")
        if speakers == 2
        else np.ones((1, 4), dtype="float32")
    )
    with torch.no_grad():
        expected = ref(
            [torch.from_numpy(x[0])],
            torch.from_numpy(t),
            [torch.from_numpy(context[0])],
            8,
            clip_fea=torch.from_numpy(clip),
            y=[torch.from_numpy(y[0])],
            audio=torch.from_numpy(audio),
            ref_target_masks=torch.from_numpy(masks.reshape(-1, 2, 2)),
        )[0].numpy()[None]
    actual = np.array(
        model(
            mx.array(x),
            mx.array(t),
            mx.array(context),
            mx.array(clip),
            mx.array(y),
            mx.array(audio),
            mx.array(masks),
        )
    )
    assert np.std(expected) > 1e-3
    error = np.max(np.abs(expected - actual))
    print("speakers", speakers, "max_abs", error, flush=True)
    assert error < 3e-5
print("PASS")
