# SPDX-License-Identifier: Apache-2.0
"""Qwen3-TTS CUDA engine using the existing Host speech contract.

Requires an audio Runtime with qwen-tts, independently pinned from cuda-torch.
No model downloads or runtime dependency installation occur in a Worker.
"""
from __future__ import annotations

import asyncio
import gc
import io
import threading
import wave
from typing import Any
from contextlib import contextmanager

from .omlx_audio import OmlxTTSAdapter
from .protocol import ModelWorkerError


def _unsupported(message: str):
    raise ModelWorkerError(message, code='unsupported_feature', status_code=400)


@contextmanager
def _cancel_on_forward(talker, event):
    # qwen-tts 0.1.1 drops stopping_criteria when constructing talker_kwargs.
    # An instance-local hook aborts before the next decoding step, without
    # modifying upstream files or global model classes.
    def check_cancel(module, args):
        if event.is_set():
            raise ModelWorkerError('Synthesis cancelled', code='request_cancelled', status_code=499)
    handle = talker.register_forward_pre_hook(check_cancel)
    try:
        yield
    finally:
        handle.remove()


class CudaQwenTTSEngine:
    def __init__(self, checkpoint):
        self.checkpoint = checkpoint
        self.model: Any = None
        self.cancelled = threading.Event()

    async def _run(self, function):
        task = asyncio.create_task(asyncio.to_thread(function))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            self.cancelled.set()
            # Keep the request lock until native generation has really stopped.
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
                except Exception:
                    break
            if not task.cancelled():
                task.exception()  # Retrieve a cancellation-related backend error.
            raise

    async def start(self):
        def load():
            import torch
            from qwen_tts import Qwen3TTSModel

            if not torch.cuda.is_available():
                raise RuntimeError('CUDA is unavailable')
            self.model = Qwen3TTSModel.from_pretrained(
                str(self.checkpoint.path), device_map='cuda:0', dtype=torch.bfloat16,
                attn_implementation='sdpa', local_files_only=True,
            )
        try:
            await self._run(load)
        except asyncio.CancelledError:
            await self.stop()
            raise

    async def stop(self):
        self.cancelled.set()
        self.model = None
        gc.collect()
        import torch
        torch.cuda.empty_cache()

    async def synthesize(self, text, *, voice=None, ref_audio=None, ref_text=None,
                         language=None, speed=1.0, instructions=None, **options):
        if not isinstance(text, str):
            _unsupported('Multi-speaker synthesis is not implemented')
        if speed != 1.0:
            _unsupported('CUDA Qwen3-TTS speed control is not yet validated')
        if self.cancelled.is_set():
            raise ModelWorkerError('Synthesis cancelled', code='request_cancelled', status_code=499)

        def generate():
            import numpy as np

            cancelled = self.cancelled
            languages = {'auto':'Auto', 'zh':'Chinese', 'en':'English', 'de':'German',
                         'it':'Italian', 'pt':'Portuguese', 'es':'Spanish', 'ja':'Japanese',
                         'ko':'Korean', 'fr':'French', 'ru':'Russian'}
            selected_language = languages.get(str(language or 'auto').lower(), language)
            kwargs = {name:value for name,value in options.items() if value is not None
                      and name in {'temperature','top_k','top_p','repetition_penalty'}}
            kind = self.model.model.tts_model_type
            # Unseeded upstream sampling can produce unrelated speech even on
            # repeated short inputs. Default to deterministic codec decoding;
            # explicit sampling controls retain the upstream sampling path.
            if not any(name in kwargs for name in ('temperature', 'top_k', 'top_p')):
                if kind == 'base':
                    # Base voice cloning can loop under greedy decoding. Keep
                    # the sampling setting validated by the four-variant probe.
                    kwargs['temperature'] = 0.8
                else:
                    kwargs.update(do_sample=False, subtalker_dosample=False)
            kwargs['max_new_tokens'] = max(1, min(int(options.get('max_tokens') or 2048), 4096))
            with _cancel_on_forward(self.model.model.talker, cancelled):
                if kind == 'custom_voice':
                    if ref_audio:
                        _unsupported('CustomVoice does not accept reference audio')
                    if instructions and self.model.model.tts_model_size == '0b6':
                        _unsupported('Qwen3-TTS 0.6B ignores voice instructions; select a 1.7B model')
                    wavs, rate = self.model.generate_custom_voice(
                        text=text, language=selected_language, speaker=voice or 'Vivian',
                        instruct=instructions, **kwargs)
                elif kind == 'voice_design':
                    if not instructions:
                        raise ModelWorkerError('VoiceDesign requires instructions')
                    if ref_audio:
                        _unsupported('VoiceDesign does not accept reference audio')
                    wavs, rate = self.model.generate_voice_design(
                        text=text, language=selected_language, instruct=instructions, **kwargs)
                elif kind == 'base':
                    if not ref_audio:
                        raise ModelWorkerError('Voice cloning requires a reference_audio request part')
                    if instructions:
                        _unsupported('Base voice cloning does not support voice instructions')
                    wavs, rate = self.model.generate_voice_clone(
                        text=text, language=selected_language, ref_audio=ref_audio,
                        ref_text=ref_text, x_vector_only_mode=not bool(ref_text), **kwargs)
                else:
                    _unsupported('Unsupported Qwen3-TTS variant')
            if cancelled.is_set():
                raise ModelWorkerError('Synthesis cancelled', code='request_cancelled', status_code=499)
            audio = np.asarray(wavs[0], dtype=np.float32)
            if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
                raise RuntimeError('Synthesis returned invalid audio')
            output = io.BytesIO()
            with wave.open(output, 'wb') as wav:
                wav.setparams((1, 2, int(rate), 0, 'NONE', 'not compressed'))
                wav.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())
            return output.getvalue()
        return await self._run(generate)


class CudaQwenTTSAdapter(OmlxTTSAdapter):
    def __init__(self, context):
        super().__init__(context)
        self._request_lock = asyncio.Lock()
        self._cancellations: dict[str, threading.Event] = {}
        self._current_event = None

    async def create_engine(self, checkpoint, runtime_options=None):
        if runtime_options:
            _unsupported('CUDA TTS runtime options have not been validated')
        engine = CudaQwenTTSEngine(checkpoint)
        engine.cancelled = self._current_event or threading.Event()
        return engine

    def cancel(self, request_id):
        if event := self._cancellations.get(request_id):
            event.set()

    async def engine_for(self, model_id, runtime_options=None):
        engine, checkpoint = await super().engine_for(model_id, runtime_options)
        engine.cancelled = self._current_event
        return engine, checkpoint

    async def invoke(self, request):
        event = threading.Event()
        self._cancellations[request.request_id] = event
        try:
            async with self._request_lock:
                if event.is_set():
                    raise ModelWorkerError('Synthesis cancelled', code='request_cancelled', status_code=499)
                self._current_event = event
                return await super().invoke(request)
        finally:
            self._cancellations.pop(request.request_id, None)

    async def stop(self):
        for event in self._cancellations.values():
            event.set()
        async with self._request_lock:
            await super().stop()


def create_adapter(context):
    return CudaQwenTTSAdapter(context)
