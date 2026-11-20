"""Offline Qwen3 speech-codec adapter using the Runtime-pinned mlx-audio."""

import json
from pathlib import Path

import mlx.core as mx
from mlx_audio.tts.models.qwen3_tts.config import (
    Qwen3TTSTokenizerConfig,
    filter_dict_for_dataclass,
)
from mlx_audio.tts.models.qwen3_tts.speech_tokenizer import Qwen3TTSSpeechTokenizer


class SpeechCodec:
    def __init__(self, path):
        root = Path(path)
        config = json.loads((root / "config.json").read_text())
        self.model = Qwen3TTSSpeechTokenizer(
            Qwen3TTSTokenizerConfig(
                **filter_dict_for_dataclass(Qwen3TTSTokenizerConfig, config)
            )
        )
        state = mx.load(str(root / "model.safetensors"))
        mapped = self.model.sanitize(state)
        # Runtime sanitizer maps encoder EMA codebooks but omits their persisted
        # initialization flags; preserve the actual checkpoint flags explicitly.
        for key, value in state.items():
            if key.startswith("encoder.quantizer.") and key.endswith(
                ".codebook.initialized"
            ):
                name = key.replace(
                    "encoder.quantizer.semantic_residual_vector_quantizer.",
                    "encoder_model.quantizer.rvq_first.vq.",
                ).replace(
                    "encoder.quantizer.acoustic_residual_vector_quantizer.",
                    "encoder_model.quantizer.rvq_rest.vq.",
                )
                mapped[name] = value
        self.model.load_weights(list(mapped.items()), strict=True)
        self.model.eval()
        books = []
        for index in range(16):
            prefix = (
                "decoder.quantizer.rvq_first.vq.layers.0._codebook"
                if index == 0
                else f"decoder.quantizer.rvq_rest.vq.layers.{index - 1}._codebook"
            )
            values = state[prefix + ".embedding_sum"].astype(mx.float32)
            usage = state[prefix + ".cluster_usage"].astype(mx.float32)
            book = values / mx.maximum(usage, 1e-5)[:, None]
            if not bool(mx.all(mx.isfinite(book)).item()):
                raise ValueError("Non-finite speech codebook")
            books.append(book)
        self.codebooks = mx.stack(books)
        mx.eval(self.model.parameters(), self.codebooks)
        self.input_sample_rate = self.model.input_sample_rate
        self.output_sample_rate = self.model.output_sample_rate

    def encode(self, audio):
        """Mono [samples] waveform at input_sample_rate -> [1,frames,16]."""
        if audio.ndim != 1 or audio.size == 0:
            raise ValueError("Expected nonempty mono audio")
        codes = self.model.encode(audio[None, None]).transpose(0, 2, 1)
        mx.eval(codes)
        return codes

    def decode(self, codes):
        """Decode every supplied codec frame, including a valid first code of zero."""
        if codes.ndim != 3 or codes.shape[0] != 1 or codes.shape[-1] != 16:
            raise ValueError("Expected [1,frames,16] speech codes")
        if codes.shape[1] == 0:
            return mx.zeros((0,))
        # The generic model.decode() infers padding from first-code > 0. Ex-Omni
        # supplies exact lengths, so retain all codes instead of dropping code 0.
        waveform = (
            self.model.decoder.chunked_decode(codes.transpose(0, 2, 1))
            .squeeze(0)
            .squeeze(0)
        )
        return waveform[: codes.shape[1] * self.model.decode_upsample_rate]
