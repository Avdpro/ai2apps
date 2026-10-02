"""Read original Diffusers safetensors without Torch or a converted checkpoint."""

import json
from pathlib import Path

import mlx.core as mx


def load_component(root, component, predicate=lambda key: True):
    result = {}
    for file in sorted((Path(root) / component).glob("*.safetensors")):
        # MLX lazily loads tensor storage; dropped audio tensors are never evaluated.
        for key, value in mx.load(str(file)).items():
            if predicate(key):
                if key in result:
                    raise ValueError(f"Duplicate tensor: {key}")
                result[key] = value
    if not result:
        raise ValueError(f"No weights for {component}")
    return result


def config(root, component):
    return json.loads((Path(root) / component / "config.json").read_text())


def linear(x, weights, name):
    y = x @ weights[name + ".weight"].T
    bias = weights.get(name + ".bias")
    return y if bias is None else y + bias


def conv_layout(value):
    if value.ndim == 5:
        return value.transpose(0, 2, 3, 4, 1)
    if value.ndim == 4:
        return value.transpose(0, 2, 3, 1)
    return value
