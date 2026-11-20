"""Reference voice encoding from the released Ex-Omni checkpoint."""

import json
from pathlib import Path

import mlx.core as mx
from mlx_audio.tts.models.qwen3_tts.config import (
    Qwen3TTSSpeakerEncoderConfig,
    filter_dict_for_dataclass,
)
from mlx_audio.tts.models.qwen3_tts.qwen3_tts import mel_spectrogram
from mlx_audio.tts.models.qwen3_tts.speaker_encoder import Qwen3TTSSpeakerEncoder


class SpeakerEncoder:
    def __init__(self, exomni_dir, qwen_config):
        root = Path(exomni_dir)
        values = json.loads(Path(qwen_config).read_text())["speaker_encoder_config"]
        config = Qwen3TTSSpeakerEncoderConfig(
            **filter_dict_for_dataclass(Qwen3TTSSpeakerEncoderConfig, values)
        )
        self.model = Qwen3TTSSpeakerEncoder(config)
        index = json.loads((root / "model.safetensors.index.json").read_text())[
            "weight_map"
        ]
        prefix = "model.speech_generator.roleplay_speaker_encoder.encoder."
        names = {key for key in index if key.startswith(prefix)}
        weights = {}
        for shard in sorted({index[key] for key in names}):
            state = mx.load(str(root / shard))
            for key in names.intersection(state):
                name = key[len(prefix) :]
                value = state[key].astype(mx.float32)
                if value.ndim == 3 and name.endswith(".weight"):
                    value = value.transpose(0, 2, 1)
                weights[name] = value
        self.model.load_weights(list(weights.items()), strict=True)
        self.model.eval()
        mx.eval(self.model.parameters())
        self.sample_rate = config.sample_rate
        self.mel_dim = config.mel_dim

    def __call__(self, waveform):
        if (
            waveform.ndim != 1
            or waveform.size == 0
            or not bool(mx.all(mx.isfinite(waveform)).item())
        ):
            raise ValueError("Expected nonempty finite mono reference audio at 24 kHz")
        waveform = mx.clip(waveform.astype(mx.float32), -1, 1)
        if waveform.size <= 1024:
            waveform = mx.pad(waveform, [(0, 1025 - waveform.size)])
        mel = mel_spectrogram(
            waveform,
            num_mels=self.mel_dim,
            sample_rate=self.sample_rate,
            fmax=self.sample_rate // 2,
        )
        embedding = self.model(mel)
        mx.eval(embedding)
        return embedding[:, None, :]
