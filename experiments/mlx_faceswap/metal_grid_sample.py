"""Metal-accelerated trilinear GridSample for NCDHW ONNX tensors.

The kernel structure is derived from FasterLivePortrait-MLX's MIT-licensed
``grid_sample.py`` by Ivan Fioravanti. See ``THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

import os

_KERNELS = {}
_SOURCE = r"""
    uint index = thread_position_in_grid.x;
    int N = (int)input_shape[0], D = (int)input_shape[1];
    int H = (int)input_shape[2], W = (int)input_shape[3];
    int C = (int)input_shape[4], OD = (int)grid_shape[1];
    int OH = (int)grid_shape[2], OW = (int)grid_shape[3];
    int total = N * OD * OH * OW * C;
    if ((int)index >= total) return;

    int c = (int)index % C;
    int remainder = (int)index / C;
    int ox = remainder % OW; remainder /= OW;
    int oy = remainder % OH; remainder /= OH;
    int oz = remainder % OD;
    int n = remainder / OD;
    int grid_offset = (((n * OD + oz) * OH + oy) * OW + ox) * 3;
    float gx = (float)grid[grid_offset];
    float gy = (float)grid[grid_offset + 1];
    float gz = (float)grid[grid_offset + 2];

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
    int x1 = x0 + 1, y1 = y0 + 1, z1 = z0 + 1;
    float wx = x - (float)x0, wy = y - (float)y0, wz = z - (float)z0;
    int DHWC = D * H * W * C, HWC = H * W * C, WC = W * C;
    int batch_offset = n * DHWC;
    auto fetch = [&](int iz, int iy, int ix) {
        if (iz < 0 || iz >= D || iy < 0 || iy >= H || ix < 0 || ix >= W)
            return 0.0f;
        return (float)input[batch_offset + iz * HWC + iy * WC + ix * C + c];
    };
    float c00 = fetch(z0, y0, x0) * (1.0f - wx) + fetch(z0, y0, x1) * wx;
    float c01 = fetch(z0, y1, x0) * (1.0f - wx) + fetch(z0, y1, x1) * wx;
    float c10 = fetch(z1, y0, x0) * (1.0f - wx) + fetch(z1, y0, x1) * wx;
    float c11 = fetch(z1, y1, x0) * (1.0f - wx) + fetch(z1, y1, x1) * wx;
    float c0 = c00 * (1.0f - wy) + c01 * wy;
    float c1 = c10 * (1.0f - wy) + c11 * wy;
    output[index] = (T)(c0 * (1.0f - wz) + c1 * wz);
"""


def grid_sample_3d_ncdhw(input_value, grid, *, align_corners: bool):
    """Return an NCDHW result, falling back only when explicitly requested."""

    if os.environ.get("AI2APPS_MLX_GRID_SAMPLE_GATHER") == "1":
        return None
    import mlx.core as mx

    source = mx.transpose(input_value, (0, 2, 3, 4, 1))
    n, _, _, _, channels = source.shape
    _, out_depth, out_height, out_width, _ = grid.shape
    key = bool(align_corners)
    if key not in _KERNELS:
        _KERNELS[key] = mx.fast.metal_kernel(
            name=f"ai2apps_grid_sample_3d_{'ac' if key else 'noac'}",
            input_names=["input", "grid"],
            output_names=["output"],
            source=_SOURCE.replace("ALIGN_CORNERS", "1" if key else "0"),
        )
    total = n * out_depth * out_height * out_width * channels
    result = _KERNELS[key](
        inputs=[source, grid],
        template=[("T", source.dtype)],
        grid=(((total + 255) // 256) * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, out_depth, out_height, out_width, channels)],
        output_dtypes=[source.dtype],
    )[0]
    return mx.transpose(result, (0, 4, 1, 2, 3))
