# ruff: noqa
"""Small fused Metal kernels for DenseMotion."""

from __future__ import annotations

import mlx.core as mx


_SOFTMAX_DEFORMATION_KERNELS = {}
_PACK_DENSE_MOTION_INPUT_KERNELS = {}


_SOFTMAX_DEFORMATION_SRC = """
    uint idx = thread_position_in_grid.x;

    int N = (int)mask_logits_shape[0];
    int D = (int)mask_logits_shape[1];
    int H = (int)mask_logits_shape[2];
    int W = (int)mask_logits_shape[3];
    int K = (int)mask_logits_shape[4];
    int total = N * D * H * W;
    if ((int)idx >= total) return;

    int w = (int)idx % W;
    int rem = (int)idx / W;
    int h = rem % H;
    rem /= H;
    int d = rem % D;
    int n = rem / D;

    int mask_base = (((n * D + d) * H + h) * W + w) * K;

    float max_logit = -INFINITY;
    for (int k = 0; k < K; ++k) {
        float v = (float)mask_logits[mask_base + k];
        max_logit = metal::max(max_logit, v);
    }

    float denom = 0.0f;
    float sx = 0.0f;
    float sy = 0.0f;
    float sz = 0.0f;

    for (int k = 0; k < K; ++k) {
        float m = metal::exp((float)mask_logits[mask_base + k] - max_logit);
        int sparse_base = ((((n * K + k) * D + d) * H + h) * W + w) * 3;
        sx += m * (float)sparse_motion[sparse_base + 0];
        sy += m * (float)sparse_motion[sparse_base + 1];
        sz += m * (float)sparse_motion[sparse_base + 2];
        denom += m;
    }

    float inv_denom = 1.0f / denom;
    int out_base = (((n * D + d) * H + h) * W + w) * 3;
    deformation[out_base + 0] = (T)(sx * inv_denom);
    deformation[out_base + 1] = (T)(sy * inv_denom);
    deformation[out_base + 2] = (T)(sz * inv_denom);
"""


_PACK_DENSE_MOTION_INPUT_SRC = """
    uint idx = thread_position_in_grid.x;

    int N = (int)deformed_feature_shape[0];
    int K = (int)deformed_feature_shape[1];
    int D = (int)deformed_feature_shape[2];
    int H = (int)deformed_feature_shape[3];
    int W = (int)deformed_feature_shape[4];
    int C = (int)deformed_feature_shape[5];
    int CP1 = C + 1;
    int OUTC = K * CP1;
    int total = N * D * H * W * OUTC;
    if ((int)idx >= total) return;

    int out_ch = (int)idx % OUTC;
    int rem = (int)idx / OUTC;
    int w = rem % W;
    rem /= W;
    int h = rem % H;
    rem /= H;
    int d = rem % D;
    int n = rem / D;

    int k = out_ch / CP1;
    int lane = out_ch - k * CP1;

    if (lane == 0) {
        if (k == 0) {
            output[idx] = (T)0;
            return;
        }

        int kp = k - 1;
        float x = ((float)w / (float)(W - 1)) * 2.0f - 1.0f;
        float y = ((float)h / (float)(H - 1)) * 2.0f - 1.0f;
        float z = ((float)d / (float)(D - 1)) * 2.0f - 1.0f;

        int kp_base = (n * (K - 1) + kp) * 3;
        float dx = x - (float)kp_driving[kp_base + 0];
        float dy = y - (float)kp_driving[kp_base + 1];
        float dz = z - (float)kp_driving[kp_base + 2];
        float dist = dx * dx + dy * dy + dz * dz;
        float g_d = metal::exp(-50.0f * dist);

        int gs_base = (((n * (K - 1) + kp) * D + d) * H + h) * W + w;
        output[idx] = (T)(g_d - (float)source_gaussian[gs_base]);
        return;
    }

    int c = lane - 1;
    int feature_base = (((((n * K + k) * D + d) * H + h) * W + w) * C + c);
    output[idx] = deformed_feature[feature_base];
"""


def _dtype_name(dtype) -> str:
    return str(dtype).replace("mlx.core.", "").replace(".", "_")


def _get_softmax_deformation_kernel(dtype):
    key = str(dtype)
    if key not in _SOFTMAX_DEFORMATION_KERNELS:
        _SOFTMAX_DEFORMATION_KERNELS[key] = mx.fast.metal_kernel(
            name=f"softmax_deformation_{_dtype_name(dtype)}",
            input_names=["mask_logits", "sparse_motion"],
            output_names=["deformation"],
            source=_SOFTMAX_DEFORMATION_SRC,
        )
    return _SOFTMAX_DEFORMATION_KERNELS[key]


def _get_pack_dense_motion_input_kernel(dtype):
    key = str(dtype)
    if key not in _PACK_DENSE_MOTION_INPUT_KERNELS:
        _PACK_DENSE_MOTION_INPUT_KERNELS[key] = mx.fast.metal_kernel(
            name=f"pack_dense_motion_input_{_dtype_name(dtype)}",
            input_names=["deformed_feature", "kp_driving", "source_gaussian"],
            output_names=["output"],
            source=_PACK_DENSE_MOTION_INPUT_SRC,
        )
    return _PACK_DENSE_MOTION_INPUT_KERNELS[key]


def pack_dense_motion_input(
    deformed_feature: mx.array,
    kp_driving: mx.array,
    source_gaussian: mx.array,
) -> mx.array:
    """Build hourglass input directly as NDHW((K+1)*(C+1)).

    ``deformed_feature`` is NKDHW(C), ``kp_driving`` is N(K-1)3, and
    ``source_gaussian`` is N(K-1)DHW. The identity branch receives a zero
    heatmap channel, matching the pure MLX construction.
    """
    if deformed_feature.ndim != 6:
        raise ValueError(f"expected deformed feature NKDHWC, got {deformed_feature.shape}")
    if kp_driving.ndim != 3 or kp_driving.shape[-1] != 3:
        raise ValueError(f"expected driving keypoints NK3, got {kp_driving.shape}")
    if source_gaussian.ndim != 5:
        raise ValueError(f"expected source gaussian NKDHW, got {source_gaussian.shape}")

    n, k, d, h, w, c = deformed_feature.shape
    if kp_driving.shape[0] != n or kp_driving.shape[1] != k - 1:
        raise ValueError(f"incompatible driving keypoints: {kp_driving.shape}, feature {deformed_feature.shape}")
    if source_gaussian.shape != (n, k - 1, d, h, w):
        raise ValueError(f"incompatible source gaussian: {source_gaussian.shape}, feature {deformed_feature.shape}")

    if kp_driving.dtype != deformed_feature.dtype:
        kp_driving = kp_driving.astype(deformed_feature.dtype)
    if source_gaussian.dtype != deformed_feature.dtype:
        source_gaussian = source_gaussian.astype(deformed_feature.dtype)

    out_channels = k * (c + 1)
    total = n * d * h * w * out_channels
    kernel = _get_pack_dense_motion_input_kernel(deformed_feature.dtype)
    return kernel(
        inputs=[deformed_feature, kp_driving, source_gaussian],
        template=[("T", deformed_feature.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, d, h, w, out_channels)],
        output_dtypes=[deformed_feature.dtype],
    )[0]


def softmax_deformation(mask_logits: mx.array, sparse_motion: mx.array) -> mx.array:
    """Fuse softmax(mask_logits) and weighted sparse-motion reduction.

    ``mask_logits`` is NDHWK and ``sparse_motion`` is NKDHW3. The result is
    NDHW3. This avoids materializing the mask, its transpose, the broadcasted
    product, and the reduction as separate MLX graph nodes.
    """
    if mask_logits.ndim != 5:
        raise ValueError(f"expected mask logits NDHWK, got {mask_logits.shape}")
    if sparse_motion.ndim != 6 or sparse_motion.shape[-1] != 3:
        raise ValueError(f"expected sparse motion NKDHW3, got {sparse_motion.shape}")
    if mask_logits.shape[0] != sparse_motion.shape[0] or mask_logits.shape[-1] != sparse_motion.shape[1]:
        raise ValueError(f"incompatible mask/motion shapes: {mask_logits.shape}, {sparse_motion.shape}")
    if mask_logits.shape[1:4] != sparse_motion.shape[2:5]:
        raise ValueError(f"incompatible spatial shapes: {mask_logits.shape}, {sparse_motion.shape}")
    if mask_logits.dtype != sparse_motion.dtype:
        sparse_motion = sparse_motion.astype(mask_logits.dtype)

    n, d, h, w, _ = mask_logits.shape
    total = n * d * h * w
    kernel = _get_softmax_deformation_kernel(mask_logits.dtype)
    return kernel(
        inputs=[mask_logits, sparse_motion],
        template=[("T", mask_logits.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, d, h, w, 3)],
        output_dtypes=[mask_logits.dtype],
    )[0]
