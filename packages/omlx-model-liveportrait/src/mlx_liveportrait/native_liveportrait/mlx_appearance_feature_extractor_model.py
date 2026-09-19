# ruff: noqa
# -*- coding: utf-8 -*-
"""MLX appearance_feature_extractor wrapper. Returns numpy NCDHW for
compatibility with the existing pipeline's caching path (which calls
`.copy()` on the result)."""

from __future__ import annotations

import os

import numpy as np
import mlx.core as mx
import mlx.utils as mu

from .mlx_modules.appearance_feature_extractor import AppearanceFeatureExtractor
from .mlx_modules.util import freeze_batch_norm_3d
from .mlx_modules.weight_convert import load_into_model


class MlxAppearanceFeatureExtractorModel:
    def __init__(self, **kwargs):
        self.predict_type = "mlx"
        from .mlx_warping_spade_model import _resolve_dtype, _cast_params
        self.dtype = _resolve_dtype(kwargs)

        self.model = AppearanceFeatureExtractor(
            image_channel=3, block_expansion=64, num_down_blocks=2, max_features=512,
            reshape_channel=32, reshape_depth=16, num_resblocks=6,
        )
        load_into_model(
            self.model,
            kwargs["model_path"],
            key_renames=((r"resblocks_3d\.3dr(\d+)\.", r"resblocks_3d.\1."),),
            strict=True,
        )
        self.model.eval()
        _cast_params(self.model, self.dtype)
        freeze_batch_norm_3d(self.model, self.dtype)
        mx.eval(self.model.parameters())
        if kwargs.get("compile_model", None) is None:
            compile_model = os.environ.get("FLP_MLX_COMPILE_APPEARANCE", "1") == "1"
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
        x_mx = (mx.array(img[None]).astype(mx.float32) / 255.0).astype(self.dtype)  # (1, H, W, 3)
        out = self._model_fn(x_mx)  # (1, D, H, W, R)
        if out.dtype != mx.float32:
            out = out.astype(mx.float32)
        mx.eval(out)
        out_np = np.array(out, dtype=np.float32)
        return np.transpose(out_np, (0, 4, 1, 2, 3))  # (1, R=32, D=16, H=64, W=64)

    def __del__(self):
        if hasattr(self, "model"):
            del self.model
