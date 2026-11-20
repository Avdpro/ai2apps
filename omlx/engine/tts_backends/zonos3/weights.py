"""Native safetensors storage for the release's dense and packed expert weights."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx import nn


def encode_name(name):
    if "__" in name:
        raise ValueError(f"unsupported tensor name: {name}")
    return name.replace(".", "__")


class NamedView(Mapping):
    def __init__(self, values):
        self.values = values

    def __getitem__(self, name):
        return self.values[encode_name(name)]

    def __iter__(self):
        return (k.replace("__", ".") for k in self.values)

    def __len__(self):
        return len(self.values)


@mx.compile
def dense_matmul(x, weight):
    return x @ weight.astype(mx.float32).swapaxes(-1, -2)


class Linear(nn.Module):
    """Dense or affine packed matrix, including stacked MoE experts.

    FP32 activations and group-32 quantization follow Zyphra's MLX runtime.
    The stored Q4_0/Q8_0 blocks are repacked without requantization.
    """

    def __init__(self, spec):
        super().__init__()
        shape = tuple(spec["shape"])
        self.bits = spec.get("bits")
        if self.bits is None:
            self.weight = mx.zeros(shape, getattr(mx, spec["dtype"]))
        else:
            *lead, rows, cols = shape
            self.weight = mx.zeros((*lead, rows, cols * self.bits // 32), mx.uint32)
            self.scales = mx.zeros((*lead, rows, cols // 32), mx.float32)
            self.biases = mx.zeros_like(self.scales)

    def __call__(self, x, indices=None):
        if self.bits is not None:
            fn = mx.quantized_matmul if indices is None else mx.gather_qmm
            kwargs = {} if indices is None else {"rhs_indices": indices}
            return fn(
                x,
                self.weight,
                self.scales,
                self.biases,
                transpose=True,
                group_size=32,
                bits=self.bits,
                **kwargs,
            )
        if indices is None:
            return dense_matmul(x, self.weight)
        if indices.size >= self.weight.shape[0]:
            return mx.gather_mm(
                x, self.weight.astype(mx.float32).swapaxes(-1, -2), rhs_indices=indices
            )
        return x @ self.weight[indices].astype(mx.float32).swapaxes(-1, -2)


class TensorStore(nn.Module):
    def __init__(self, specs):
        super().__init__()
        self.matrices = {}
        self.tables = {}
        for name, spec in specs.items():
            key = encode_name(name)
            if spec["matrix"]:
                self.matrices[key] = Linear(spec)
            else:
                self.tables[key] = mx.zeros(
                    tuple(spec["shape"]), getattr(mx, spec["dtype"])
                )

    @property
    def t(self):
        return NamedView(self.tables)

    @property
    def w(self):
        return NamedView(self.matrices)


class NativeFile:
    """Read a converted component's metadata and tensors; no GGUF runtime dependency."""

    def __init__(self, path):
        self.root = Path(path)
        self.path = str(self.root)
        self.config = json.loads((self.root / "config.json").read_text())
        self.arch = self.meta("general.architecture")
        self.weights = mx.load(str(self.root / "model.safetensors"))
        host = self.root / "frontend.npz"
        self.host = {}
        if host.exists():
            with np.load(host, allow_pickle=False) as arrays:
                self.host = dict(arrays)

    def meta(self, key, *default):
        if default:
            return self.config["metadata"].get(key, default[0])
        return self.config["metadata"][key]

    def names(self):
        return list(self.config["tensors"])

    def shape(self, name):
        return tuple(self.config["tensors"][name]["shape"])

    def array(self, name):
        if name in self.host:
            return self.host[name]
        return np.array(self.f32(name))

    def f32(self, name):
        return self.weights["tables." + encode_name(name)].astype(mx.float32)
