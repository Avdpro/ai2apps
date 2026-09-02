"""Benchmark-only Metal RMSNorm/AdaLN fusions for Z-Image blocks."""

from functools import lru_cache

import mlx.core as mx


_THREADS = 256
_SIMDGROUPS = _THREADS // 32


def available() -> bool:
    try:
        return (
            getattr(mx, "default_device", lambda: None)()
            == getattr(mx, "gpu", None)
            and getattr(mx, "metal", None) is not None
            and mx.metal.is_available()
        )
    except RuntimeError:
        return False


_REDUCE_SQUARE = f"""
        threadgroup float partial_square[{_SIMDGROUPS}];
        float row_square = 0.0f;
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            float value = VALUE_AT_D;
            row_square = fma(value, value, row_square);
        }}
        row_square = simd_sum(row_square);
        if (lane == 0) partial_square[sg] = row_square;
        threadgroup_barrier(mem_flags::mem_threadgroup);
        float total_square = lane < {_SIMDGROUPS} ? partial_square[lane] : 0.0f;
        total_square = simd_sum(total_square);
        float inv_rms = rsqrt(total_square / float(D) + float(EPS_NANO) * 1.0e-9f);
"""


@lru_cache(maxsize=1)
def _rms_scale_kernel():
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        const device X* x_row = x + (size_t)row * D;
        device O* out_row = out + (size_t)row * D;
    """ + _REDUCE_SQUARE.replace("VALUE_AT_D", "float(x_row[d])") + f"""
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            O normalized = O(float(x_row[d]) * inv_rms * float(weight[d]));
            out_row[d] = O(float(normalized) * float(scale[d]));
        }}
    """
    return mx.fast.metal_kernel(
        name="ai2apps_z_image_rms_scale",
        input_names=["x", "weight", "scale"],
        output_names=["out"],
        source=source,
        ensure_row_contiguous=True,
    )


@lru_cache(maxsize=1)
def _residual_rms_gate_kernel():
    source = """
        uint tid = thread_position_in_threadgroup.x;
        uint lane = thread_index_in_simdgroup;
        uint sg = simdgroup_index_in_threadgroup;
        uint row = threadgroup_position_in_grid.x;
        const device X* x_row = x + (size_t)row * D;
        const device B* branch_row = branch + (size_t)row * D;
        device O* out_row = out + (size_t)row * D;
    """ + _REDUCE_SQUARE.replace("VALUE_AT_D", "float(branch_row[d])") + f"""
        for (uint d = tid; d < (uint)D; d += {_THREADS}) {{
            O normalized = O(float(branch_row[d]) * inv_rms * float(weight[d]));
            O product = O(float(gate[d]) * float(normalized));
            out_row[d] = O(float(x_row[d]) + float(product));
        }}
    """
    return mx.fast.metal_kernel(
        name="ai2apps_z_image_residual_rms_gate",
        input_names=["x", "branch", "weight", "gate"],
        output_names=["out"],
        source=source,
        ensure_row_contiguous=True,
    )


def rms_scale(x, weight, scale, eps):
    hidden = x.shape[-1]
    rows = x.size // hidden
    (out,) = _rms_scale_kernel()(
        inputs=[x, weight, scale],
        template=[
            ("X", x.dtype), ("O", x.dtype), ("D", hidden),
            ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape],
        output_dtypes=[x.dtype],
    )
    return out


def residual_rms_gate(x, branch, weight, gate, eps):
    hidden = x.shape[-1]
    rows = x.size // hidden
    (out,) = _residual_rms_gate_kernel()(
        inputs=[x, branch, weight, gate],
        template=[
            ("X", x.dtype), ("B", branch.dtype), ("O", x.dtype),
            ("D", hidden), ("EPS_NANO", round(eps * 1_000_000_000)),
        ],
        grid=(rows * _THREADS, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape],
        output_dtypes=[x.dtype],
    )
    return out


def install() -> bool:
    if not available():
        return False
    from mflux.models.z_image.model.z_image_transformer.transformer_block import (
        ZImageTransformerBlock,
    )

    def fused_call(self, x, attn_mask, freqs_cis, t_emb):
        modulation = mx.expand_dims(self.adaLN_modulation[0](t_emb), axis=1)
        scale_msa, gate_msa, scale_mlp, gate_mlp = mx.split(modulation, 4, axis=2)
        scale_msa = 1.0 + scale_msa
        scale_mlp = 1.0 + scale_mlp
        gate_msa = mx.tanh(gate_msa)
        gate_mlp = mx.tanh(gate_mlp)
        attn_input = rms_scale(
            x, self.attention_norm1.weight, scale_msa[0], self.attention_norm1.eps
        )
        attn_out = self.attention(
            attn_input, attention_mask=attn_mask, freqs_cis=freqs_cis
        )
        x = residual_rms_gate(
            x, attn_out, self.attention_norm2.weight, gate_msa[0], self.attention_norm2.eps
        )
        ffn_input = rms_scale(
            x, self.ffn_norm1.weight, scale_mlp[0], self.ffn_norm1.eps
        )
        ffn_out = self.feed_forward(ffn_input)
        return residual_rms_gate(
            x, ffn_out, self.ffn_norm2.weight, gate_mlp[0], self.ffn_norm2.eps
        )

    ZImageTransformerBlock.__call__ = fused_call
    return True
