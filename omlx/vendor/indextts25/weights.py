"""Runtime-only MLX checkpoint loader for the vendored IndexTTS 2.5 port."""
from pathlib import Path

import mlx.core as mx

DEFAULT_MLX_DIR = Path("IndexTTS-2.5-mlx")


def load_mlx(weights_dir, name):
    st = mx.load(str(Path(weights_dir) / f"{name}.safetensors"), format="safetensors")
    # safetensors is mmap-backed: without this, the first GPU kernel that
    # touches a weight page pulls it from disk mid-kernel (mechanical HDD =
    # 10ms+/page), blowing the Metal 2s watchdog. Force the whole file into
    # memory once at load time.
    mx.eval(*st.values())
    return st


def load_into(model, st, dtype=None):
    # filter to the model's own param names (drops ckpt extras like tied lm_head),
    # then assign leaves by attribute path. Direct leaf assignment (instead of
    # model.update(tree_unflatten(...))) sidesteps list/dict shape mismatch with
    # name-preserving Seq containers.
    from mlx.utils import tree_flatten

    flat = dict(tree_flatten(model.parameters()))
    sel = {k: v for k, v in st.items() if k in flat}
    if dtype is not None:
        sel = {k: (v.astype(dtype) if v.dtype != mx.int32 else v) for k, v in sel.items()}
    for k, v in sel.items():
        parts = k.split(".")
        target = model
        for p in parts[:-1]:
            target = target[int(p)] if isinstance(target, list) else getattr(target, p)
        setattr(target, parts[-1], v)

