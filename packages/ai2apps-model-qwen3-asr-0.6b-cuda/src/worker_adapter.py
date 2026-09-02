# SPDX-License-Identifier: Apache-2.0
"""CUDA Transformers adapter for Qwen3-ASR."""

from __future__ import annotations

import asyncio
import wave
from contextlib import suppress
from typing import Any

from ai2apps.model_worker.protocol import (
    ModelWorkerContext,
    ModelWorkerError,
    ModelWorkerRequest,
)


def _error(message: str, *, code: str = "invalid_request_error", status: int = 400):
    raise ModelWorkerError(message, code=code, status_code=status)


class CudaQwen3ASRAdapter:
    def __init__(self, context: ModelWorkerContext) -> None:
        self.context = context
        self._model: Any | None = None
        self._processor: Any | None = None
        self._model_id: str | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        async with self._lock:
            self._model = None
            self._processor = None
            self._model_id = None
            with suppress(Exception):
                import torch

                torch.cuda.empty_cache()

    async def _ensure_loaded(self, model_id: str) -> tuple[Any, Any]:
        checkpoint = self.context.checkpoint_for(model_id)
        if checkpoint is None:
            _error(f"Unsupported model: {model_id}")
        if checkpoint.path is None:
            _error(
                f"Checkpoint is not installed: {checkpoint.repo_id}@{checkpoint.revision}",
                code="model_unavailable",
                status=503,
            )
        async with self._lock:
            if self._model is not None and self._model_id == checkpoint.model_id:
                return self._model, self._processor

            def load():
                import torch
                from transformers import AutoModelForMultimodalLM, AutoProcessor

                if not torch.cuda.is_available():
                    _error("CUDA is unavailable inside the Model Worker", status=503)
                processor = AutoProcessor.from_pretrained(
                    checkpoint.path, local_files_only=True, trust_remote_code=False
                )
                model = AutoModelForMultimodalLM.from_pretrained(
                    checkpoint.path,
                    local_files_only=True,
                    trust_remote_code=False,
                    dtype=torch.bfloat16,
                ).to("cuda:0")
                model.eval()
                return model, processor

            try:
                self._model, self._processor = await asyncio.to_thread(load)
            except ModelWorkerError:
                raise
            except Exception as error:
                raise ModelWorkerError(
                    f"Unable to load {checkpoint.repo_id}: {error}",
                    code="model_load_failed",
                    status_code=503,
                ) from error
            self._model_id = checkpoint.model_id
            return self._model, self._processor

    @staticmethod
    def _read_wav(path: str):
        import numpy as np

        with wave.open(path, "rb") as source:
            channels = source.getnchannels()
            sample_width = source.getsampwidth()
            sample_rate = source.getframerate()
            frames = source.readframes(source.getnframes())
        if sample_width == 1:
            audio = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128) / 128
        elif sample_width == 2:
            audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768
        elif sample_width == 3:
            octets = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
            values = (
                octets[:, 0].astype(np.int32)
                | (octets[:, 1].astype(np.int32) << 8)
                | (octets[:, 2].astype(np.int32) << 16)
            )
            values = (values ^ 0x800000) - 0x800000
            audio = values.astype(np.float32) / 8388608
        elif sample_width == 4:
            audio = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648
        else:
            _error("Qwen3-ASR accepts 8, 16, 24, or 32-bit PCM WAV input")
        if channels > 1:
            audio = audio.reshape(-1, channels).mean(axis=1)
        if sample_rate != 16000 and audio.size:
            duration = audio.size / sample_rate
            old_time = np.arange(audio.size, dtype=np.float64) / sample_rate
            new_time = np.arange(round(duration * 16000), dtype=np.float64) / 16000
            audio = np.interp(new_time, old_time, audio).astype(np.float32)
        return audio

    @staticmethod
    def _transcribe(model: Any, processor: Any, audio_path: str, body: dict[str, Any]):
        import torch

        audio = CudaQwen3ASRAdapter._read_wav(audio_path)
        language = body.get("language") or None
        prompt = body.get("prompt") or None
        if language is not None:
            inputs = processor.apply_transcription_request(
                audio=audio, language=language, prompt=prompt
            )
        else:
            messages = []
            if prompt:
                messages.append(
                    {"role": "system", "content": [{"type": "text", "text": prompt}]}
                )
            messages.append(
                {"role": "user", "content": [{"type": "audio", "audio": audio}]}
            )
            inputs = processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
            )
        inputs = inputs.to(model.device, model.dtype)
        with torch.inference_mode():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=max(1, min(int(body.get("max_tokens") or 256), 4096)),
                do_sample=False,
            )
        generated = output_ids[:, inputs["input_ids"].shape[1] :]
        parsed = processor.decode(generated, return_format="parsed")[0]
        return {
            "text": str(parsed.get("transcription") or ""),
            "language": parsed.get("language"),
        }

    async def invoke(self, request: ModelWorkerRequest):
        if request.operation != "audio_transcription":
            _error(f"Unsupported operation: {request.operation}")
        body = dict(request.payload)
        model_id = body.get("model")
        if not isinstance(model_id, str) or not model_id:
            _error("model is required")
        if str(body.get("response_format") or "json") not in {"json", "verbose_json"}:
            _error("Only JSON transcription responses are supported")
        if body.get("stream") in {True, "true"}:
            _error("Streaming transcription is not implemented", code="unsupported_feature")
        if body.get("word_timestamps") in {True, "true"}:
            _error("Word timestamps require the optional aligner Package", code="unsupported_feature")
        body.pop("_ai2apps_model_settings", None)
        model, processor = await self._ensure_loaded(model_id)
        audio = request.part("file")
        try:
            result = await asyncio.to_thread(
                self._transcribe, model, processor, str(audio.path), body
            )
        except ModelWorkerError:
            raise
        except Exception as error:
            raise ModelWorkerError(
                f"Transcription failed: {error}",
                code="transcription_failed",
                status_code=500,
            ) from error
        result["features"] = {
            "timestamps": {"requested": "none", "effective": "none", "status": "unsupported"}
        }
        return result


def create_adapter(context: ModelWorkerContext):
    return CudaQwen3ASRAdapter(context)
