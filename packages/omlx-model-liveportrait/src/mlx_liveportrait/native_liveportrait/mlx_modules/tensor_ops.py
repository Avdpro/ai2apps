# ruff: noqa
"""Small Metal 4 TensorOps helpers for MLX experiments."""

from __future__ import annotations

import mlx.core as mx


_TENSOROPS_MATMUL_KERNELS = {}
_CONV2D_3X3_TENSOROPS_KERNELS = {}


_TENSOROPS_HEADER = """
#include <metal_tensor>
#include <MetalPerformancePrimitives/MPPTensorOpsMatMul2d.h>
using namespace metal;
using namespace mpp::tensor_ops;
"""


_TENSOROPS_MATMUL_SRC = """
    int M = (int)a_shape[0];
    int K = (int)a_shape[1];
    int N = (int)b_shape[1];

    device T* a_mut = const_cast<device T*>(a);
    device T* b_mut = const_cast<device T*>(b);

    auto A = tensor(a_mut, dextents<int32_t, 2>(K, M));
    auto B = tensor(b_mut, dextents<int32_t, 2>(N, K));
    auto C = tensor(out, dextents<int32_t, 2>(N, M));

    constexpr auto desc = matmul2d_descriptor(
        64,
        32,
        static_cast<int>(dynamic_extent),
        false,
        false,
        RELAXED_PRECISION
    );
    matmul2d<desc, execution_simdgroups<4>> op;

    uint2 tgid = threadgroup_position_in_grid.xy;
    auto tA = A.slice(0, (int)tgid.y * 64);
    auto tB = B.slice((int)tgid.x * 32, 0);
    auto tC = C.slice((int)tgid.x * 32, (int)tgid.y * 64);

    auto cT = op.get_destination_cooperative_tensor<decltype(tA), decltype(tB), float>();
    for (uint16_t i = 0; i < cT.get_capacity(); ++i) {
        cT.set(i, 0.0f);
    }
    op.run(tA, tB, cT);
    cT.store(tC);
"""


_CONV2D_3X3_TENSOROPS_SRC_TMPL = """
    constexpr int MTILE = __MTILE__;
    constexpr int NTILE = 32;
    constexpr int ICMAX = __ICMAX__;

    threadgroup T a_tile[MTILE * ICMAX];
    threadgroup int x_base[MTILE];

    int N = (int)x_shape[0];
    int H = (int)x_shape[1];
    int W = (int)x_shape[2];
    int IC = (int)x_shape[3];
    int KH = (int)weight_packed_shape[0];
    int KW = (int)weight_packed_shape[1];
    int OC = (int)weight_packed_shape[3];
    int M = N * H * W;
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

    for (int kh = 0; kh < KH; ++kh) {
        for (int kw = 0; kw < KW; ++kw) {
            for (int mm = tid; mm < MTILE; mm += 128) {
                int m = m0 + mm;
                int base = -1;
                if (m < M) {
                    int ow = m % W;
                    int rem_m = m / W;
                    int oh = rem_m % H;
                    int n = rem_m / H;

                    int iy = oh + kh - pad_h;
                    int ix = ow + kw - pad_w;
                    if (iy >= 0 && iy < H && ix >= 0 && ix < W) {
                        base = ((n * H + iy) * W + ix) * IC;
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
            device T* weight_offset = weight_mut + (kh * KW + kw) * IC * OC;
            auto Bfull = tensor(weight_offset, dextents<int32_t, 2>(OC, IC));
            auto B = Bfull.slice(oc0, 0);
            op.run(A, B, part);
            for (uint16_t i = 0; i < acc.get_capacity(); ++i) {
                acc.set(i, acc.get(i) + part.get(i));
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
    }

    acc.store(tC);
"""


def _dtype_name(dtype) -> str:
    return str(dtype).replace("mlx.core.", "").replace(".", "_")


def _get_tensorops_matmul_kernel(dtype, relaxed_precision: bool):
    key = (str(dtype), relaxed_precision)
    if key not in _TENSOROPS_MATMUL_KERNELS:
        relaxed = "true" if relaxed_precision else "false"
        _TENSOROPS_MATMUL_KERNELS[key] = mx.fast.metal_kernel(
            name=f"tensorops_matmul_2d_{_dtype_name(dtype)}_{int(relaxed_precision)}",
            input_names=["a", "b"],
            output_names=["out"],
            header=_TENSOROPS_HEADER,
            source=_TENSOROPS_MATMUL_SRC.replace("RELAXED_PRECISION", relaxed),
        )
    return _TENSOROPS_MATMUL_KERNELS[key]


def _get_conv2d_3x3_tensorops_kernel(dtype, mtile: int, icmax: int):
    key = (str(dtype), mtile, icmax)
    if key not in _CONV2D_3X3_TENSOROPS_KERNELS:
        source = (
            _CONV2D_3X3_TENSOROPS_SRC_TMPL
            .replace("__MTILE__", str(mtile))
            .replace("__ICMAX__", str(icmax))
        )
        _CONV2D_3X3_TENSOROPS_KERNELS[key] = mx.fast.metal_kernel(
            name=f"conv2d_3x3_tensorops_{_dtype_name(dtype)}_{mtile}_{icmax}",
            input_names=["x", "weight_packed"],
            output_names=["out"],
            header=_TENSOROPS_HEADER,
            source=source,
        )
    return _CONV2D_3X3_TENSOROPS_KERNELS[key]


def tensorops_matmul(
    a: mx.array,
    b: mx.array,
    *,
    output_dtype=mx.float32,
    relaxed_precision: bool = False,
) -> mx.array:
    """Matrix multiply through Metal 4 MPP TensorOps.

    This is intentionally narrow and experimental: it supports packed 2D MLX
    arrays with float16 or bfloat16 inputs and dispatches one 64x32 output tile
    per cooperative threadgroup. It gives us a repo-local primitive for testing
    TensorOps-backed lowering without changing MLX's default matmul behavior.
    """
    if a.ndim != 2 or b.ndim != 2:
        raise ValueError("tensorops_matmul expects 2D inputs")
    if a.shape[1] != b.shape[0]:
        raise ValueError(f"incompatible matmul shapes: {a.shape} and {b.shape}")
    if a.dtype != b.dtype:
        raise ValueError(f"input dtypes must match: {a.dtype} and {b.dtype}")
    if a.dtype not in (mx.float16, mx.bfloat16):
        raise ValueError(f"TensorOps matmul supports float16/bfloat16 inputs, got {a.dtype}")
    if output_dtype not in (mx.float32, mx.float16, mx.bfloat16):
        raise ValueError(f"unsupported output dtype: {output_dtype}")

    a = mx.contiguous(a)
    b = mx.contiguous(b)
    m, _ = a.shape
    _, n = b.shape
    tiles_x = (n + 31) // 32
    tiles_y = (m + 63) // 64
    kernel = _get_tensorops_matmul_kernel(a.dtype, relaxed_precision)
    return kernel(
        inputs=[a, b],
        template=[("T", a.dtype)],
        grid=(tiles_x * 128, tiles_y, 1),
        threadgroup=(128, 1, 1),
        output_shapes=[(m, n)],
        output_dtypes=[output_dtype],
    )[0]


def conv3d_1x1_tensorops(x: mx.array, weight: mx.array, bias: mx.array | None = None) -> mx.array:
    """1x1x1 NDHWC Conv3d through TensorOps matmul."""
    if x.ndim != 5:
        raise ValueError(f"expected NDHWC input, got shape {x.shape}")
    if weight.ndim != 5 or weight.shape[1:4] != (1, 1, 1):
        raise ValueError(f"expected 1x1x1 Conv3d weight, got shape {weight.shape}")

    n, d, h, w, ic = x.shape
    oc = weight.shape[0]
    lhs = x.reshape(n * d * h * w, ic)
    rhs = mx.transpose(weight[:, 0, 0, 0, :], (1, 0))
    out = tensorops_matmul(lhs, rhs, output_dtype=mx.float32)
    if bias is not None:
        out = out + bias.astype(mx.float32)
    return out.astype(x.dtype).reshape(n, d, h, w, oc)


def conv2d_1x1_tensorops(x: mx.array, weight: mx.array, bias: mx.array | None = None) -> mx.array:
    """1x1 NHWC Conv2d through TensorOps matmul."""
    if x.ndim != 4:
        raise ValueError(f"expected NHWC input, got shape {x.shape}")
    if weight.ndim != 4 or weight.shape[1:3] != (1, 1):
        raise ValueError(f"expected 1x1 Conv2d weight, got shape {weight.shape}")

    n, h, w, ic = x.shape
    oc = weight.shape[0]
    lhs = x.reshape(n * h * w, ic)
    rhs = mx.transpose(weight[:, 0, 0, :], (1, 0))
    out = tensorops_matmul(lhs, rhs, output_dtype=mx.float32)
    if bias is not None:
        out = out + bias.astype(mx.float32)
    return out.astype(x.dtype).reshape(n, h, w, oc)


def pack_conv2d_weight_tensorops(weight: mx.array) -> mx.array:
    """Pack Conv2d weights as KH/KW/IC/OC for TensorOps conv kernels."""
    return mx.contiguous(mx.transpose(weight, (1, 2, 3, 0)))


def conv2d_3x3_tensorops(
    x: mx.array,
    weight_packed: mx.array,
    bias: mx.array | None = None,
) -> mx.array:
    """3x3 NHWC Conv2d through implicit-im2col TensorOps tiles.

    The weight must be prepacked with :func:`pack_conv2d_weight_tensorops`.
    This is experimental and currently assumes stride 1 with same padding.
    """
    if x.ndim != 4:
        raise ValueError(f"expected NHWC input, got shape {x.shape}")
    if weight_packed.ndim != 4 or weight_packed.shape[:2] != (3, 3):
        raise ValueError(f"expected packed 3x3 weight KH/KW/IC/OC, got {weight_packed.shape}")
    if x.dtype not in (mx.float16, mx.bfloat16):
        raise ValueError(f"TensorOps Conv2d supports fp16/bf16 inputs, got {x.dtype}")
    if weight_packed.dtype != x.dtype:
        raise ValueError(f"weight dtype must match input dtype: {weight_packed.dtype} vs {x.dtype}")

    n, h, w, ic = x.shape
    oc = weight_packed.shape[-1]
    if weight_packed.shape[2] != ic:
        raise ValueError(f"incompatible input channels: {ic} vs weight {weight_packed.shape}")
    if ic <= 256:
        mtile, icmax = 32, 256
    elif ic <= 512:
        mtile, icmax = 16, 512
    else:
        raise ValueError(f"TensorOps 3x3 Conv2d supports up to 512 input channels, got {ic}")

    tiles_x = (oc + 31) // 32
    tiles_y = (n * h * w + mtile - 1) // mtile
    kernel = _get_conv2d_3x3_tensorops_kernel(x.dtype, mtile, icmax)
    out = kernel(
        inputs=[mx.contiguous(x), weight_packed],
        template=[("T", x.dtype)],
        grid=(tiles_x * 128, tiles_y, 1),
        threadgroup=(128, 1, 1),
        output_shapes=[(n, h, w, oc)],
        output_dtypes=[mx.float32],
    )[0]
    if bias is not None:
        out = out + bias.astype(mx.float32)
    return out.astype(x.dtype)
