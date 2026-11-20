import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT
import ast, sys
from pathlib import Path
import numpy as np, torch
from einops import rearrange
import mlx.core as mx

from exomni_mlx.speech import TQGF, convert_fusion_weights

source = Path(
    UPSTREAM_ROOT / "exomni/ex_omni/model/speech_generator/speech_generator.py"
)
tree = ast.parse(source.read_text())
tree.body = [
    n
    for n in tree.body
    if isinstance(n, (ast.ClassDef, ast.FunctionDef))
    and n.name in {"FeedForward", "TQGFCrossAttention", "TQGF"}
]
ns = dict(torch=torch, nn=torch.nn, rearrange=rearrange, einsum=torch.einsum)
exec(compile(tree, str(source), "exec"), ns)
torch.manual_seed(5)
args = dict(dim=12, depth=2, dim_head=4, heads=3, ff_mult=2)
ref = ns["TQGF"](**args).eval()
model = TQGF(**args)
model.load_weights(
    list(
        convert_fusion_weights(
            {k: v.detach().numpy() for k, v in ref.state_dict().items()}
        ).items()
    ),
    strict=True,
)
model.eval()
rng = np.random.default_rng(1)
query = rng.normal(size=(2, 3, 12)).astype("float32")
for length in [0, 4]:
    text = rng.normal(size=(2, length, 12)).astype("float32")
    for mask in [
        None,
        np.zeros((2, length), dtype=bool),
        np.ones((2, length), dtype=bool),
    ]:
        with torch.no_grad():
            expected = ref(
                torch.from_numpy(text),
                torch.from_numpy(query),
                None if mask is None else torch.from_numpy(mask),
            ).numpy()
        actual = np.array(
            model(
                mx.array(text),
                mx.array(query),
                None if mask is None else mx.array(mask),
            )
        )
        error = np.max(np.abs(expected - actual))
        print(length, "mask", mask is not None, "max_abs", error)
        assert error < 3e-5
print("PASS")
