# ruff: noqa
"""Small image post-processing Metal kernels."""

from __future__ import annotations

import mlx.core as mx


_TO_UINT8_KERNELS = {}


_TO_UINT8_SRC = """
    uint idx = thread_position_in_grid.x;
    int total = (int)(img_shape[0] * img_shape[1] * img_shape[2] * img_shape[3]);
    if ((int)idx >= total) return;

    float v = (float)img[idx];
    v = metal::min(metal::max(v, 0.0f), 1.0f) * 255.0f;
    output[idx] = (uint8_t)v;
"""


def _dtype_name(dtype) -> str:
    return str(dtype).replace("mlx.core.", "").replace(".", "_")


def _get_to_uint8_kernel(dtype):
    key = str(dtype)
    if key not in _TO_UINT8_KERNELS:
        _TO_UINT8_KERNELS[key] = mx.fast.metal_kernel(
            name=f"image_to_uint8_{_dtype_name(dtype)}",
            input_names=["img"],
            output_names=["output"],
            source=_TO_UINT8_SRC,
        )
    return _TO_UINT8_KERNELS[key]


def image_to_uint8(img: mx.array) -> mx.array:
    """Clamp an image in [0, 1], scale to [0, 255], and cast to uint8."""
    total = 1
    for dim in img.shape:
        total *= dim
    kernel = _get_to_uint8_kernel(img.dtype)
    return kernel(
        inputs=[img],
        grid=((total + 255) // 256 * 256, 1, 1),
        threadgroup=(256, 1, 1),
        output_shapes=[img.shape],
        output_dtypes=[mx.uint8],
    )[0]
