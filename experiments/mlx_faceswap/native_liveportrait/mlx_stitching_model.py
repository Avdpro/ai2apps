# ruff: noqa
# -*- coding: utf-8 -*-
"""MLX implementation of LivePortrait stitching and retargeting MLPs."""

from __future__ import annotations

import os
import re
from typing import List, Tuple

import numpy as np
import mlx.core as mx


_LAYER_RE = re.compile(r"(?:^|\.)(\d+)\.weight$")


def _layer_index(name: str) -> int:
    match = _LAYER_RE.search(name)
    if match is None:
        raise ValueError(f"Cannot infer MLP layer index from {name}")
    return int(match.group(1))


def _resolve_dtype(kwargs):
    from .mlx_warping_spade_model import _resolve_dtype as resolve

    return resolve(kwargs)


def _load_from_npz(path: str) -> List[Tuple[np.ndarray, np.ndarray]]:
    with np.load(path) as data:
        layer_ids = sorted(
            {
                int(name.split(".")[1])
                for name in data.files
                if name.startswith("layers.") and name.endswith(".weight")
            }
        )
        layers = [
            (
                data[f"layers.{idx}.weight"].astype(np.float32),
                data[f"layers.{idx}.bias"].astype(np.float32),
            )
            for idx in layer_ids
        ]
    if not layers:
        raise ValueError(f"No MLP weights found in {path}")
    return layers


class MlxStitchingModel:
    """Small MLX MLP used for stitching and eye/lip retargeting."""

    def __init__(self, **kwargs):
        self.predict_type = "mlx"
        self.dtype = _resolve_dtype(kwargs)
        path = str(kwargs["model_path"])
        if not path.endswith(".npz"):
            raise ValueError(
                f"MlxStitchingModel requires exported .npz weights, got {path}. "
                "Run scripts/export_mlx_weights.py first."
            )
        layers = _load_from_npz(path)

        self.layers = [
            (mx.array(weight).astype(self.dtype), mx.array(bias).astype(self.dtype))
            for weight, bias in layers
        ]
        mx.eval([item for layer in self.layers for item in layer])

        if kwargs.get("compile_model", None) is None:
            compile_model = os.environ.get("FLP_MLX_COMPILE_STITCHING", "0") == "1"
        else:
            compile_model = kwargs.get("compile_model", False)
        if compile_model:
            self._forward = mx.compile(self._forward_impl)
        else:
            self._forward = self._forward_impl

    def _forward_impl(self, x):
        for idx, (weight, bias) in enumerate(self.layers):
            x = x @ weight.T + bias
            if idx != len(self.layers) - 1:
                x = mx.maximum(x, 0)
        return x

    def predict(self, *data):
        x_np = np.asarray(data[0], dtype=np.float32)
        x = mx.array(x_np).astype(self.dtype)
        out = self._forward(x).astype(mx.float32)
        mx.eval(out)
        return np.array(out, dtype=np.float32)

    def __del__(self):
        if hasattr(self, "layers"):
            del self.layers
