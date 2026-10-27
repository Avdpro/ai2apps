import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Compare teacher DiT with audio injection against fixed upstream class bodies."""
import ast, sys, math
from pathlib import Path
from types import SimpleNamespace
from typing import Tuple, Optional, Union
import numpy as np, torch
from einops import rearrange
import mlx.core as mx

from exomni_mlx.video import WanModel, AudioPack, convert_weights, embed_speech_tokens

root = Path(UPSTREAM_ROOT / "exomni/ex_omni/model/video_generator/models")
ns = dict(
    torch=torch,
    nn=torch.nn,
    F=torch.nn.functional,
    math=math,
    Tuple=Tuple,
    Optional=Optional,
    Union=Union,
    rearrange=rearrange,
)
for name in ["audio_pack.py", "wan_video_dit.py"]:
    tree = ast.parse((root / name).read_text())
    tree.body = [
        n
        for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not n.name.startswith("_")
    ]
    exec(compile(tree, str(root / name), "exec"), ns)
ns["_runtime_args"] = lambda: SimpleNamespace(use_audio=True, sp_size=1)


def flash(q, k, v, num_heads, **kw):
    return rearrange(
        torch.nn.functional.scaled_dot_product_attention(
            *[rearrange(a, "b s (n d) -> b n s d", n=num_heads) for a in (q, k, v)]
        ),
        "b n s d -> b s (n d)",
    )


ns["flash_attention"] = flash
torch.manual_seed(14)
config = dict(
    dim=24,
    in_dim=5,
    ffn_dim=48,
    out_dim=2,
    text_dim=8,
    freq_dim=8,
    eps=1e-6,
    patch_size=(1, 2, 2),
    num_heads=2,
    num_layers=4,
    has_image_input=False,
    audio_hidden_size=4,
)
ref = ns["WanModel"](**config).eval()
ref.audio_proj = ns["AudioPack"](6, (4, 1, 1), 4, True)
model = WanModel(**config, audio_input_dim=6)
model.load_weights(
    list(
        convert_weights(
            {k: v.detach().numpy() for k, v in ref.state_dict().items()}
        ).items()
    ),
    strict=True,
)
model.eval()
rng = np.random.default_rng(4)
x = rng.normal(size=(1, 2, 2, 4, 4)).astype("float32")
y = rng.normal(size=(1, 3, 2, 4, 4)).astype("float32")
c = rng.normal(size=(1, 3, 8)).astype("float32")
audio = rng.normal(size=(1, 5, 6)).astype("float32")
t = np.array([750], dtype="float32")
with torch.no_grad():
    expected = ref(
        torch.from_numpy(x),
        torch.from_numpy(t),
        torch.from_numpy(c),
        y=torch.from_numpy(y),
        audio_emb=torch.from_numpy(audio),
    ).numpy()
actual = np.array(
    model(mx.array(x), mx.array(t), mx.array(c), mx.array(y), audio_emb=mx.array(audio))
)
assert np.std(expected) > 1e-3
error = float(np.max(np.abs(expected - actual)))
print("teacher max_abs", error)
assert error < 3e-5
books = rng.normal(size=(3, 16, 4)).astype("float32")
tokens = np.array([[-1, 4, 19], [2, 3, 4]], dtype=np.int64)
expected = sum(books[i, np.clip(tokens[:, i], 0, 15)] for i in range(3))
np.testing.assert_allclose(
    np.array(embed_speech_tokens(mx.array(tokens), mx.array(books))),
    expected,
    atol=1e-6,
)
print("PASS")
