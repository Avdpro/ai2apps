"""Compatibility processor for GLM-5 Next checkpoints.

Transformers releases before native ``glm5_next`` registration silently load
the checkpoint tokenizer as an ``AutoProcessor``.  That leaves the literal
``<|image|>`` placeholder in the prompt and drops ``pixel_values`` entirely.
GLM-5 Next uses the same visual patch contract as GLM-4.6V/GLM-GA, so compose
those public processor components until Transformers ships the native alias.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_INSTALLED = False


def _is_glm5_next(model_path: Any) -> bool:
    try:
        config_path = Path(model_path) / "config.json"
        config = json.loads(config_path.read_text())
    except (OSError, TypeError, ValueError):
        return False
    return config.get("model_type") == "glm5_next"


def _build_glm5_next_processor(
    model_path: Any,
    *,
    add_detokenizer: bool,
    eos_token_ids: Any = None,
    **kwargs: Any,
):
    from transformers import AutoTokenizer
    from transformers.models.glm46v.processing_glm46v import Glm46VProcessor
    from transformers.models.glmga.image_processing_pil_glmga import (
        GlmgaImageProcessorPil,
    )
    from transformers.video_processing_utils import BaseVideoProcessor

    from mlx_vlm.tokenizer_utils import load_tokenizer
    from mlx_vlm.utils import StoppingCriteria

    class _ImageOnlyVideoProcessor(BaseVideoProcessor):
        """Satisfy ProcessorMixin without importing optional torchvision.

        GLM-5 video support gets its own native implementation later; this
        compatibility object is deliberately explicit if it is called.
        """

        merge_size = 2
        model_input_names = ["pixel_values_videos", "video_grid_thw"]

        def preprocess(self, *args: Any, **video_kwargs: Any):
            raise NotImplementedError(
                "GLM-5 Next video preprocessing requires the native processor"
            )

    class _Glm5NextProcessor(Glm46VProcessor):
        # Transformers maps BaseVideoProcessor to an optional-dependency dummy
        # when torchvision is absent, even though image preprocessing itself
        # is PIL/NumPy-only. Avoid that unrelated constructor type check while
        # retaining the upstream GLM-4.6V token expansion implementation.
        def __init__(
            self,
            image_processor: Any,
            tokenizer: Any,
            video_processor: Any,
            chat_template: str | None = None,
        ):
            self.image_processor = image_processor
            self.tokenizer = tokenizer
            self.video_processor = video_processor
            self.chat_template = chat_template
            self.image_token = getattr(tokenizer, "image_token", "<|image|>")
            self.video_token = getattr(tokenizer, "video_token", "<|video|>")
            self.image_token_id = getattr(tokenizer, "image_token_id", None) or tokenizer.convert_tokens_to_ids(
                self.image_token
            )
            self.video_token_id = getattr(tokenizer, "video_token_id", None) or tokenizer.convert_tokens_to_ids(
                self.video_token
            )
            self.video_start_id = tokenizer.convert_tokens_to_ids("<|begin_of_video|>")
            self.video_end_id = tokenizer.convert_tokens_to_ids("<|end_of_video|>")

    root = Path(model_path)
    processor_config = json.loads((root / "processor_config.json").read_text())
    image_config = processor_config.get("image_processor", {})

    patch_size = int(image_config.get("patch_size", 14))
    temporal_patch_size = int(image_config.get("temporal_patch_size", 2))
    merge_size = int(image_config.get("merge_size", 2))
    expand = int(image_config.get("patch_expand_factor", 1))
    token_pixels = (patch_size * merge_size * expand) ** 2
    min_tokens = int(image_config.get("min_image_tokens", 16))
    max_tokens = int(
        os.environ.get(
            "OMLX_GLM5_MAX_IMAGE_TOKENS",
            image_config.get("max_image_tokens", 8000),
        )
    )

    tokenizer_kwargs = dict(kwargs)
    # Processor-only arguments are not accepted by AutoTokenizer.
    tokenizer_kwargs.pop("use_fast", None)
    tokenizer = AutoTokenizer.from_pretrained(root, **tokenizer_kwargs)
    image_processor = GlmgaImageProcessorPil(
        size={
            "shortest_edge": min_tokens * token_pixels,
            "longest_edge": max_tokens * token_pixels,
        },
        patch_size=patch_size,
        temporal_patch_size=temporal_patch_size,
        merge_size=merge_size,
        patch_expand_factor=expand,
    )
    video_processor = _ImageOnlyVideoProcessor()
    processor = _Glm5NextProcessor(
        image_processor=image_processor,
        tokenizer=tokenizer,
        video_processor=video_processor,
        chat_template=getattr(tokenizer, "chat_template", None),
    )

    if add_detokenizer:
        detokenizer_class = load_tokenizer(root, return_tokenizer=False)
        processor.detokenizer = detokenizer_class(tokenizer)
        final_eos = (
            eos_token_ids
            or getattr(tokenizer, "eos_token_ids", None)
            or getattr(tokenizer, "eos_token_id", None)
        )
        tokenizer.stopping_criteria = StoppingCriteria(final_eos, tokenizer)
    return processor


def install_glm5_next_processor_patch() -> bool:
    """Patch mlx-vlm's loader only for ``model_type=glm5_next``."""

    global _INSTALLED
    if _INSTALLED:
        return False

    import mlx_vlm.utils as vlm_utils

    original = vlm_utils.load_processor

    def load_processor(
        model_path: Any,
        add_detokenizer: bool = True,
        eos_token_ids: Any = None,
        **kwargs: Any,
    ):
        if not _is_glm5_next(model_path):
            return original(model_path, add_detokenizer, eos_token_ids, **kwargs)
        return _build_glm5_next_processor(
            model_path,
            add_detokenizer=add_detokenizer,
            eos_token_ids=eos_token_ids,
            **kwargs,
        )

    vlm_utils.load_processor = load_processor
    _INSTALLED = True
    return True
