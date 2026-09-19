# ruff: noqa
"""5D `grid_sample` for MLX.

MLX has no built-in equivalent of PyTorch's `F.grid_sample`. We implement the
trilinear, zero-padded variant on volumetric inputs that the warping module
relies on. The interface mirrors PyTorch:

    grid_sample_3d(input, grid, align_corners=False) -> array

Layout follows MLX's NDHWC convention:

    input  : (N, D, H, W, C)
    grid   : (N, Do, Ho, Wo, 3)   last axis is (x, y, z) in [-1, 1]
    output : (N, Do, Ho, Wo, C)
"""

from __future__ import annotations

import os

import mlx.core as mx


_USE_GATHER = os.environ.get("FLP_MLX_GS3D_GATHER", "0") == "1"


_KERNEL_SRC_TMPL = """
    uint idx = thread_position_in_grid.x;
    int N  = (int)input_shape[0];
    int D  = (int)input_shape[1];
    int H  = (int)input_shape[2];
    int W  = (int)input_shape[3];
    int C  = (int)input_shape[4];
    int Do = (int)grid_shape[1];
    int Ho = (int)grid_shape[2];
    int Wo = (int)grid_shape[3];
    int total = N * Do * Ho * Wo * C;
    if ((int)idx >= total) return;

    int c   = (int)idx % C;
    int rem = (int)idx / C;
    int wo_ = rem % Wo;
    rem /= Wo;
    int ho_ = rem % Ho;
    rem /= Ho;
    int do_ = rem % Do;
    int n   = rem / Do;

    int g_base = (((n * Do + do_) * Ho + ho_) * Wo + wo_) * 3;
    float gx = (float)grid[g_base + 0];
    float gy = (float)grid[g_base + 1];
    float gz = (float)grid[g_base + 2];

    float x, y, z;
    if (ALIGN_CORNERS) {
        x = (gx + 1.0f) * (float)(W - 1) * 0.5f;
        y = (gy + 1.0f) * (float)(H - 1) * 0.5f;
        z = (gz + 1.0f) * (float)(D - 1) * 0.5f;
    } else {
        x = ((gx + 1.0f) * (float)W - 1.0f) * 0.5f;
        y = ((gy + 1.0f) * (float)H - 1.0f) * 0.5f;
        z = ((gz + 1.0f) * (float)D - 1.0f) * 0.5f;
    }

    int x0 = (int)metal::floor(x), y0 = (int)metal::floor(y), z0 = (int)metal::floor(z);
    int x1 = x0 + 1,                y1 = y0 + 1,                z1 = z0 + 1;
    float wx = x - (float)x0;
    float wy = y - (float)y0;
    float wz = z - (float)z0;

    int DHWC = D * H * W * C;
    int HWC  = H * W * C;
    int WC   = W * C;
    int n_off = n * DHWC;

    auto fetch = [&](int zi, int yi, int xi) {
        if (zi < 0 || zi >= D || yi < 0 || yi >= H || xi < 0 || xi >= W) return 0.0f;
        int off = n_off + zi * HWC + yi * WC + xi * C + c;
        return (float)input[off];
    };

    float v000 = fetch(z0, y0, x0);
    float v001 = fetch(z0, y0, x1);
    float v010 = fetch(z0, y1, x0);
    float v011 = fetch(z0, y1, x1);
    float v100 = fetch(z1, y0, x0);
    float v101 = fetch(z1, y0, x1);
    float v110 = fetch(z1, y1, x0);
    float v111 = fetch(z1, y1, x1);

    float c00 = v000 * (1.0f - wx) + v001 * wx;
    float c01 = v010 * (1.0f - wx) + v011 * wx;
    float c10 = v100 * (1.0f - wx) + v101 * wx;
    float c11 = v110 * (1.0f - wx) + v111 * wx;
    float c0 = c00 * (1.0f - wy) + c01 * wy;
    float c1 = c10 * (1.0f - wy) + c11 * wy;
    output[idx] = (T)(c0 * (1.0f - wz) + c1 * wz);
"""


_KERNEL_TO_2D_CHANNELS_SRC_TMPL = """
    uint idx = thread_position_in_grid.x;
    int N  = (int)input_shape[0];
    int D  = (int)input_shape[1];
    int H  = (int)input_shape[2];
    int W  = (int)input_shape[3];
    int C  = (int)input_shape[4];
    int Do = (int)grid_shape[1];
    int Ho = (int)grid_shape[2];
    int Wo = (int)grid_shape[3];
    int CD = C * Do;
    int total = N * Ho * Wo * CD;
    if ((int)idx >= total) return;

    int cd = (int)idx % CD;
    int rem = (int)idx / CD;
    int wo_ = rem % Wo;
    rem /= Wo;
    int ho_ = rem % Ho;
    int n = rem / Ho;
    int do_ = cd % Do;
    int c = cd / Do;

    int g_base = (((n * Do + do_) * Ho + ho_) * Wo + wo_) * 3;
    float gx = (float)grid[g_base + 0];
    float gy = (float)grid[g_base + 1];
    float gz = (float)grid[g_base + 2];

    float x, y, z;
    if (ALIGN_CORNERS) {
        x = (gx + 1.0f) * (float)(W - 1) * 0.5f;
        y = (gy + 1.0f) * (float)(H - 1) * 0.5f;
        z = (gz + 1.0f) * (float)(D - 1) * 0.5f;
    } else {
        x = ((gx + 1.0f) * (float)W - 1.0f) * 0.5f;
        y = ((gy + 1.0f) * (float)H - 1.0f) * 0.5f;
        z = ((gz + 1.0f) * (float)D - 1.0f) * 0.5f;
    }

    int x0 = (int)metal::floor(x), y0 = (int)metal::floor(y), z0 = (int)metal::floor(z);
    int x1 = x0 + 1,                y1 = y0 + 1,                z1 = z0 + 1;
    float wx = x - (float)x0;
    float wy = y - (float)y0;
    float wz = z - (float)z0;

    int DHWC = D * H * W * C;
    int HWC  = H * W * C;
    int WC   = W * C;
    int n_off = n * DHWC;

    auto fetch = [&](int zi, int yi, int xi) {
        if (zi < 0 || zi >= D || yi < 0 || yi >= H || xi < 0 || xi >= W) return 0.0f;
        int off = n_off + zi * HWC + yi * WC + xi * C + c;
        return (float)input[off];
    };

    float v000 = fetch(z0, y0, x0);
    float v001 = fetch(z0, y0, x1);
    float v010 = fetch(z0, y1, x0);
    float v011 = fetch(z0, y1, x1);
    float v100 = fetch(z1, y0, x0);
    float v101 = fetch(z1, y0, x1);
    float v110 = fetch(z1, y1, x0);
    float v111 = fetch(z1, y1, x1);

    float c00 = v000 * (1.0f - wx) + v001 * wx;
    float c01 = v010 * (1.0f - wx) + v011 * wx;
    float c10 = v100 * (1.0f - wx) + v101 * wx;
    float c11 = v110 * (1.0f - wx) + v111 * wx;
    float c0 = c00 * (1.0f - wy) + c01 * wy;
    float c1 = c10 * (1.0f - wy) + c11 * wy;
    output[idx] = (T)(c0 * (1.0f - wz) + c1 * wz);
"""


_KERNEL_TO_2D_CHANNELS_C4_SRC_TMPL = """
    uint idx = thread_position_in_grid.x;
    int N  = (int)input_shape[0];
    int D  = (int)input_shape[1];
    int H  = (int)input_shape[2];
    int W  = (int)input_shape[3];
    int C  = (int)input_shape[4];
    int Do = (int)grid_shape[1];
    int Ho = (int)grid_shape[2];
    int Wo = (int)grid_shape[3];
    int C4 = C / 4;
    int total = N * Ho * Wo * Do * C4;
    if ((int)idx >= total) return;

    int c4 = (int)idx % C4;
    int rem = (int)idx / C4;
    int do_ = rem % Do;
    rem /= Do;
    int wo_ = rem % Wo;
    rem /= Wo;
    int ho_ = rem % Ho;
    int n = rem / Ho;
    int c0 = c4 * 4;

    int g_base = (((n * Do + do_) * Ho + ho_) * Wo + wo_) * 3;
    float gx = (float)grid[g_base + 0];
    float gy = (float)grid[g_base + 1];
    float gz = (float)grid[g_base + 2];

    float x, y, z;
    if (ALIGN_CORNERS) {
        x = (gx + 1.0f) * (float)(W - 1) * 0.5f;
        y = (gy + 1.0f) * (float)(H - 1) * 0.5f;
        z = (gz + 1.0f) * (float)(D - 1) * 0.5f;
    } else {
        x = ((gx + 1.0f) * (float)W - 1.0f) * 0.5f;
        y = ((gy + 1.0f) * (float)H - 1.0f) * 0.5f;
        z = ((gz + 1.0f) * (float)D - 1.0f) * 0.5f;
    }

    int x0 = (int)metal::floor(x), y0 = (int)metal::floor(y), z0 = (int)metal::floor(z);
    int x1 = x0 + 1,                y1 = y0 + 1,                z1 = z0 + 1;
    float wx = x - (float)x0;
    float wy = y - (float)y0;
    float wz = z - (float)z0;

    int DHWC = D * H * W * C;
    int HWC  = H * W * C;
    int WC   = W * C;
    int n_off = n * DHWC;
    int out_base = (((n * Ho + ho_) * Wo + wo_) * C + c0) * Do + do_;

    for (int lane = 0; lane < 4; ++lane) {
        int c = c0 + lane;
        auto fetch = [&](int zi, int yi, int xi) {
            if (zi < 0 || zi >= D || yi < 0 || yi >= H || xi < 0 || xi >= W) return 0.0f;
            int off = n_off + zi * HWC + yi * WC + xi * C + c;
            return (float)input[off];
        };

        float v000 = fetch(z0, y0, x0);
        float v001 = fetch(z0, y0, x1);
        float v010 = fetch(z0, y1, x0);
        float v011 = fetch(z0, y1, x1);
        float v100 = fetch(z1, y0, x0);
        float v101 = fetch(z1, y0, x1);
        float v110 = fetch(z1, y1, x0);
        float v111 = fetch(z1, y1, x1);

        float c00 = v000 * (1.0f - wx) + v001 * wx;
        float c01 = v010 * (1.0f - wx) + v011 * wx;
        float c10 = v100 * (1.0f - wx) + v101 * wx;
        float c11 = v110 * (1.0f - wx) + v111 * wx;
        float cy0 = c00 * (1.0f - wy) + c01 * wy;
        float cy1 = c10 * (1.0f - wy) + c11 * wy;
        output[out_base + lane * Do] = (T)(cy0 * (1.0f - wz) + cy1 * wz);
    }
"""


_KERNEL_SPARSE_MOTIONS_SRC_TMPL = """
    uint idx = thread_position_in_grid.x;
    int N  = (int)input_shape[0];
    int D  = (int)input_shape[1];
    int H  = (int)input_shape[2];
    int W  = (int)input_shape[3];
    int C  = (int)input_shape[4];
    int K  = (int)grid_shape[1];
    int Do = (int)grid_shape[2];
    int Ho = (int)grid_shape[3];
    int Wo = (int)grid_shape[4];
    int total = N * K * Do * Ho * Wo * C;
    if ((int)idx >= total) return;

    int c = (int)idx % C;
    int rem = (int)idx / C;
    int wo_ = rem % Wo;
    rem /= Wo;
    int ho_ = rem % Ho;
    rem /= Ho;
    int do_ = rem % Do;
    rem /= Do;
    int k = rem % K;
    int n = rem / K;

    int g_base = ((((n * K + k) * Do + do_) * Ho + ho_) * Wo + wo_) * 3;
    float gx = (float)grid[g_base + 0];
    float gy = (float)grid[g_base + 1];
    float gz = (float)grid[g_base + 2];

    float x, y, z;
    if (ALIGN_CORNERS) {
        x = (gx + 1.0f) * (float)(W - 1) * 0.5f;
        y = (gy + 1.0f) * (float)(H - 1) * 0.5f;
        z = (gz + 1.0f) * (float)(D - 1) * 0.5f;
    } else {
        x = ((gx + 1.0f) * (float)W - 1.0f) * 0.5f;
        y = ((gy + 1.0f) * (float)H - 1.0f) * 0.5f;
        z = ((gz + 1.0f) * (float)D - 1.0f) * 0.5f;
    }

    int x0 = (int)metal::floor(x), y0 = (int)metal::floor(y), z0 = (int)metal::floor(z);
    int x1 = x0 + 1,                y1 = y0 + 1,                z1 = z0 + 1;
    float wx = x - (float)x0;
    float wy = y - (float)y0;
    float wz = z - (float)z0;

    int DHWC = D * H * W * C;
    int HWC  = H * W * C;
    int WC   = W * C;
    int n_off = n * DHWC;

    auto fetch = [&](int zi, int yi, int xi) {
        if (zi < 0 || zi >= D || yi < 0 || yi >= H || xi < 0 || xi >= W) return 0.0f;
        int off = n_off + zi * HWC + yi * WC + xi * C + c;
        return (float)input[off];
    };

    float v000 = fetch(z0, y0, x0);
    float v001 = fetch(z0, y0, x1);
    float v010 = fetch(z0, y1, x0);
    float v011 = fetch(z0, y1, x1);
    float v100 = fetch(z1, y0, x0);
    float v101 = fetch(z1, y0, x1);
    float v110 = fetch(z1, y1, x0);
    float v111 = fetch(z1, y1, x1);

    float c00 = v000 * (1.0f - wx) + v001 * wx;
    float c01 = v010 * (1.0f - wx) + v011 * wx;
    float c10 = v100 * (1.0f - wx) + v101 * wx;
    float c11 = v110 * (1.0f - wx) + v111 * wx;
    float c0 = c00 * (1.0f - wy) + c01 * wy;
    float c1 = c10 * (1.0f - wy) + c11 * wy;
    output[idx] = (T)(c0 * (1.0f - wz) + c1 * wz);
"""


# Cached metal kernel objects keyed by (align_corners,)
_METAL_KERNELS = {}
_METAL_TO_2D_CHANNELS_KERNELS = {}
_METAL_TO_2D_CHANNELS_C4_KERNELS = {}
_METAL_SPARSE_MOTIONS_KERNELS = {}


def _get_metal_kernel(align_corners: bool):
    key = bool(align_corners)
    if key not in _METAL_KERNELS:
        src = _KERNEL_SRC_TMPL.replace("ALIGN_CORNERS", "1" if key else "0")
        _METAL_KERNELS[key] = mx.fast.metal_kernel(
            name=f"grid_sample_3d_{'ac' if key else 'noac'}",
            input_names=["input", "grid"],
            output_names=["output"],
            source=src,
        )
    return _METAL_KERNELS[key]


def _get_metal_to_2d_channels_kernel(align_corners: bool):
    key = bool(align_corners)
    if key not in _METAL_TO_2D_CHANNELS_KERNELS:
        src = _KERNEL_TO_2D_CHANNELS_SRC_TMPL.replace("ALIGN_CORNERS", "1" if key else "0")
        _METAL_TO_2D_CHANNELS_KERNELS[key] = mx.fast.metal_kernel(
            name=f"grid_sample_3d_to_2d_channels_{'ac' if key else 'noac'}",
            input_names=["input", "grid"],
            output_names=["output"],
            source=src,
        )
    return _METAL_TO_2D_CHANNELS_KERNELS[key]


def _get_metal_to_2d_channels_c4_kernel(align_corners: bool):
    key = bool(align_corners)
    if key not in _METAL_TO_2D_CHANNELS_C4_KERNELS:
        src = _KERNEL_TO_2D_CHANNELS_C4_SRC_TMPL.replace("ALIGN_CORNERS", "1" if key else "0")
        _METAL_TO_2D_CHANNELS_C4_KERNELS[key] = mx.fast.metal_kernel(
            name=f"grid_sample_3d_to_2d_channels_c4_{'ac' if key else 'noac'}",
            input_names=["input", "grid"],
            output_names=["output"],
            source=src,
        )
    return _METAL_TO_2D_CHANNELS_C4_KERNELS[key]


def _get_metal_sparse_motions_kernel(align_corners: bool):
    key = bool(align_corners)
    if key not in _METAL_SPARSE_MOTIONS_KERNELS:
        src = _KERNEL_SPARSE_MOTIONS_SRC_TMPL.replace("ALIGN_CORNERS", "1" if key else "0")
        _METAL_SPARSE_MOTIONS_KERNELS[key] = mx.fast.metal_kernel(
            name=f"grid_sample_3d_sparse_motions_{'ac' if key else 'noac'}",
            input_names=["input", "grid"],
            output_names=["output"],
            source=src,
        )
    return _METAL_SPARSE_MOTIONS_KERNELS[key]


def _grid_sample_3d_metal(input: mx.array, grid: mx.array, *, align_corners: bool) -> mx.array:
    n, d, h, w, c = input.shape
    _, do, ho, wo, _ = grid.shape
    total = n * do * ho * wo * c
    threadgroup = (256, 1, 1)
    grid_sz = ((total + 255) // 256 * 256, 1, 1)
    kernel = _get_metal_kernel(align_corners)
    outputs = kernel(
        inputs=[input, grid],
        template=[("T", input.dtype)],
        grid=grid_sz,
        threadgroup=threadgroup,
        output_shapes=[(n, do, ho, wo, c)],
        output_dtypes=[input.dtype],
    )
    return outputs[0]


def grid_sample_3d_to_2d_channels(
    input: mx.array,
    grid: mx.array,
    *,
    align_corners: bool = False,
) -> mx.array:
    """Sample NDHWC volume and write directly as NHW(C*D).

    This is equivalent to ``grid_sample_3d(...).transpose(0, 2, 3, 4, 1)``
    followed by reshaping the last two axes as ``C * D``.
    """
    if input.ndim != 5 or grid.ndim != 5 or grid.shape[-1] != 3:
        raise ValueError(
            f"expected input (N,D,H,W,C) and grid (N,Do,Ho,Wo,3); got "
            f"{tuple(input.shape)} and {tuple(grid.shape)}"
        )
    n, _, _, _, c = input.shape
    _, do, ho, wo, _ = grid.shape
    total = n * ho * wo * c * do
    kernel = _get_metal_to_2d_channels_kernel(align_corners)
    return kernel(
        inputs=[input, grid],
        template=[("T", input.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, ho, wo, c * do)],
        output_dtypes=[input.dtype],
    )[0]


def grid_sample_3d_to_2d_channels_c4(
    input: mx.array,
    grid: mx.array,
    *,
    align_corners: bool = False,
) -> mx.array:
    """Sample NDHWC volume as NHW(C*D), computing four channels per thread."""
    if input.ndim != 5 or grid.ndim != 5 or grid.shape[-1] != 3:
        raise ValueError(
            f"expected input (N,D,H,W,C) and grid (N,Do,Ho,Wo,3); got "
            f"{tuple(input.shape)} and {tuple(grid.shape)}"
        )
    n, _, _, _, c = input.shape
    if c % 4 != 0:
        return grid_sample_3d_to_2d_channels(input, grid, align_corners=align_corners)
    _, do, ho, wo, _ = grid.shape
    total = n * ho * wo * do * (c // 4)
    kernel = _get_metal_to_2d_channels_c4_kernel(align_corners)
    return kernel(
        inputs=[input, grid],
        template=[("T", input.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, ho, wo, c * do)],
        output_dtypes=[input.dtype],
    )[0]


def grid_sample_3d_sparse_motions(
    input: mx.array,
    grid: mx.array,
    *,
    align_corners: bool = False,
) -> mx.array:
    """Sample one NDHWC feature volume with an NKDHW3 sparse-motion grid."""
    if input.ndim != 5 or grid.ndim != 6 or grid.shape[-1] != 3:
        raise ValueError(
            f"expected input (N,D,H,W,C) and grid (N,K,D,H,W,3); got "
            f"{tuple(input.shape)} and {tuple(grid.shape)}"
        )
    if input.shape[0] != grid.shape[0]:
        raise ValueError(f"incompatible batch shapes: {tuple(input.shape)} and {tuple(grid.shape)}")
    n, _, _, _, c = input.shape
    _, k, do, ho, wo, _ = grid.shape
    total = n * k * do * ho * wo * c
    kernel = _get_metal_sparse_motions_kernel(align_corners)
    return kernel(
        inputs=[input, grid],
        template=[("T", input.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, k, do, ho, wo, c)],
        output_dtypes=[input.dtype],
    )[0]


def _grid_sample_3d_gather(input: mx.array, grid: mx.array, *, align_corners: bool) -> mx.array:
    """Pure-MLX trilinear grid_sample with zero padding, gather-style.

    Each output voxel is the trilinear interpolation of the 8 surrounding
    input voxels. Out-of-range corners contribute zero (zeros padding).
    """
    n, d, h, w, c = input.shape
    _, do, ho, wo, _ = grid.shape

    gx = grid[..., 0]
    gy = grid[..., 1]
    gz = grid[..., 2]

    if align_corners:
        x = (gx + 1.0) * (w - 1) * 0.5
        y = (gy + 1.0) * (h - 1) * 0.5
        z = (gz + 1.0) * (d - 1) * 0.5
    else:
        x = ((gx + 1.0) * w - 1.0) * 0.5
        y = ((gy + 1.0) * h - 1.0) * 0.5
        z = ((gz + 1.0) * d - 1.0) * 0.5

    x0 = mx.floor(x).astype(mx.int32)
    y0 = mx.floor(y).astype(mx.int32)
    z0 = mx.floor(z).astype(mx.int32)
    x1 = x0 + 1
    y1 = y0 + 1
    z1 = z0 + 1

    wx = (x - x0.astype(x.dtype))[..., None]  # (N, Do, Ho, Wo, 1)
    wy = (y - y0.astype(y.dtype))[..., None]
    wz = (z - z0.astype(z.dtype))[..., None]

    vx0 = (x0 >= 0) & (x0 < w)
    vx1 = (x1 >= 0) & (x1 < w)
    vy0 = (y0 >= 0) & (y0 < h)
    vy1 = (y1 >= 0) & (y1 < h)
    vz0 = (z0 >= 0) & (z0 < d)
    vz1 = (z1 >= 0) & (z1 < d)

    x0c = mx.clip(x0, 0, w - 1)
    x1c = mx.clip(x1, 0, w - 1)
    y0c = mx.clip(y0, 0, h - 1)
    y1c = mx.clip(y1, 0, h - 1)
    z0c = mx.clip(z0, 0, d - 1)
    z1c = mx.clip(z1, 0, d - 1)

    # Build a flat batch index broadcast to grid shape.
    n_idx = mx.broadcast_to(
        mx.arange(n, dtype=mx.int32).reshape(n, 1, 1, 1),
        (n, do, ho, wo),
    )

    def gather(zi, yi, xi, mask):
        # input[n, zi, yi, xi, :] using fancy indexing (broadcast over channels).
        sampled = input[n_idx, zi, yi, xi]  # (N, Do, Ho, Wo, C)
        m = mask[..., None].astype(sampled.dtype)
        return sampled * m

    c000 = gather(z0c, y0c, x0c, vz0 & vy0 & vx0) * (1 - wz) * (1 - wy) * (1 - wx)
    c001 = gather(z0c, y0c, x1c, vz0 & vy0 & vx1) * (1 - wz) * (1 - wy) * wx
    c010 = gather(z0c, y1c, x0c, vz0 & vy1 & vx0) * (1 - wz) * wy * (1 - wx)
    c011 = gather(z0c, y1c, x1c, vz0 & vy1 & vx1) * (1 - wz) * wy * wx
    c100 = gather(z1c, y0c, x0c, vz1 & vy0 & vx0) * wz * (1 - wy) * (1 - wx)
    c101 = gather(z1c, y0c, x1c, vz1 & vy0 & vx1) * wz * (1 - wy) * wx
    c110 = gather(z1c, y1c, x0c, vz1 & vy1 & vx0) * wz * wy * (1 - wx)
    c111 = gather(z1c, y1c, x1c, vz1 & vy1 & vx1) * wz * wy * wx

    return c000 + c001 + c010 + c011 + c100 + c101 + c110 + c111


def grid_sample_3d(input: mx.array, grid: mx.array, *, align_corners: bool = False) -> mx.array:
    """Public entry point. Layout is NDHWC for `input`.

    Default backend is the custom Metal kernel; set FLP_MLX_GS3D_GATHER=1 to
    fall back to the gather-based pure-MLX implementation.
    """
    if input.ndim != 5 or grid.ndim != 5 or grid.shape[-1] != 3:
        raise ValueError(
            f"expected input (N,D,H,W,C) and grid (N,Do,Ho,Wo,3); got "
            f"{tuple(input.shape)} and {tuple(grid.shape)}"
        )
    if _USE_GATHER:
        return _grid_sample_3d_gather(input, grid, align_corners=align_corners)
    return _grid_sample_3d_metal(input, grid, align_corners=align_corners)
