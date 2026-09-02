"""Qwen3-VL text-only feature taps used by Ideogram 4."""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
from mlx_vlm.models.base import create_attention_mask
from mlx_vlm.models.qwen3_vl.config import ModelConfig
from mlx_vlm.models.qwen3_vl.language import Qwen3VLModel

ACTIVATION_LAYERS = (0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 35)


class Ideogram4TextEncoder:
    def __init__(self, model: Qwen3VLModel) -> None:
        self.model = model

    def __call__(self, token_ids: mx.array) -> mx.array:
        hidden = self.model.embed_tokens(token_ids)
        mask = create_attention_mask(hidden, None)
        captured = []
        tap_set = set(ACTIVATION_LAYERS)
        for index, layer in enumerate(self.model.layers):
            hidden = layer(hidden, mask=mask)
            if index in tap_set:
                captured.append(hidden)
        if len(captured) != len(ACTIVATION_LAYERS):
            raise RuntimeError("Qwen3-VL did not expose all Ideogram 4 feature taps")
        return mx.stack(captured, axis=-1).reshape(
            hidden.shape[0], hidden.shape[1], -1
        )


def load_quantized_text_encoder(
    checkpoint: str | Path,
    config_path: str | Path,
    *,
    bits: int,
    group_size: int,
) -> Ideogram4TextEncoder:
    config_data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    config = ModelConfig.from_dict(config_data)
    model = Qwen3VLModel(config.text_config)
    weights = mx.load(str(checkpoint))

    def predicate(path: str, module: nn.Module) -> bool:
        return hasattr(module, "to_quantized") and f"{path}.scales" in weights

    nn.quantize(
        model,
        bits=bits,
        group_size=group_size,
        class_predicate=predicate,
    )
    # The final LM norm is not used: Ideogram taps decoder-layer outputs before
    # that norm. Older derived checkpoints therefore legitimately omit it.
    model.load_weights(list(weights.items()), strict=False)
    model.eval()
    mx.eval(model.parameters())
    return Ideogram4TextEncoder(model)
