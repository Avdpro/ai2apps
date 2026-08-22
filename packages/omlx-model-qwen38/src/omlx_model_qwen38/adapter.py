# SPDX-License-Identifier: Apache-2.0
"""Qwen3.8 adapter implementation."""

from __future__ import annotations

import logging

from omlx.model_adapters import ModelAdapterContext

from .modelopt_config import is_supported_config as is_modelopt_config

logger = logging.getLogger(__name__)


def is_qwen38_config(config: dict) -> bool:
    """Match Qwen3.8 without relying on a user-controlled directory name.

    Qwen3.8 intentionally reuses the ``qwen3_5`` architecture identifier.
    The official 27B release adds the gated-output contract below; Qwen3.5
    27B has otherwise nearly identical geometry, so layer counts alone are
    not a safe discriminator.
    """

    text = config.get("text_config")
    return bool(
        config.get("model_type") == "qwen3_5"
        and config.get("architectures") == ["Qwen3_5ForConditionalGeneration"]
        and config.get("language_model_only") is False
        and isinstance(text, dict)
        and text.get("model_type") == "qwen3_5_text"
        and text.get("output_gate_type") == "swish"
        and text.get("num_hidden_layers") == 64
        and text.get("hidden_size") == 5120
    )


class Qwen38Adapter:
    adapter_id = "qwen38"
    priority = 100

    def match(self, context: ModelAdapterContext) -> bool:
        return is_qwen38_config(context.config) or is_modelopt_config(context.config)

    def classify(self, context: ModelAdapterContext) -> str | None:
        if context.config.get("vision_config"):
            return "vlm"
        return None

    def prepare(self, context: ModelAdapterContext) -> None:
        if not context.for_vlm:
            return

        # Install oMLX's MTP-preserving Qwen3.5-family sanitizer first, then
        # place the Qwen3.8 FP8 expansion immediately in front of it.  The
        # class marker makes this safe across repeated model loads.
        from omlx.patches.mlx_vlm_mtp import apply_mlx_vlm_mtp_patch

        apply_mlx_vlm_mtp_patch()

        from mlx_vlm.models.qwen3_5 import qwen3_5

        from .fp8 import dequantize_fp8_weights

        model_class = qwen3_5.Model
        if model_class.__dict__.get("_omlx_qwen38_fp8_patched", False):
            return

        original_sanitize = model_class.sanitize

        def sanitize(self, weights):
            return original_sanitize(self, dequantize_fp8_weights(weights))

        model_class.sanitize = sanitize
        model_class._omlx_qwen38_fp8_patched = True
        logger.info("Installed Qwen3.8 block-FP8 sanitizer")

    def load(self, context: ModelAdapterContext):
        """Take over only the supported mixed ModelOpt VLM contract."""
        from . import modelopt_mixed

        if not modelopt_mixed.is_supported_config(context.config):
            return None
        if not context.for_vlm:
            raise ValueError(
                "Qwen3.8 mixed ModelOpt checkpoints require the VLM loader; "
                "refusing the text-only fallback"
            )
        return modelopt_mixed.load(context.model_path)
