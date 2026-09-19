"""MLX HuBERT/ContentVec adapter used by RVC."""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx


def normalize_audio(audio: mx.array, *, epsilon: float = 1e-7) -> mx.array:
    """Apply the zero-mean/unit-variance normalization used by RVC HuBERT."""

    if audio.ndim == 1:
        audio = audio[None, :]
    if audio.ndim != 2:
        raise ValueError("audio must have shape [samples] or [batch, samples]")
    mean = mx.mean(audio, axis=-1, keepdims=True)
    variance = mx.mean(mx.square(audio - mean), axis=-1, keepdims=True)
    return (audio - mean) / mx.sqrt(variance + epsilon)


class ContentVec:
    """RVC-compatible v1/v2 features backed by mlx-audio's Wav2Vec2 model."""

    def __init__(
        self, model, final_projection: tuple[mx.array, mx.array] | None = None
    ):
        self.model = model
        self.final_projection = final_projection

    @classmethod
    def from_directory(cls, path: str | Path) -> ContentVec:
        from mlx_audio.stt.models.wav2vec.wav2vec import ModelConfig, Wav2Vec2Model

        root = Path(path)
        config = ModelConfig.from_dict(json.loads((root / "config.json").read_text()))
        model = Wav2Vec2Model(config)
        weights = mx.load(str(root / "model.safetensors"), format="safetensors")
        final_weight = weights.pop("final_proj.weight", None)
        final_bias = weights.pop("final_proj.bias", None)
        weights = model.sanitize(weights)
        model.load_weights(list(weights.items()), strict=True)
        model.eval()
        mx.eval(model.parameters())
        projection = None
        if final_weight is not None and final_bias is not None:
            projection = (final_weight, final_bias)
        return cls(model, projection)

    def __call__(self, audio: mx.array, *, version: str = "v2") -> mx.array:
        if version not in {"v1", "v2"}:
            raise ValueError(f"unsupported RVC feature version: {version!r}")
        source = normalize_audio(audio)
        output = self.model(
            source,
            attention_mask=None,
            output_hidden_states=version == "v1",
            return_dict=True,
        )
        if version == "v2":
            return output.last_hidden_state
        if self.final_projection is None:
            raise ValueError("v1 features require final_proj weights")
        weight, bias = self.final_projection
        return output.hidden_states[9] @ weight.T + bias
