# SPDX-License-Identifier: Apache-2.0
"""Checkpoint compatibility required before Qwen4 cache experiments.

Early community MLX conversions stored Qwen4 RMSNorm parameters as the direct
gamma (centred near one).  The Qwen4 runtime stores the trained residual and
applies ``1 + weight``.  Loading a direct-gamma checkpoint without converting
it therefore produces plausible throughput but invalid token logits.
"""

from __future__ import annotations

import logging
import re

import mlx.core as mx

logger = logging.getLogger(__name__)

_ANCHOR_RE = re.compile(
    r"^language_model\.model\.layers\.\d+"
    r"\.attn_hyper_connection\.hc_norm\.weight$"
)
_MIN_ANCHORS = 8


def _canonicalize_rmsnorm_weights(model, weights, rmsnorm_type) -> None:
    anchors = [
        value
        for key, value in weights.items()
        if _ANCHOR_RE.fullmatch(key)
        and isinstance(value, mx.array)
        and mx.issubdtype(value.dtype, mx.floating)
    ]
    if len(anchors) < _MIN_ANCHORS:
        return

    means = mx.stack([mx.mean(value.astype(mx.float32)) for value in anchors])
    median = mx.median(means)
    ones_vote = mx.mean((means > 0.5).astype(mx.float32))
    mx.eval(median, ones_vote)
    median_value = float(median.item())
    ones_vote_value = float(ones_vote.item())

    ones_centered = (
        ones_vote_value >= 0.9 and 0.75 <= median_value <= 1.5
    )
    zero_centered = (
        ones_vote_value <= 0.1 and -0.5 <= median_value <= 0.25
    )
    if not ones_centered:
        if not zero_centered:
            logger.warning(
                "Ambiguous Qwen4 RMSNorm centering: %d anchors, median %.4f, "
                "ones vote %.1f%%; leaving weights unchanged",
                len(anchors),
                median_value,
                ones_vote_value * 100.0,
            )
        return

    named_modules = getattr(model, "named_modules", None)
    if named_modules is None:
        return
    target_keys = {
        f"{path}.weight"
        for path, module in named_modules()
        if isinstance(module, rmsnorm_type)
    }
    normalized = 0
    for key in target_keys:
        value = weights.get(key)
        if not isinstance(value, mx.array) or not mx.issubdtype(
            value.dtype, mx.floating
        ):
            continue
        # Keep the subtraction in FP32; BF16 loses meaningful residual bits.
        weights[key] = value.astype(mx.float32) - 1.0
        normalized += 1
    logger.info(
        "Canonicalized %d direct-gamma Qwen4 RMSNorm tensors "
        "(%d anchors, median %.4f)",
        normalized,
        len(anchors),
        median_value,
    )


def apply_qwen4_rmsnorm_compat_patch() -> bool:
    """Patch the active mlx-vlm Qwen4 sanitizer, once.

    This small compatibility hook works with both the upstream Qwen4 module
    and the vendored module that the Cached-MoE runtime will install.
    """

    from omlx.patches.mlx_vlm_qwen4_exp_compat import (
        apply_mlx_vlm_qwen4_exp_compat_patch,
    )

    apply_mlx_vlm_qwen4_exp_compat_patch()
    from mlx_vlm.models.qwen4_exp.language import Qwen4ExpRMSNorm
    from mlx_vlm.models.qwen4_exp.qwen4_exp import Model

    current = Model.sanitize
    if getattr(current, "_omlx_qwen4_rmsnorm_compat", False):
        return False

    def sanitize(self, weights):
        sanitized = current(self, weights)
        _canonicalize_rmsnorm_weights(self, sanitized, Qwen4ExpRMSNorm)
        return sanitized

    sanitize._omlx_qwen4_rmsnorm_compat = True
    Model.sanitize = sanitize
    return True


__all__ = ["apply_qwen4_rmsnorm_compat_patch"]
