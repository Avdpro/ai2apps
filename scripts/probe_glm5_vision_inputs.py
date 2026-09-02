#!/usr/bin/env python3
"""Inspect GLM-5.3 image placeholder expansion without loading model weights."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import mlx.core as mx
from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("image", type=Path)
    parser.add_argument("--prompt", default="请描述图片。")
    args = parser.parse_args()

    from omlx.patches.glm5_next_cache.runtime import _install_vendor_namespace

    _install_vendor_namespace()
    from mlx_vlm.prompt_utils import get_message_json
    from mlx_vlm.utils import load_processor, prepare_inputs

    processor = load_processor(args.checkpoint, add_detokenizer=False)
    message = get_message_json(
        "glm5_next", args.prompt, num_images=1, skip_image_token=False
    )
    prompt = processor.apply_chat_template(
        [message], tokenize=False, add_generation_prompt=True
    )
    image = Image.open(args.image).convert("RGB")
    inputs = prepare_inputs(processor, images=[image], prompts=[prompt])
    ids = inputs["input_ids"]
    config = json.loads((args.checkpoint / "config.json").read_text())
    image_token_id = int(config["image_token_id"])
    print(f"message={message!r}")
    print(f"prompt={prompt!r}")
    print(f"input_ids_shape={tuple(ids.shape)}")
    print(f"image_tokens={int(mx.sum(ids == image_token_id).item())}")
    for key, value in inputs.items():
        shape = getattr(value, "shape", None)
        print(f"{key}: type={type(value).__name__} shape={shape}")


if __name__ == "__main__":
    main()
