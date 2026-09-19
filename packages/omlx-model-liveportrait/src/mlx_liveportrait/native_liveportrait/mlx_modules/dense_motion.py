# ruff: noqa
"""DenseMotionNetwork: predicts the dense motion field used by WarpingNetwork.

Layout convention in this module is NDHWC (and NKDHWC for keypoint-indexed
tensors), the natural MLX channel-last layout.
"""

from __future__ import annotations

import mlx.core as mx
import mlx.nn as nn

from .util import Hourglass, BatchNorm3d, make_coordinate_grid, kp2gaussian, conv3d_via_2d
from .grid_sample import grid_sample_3d, grid_sample_3d_sparse_motions
from .mask_conv import (
    mask_conv3d_direct_metal,
    mask_conv3d_packed_2d,
    mask_conv3d_packed_2d_stack,
    mask_conv3d_tensorops_tiled,
    pack_mask_conv3d_weight_2d,
    pack_mask_conv3d_weight_tensorops,
)
from .motion_kernels import pack_dense_motion_input, softmax_deformation
from .tensor_ops import conv3d_1x1_tensorops


import os
_MASK_BACKEND = os.environ.get("FLP_MLX_MASK_BACKEND")
if _MASK_BACKEND is None:
    _MASK_BACKEND = "packed2d" if os.environ.get("FLP_MLX_2D_MASK", "1") == "1" else "native"
_COMPRESS_BACKEND = os.environ.get("FLP_MLX_COMPRESS_BACKEND", "native")
_COMPILE_HOURGLASS = os.environ.get("FLP_MLX_COMPILE_HOURGLASS", "1") == "1"
_FUSED_DEFORMATION = os.environ.get("FLP_MLX_FUSED_DEFORMATION", "0") == "1"
_FUSED_SPARSE_SAMPLE = os.environ.get("FLP_MLX_FUSED_SPARSE_SAMPLE", "0") == "1"
_FUSED_HOURGLASS_INPUT = os.environ.get("FLP_MLX_FUSED_HOURGLASS_INPUT", "0") == "1"
_CACHE_SOURCE_GAUSSIAN = (
    os.environ.get("FLP_MLX_CACHE_SOURCE_GAUSSIAN", "1") == "1"
    and os.environ.get("FLP_MLX_COMPILE_WARPING", "0") != "1"
)
_SKIP_OCCLUSION = os.environ.get("FLP_MLX_SKIP_OCCLUSION", "0") == "1"


class DenseMotionNetwork(nn.Module):
    def __init__(
        self,
        block_expansion: int,
        num_blocks: int,
        max_features: int,
        num_kp: int,
        feature_channel: int,
        reshape_depth: int,
        compress: int,
        estimate_occlusion_map: bool = True,
    ):
        super().__init__()
        in_features = (num_kp + 1) * (compress + 1)
        self.hourglass = Hourglass(
            block_expansion=block_expansion,
            in_features=in_features,
            max_features=max_features,
            num_blocks=num_blocks,
        )
        if _COMPILE_HOURGLASS:
            hourglass = self.hourglass
            self._hourglass_fn = mx.compile(lambda x: hourglass(x))
        else:
            self._hourglass_fn = self.hourglass
        self.mask = nn.Conv3d(self.hourglass.out_filters, num_kp + 1, kernel_size=7, padding=3)
        self.compress = nn.Conv3d(feature_channel, compress, kernel_size=1)
        self.norm = BatchNorm3d(compress)
        self.num_kp = num_kp
        self.flag_estimate_occlusion_map = estimate_occlusion_map
        self._source_gaussian_kp = None
        self._source_gaussian_shape = None
        self._source_gaussian = None
        self._mask_tensorops_weight_source = None
        self._mask_tensorops_weight_packed = None
        self._mask_2d_weight_source = None
        self._mask_2d_weight_packed = None

        if estimate_occlusion_map:
            self.occlusion = nn.Conv2d(
                self.hourglass.out_filters * reshape_depth, 1, kernel_size=7, padding=3
            )
        else:
            self.occlusion = None

    def create_sparse_motions(self, feature, kp_driving, kp_source):
        # feature: (N, D, H, W, _) -- only shape used.
        n, d, h, w, _ = feature.shape
        identity_grid = make_coordinate_grid((d, h, w), dtype=kp_source.dtype)
        identity_grid = identity_grid.reshape(1, 1, d, h, w, 3)
        coordinate_grid = identity_grid - kp_driving.reshape(n, self.num_kp, 1, 1, 1, 3)
        driving_to_source = coordinate_grid + kp_source.reshape(n, self.num_kp, 1, 1, 1, 3)
        # (N, 1, D, H, W, 3) for the identity branch
        identity_grid_b = mx.broadcast_to(identity_grid, (n, 1, d, h, w, 3))
        return mx.concatenate([identity_grid_b, driving_to_source], axis=1)

    def create_deformed_feature(self, feature, sparse_motions):
        # feature: (N, D, H, W, C). Sparse_motions: (N, K+1, D, H, W, 3)
        if _FUSED_SPARSE_SAMPLE:
            return grid_sample_3d_sparse_motions(feature, sparse_motions, align_corners=False)
        n, d, h, w, c = feature.shape
        kpp1 = self.num_kp + 1
        feat_rep = mx.broadcast_to(feature[:, None, ...], (n, kpp1, d, h, w, c))
        feat_rep = feat_rep.reshape(n * kpp1, d, h, w, c)
        sm = sparse_motions.reshape(n * kpp1, d, h, w, 3)
        out = grid_sample_3d(feat_rep, sm, align_corners=False)
        return out.reshape(n, kpp1, d, h, w, c)

    def _source_gaussian_for(self, kp_source, spatial_size):
        if not _CACHE_SOURCE_GAUSSIAN:
            return kp2gaussian(kp_source, spatial_size, kp_variance=0.01)
        if (
            self._source_gaussian_kp is kp_source
            and self._source_gaussian_shape == tuple(spatial_size)
            and self._source_gaussian is not None
        ):
            return self._source_gaussian
        g_s = kp2gaussian(kp_source, spatial_size, kp_variance=0.01)
        mx.eval(g_s)
        self._source_gaussian_kp = kp_source
        self._source_gaussian_shape = tuple(spatial_size)
        self._source_gaussian = g_s
        return g_s

    def create_heatmap_representations(self, feature, kp_driving, kp_source):
        # feature: (N, K+1, D, H, W, C). spatial_size = (D, H, W)
        spatial_size = feature.shape[2:5]
        g_d = kp2gaussian(kp_driving, spatial_size, kp_variance=0.01)  # (N, K, D, H, W)
        g_s = self._source_gaussian_for(kp_source, spatial_size)
        heatmap = g_d - g_s
        n = heatmap.shape[0]
        zeros = mx.zeros((n, 1, *spatial_size), dtype=heatmap.dtype)
        heatmap = mx.concatenate([zeros, heatmap], axis=1)  # (N, K+1, D, H, W)
        return heatmap[..., None]  # (N, K+1, D, H, W, 1)

    def create_hourglass_input(self, deformed_feature, kp_driving, kp_source):
        if _FUSED_HOURGLASS_INPUT:
            spatial_size = deformed_feature.shape[2:5]
            g_s = self._source_gaussian_for(kp_source, spatial_size)
            return pack_dense_motion_input(deformed_feature, kp_driving, g_s)
        else:
            heatmap = self.create_heatmap_representations(deformed_feature, kp_driving, kp_source)
            x = mx.concatenate([heatmap, deformed_feature], axis=-1)
            x = mx.transpose(x, (0, 2, 3, 4, 1, 5))
            return x.reshape(x.shape[0], x.shape[1], x.shape[2], x.shape[3], x.shape[4] * x.shape[5])

    def _tensorops_mask_weight(self):
        if self._mask_tensorops_weight_source is not self.mask.weight:
            weight = pack_mask_conv3d_weight_tensorops(self.mask.weight)
            mx.eval(weight)
            self._mask_tensorops_weight_source = self.mask.weight
            self._mask_tensorops_weight_packed = weight
        return self._mask_tensorops_weight_packed

    def _packed_2d_mask_weight(self):
        if self._mask_2d_weight_source is not self.mask.weight:
            weight = pack_mask_conv3d_weight_2d(self.mask.weight)
            mx.eval(weight)
            self._mask_2d_weight_source = self.mask.weight
            self._mask_2d_weight_packed = weight
        return self._mask_2d_weight_packed

    def __call__(self, feature, kp_driving, kp_source):
        # feature: (N, D, H, W, feature_channel)
        n, d, h, w, _ = feature.shape

        # Compress + BN3d + ReLU
        if _COMPRESS_BACKEND == "tensorops":
            feature = conv3d_1x1_tensorops(feature, self.compress.weight, self.compress.bias)
        else:
            feature = self.compress(feature)
        feature = self.norm(feature)
        feature = nn.relu(feature)

        sparse_motion = self.create_sparse_motions(feature, kp_driving, kp_source)
        deformed_feature = self.create_deformed_feature(feature, sparse_motion)
        x = self.create_hourglass_input(deformed_feature, kp_driving, kp_source)

        prediction = self._hourglass_fn(x)  # (N, D, H, W, hourglass_out)
        if _MASK_BACKEND == "tensorops":
            mask_logits = mask_conv3d_tensorops_tiled(
                prediction, self._tensorops_mask_weight(), self.mask.bias
            )
        elif _MASK_BACKEND == "packed2d":
            mask_logits = mask_conv3d_packed_2d(
                prediction,
                self._packed_2d_mask_weight(),
                self.mask.bias,
                depth_kernel=self.mask.weight.shape[1],
                padding=3,
            )
        elif _MASK_BACKEND == "packed2d_stack":
            mask_logits = mask_conv3d_packed_2d_stack(
                prediction,
                self._packed_2d_mask_weight(),
                self.mask.bias,
                depth_kernel=self.mask.weight.shape[1],
                padding=3,
            )
        elif _MASK_BACKEND == "metal":
            mask_logits = mask_conv3d_direct_metal(prediction, self.mask.weight, self.mask.bias)
        elif _MASK_BACKEND == "2d":
            mask_logits = conv3d_via_2d(prediction, self.mask.weight, self.mask.bias, padding=3)
        else:
            mask_logits = self.mask(prediction)  # (N, D, H, W, K+1)
        if _FUSED_DEFORMATION:
            deformation = softmax_deformation(mask_logits, sparse_motion)
            out = {"deformation": deformation}
        else:
            mask = mx.softmax(mask_logits, axis=-1)
            # Take mask in shape (N, K+1, D, H, W, 1) for broadcasting against sparse_motion
            mask_perm = mx.transpose(mask, (0, 4, 1, 2, 3))[..., None]
            # sparse_motion: (N, K+1, D, H, W, 3)
            deformation = mx.sum(sparse_motion * mask_perm, axis=1)  # (N, D, H, W, 3)
            out = {"mask": mask, "deformation": deformation}

        if self.flag_estimate_occlusion_map and not _SKIP_OCCLUSION:
            # PyTorch did `prediction.view(B, F*D, H, W)` on a (B, F, D, H, W)
            # tensor, flattening (F, D) with F outer / D inner. In NDHWC we
            # transpose to (N, H, W, F, D) before the channel reshape so the
            # last axis carries the same f*D + d ordering that the occlusion
            # conv expects.
            n_, d_, h_, w_, f_ = prediction.shape
            pred2d = mx.transpose(prediction, (0, 2, 3, 4, 1)).reshape(n_, h_, w_, f_ * d_)
            occ = mx.sigmoid(self.occlusion(pred2d))  # (N, H, W, 1)
            out["occlusion_map"] = occ

        return out
