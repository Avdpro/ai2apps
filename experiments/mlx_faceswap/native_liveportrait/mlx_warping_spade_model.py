# ruff: noqa
# -*- coding: utf-8 -*-
"""MLX implementation of warping_module + spade_generator combined inference."""

from __future__ import annotations

import os

import numpy as np
import mlx.core as mx
import mlx.utils as mu

from .mlx_modules.warping_network import WarpingNetwork
from .mlx_modules.spade_generator import SPADEDecoder
from .mlx_modules.image_kernels import image_to_uint8
from .mlx_modules.util import freeze_batch_norm_3d
from .mlx_modules.weight_convert import load_into_model


WARPING_PARAMS = dict(
    num_kp=21,
    block_expansion=64,
    max_features=512,
    num_down_blocks=2,
    reshape_channel=32,
    estimate_occlusion_map=True,
    dense_motion_params=dict(
        block_expansion=32,
        max_features=1024,
        num_blocks=5,
        reshape_depth=16,
        compress=4,
    ),
)

SPADE_PARAMS = dict(
    upscale=2,
    block_expansion=64,
    max_features=512,
    num_down_blocks=2,
)


_DTYPE_MAP = {
    "fp32": mx.float32, "float32": mx.float32,
    "fp16": mx.float16, "float16": mx.float16, "half": mx.float16,
    "bf16": mx.bfloat16, "bfloat16": mx.bfloat16,
}


def _resolve_dtype(kwargs):
    dt = kwargs.get("dtype")
    if dt is not None:
        return _DTYPE_MAP[dt.lower()]
    if kwargs.get("use_bf16"):
        return mx.bfloat16
    if kwargs.get("use_fp16"):
        return mx.float16
    return mx.float32


def _cast_params(model, dtype):
    if dtype == mx.float32:
        return
    flat = dict(mu.tree_flatten(model.parameters()))
    model.update(mu.tree_unflatten([(k, v.astype(dtype)) for k, v in flat.items()]))


class MlxWarpingSpadeModel:
    """warping_module + spade_generator running on MLX (Apple Silicon)."""

    def __init__(self, **kwargs):
        self.predict_type = "mlx"

        self.dtype = _resolve_dtype(kwargs)

        warping_path, spade_path = kwargs["model_path"]

        self.warping = WarpingNetwork(**WARPING_PARAMS)
        load_into_model(self.warping, warping_path, strict=True)
        self.warping.eval()

        self.spade = SPADEDecoder(**SPADE_PARAMS)
        load_into_model(self.spade, spade_path, strict=True)
        self.spade.eval()

        _cast_params(self.warping, self.dtype)
        _cast_params(self.spade, self.dtype)
        freeze_batch_norm_3d(self.warping, self.dtype)

        mx.eval(self.warping.parameters())
        mx.eval(self.spade.parameters())

        compile_spade = kwargs.get("compile_spade")
        if compile_spade is None:
            compile_spade = os.environ.get("FLP_MLX_COMPILE_SPADE", "1") == "1"
        if compile_spade:
            spade = self.spade
            self._spade_fn = mx.compile(lambda x: spade(x))
        else:
            self._spade_fn = self.spade

        compile_warping = kwargs.get("compile_warping")
        if compile_warping is None:
            compile_warping = os.environ.get("FLP_MLX_COMPILE_WARPING", "0") == "1"
        if compile_warping:
            warping = self.warping
            self._warping_fn = mx.compile(lambda f_s, kp_d, kp_s: warping(f_s, kp_d, kp_s)["out"])
        else:
            self._warping_fn = None

        self._feature_cache_key = None
        self._feature_cache_value = None
        self._kp_source_cache_key = None
        self._kp_source_cache_value = None
        self._temporal_warp_interval = int(
            kwargs.get("temporal_warp_interval", os.environ.get("FLP_MLX_TEMPORAL_WARP_INTERVAL", "1"))
        )
        self._temporal_warp_interval = max(1, self._temporal_warp_interval)
        self._temporal_warp_threshold = float(
            kwargs.get(
                "temporal_warp_threshold",
                os.environ.get("FLP_MLX_TEMPORAL_WARP_THRESHOLD", "0"),
            )
        )
        self._temporal_warp_index = 0
        self._temporal_warp_source_key = None
        self._temporal_warp_value = None
        self._temporal_warp_prev_kp_np = None
        self._fused_uint8 = os.environ.get("FLP_MLX_FUSED_UINT8", "1") == "1"

    def reset_temporal_cache(self):
        self._temporal_warp_index = 0
        self._temporal_warp_source_key = None
        self._temporal_warp_value = None
        self._temporal_warp_prev_kp_np = None

    def _to_mx(self, x):
        if isinstance(x, mx.array):
            return x if x.dtype == self.dtype else x.astype(self.dtype)
        return mx.array(np.asarray(x, dtype=np.float32)).astype(self.dtype)

    def _array_cache_key(self, x):
        arr = np.asarray(x)
        return (
            id(arr),
            arr.__array_interface__["data"][0],
            arr.shape,
            arr.strides,
            arr.dtype.str,
            self.dtype,
        ), arr

    def _feature_to_mx(self, feature):
        if isinstance(feature, mx.array):
            return feature if feature.dtype == self.dtype else feature.astype(self.dtype)

        cache_key, arr = self._array_cache_key(feature)
        if cache_key == self._feature_cache_key and self._feature_cache_value is not None:
            return self._feature_cache_value

        # f_s comes in as NCDHW (1, 32, 16, 64, 64). Convert once to NDHWC.
        if arr.ndim == 5 and arr.shape[1] == 32 and arr.shape[2] == 16:
            arr = np.transpose(arr, (0, 2, 3, 4, 1))
        feature_mx = self._to_mx(arr)
        mx.eval(feature_mx)
        self._feature_cache_key = cache_key
        self._feature_cache_value = feature_mx
        return feature_mx

    def _source_kp_to_mx(self, kp_source):
        if isinstance(kp_source, mx.array):
            return kp_source if kp_source.dtype == self.dtype else kp_source.astype(self.dtype)

        cache_key, arr = self._array_cache_key(kp_source)
        if cache_key == self._kp_source_cache_key and self._kp_source_cache_value is not None:
            return self._kp_source_cache_value

        kp_mx = self._to_mx(arr)
        mx.eval(kp_mx)
        self._kp_source_cache_key = cache_key
        self._kp_source_cache_value = kp_mx
        return kp_mx

    def _temporal_source_key(self, feature: mx.array, kp_source: mx.array):
        return (
            id(feature),
            tuple(feature.shape),
            str(feature.dtype),
            id(kp_source),
            tuple(kp_source.shape),
            str(kp_source.dtype),
        )

    def _driving_keypoint_delta(self, kp_d_np):
        if self._temporal_warp_threshold <= 0 or self._temporal_warp_prev_kp_np is None:
            return None
        return float(np.max(np.abs(kp_d_np.astype(np.float32, copy=False) - self._temporal_warp_prev_kp_np)))

    def _fresh_warping_out(self, f_s_mx: mx.array, kp_d_mx: mx.array, kp_s_mx: mx.array):
        if self._warping_fn is not None:
            return self._warping_fn(f_s_mx, kp_d_mx, kp_s_mx)
        return self.warping(f_s_mx, kp_d_mx, kp_s_mx)["out"]

    def _warping_out(self, f_s_mx: mx.array, kp_d_mx: mx.array, kp_s_mx: mx.array, kp_delta=None, kp_d_np=None):
        if self._temporal_warp_interval <= 1:
            return self._fresh_warping_out(f_s_mx, kp_d_mx, kp_s_mx)

        source_key = self._temporal_source_key(f_s_mx, kp_s_mx)
        if source_key != self._temporal_warp_source_key:
            self._temporal_warp_source_key = source_key
            self._temporal_warp_index = 0
            self._temporal_warp_value = None
            self._temporal_warp_prev_kp_np = None

        should_refresh = (
            self._temporal_warp_value is None
            or self._temporal_warp_index % self._temporal_warp_interval == 0
            or (kp_delta is not None and kp_delta > self._temporal_warp_threshold)
        )
        if should_refresh:
            out = self._fresh_warping_out(f_s_mx, kp_d_mx, kp_s_mx)
            mx.eval(out)
            self._temporal_warp_value = out
            if kp_d_np is not None:
                self._temporal_warp_prev_kp_np = kp_d_np.astype(np.float32, copy=True)
        else:
            out = self._temporal_warp_value
        self._temporal_warp_index += 1
        return out

    def predict(
        self,
        *data,
        return_numpy: bool = False,
        return_uint8: bool = False,
        return_mx: bool = False,
        return_torch: bool = False,
    ):
        # data = (f_s NCDHW numpy, kp_source numpy, kp_driving numpy)
        if return_torch:
            raise ValueError("return_torch is not supported in the MLX-only runtime")
        if return_mx and return_numpy:
            raise ValueError("return_mx and return_numpy are mutually exclusive")
        f_s_pt, kp_s, kp_d = data
        f_s_mx = self._feature_to_mx(f_s_pt)
        kp_s_mx = self._source_kp_to_mx(kp_s)
        kp_d_np = None if isinstance(kp_d, mx.array) else np.asarray(kp_d, dtype=np.float32)
        kp_delta = self._driving_keypoint_delta(kp_d_np) if kp_d_np is not None else None
        kp_d_mx = self._to_mx(kp_d)

        warped_feature = self._warping_out(f_s_mx, kp_d_mx, kp_s_mx, kp_delta=kp_delta, kp_d_np=kp_d_np)
        img = self._spade_fn(warped_feature)  # (N, H, W, 3) in [0, 1]
        if return_uint8 and self._fused_uint8:
            img = image_to_uint8(img)
        elif img.dtype != mx.float32:
            img = img.astype(mx.float32)
        if not (return_uint8 and self._fused_uint8):
            img = mx.clip(img, 0.0, 1.0) * 255.0
            if return_uint8:
                img = img.astype(mx.uint8)
        if return_mx:
            mx.eval(img)
            return img
        mx.eval(img)

        # MLX (N, H, W, 3) -> NumPy (H, W, 3), in [0, 255].
        if return_uint8:
            img_np = np.array(img, dtype=np.uint8)[0]  # (H, W, 3)
        else:
            img_np = np.array(img, dtype=np.float32)[0]  # (H, W, 3)
        return img_np

    def __del__(self):
        for attr in ("warping", "spade"):
            if hasattr(self, attr):
                delattr(self, attr)
