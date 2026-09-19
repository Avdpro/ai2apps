# ruff: noqa
# -*- coding: utf-8 -*-
"""MLX motion_extractor wrapper for the LivePortrait pipeline."""

from __future__ import annotations

import os

import numpy as np
import mlx.core as mx
import mlx.utils as mu

from .mlx_modules.convnextv2 import convnextv2_tiny
from .mlx_modules.weight_convert import load_into_model


def _headpose_pred_to_degree_np(pred):
    if pred.ndim > 1 and pred.shape[1] == 66:
        idx = np.arange(0, 66)
        pred = np.exp(pred - pred.max(axis=1, keepdims=True))
        pred = pred / pred.sum(axis=1, keepdims=True)
        return (pred * idx).sum(axis=1) * 3 - 97.5
    return pred


class MlxMotionExtractorModel:
    """Takes a uint8 RGB image and returns motion arrays used by the pipeline."""

    def __init__(self, **kwargs):
        self.predict_type = "mlx"
        self.flag_refine_info = kwargs.get("flag_refine_info", True)

        from .mlx_warping_spade_model import _resolve_dtype, _cast_params
        self.dtype = _resolve_dtype(kwargs)

        self.model = convnextv2_tiny(num_kp=21)
        load_into_model(self.model, kwargs["model_path"], dropping_prefix="detector.", strict=True)
        self.model.eval()
        _cast_params(self.model, self.dtype)
        mx.eval(self.model.parameters())
        if kwargs.get("compile_model", None) is None:
            compile_model = os.environ.get("FLP_MLX_COMPILE_MOTION", "1") == "1"
        else:
            compile_model = kwargs.get("compile_model", False)
        if compile_model:
            model = self.model
            self._model_fn = mx.compile(lambda x: model(x))
        else:
            self._model_fn = self.model

    def predict(self, *data):
        img = np.asarray(data[0])
        if img.dtype != np.uint8:
            img = img.astype(np.uint8)
        x_mx = (mx.array(img[None]).astype(mx.float32) / 255.0).astype(self.dtype)  # (1, H, W, 3) NHWC
        out = self._model_fn(x_mx)
        keys = ("pitch", "yaw", "roll", "t", "exp", "scale", "kp")
        mx_out = [out[k].astype(mx.float32) for k in keys]
        mx.eval(mx_out)
        cpu = {k: np.array(v, dtype=np.float32) for k, v in zip(keys, mx_out)}
        if self.flag_refine_info:
            bs = cpu["kp"].shape[0]
            for k in ("pitch", "yaw", "roll"):
                cpu[k] = _headpose_pred_to_degree_np(cpu[k])[:, None]
            cpu["kp"] = cpu["kp"].reshape(bs, -1, 3)
            cpu["exp"] = cpu["exp"].reshape(bs, -1, 3)
        return (cpu["pitch"], cpu["yaw"], cpu["roll"], cpu["t"],
                cpu["exp"], cpu["scale"], cpu["kp"])

    def __del__(self):
        if hasattr(self, "model"):
            del self.model
