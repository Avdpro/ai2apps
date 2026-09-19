# ruff: noqa
"""Experimental Metal kernels for DenseMotion mask prediction."""

from __future__ import annotations

import mlx.core as mx


_MASK_CONV_KERNELS = {}
_MASK_CONV_TENSOROPS_KERNELS = {}


_MASK_CONV_3D_SRC = """
    uint idx = thread_position_in_grid.x;

    int N = (int)x_shape[0];
    int D = (int)x_shape[1];
    int H = (int)x_shape[2];
    int W = (int)x_shape[3];
    int IC = (int)x_shape[4];
    int OC = (int)weight_shape[0];
    int KD = (int)weight_shape[1];
    int KH = (int)weight_shape[2];
    int KW = (int)weight_shape[3];
    int total = N * D * H * W * OC;
    if ((int)idx >= total) return;

    int oc = (int)idx % OC;
    int rem = (int)idx / OC;
    int wo = rem % W;
    rem /= W;
    int ho = rem % H;
    rem /= H;
    int d = rem % D;
    int n = rem / D;

    int pd = KD / 2;
    int ph = KH / 2;
    int pw = KW / 2;
    float acc = (float)bias[oc];

    int x_n_off = n * D * H * W * IC;
    int w_oc_off = oc * KD * KH * KW * IC;
    for (int kd = 0; kd < KD; ++kd) {
        int zd = d + kd - pd;
        if (zd < 0 || zd >= D) continue;
        int x_d_off = x_n_off + zd * H * W * IC;
        int w_kd_off = w_oc_off + kd * KH * KW * IC;
        for (int kh = 0; kh < KH; ++kh) {
            int yh = ho + kh - ph;
            if (yh < 0 || yh >= H) continue;
            int x_h_off = x_d_off + yh * W * IC;
            int w_kh_off = w_kd_off + kh * KW * IC;
            for (int kw = 0; kw < KW; ++kw) {
                int xw = wo + kw - pw;
                if (xw < 0 || xw >= W) continue;
                int x_base = x_h_off + xw * IC;
                int w_base = w_kh_off + kw * IC;
                for (int ic = 0; ic < IC; ++ic) {
                    acc += (float)x[x_base + ic] * (float)weight[w_base + ic];
                }
            }
        }
    }

    output[idx] = (T)acc;
"""


def _get_mask_conv_3d_kernel(dtype):
    key = str(dtype)
    if key not in _MASK_CONV_KERNELS:
        _MASK_CONV_KERNELS[key] = mx.fast.metal_kernel(
            name=f"mask_conv_3d_direct_{key.replace('.', '_')}",
            input_names=["x", "weight", "bias"],
            output_names=["output"],
            source=_MASK_CONV_3D_SRC,
        )
    return _MASK_CONV_KERNELS[key]


def mask_conv3d_direct_metal(x: mx.array, weight: mx.array, bias: mx.array) -> mx.array:
    """Direct 3D conv for the mask head.

    This is intentionally conservative and env-gated by the caller. It avoids
    lowering through seven Conv2d launches, but does not yet use Metal 4
    TensorOps/cooperative matrices.
    """
    n, d, h, w, _ = x.shape
    oc = weight.shape[0]
    total = n * d * h * w * oc
    kernel = _get_mask_conv_3d_kernel(x.dtype)
    outputs = kernel(
        inputs=[x, weight, bias],
        template=[("T", x.dtype)],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[(n, d, h, w, oc)],
        output_dtypes=[x.dtype],
    )
    return outputs[0]


def pack_mask_conv3d_weight_2d(weight: mx.array) -> mx.array:
    """Pack Conv3d weights as a single Conv2d kernel over depth-stacked channels."""
    oc, kd, kh, kw, ic = weight.shape
    return mx.contiguous(mx.transpose(weight, (0, 2, 3, 1, 4)).reshape(oc, kh, kw, kd * ic))


def mask_conv3d_packed_2d(
    x: mx.array,
    weight_packed: mx.array,
    bias: mx.array,
    *,
    depth_kernel: int,
    padding: int,
) -> mx.array:
    """Conv3d mask head as one Conv2d over depth-stacked channels."""
    n, d, h, w, ic = x.shape
    pad_d = depth_kernel // 2
    x_padded = mx.pad(x, [(0, 0), (pad_d, pad_d), (0, 0), (0, 0), (0, 0)])
    x_packed = mx.concatenate(
        [x_padded[:, kd : kd + d, :, :, :] for kd in range(depth_kernel)],
        axis=-1,
    )
    y = mx.conv2d(x_packed.reshape(n * d, h, w, depth_kernel * ic), weight_packed, padding=padding)
    return y.reshape(n, d, h, w, weight_packed.shape[0]) + bias


def mask_conv3d_packed_2d_stack(
    x: mx.array,
    weight_packed: mx.array,
    bias: mx.array,
    *,
    depth_kernel: int,
    padding: int,
) -> mx.array:
    """Conv3d mask head as Conv2d, packing depth slices via stack+reshape."""
    n, d, h, w, ic = x.shape
    pad_d = depth_kernel // 2
    x_padded = mx.pad(x, [(0, 0), (pad_d, pad_d), (0, 0), (0, 0), (0, 0)])
    x_packed = mx.stack(
        [x_padded[:, kd : kd + d, :, :, :] for kd in range(depth_kernel)],
        axis=-2,
    )
    x_packed = x_packed.reshape(n * d, h, w, depth_kernel * ic)
    y = mx.conv2d(x_packed, weight_packed, padding=padding)
    return y.reshape(n, d, h, w, weight_packed.shape[0]) + bias


_MASK_CONV_3D_TENSOROPS_HEADER = """
#include <metal_tensor>
#include <MetalPerformancePrimitives/MPPTensorOpsMatMul2d.h>
using namespace metal;
using namespace mpp::tensor_ops;
"""


_MASK_CONV_3D_TENSOROPS_SRC = """
    constexpr int MTILE = 64;
    constexpr int NTILE = 32;
    constexpr int KMAX = 144;

    threadgroup T a_tile[MTILE * KMAX];
    threadgroup int x_base[MTILE];

    int N = (int)x_shape[0];
    int D = (int)x_shape[1];
    int H = (int)x_shape[2];
    int W = (int)x_shape[3];
    int IC = (int)x_shape[4];
    int KD = (int)weight_packed_shape[0];
    int KH = (int)weight_packed_shape[1];
    int KW = (int)weight_packed_shape[2];
    int OC = (int)weight_packed_shape[4];
    int M = N * D * H * W;
    int pad_d = KD / 2;
    int pad_h = KH / 2;
    int pad_w = KW / 2;

    int tid = (int)thread_position_in_threadgroup.x;
    uint2 tgid = threadgroup_position_in_grid.xy;
    int m0 = (int)tgid.y * MTILE;
    int oc0 = (int)tgid.x * NTILE;

    auto A = tensor(a_tile, dextents<int32_t, 2>(IC, MTILE));
    device T* weight_mut = const_cast<device T*>(weight_packed);
    auto B0full = tensor(weight_mut, dextents<int32_t, 2>(OC, IC));
    auto B0 = B0full.slice(oc0, 0);
    auto C = tensor(out, dextents<int32_t, 2>(OC, M));
    auto tC = C.slice(oc0, m0);

    constexpr auto desc = matmul2d_descriptor(MTILE, NTILE, static_cast<int>(dynamic_extent));
    matmul2d<desc, execution_simdgroups<4>> op;
    auto acc = op.get_destination_cooperative_tensor<decltype(A), decltype(B0), float>();
    auto part = op.get_destination_cooperative_tensor<decltype(A), decltype(B0), float>();

    for (uint16_t i = 0; i < acc.get_capacity(); ++i) {
        acc.set(i, 0.0f);
    }

    for (int kd = 0; kd < KD; ++kd) {
        for (int kh = 0; kh < KH; ++kh) {
            for (int kw = 0; kw < KW; ++kw) {
                for (int mm = tid; mm < MTILE; mm += 128) {
                    int m = m0 + mm;
                    int base = -1;

                    if (m < M) {
                        int ow = m % W;
                        int rem_m = m / W;
                        int oh = rem_m % H;
                        rem_m /= H;
                        int od = rem_m % D;
                        int n = rem_m / D;

                        int iz = od + kd - pad_d;
                        int iy = oh + kh - pad_h;
                        int ix = ow + kw - pad_w;
                        if (iz >= 0 && iz < D && iy >= 0 && iy < H && ix >= 0 && ix < W) {
                            base = (((n * D + iz) * H + iy) * W + ix) * IC;
                        }
                    }
                    x_base[mm] = base;
                }

                threadgroup_barrier(mem_flags::mem_threadgroup);
                for (int i = tid; i < MTILE * IC; i += 128) {
                    int ic = i % IC;
                    int mm = i / IC;
                    int base = x_base[mm];
                    a_tile[i] = base >= 0 ? x[base + ic] : (T)0;
                }

                for (uint16_t i = 0; i < part.get_capacity(); ++i) {
                    part.set(i, 0.0f);
                }
                threadgroup_barrier(mem_flags::mem_threadgroup);
                device T* weight_offset = weight_mut + ((kd * KH + kh) * KW + kw) * IC * OC;
                auto Bfull = tensor(weight_offset, dextents<int32_t, 2>(OC, IC));
                auto B = Bfull.slice(oc0, 0);
                op.run(A, B, part);
                for (uint16_t i = 0; i < acc.get_capacity(); ++i) {
                    acc.set(i, acc.get(i) + part.get(i));
                }
                threadgroup_barrier(mem_flags::mem_threadgroup);
            }
        }
    }

    acc.store(tC);
"""


def _get_mask_conv_3d_tensorops_kernel(dtype):
    key = str(dtype)
    if key not in _MASK_CONV_TENSOROPS_KERNELS:
        _MASK_CONV_TENSOROPS_KERNELS[key] = mx.fast.metal_kernel(
            name=f"mask_conv_3d_tensorops_{key.replace('.', '_')}",
            input_names=["x", "weight_packed"],
            output_names=["out"],
            header=_MASK_CONV_3D_TENSOROPS_HEADER,
            source=_MASK_CONV_3D_TENSOROPS_SRC,
        )
    return _MASK_CONV_TENSOROPS_KERNELS[key]


def pack_mask_conv3d_weight_tensorops(weight: mx.array) -> mx.array:
    """Pack Conv3d weights as KD/KH/KW/IC/OC for TensorOps mask conv."""
    return mx.contiguous(mx.transpose(weight, (1, 2, 3, 4, 0)))


def mask_conv3d_tensorops_tiled(x: mx.array, weight_packed: mx.array, bias: mx.array) -> mx.array:
    """Implicit-im2col 3D conv using Metal 4 TensorOps matmul tiles.

    This is experimental and intended for the DenseMotion mask head geometry.
    It materializes only a 64-position by channel-reduction tile in threadgroup
    memory, avoiding the multi-GB full im2col matrix. The weight must be packed
    with :func:`pack_mask_conv3d_weight_tensorops`.
    """
    if x.dtype not in (mx.float16, mx.bfloat16):
        raise ValueError(f"TensorOps mask conv expects fp16/bf16 input, got {x.dtype}")
    if weight_packed.dtype != x.dtype:
        raise ValueError(f"weight dtype must match input dtype: {weight_packed.dtype} vs {x.dtype}")
    if weight_packed.shape[3] > 144:
        raise ValueError(f"TensorOps mask conv supports up to 144 input channels, got {weight_packed.shape[3]}")
    n, d, h, w, _ = x.shape
    oc = weight_packed.shape[-1]
    m = n * d * h * w
    tiles_x = (oc + 31) // 32
    tiles_y = (m + 63) // 64
    kernel = _get_mask_conv_3d_tensorops_kernel(x.dtype)
    out = kernel(
        inputs=[mx.contiguous(x), weight_packed],
        template=[("T", x.dtype)],
        grid=(tiles_x * 128, tiles_y, 1),
        threadgroup=(128, 1, 1),
        output_shapes=[(n, d, h, w, oc)],
        output_dtypes=[mx.float32],
    )[0]
    return (out + bias.astype(mx.float32)).astype(x.dtype)
