"""Local native Wan conditioning encoders shared by avatar inference paths."""

import json
from pathlib import Path

import mlx.core as mx

from .audio_encoder import (
    wav2vec2_encode,
    wav2vec2_parameters_from_tensors,
    wav2vec2_tensor_names,
)
from .image_encoder import (
    wan_clip_preprocess,
    wan_clip_vision_encode,
    wan_clip_vision_parameters_from_tensors,
    wan_clip_vision_tensor_names,
)
from .text_encoder import (
    load_wan_t5_tokenizer,
    wan_t5_encode_trimmed,
    wan_t5_parameters_from_tensors,
    wan_t5_tokenize,
)


class TextEncoder:
    def __init__(self, weights, tokenizer):
        tensors = mx.load(str(weights))
        self.parameters = wan_t5_parameters_from_tensors(tensors)
        self.tokenizer = load_wan_t5_tokenizer(Path(tokenizer))

    def __call__(self, prompt):
        ids, mask = wan_t5_tokenize([prompt], self.tokenizer)
        hidden, lengths = wan_t5_encode_trimmed(ids, mask, self.parameters)
        return hidden[:, : int(lengths[0].item())]


class ImageEncoder:
    def __init__(self, weights):
        tensors = mx.load(str(weights))
        names = wan_clip_vision_tensor_names()
        self.parameters = wan_clip_vision_parameters_from_tensors(
            {k: tensors[k] for k in names}
        )

    def __call__(self, image):
        return wan_clip_vision_encode(wan_clip_preprocess(image), self.parameters)


class AudioEncoder:
    def __init__(self, root):
        root = Path(root)
        config = json.loads((root / "config.json").read_text())
        if (
            config.get("hidden_size"),
            config.get("num_hidden_layers"),
            config.get("feat_extract_norm"),
        ) != (768, 12, "group"):
            raise ValueError("Expected compatible base Wav2Vec2 encoder")
        tensors = mx.load(str(root / "model.safetensors"))
        prefix = "wav2vec2.encoder.pos_conv_embed.conv."
        for old, new in [
            ("parametrizations.weight.original0", "weight_g"),
            ("parametrizations.weight.original1", "weight_v"),
        ]:
            if prefix + old in tensors:
                tensors[prefix + new] = tensors.pop(prefix + old)
        self.parameters = wav2vec2_parameters_from_tensors(
            {k: tensors[k] for k in wav2vec2_tensor_names()}
        )

    def hidden_states(self, waveform, frames):
        waveform = waveform.astype(mx.float32)
        waveform = (waveform - mx.mean(waveform)) / mx.sqrt(mx.var(waveform) + 1e-7)
        return mx.stack(
            wav2vec2_encode(waveform[None], self.parameters, output_length=frames),
            axis=2,
        )
