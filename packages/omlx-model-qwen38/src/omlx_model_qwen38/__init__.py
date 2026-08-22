# SPDX-License-Identifier: Apache-2.0
"""Qwen3.8 model adapter for oMLX."""

from .adapter import Qwen38Adapter, is_qwen38_config

__all__ = [
    "FP8_BLOCK_SIZE",
    "Qwen38Adapter",
    "dequantize_fp8_weights",
    "is_qwen38_config",
]


def __getattr__(name):
    """Keep adapter discovery MLX-free until runtime preparation is needed."""
    if name in {"FP8_BLOCK_SIZE", "dequantize_fp8_weights"}:
        from . import fp8

        return getattr(fp8, name)
    raise AttributeError(name)
