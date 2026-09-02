"""Benchmark-only fused Metal implementation of Qwen Image 3D RoPE."""

from functools import lru_cache

import mlx.core as mx


_THREADS = 256


def _metal_available() -> bool:
    return (
        getattr(mx, "default_device", lambda: None)() == getattr(mx, "gpu", None)
        and getattr(mx, "metal", None) is not None
        and mx.metal.is_available()
    )


@lru_cache(maxsize=1)
def _kernel():
    if not _metal_available():
        return None
    return mx.fast.metal_kernel(
        name="ai2apps_qwen_fused_rope",
        input_names=["x", "cos_values", "sin_values"],
        output_names=["out"],
        source="""
            uint index = thread_position_in_grid.x;
            if (index >= (uint)PAIR_ELEMENTS) return;
            uint pair = index % (uint)PAIRS;
            uint sequence = (index / ((uint)HEADS * (uint)PAIRS)) % (uint)SEQUENCE;
            uint pair_base = index << 1;
            float real_value = float(x[pair_base]);
            float imag_value = float(x[pair_base + 1u]);
            float cosine = float(cos_values[sequence * (uint)PAIRS + pair]);
            float sine = float(sin_values[sequence * (uint)PAIRS + pair]);
            out[pair_base] = O(real_value * cosine - imag_value * sine);
            out[pair_base + 1u] = O(real_value * sine + imag_value * cosine);
        """,
        ensure_row_contiguous=True,
    )


def fused_rope(x: mx.array, cos_values: mx.array, sin_values: mx.array) -> mx.array:
    kernel = _kernel()
    if (
        kernel is None
        or x.ndim != 4
        or cos_values.ndim != 2
        or sin_values.shape != cos_values.shape
        or x.shape[1] != cos_values.shape[0]
        or x.shape[-1] != cos_values.shape[-1] * 2
    ):
        x_float = x.astype(mx.float32)
        pairs = mx.reshape(x_float, (*x.shape[:-1], -1, 2))
        real = pairs[..., 0]
        imag = pairs[..., 1]
        cosine = cos_values[None, :, None, :]
        sine = sin_values[None, :, None, :]
        return mx.reshape(
            mx.stack([real * cosine - imag * sine, real * sine + imag * cosine], axis=-1),
            x.shape,
        ).astype(x.dtype)

    elements = x.size
    pair_elements = elements // 2
    grid = ((pair_elements + _THREADS - 1) // _THREADS) * _THREADS
    (out,) = kernel(
        inputs=[x, cos_values, sin_values],
        template=[
            ("O", x.dtype),
            ("PAIR_ELEMENTS", pair_elements),
            ("SEQUENCE", x.shape[1]),
            ("HEADS", x.shape[2]),
            ("PAIRS", cos_values.shape[1]),
        ],
        grid=(grid, 1, 1),
        threadgroup=(_THREADS, 1, 1),
        output_shapes=[x.shape],
        output_dtypes=[x.dtype],
    )
    return out


def install_fused_rope() -> bool:
    if _kernel() is None:
        return False
    from mflux.models.qwen.model.qwen_transformer.qwen_attention import QwenAttention

    QwenAttention._apply_rope_qwen = staticmethod(fused_rope)
    return True
