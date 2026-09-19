"""Optional Metal fusions for FLUX.2's LayerNorm/AdaLN hot path."""

from __future__ import annotations

from functools import lru_cache

import mlx.core as mx


_THREADS = 256
_SIMDGROUPS = _THREADS // 32


def metal_fusions_available() -> bool:
    metal = getattr(mx, "metal", None)
    default_device = getattr(mx, "default_device", None)
    gpu = getattr(mx, "gpu", None)
    return (
        default_device is not None
        and gpu is not None
        and default_device() == gpu
        and metal is not None
        and metal.is_available()
    )


_REDUCE = f"""
        threadgroup float partial_sum[{_SIMDGROUPS}];
        threadgroup float partial_square[{_SIMDGROUPS}];
        float row_sum = 0.0f;
        float row_square = 0.0f;
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            float value = VALUE_AT_D;
            row_sum += value;
            row_square = fma(value, value, row_square);
        }}
        row_sum = simd_sum(row_sum);
        row_square = simd_sum(row_square);
        if (lane == 0) {{
            partial_sum[sg] = row_sum;
            partial_square[sg] = row_square;
        }}
        threadgroup_barrier(mem_flags::mem_threadgroup);
        float total_sum = lane < {_SIMDGROUPS} ? partial_sum[lane] : 0.0f;
        float total_square = lane < {_SIMDGROUPS} ? partial_square[lane] : 0.0f;
        total_sum = simd_sum(total_sum);
        total_square = simd_sum(total_square);
        float mean = total_sum / float(D);
        float variance = max(total_square / float(D) - mean * mean, 0.0f);
        float inv_std = rsqrt(variance + float(EPS_NANO) * 1.0e-9f);
"""


@lru_cache(maxsize=1)
def _layer_norm_adaln_kernel():
    if not metal_fusions_available():
        return None
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        uint mod_row = M_ROWS == 1 ? 0 : row;
        const device X* x_row = x + (size_t)row * D;
        const device M* shift_row = shift + (size_t)mod_row * D;
        const device M* scale_row = scale + (size_t)mod_row * D;
        device O* out_row = out + (size_t)row * D;
    """ + _REDUCE.replace("VALUE_AT_D", "float(x_row[d])") + f"""
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            float normalized = (float(x_row[d]) - mean) * inv_std;
            out_row[d] = O(fma(normalized, 1.0f + float(scale_row[d]),
                               float(shift_row[d])));
        }}
    """
    return mx.fast.metal_kernel(
        name="ai2apps_flux2_layer_norm_adaln",
        input_names=["x", "shift", "scale"],
        output_names=["out"],
        source=source,
        ensure_row_contiguous=True,
    )


@lru_cache(maxsize=1)
def _residual_layer_norm_adaln_kernel():
    if not metal_fusions_available():
        return None
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        uint mod_row = M_ROWS == 1 ? 0 : row;
        const device X* x_row = x + (size_t)row * D;
        const device B* branch_row = branch + (size_t)row * D;
        const device M* gate_row = gate + (size_t)mod_row * D;
        const device M* shift_row = shift + (size_t)mod_row * D;
        const device M* scale_row = scale + (size_t)mod_row * D;
        device O* residual_row = residual + (size_t)row * D;
        device O* out_row = out + (size_t)row * D;
    """ + _REDUCE.replace(
        "VALUE_AT_D",
        "float(O(float(x_row[d]) + float(O(float(gate_row[d]) * float(branch_row[d])))))",
    ) + f"""
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            O product = O(float(gate_row[d]) * float(branch_row[d]));
            O residual_value = O(float(x_row[d]) + float(product));
            residual_row[d] = residual_value;
            float normalized = (float(residual_value) - mean) * inv_std;
            out_row[d] = O(fma(normalized, 1.0f + float(scale_row[d]),
                               float(shift_row[d])));
        }}
    """
    return mx.fast.metal_kernel(
        name="ai2apps_flux2_residual_layer_norm_adaln",
        input_names=["x", "branch", "gate", "shift", "scale"],
        output_names=["residual", "out"],
        source=source,
        ensure_row_contiguous=True,
    )


def _supported_modulation(x: mx.array, *params: mx.array) -> bool:
    hidden = x.shape[-1]
    rows = x.size // hidden
    return all(param.size // hidden in (1, rows) for param in params)


def layer_norm_adaln(
    x: mx.array,
    shift: mx.array,
    scale: mx.array,
    eps: float = 1e-6,
) -> mx.array:
    kernel = _layer_norm_adaln_kernel()
    if kernel is None or not _supported_modulation(x, shift, scale):
        normalized = mx.fast.layer_norm(x, None, None, eps)
        return normalized * (1.0 + scale) + shift
    hidden = x.shape[-1]
    rows = x.size // hidden
    mod_rows = shift.size // hidden
    (out,) = kernel(
        inputs=[x, shift, scale],
        template=[
            ("X", x.dtype), ("M", shift.dtype), ("O", x.dtype),
            ("D", hidden), ("M_ROWS", mod_rows),
            ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape],
        output_dtypes=[x.dtype],
    )
    return out


def residual_layer_norm_adaln(
    x: mx.array,
    branch: mx.array,
    gate: mx.array,
    shift: mx.array,
    scale: mx.array,
    eps: float = 1e-6,
) -> tuple[mx.array, mx.array]:
    kernel = _residual_layer_norm_adaln_kernel()
    if kernel is None or not _supported_modulation(x, gate, shift, scale):
        residual = x + gate * branch
        normalized = mx.fast.layer_norm(residual, None, None, eps)
        return residual, normalized * (1.0 + scale) + shift
    hidden = x.shape[-1]
    rows = x.size // hidden
    mod_rows = shift.size // hidden
    residual, out = kernel(
        inputs=[x, branch, gate, shift, scale],
        template=[
            ("X", x.dtype), ("B", branch.dtype), ("M", shift.dtype),
            ("O", x.dtype), ("D", hidden), ("M_ROWS", mod_rows),
            ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape, x.shape],
        output_dtypes=[x.dtype, x.dtype],
    )
    return residual, out
