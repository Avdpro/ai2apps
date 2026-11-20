import bootstrap
from bootstrap import UPSTREAM_ROOT, CHECKPOINT_ROOT

"""Validate the Runtime's pinned native Talker against Ex-Omni, including KV continuation."""
import ast, sys, math
from pathlib import Path
from types import SimpleNamespace
from typing import Optional
import torch, numpy as np, mlx.core as mx

from mlx_audio.tts.models.qwen3_tts.talker import Qwen3TTSTalkerModel
from mlx_audio.tts.models.qwen3_tts.config import Qwen3TTSTalkerConfig

source = Path(
    UPSTREAM_ROOT / "exomni/ex_omni/model/speech_generator/qwen3_tts_talker.py"
)
tree = ast.parse(source.read_text())
tree.body = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))]
ns = dict(
    torch=torch,
    nn=torch.nn,
    F=torch.nn.functional,
    SimpleNamespace=SimpleNamespace,
    Optional=Optional,
    math=math,
    FLASH_ATTENTION_2="flash_attention_2",
    FLASH_ATTENTION_3="flash_attention_3",
    SDPA="sdpa",
    resolve_attn_implementation=lambda v: "sdpa",
    resolve_decode_attn_implementation=lambda v: None,
)
exec(compile(tree, str(source), "exec"), ns)
config = Qwen3TTSTalkerConfig(
    hidden_size=16,
    intermediate_size=32,
    num_hidden_layers=2,
    num_attention_heads=2,
    num_key_value_heads=1,
    head_dim=8,
    vocab_size=32,
    text_vocab_size=40,
    text_hidden_size=16,
    rope_scaling={
        "mrope_section": [2, 1, 1],
        "interleaved": True,
        "rope_type": "default",
    },
)
ref = ns["Qwen3TTSTalkerModel"](SimpleNamespace(**vars(config))).eval()
model = Qwen3TTSTalkerModel(config)
model.load_weights(
    [(k, mx.array(v.detach().numpy())) for k, v in ref.state_dict().items()],
    strict=True,
)
model.eval()
rng = np.random.default_rng(4)
inputs = rng.normal(size=(1, 5, 16)).astype("float32")
ref_cache = None
cache = model.make_cache()
for x in [inputs[:, :3], inputs[:, 3:4], inputs[:, 4:]]:
    with torch.no_grad():
        expected, ref_cache = ref(
            torch.from_numpy(x), past_key_values=ref_cache, use_cache=True
        )
    actual = model(mx.array(x), cache=cache)
    error = np.max(np.abs(np.array(actual) - expected.numpy()))
    print("query_length", x.shape[1], "max_abs", error)
    assert error < 3e-5
print("PASS")
