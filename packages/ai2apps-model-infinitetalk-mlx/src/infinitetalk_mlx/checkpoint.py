"""Strict offline checkpoint loading with bounded temporary shard memory."""

import json
from pathlib import Path

import mlx.core as mx
from mlx.utils import tree_flatten

from .model import WanModel, convert_weights


def load_model(base_dir, adapter_path, *, dtype=mx.bfloat16):
    root = Path(base_dir)
    config = json.loads((root / "config.json").read_text())
    if config.get("model_type") != "i2v":
        raise ValueError("InfiniteTalk requires a Wan I2V base")
    index = json.loads(
        (root / "diffusion_pytorch_model.safetensors.index.json").read_text()
    )["weight_map"]
    config = {k: v for k, v in config.items() if not k.startswith("_")}
    model = WanModel(**config)
    shapes = {k: v.shape for k, v in tree_flatten(model.parameters())}
    seen = set()
    for path in [
        *(root / name for name in sorted(set(index.values()))),
        Path(adapter_path),
    ]:
        raw = mx.load(str(path))
        weights = convert_weights({k: v.astype(dtype) for k, v in raw.items()})
        for name, value in weights.items():
            if name not in shapes or value.shape != shapes[name]:
                raise ValueError(
                    f"Unexpected checkpoint tensor/shape: {name} {value.shape}"
                )
        mx.eval(list(weights.values()))
        model.load_weights(list(weights.items()), strict=False)
        seen.update(weights)
        del raw, weights
        mx.clear_cache()
    if seen != set(shapes):
        raise ValueError(
            "Missing checkpoint tensors: " + str(sorted(set(shapes) - seen))
        )
    model.eval()
    mx.eval(model.parameters())
    mx.clear_cache()
    return model
