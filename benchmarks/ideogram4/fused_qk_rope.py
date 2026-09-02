"""Fused Q/K RMSNorm and half-rotation MRoPE for Ideogram 4."""

from __future__ import annotations

from functools import lru_cache

import mlx.core as mx

_THREADS = 256
_SIMDGROUPS = _THREADS // 32


def available() -> bool:
    try:
        return (
            mx.default_device() == mx.gpu
            and getattr(mx, "metal", None) is not None
            and mx.metal.is_available()
        )
    except RuntimeError:
        return False


@lru_cache(maxsize=1)
def _kernel():
    if not available():
        return None
    return mx.fast.metal_kernel(
        name="ai2apps_ideogram4_qk_rms_mrope",
        input_names=["q", "k", "q_weight", "k_weight", "cosine", "sine"],
        output_names=["q_out", "k_out"],
        source=f"""
            uint tid = thread_position_in_threadgroup.x;
            uint lane = thread_index_in_simdgroup;
            uint sg = simdgroup_index_in_threadgroup;
            uint row = threadgroup_position_in_grid.x;
            uint head = row % (uint)HEADS;
            uint sequence = (row / (uint)HEADS) % (uint)SEQUENCE;
            const device X* q_row = q + (size_t)row * D;
            const device X* k_row = k + (size_t)row * D;
            threadgroup float q_partial[{_SIMDGROUPS}];
            threadgroup float k_partial[{_SIMDGROUPS}];

            float q_square = 0.0f;
            float k_square = 0.0f;
            for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
                float q_value = float(q_row[d]);
                float k_value = float(k_row[d]);
                q_square = fma(q_value, q_value, q_square);
                k_square = fma(k_value, k_value, k_square);
            }}
            q_square = simd_sum(q_square);
            k_square = simd_sum(k_square);
            if (lane == 0) {{
                q_partial[sg] = q_square;
                k_partial[sg] = k_square;
            }}
            threadgroup_barrier(mem_flags::mem_threadgroup);
            float q_total = lane < {_SIMDGROUPS} ? q_partial[lane] : 0.0f;
            float k_total = lane < {_SIMDGROUPS} ? k_partial[lane] : 0.0f;
            q_total = simd_sum(q_total);
            k_total = simd_sum(k_total);
            float q_inv = rsqrt(q_total / float(D) + float(EPS_NANO) * 1.0e-9f);
            float k_inv = rsqrt(k_total / float(D) + float(EPS_NANO) * 1.0e-9f);

            size_t rope_base = (size_t)sequence * D;
            size_t output_base = ((size_t)head * SEQUENCE + sequence) * D;
            for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
                uint rotated_d = d < (uint)(D / 2) ? d + D / 2 : d - D / 2;
                float sign = d < (uint)(D / 2) ? -1.0f : 1.0f;
                float c = float(cosine[rope_base + d]);
                float s = float(sine[rope_base + d]);
                float q_value = float(q_row[d]) * q_inv * float(q_weight[d]);
                float k_value = float(k_row[d]) * k_inv * float(k_weight[d]);
                float q_rotated = sign * float(q_row[rotated_d]) * q_inv
                                  * float(q_weight[rotated_d]);
                float k_rotated = sign * float(k_row[rotated_d]) * k_inv
                                  * float(k_weight[rotated_d]);
                q_out[output_base + d] = O(fma(q_value, c, q_rotated * s));
                k_out[output_base + d] = O(fma(k_value, c, k_rotated * s));
            }}
        """,
        ensure_row_contiguous=True,
    )


def fused_qk_rms_mrope(
    query: mx.array,
    key: mx.array,
    q_weight: mx.array,
    k_weight: mx.array,
    cosine: mx.array,
    sine: mx.array,
    eps: float,
) -> tuple[mx.array, mx.array] | None:
    kernel = _kernel()
    if (
        kernel is None
        or query.ndim != 4
        or query.shape != key.shape
        or query.shape[0] != 1
        or query.shape[-1] != _THREADS
    ):
        return None
    _, sequence, heads, hidden = query.shape
    rows = sequence * heads
    query_out, key_out = kernel(
        inputs=[query, key, q_weight, k_weight, cosine, sine],
        template=[
            ("X", query.dtype),
            ("O", query.dtype),
            ("D", hidden),
            ("SEQUENCE", sequence),
            ("HEADS", heads),
            ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[
            (1, heads, sequence, hidden),
            (1, heads, sequence, hidden),
        ],
        output_dtypes=[query.dtype, key.dtype],
    )
    return query_out, key_out
