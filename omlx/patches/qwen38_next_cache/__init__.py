# SPDX-License-Identifier: Apache-2.0
"""Cached-MoE runtime for Qwen3.8 Flash Next (``qwen4_exp``)."""

from .compat import apply_qwen4_rmsnorm_compat_patch
from .boost import (
    normalize_qwen4_boost,
    qwen4_boost_policy,
    set_qwen4_boost_mode,
)
from .runtime import (
    apply_qwen4_dynamic_patch,
    get_qwen4_dynamic_cache,
    qwen4_dynamic_safetensors_on_load,
)

__all__ = [
    "apply_qwen4_dynamic_patch",
    "apply_qwen4_rmsnorm_compat_patch",
    "get_qwen4_dynamic_cache",
    "qwen4_dynamic_safetensors_on_load",
    "normalize_qwen4_boost",
    "qwen4_boost_policy",
    "set_qwen4_boost_mode",
]
