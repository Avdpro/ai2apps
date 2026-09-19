"""Seed-VC v2's HuBERT-large layer-18 frontend on MLX."""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx


class HubertLayer18:
    def __init__(self, model) -> None:
        self.model = model

    @classmethod
    def from_directory(cls, path: str | Path) -> HubertLayer18:
        from mlx_audio.stt.models.wav2vec.wav2vec import ModelConfig, Wav2Vec2Model

        root = Path(path)
        values = json.loads((root / "config.json").read_text())
        values["num_hidden_layers"] = 18
        values["apply_spec_augment"] = False
        model = Wav2Vec2Model(ModelConfig.from_dict(values))
        weights = mx.load(str(root / "model.safetensors"), format="safetensors")
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mx.eval(model.parameters())
        return cls(model)

    @staticmethod
    def normalize(waveform: mx.array) -> mx.array:
        if waveform.ndim == 1:
            waveform = waveform[None]
        mean = mx.mean(waveform, axis=-1, keepdims=True)
        variance = mx.mean(mx.square(waveform - mean), axis=-1, keepdims=True)
        return (waveform - mean) * mx.rsqrt(variance + 1e-7)

    def __call__(self, waveform: mx.array) -> mx.array:
        """Return the truncated encoder output before its final LayerNorm."""

        values = self.normalize(waveform)
        features = self.model.feature_extractor(values).transpose(0, 2, 1)
        values, _ = self.model.feature_projection(features)
        encoder = self.model.encoder
        values = values + encoder.pos_conv_embed(values)
        values = encoder.dropout(values)
        for layer in encoder.layers:
            values = layer(values, attention_mask=None)[0]
        return values
