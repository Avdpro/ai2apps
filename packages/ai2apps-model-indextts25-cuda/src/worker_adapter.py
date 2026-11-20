from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ai2apps.model_worker import ModelWorkerError
from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter, CudaQwenTTSEngine
from dataclasses import replace
from pathlib import Path
import tempfile
import threading


_EMOTIONS = (
    "happy",
    "angry",
    "sad",
    "afraid",
    "disgusted",
    "melancholic",
    "surprised",
    "calm",
)
_BIASES = (0.9375, 0.875, 1.0, 1.0, 0.9375, 0.9375, 0.6875, 0.5625)
_ALIASES = {
    "happy": {"happy": 0.8},
    "angry": {"angry": 0.8},
    "sad": {"sad": 0.8},
    "calm": {"calm": 0.8},
    "surprised": {"surprised": 0.8},
}


def _emotion_vector(emotion: str | None) -> list[float] | None:
    if not emotion or emotion.lower() == "neutral":
        return None
    raw = _ALIASES[emotion.lower()]
    values = [raw.get(name, 0.0) * bias for name, bias in zip(_EMOTIONS, _BIASES)]
    total = sum(values)
    if total > 0.8:
        values = [value * 0.8 / total for value in values]
    return values


def _language(value: Any, text: Any) -> str:
    requested = str(value or "auto").lower().replace("_", "-")
    if requested in {"zh", "zh-cn", "zh-hans", "chinese"}:
        return "ZH"
    if requested in {"en", "en-us", "en-gb", "english"}:
        return "EN"
    if requested != "auto":
        raise ModelWorkerError(
            f"IndexTTS 2.5 P0 does not support language: {value}",
            code="unsupported_feature",
            status_code=400,
        )
    return "ZH" if re.search(r"[\u3400-\u9fff]", str(text or "")) else "EN"


MODEL_ID = 'ai2apps.model.indextts25-cuda/fp16'
CHECKPOINT = ('Avdpro/MLX-IndexTTS-2.5', '01d27e6d8a0c628859abe2142a0fd431b91e79af')


def invalid(message, code='invalid_request_error', status=400):
    raise ModelWorkerError(message, code=code, status_code=status)


class CudaIndexSpeechEngine(CudaQwenTTSEngine):
    def _check(self):
        if self.cancelled.is_set():
            invalid('Speech generation cancelled', 'request_cancelled', 499)

    async def start(self):
        def load():
            import cuda_indextts_engine as implementation
            self._check()
            self.model = implementation.CudaIndexTTSEngine(self.checkpoint.path,
                Path(implementation.__file__).with_name('indextts25-data'), check=self._check)
        try:
            await self._run(load)
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        self.cancelled.set()
        def release():
            model, self.model = self.model, None
            if model is not None:
                model.close()
        await self._run(release)

    async def synthesize(self, text, *, voice=None, ref_audio=None, ref_text=None,
                         language='ZH', speed=1., instructions=None, **options):
        if voice or instructions:
            invalid('IndexTTS does not support named voices or text instructions', 'unsupported_feature')
        if not ref_audio:
            invalid('IndexTTS requires reference_audio', 'invalid_reference_audio')
        if options.get('max_tokens') is not None:
            invalid('IndexTTS uses per-segment text-derived token limits', 'unsupported_feature')
        if self.model is None:
            await self.start()
        def generate():
            import torch
            self._check()
            with tempfile.TemporaryDirectory(prefix='indextts-request-') as directory:
                output = Path(directory) / 'speech.wav'
                sampling = {k: options[k] for k in ('temperature', 'top_k', 'top_p', 'repetition_penalty')
                            if options.get(k) is not None}
                try:
                    self.model.generate(text, ref_audio, output, language=language, speed=speed,
                        emotion_vector=options.get('emotion_vector'),
                        emotion_strength=options.get('emotion_strength', 1.),
                        seed=options.get('seed', 42), check=self._check, **sampling)
                except ValueError as error:
                    invalid(str(error))
                except torch.cuda.OutOfMemoryError as error:
                    model, self.model = self.model, None
                    model.close()
                    raise ModelWorkerError('CUDA memory exhausted during IndexTTS generation',
                        code='resource_exhausted', status_code=503) from error
                self._check()
                return output.read_bytes()
        return await self._run(generate)


class CudaIndexTTSAdapter(CudaQwenTTSAdapter):
    def __init__(self, context):
        super().__init__(context)
        self._stopping = False

    async def start(self):
        self._stopping = False

    async def stop(self):
        self._stopping = True
        await super().stop()

    async def invoke(self, request):
        if self._stopping:
            invalid('Worker is stopping', 'worker_stopping', 503)
        if request.request_id in self._cancellations:
            invalid('Request already active', 'request_conflict', 409)
        if request.payload.get('model') != MODEL_ID:
            invalid('Unknown IndexTTS model', 'model_not_found', 404)
        if (request.parts or {}).get('reference_audio') is None:
            invalid('IndexTTS requires an authorized reference_audio part', 'invalid_reference_audio')
        body = dict(request.payload)
        seed = body.get('seed', 42)
        if isinstance(seed, str) and re.fullmatch(r'[0-9]{1,10}', seed):
            seed = int(seed)
        if type(seed) is not int or not 0 <= seed < 2**32:
            invalid('seed must be uint32')
        body['seed'] = seed
        return await super().invoke(replace(request, payload=body))

    async def create_engine(self, checkpoint, runtime_options=None):
        if checkpoint.model_id != MODEL_ID or checkpoint.path is None or (
                checkpoint.repo_id, checkpoint.revision) != CHECKPOINT:
            invalid('Host-selected fixed IndexTTS checkpoint required', 'checkpoint_not_ready', 409)
        if runtime_options:
            invalid('Unsupported IndexTTS runtime settings', 'unsupported_feature')
        engine = CudaIndexSpeechEngine(checkpoint)
        engine.cancelled = self._current_event or threading.Event()
        return engine

    def synthesis_options(self, model_id, body, *, speed, emotion, emotion_strength, instructions):
        return {'speed': speed, 'emotion_vector': _emotion_vector(emotion),
                'emotion_strength': emotion_strength,
                'language': _language(body.get('language'), body.get('input')),
                'instructions': None, 'seed': body.get('seed', 42)}


def create_adapter(context):
    return CudaIndexTTSAdapter(context)
