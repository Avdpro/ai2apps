"""Optional Metal fusions for H3's row-wise AdaLN transformer hot path."""

from __future__ import annotations

from functools import lru_cache

import mlx.core as mx


_THREADS = 256
_SIMDGROUPS = _THREADS // 32


def metal_fusions_available() -> bool:
    return mx.default_device() == mx.gpu and mx.metal.is_available()


_REDUCE = f"""
        threadgroup float partial[{_SIMDGROUPS}];
        float square_sum = 0.0f;
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            float value = VALUE_AT_D;
            square_sum = fma(value, value, square_sum);
        }}
        square_sum = simd_sum(square_sum);
        if (lane == 0) partial[sg] = square_sum;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        float total = lane < {_SIMDGROUPS} ? partial[lane] : 0.0f;
        total = simd_sum(total);
        float inv_rms = rsqrt(total / float(D) + float(EPS_NANO) * 1.0e-9f);
"""


@lru_cache(maxsize=1)
def _rms_adaln_kernel():
    if not metal_fusions_available():
        return None
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        uint table_row = (uint)indices[row];
        const device X* x_row = x + (size_t)row * D;
        const device W* weight_row = weight;
        const device M* shift_row = shift + (size_t)table_row * D;
        const device M* scale_row = scale + (size_t)table_row * D;
        device O* out_row = out + (size_t)row * D;
    """ + _REDUCE.replace("VALUE_AT_D", "float(x_row[d])") + f"""
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            O normalized = O(float(x_row[d]) * inv_rms * float(weight_row[d]));
            out_row[d] = O(fma(float(normalized), 1.0f + float(scale_row[d]),
                               float(shift_row[d])));
        }}
    """
    return mx.fast.metal_kernel(
        name="minimax_h3_rms_adaln",
        input_names=["x", "weight", "shift", "scale", "indices"],
        output_names=["out"],
        source=source,
        ensure_row_contiguous=True,
    )


@lru_cache(maxsize=1)
def _residual_rms_adaln_kernel():
    if not metal_fusions_available():
        return None
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        uint table_row = (uint)indices[row];
        const device X* x_row = x + (size_t)row * D;
        const device B* branch_row = branch + (size_t)row * D;
        const device M* gate_row = gate + (size_t)table_row * D;
        const device W* weight_row = weight;
        const device M* shift_row = shift + (size_t)table_row * D;
        const device M* scale_row = scale + (size_t)table_row * D;
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
            O normalized = O(float(residual_value) * inv_rms * float(weight_row[d]));
            out_row[d] = O(fma(float(normalized), 1.0f + float(scale_row[d]),
                               float(shift_row[d])));
        }}
    """
    return mx.fast.metal_kernel(
        name="minimax_h3_residual_rms_adaln",
        input_names=["x", "branch", "gate", "weight", "shift", "scale", "indices"],
        output_names=["residual", "out"],
        source=source,
        ensure_row_contiguous=True,
    )


def rms_adaln(
    x: mx.array,
    weight: mx.array,
    shift: mx.array,
    scale: mx.array,
    indices: mx.array,
    eps: float,
) -> mx.array:
    kernel = _rms_adaln_kernel()
    if kernel is None:
        normalized = mx.fast.rms_norm(x, weight, eps)
        return normalized * (1.0 + scale[indices]) + shift[indices]
    hidden = x.shape[-1]
    rows = x.size // hidden
    (out,) = kernel(
        inputs=[x, weight, shift, scale, indices.astype(mx.uint32)],
        template=[
            ("X", x.dtype), ("W", weight.dtype), ("M", shift.dtype), ("O", x.dtype),
            ("D", hidden), ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape],
        output_dtypes=[x.dtype],
    )
    return out


def residual_rms_adaln(
    x: mx.array,
    branch: mx.array,
    gate: mx.array,
    weight: mx.array,
    shift: mx.array,
    scale: mx.array,
    indices: mx.array,
    eps: float,
) -> tuple[mx.array, mx.array]:
    kernel = _residual_rms_adaln_kernel()
    if kernel is None:
        residual = x + gate[indices] * branch
        normalized = mx.fast.rms_norm(residual, weight, eps)
        return residual, normalized * (1.0 + scale[indices]) + shift[indices]
    hidden = x.shape[-1]
    rows = x.size // hidden
    residual, out = kernel(
        inputs=[x, branch, gate, weight, shift, scale, indices.astype(mx.uint32)],
        template=[
            ("X", x.dtype), ("B", branch.dtype), ("W", weight.dtype),
            ("M", shift.dtype), ("O", x.dtype), ("D", hidden),
            ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape, x.shape],
        output_dtypes=[x.dtype, x.dtype],
    )
    return residual, out
