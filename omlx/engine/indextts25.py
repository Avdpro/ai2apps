# SPDX-License-Identifier: Apache-2.0
"""Native MLX IndexTTS 2.5 engine used by isolated Model Packages."""

from __future__ import annotations

import asyncio
import gc
from pathlib import Path
from typing import Any

import mlx.core as mx
import numpy as np

from ..engine_core import get_mlx_executor
from .audio_utils import audio_to_wav_bytes


_REQUIRED_FILES = (
    "config.yaml",
    "gpt.safetensors",
    "codec.safetensors",
    "s2mel.safetensors",
    "bigvgan.safetensors",
    "w2v_bert.safetensors",
    "campplus.safetensors",
    "feat.npz",
    "stats.npz",
    "bigvgan_config.json",
    "multilingual_zh_ja_yue_char_del.tiktoken",
)


class IndexTTS25Engine:
    """Model-resident, Torch-free IndexTTS 2.5 synthesis engine."""

    def __init__(
        self,
        model_path: str,
        *,
        dtype: str = "fp16",
        quantize: bool = False,
        cache_limit_gb: float = 1.0,
        **_: Any,
    ) -> None:
        self.model_path = Path(model_path).resolve()
        self.dtype = dtype
        self.quantize = quantize
        self.cache_limit_gb = cache_limit_gb
        self._model: Any | None = None

    def _validate_checkpoint(self) -> None:
        missing = [name for name in _REQUIRED_FILES if not (self.model_path / name).is_file()]
        if missing:
            raise FileNotFoundError(
                "IndexTTS 2.5 MLX checkpoint is incomplete: " + ", ".join(missing)
            )

    async def start(self) -> None:
        self._validate_checkpoint()

        def load():
            from omlx.vendor.indextts25.inference import WIndexTTSMLX
            from omlx.vendor.indextts25.support.config import load_default_config

            return WIndexTTSMLX(
                cfg=load_default_config(str(self.model_path)),
                weights_dir=self.model_path,
                dtype=self.dtype,
                quantize=self.quantize,
                # The conditioning stack is also required to blend structured
                # emotion vectors with the reference speaker baseline.  It is
                # not limited to the optional second emotion-audio prompt.
                enable_emo_ref=True,
                cache_limit_gb=self.cache_limit_gb,
            )

        loop = asyncio.get_running_loop()
        self._model = await loop.run_in_executor(get_mlx_executor(), load)

    async def stop(self) -> None:
        self._model = None
        gc.collect()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            get_mlx_executor(), lambda: (mx.synchronize(), mx.clear_cache())
        )

    async def synthesize(
        self,
        text: str,
        *,
        ref_audio: str | None = None,
        language: str | None = None,
        duration_factor: float = 1.0,
        emotion_vector: list[float] | None = None,
        emotion_strength: float = 1.0,
        temperature: float | None = None,
        top_k: int | None = None,
        top_p: float | None = None,
        repetition_penalty: float | None = None,
        **_: Any,
    ) -> bytes:
        if self._model is None:
            raise RuntimeError("Engine not started. Call start() first.")
        if not ref_audio:
            raise ValueError("IndexTTS 2.5 requires reference audio")
        if not 0.5 <= duration_factor <= 2.0:
            raise ValueError("duration_factor must be between 0.5 and 2.0")
        if not 0.0 <= emotion_strength <= 1.0:
            raise ValueError("emotion_strength must be between 0 and 1")
        effective_vector = (
            [float(value) * emotion_strength for value in emotion_vector]
            if emotion_vector is not None
            else None
        )

        def generate():
            return self._model.infer(
                spk_audio_prompt=ref_audio,
                text=text,
                lang=language or "ZH",
                emo_vector=effective_vector,
                duration_factor=duration_factor,
                temperature=temperature if temperature is not None else 0.8,
                top_k=top_k if top_k is not None else 30,
                top_p=top_p if top_p is not None else 0.8,
                repetition_penalty=(
                    repetition_penalty if repetition_penalty is not None else 10.0
                ),
            )

        loop = asyncio.get_running_loop()
        sample_rate, audio = await loop.run_in_executor(get_mlx_executor(), generate)
        waveform = np.asarray(audio, dtype=np.float32)
        return audio_to_wav_bytes(waveform, int(sample_rate))
