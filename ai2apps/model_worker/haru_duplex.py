# SPDX-License-Identifier: Apache-2.0
"""Local Haru MLX frame backend; no microphone, HTTP endpoint or Tool authority.

The continuous model consumes input while emitting output on every step. All
MLX state lives on one dedicated thread; playback remains a client concern.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import numpy as np

SAMPLE_RATE = 24000
FRAME_SAMPLES = 3200
UPSTREAM_COMMIT = '7fe6b7665f8bf035998f401f8cb779fbe53f2751'
CHECKPOINT_REVISION = '8d6e83bcd3701a76fc27a764965665da1df7da78'


@dataclass(frozen=True)
class DuplexOutput:
    session_id: str
    index: int
    sample_start: int
    playback_epoch: int
    audio: np.ndarray
    text: str
    compute_seconds: float
    done: bool
    suppressed: bool


class HaruDuplexBackend:
    """One model, one conversation, at most one outstanding frame.

    A cancelled inference await invalidates the conversation. The GPU job may
    finish, but cannot be replayed as if its input had never been consumed.
    ``close`` drains that worker before releasing model state on its own thread.
    """

    capabilities = {
        'model': 'higurashi-ai/Haru-4B', 'backend': 'mlx',
        'stream_audio_in': True, 'stream_audio_out': True, 'native_duplex': True,
        'text_out': True, 'text_in': False, 'attachment_types': [],
        'tool_calls': False, 'async_result_injection': False,
        'response_cancel': False, 'context_truncate': False,
        'playback_alignment': 'frame', 'voice_control': 'reference_audio',
        'sample_rate': SAMPLE_RATE, 'frame_samples': FRAME_SAMPLES,
        'verification': 'experimental',
    }

    def __init__(self, checkpoint: str | Path, *, quantize: int | None = 8):
        self.checkpoint = Path(checkpoint).expanduser().resolve()
        for name in ('config.json', 'tokenizer.json', 'model.safetensors'):
            if not (self.checkpoint / name).is_file():
                raise ValueError(f'Local Haru checkpoint is missing {name}')
        if quantize not in (None, 8):
            raise ValueError('Supported backbone precision: bfloat16 or 8-bit')
        self.quantize = quantize
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ai2apps-haru-mlx')
        self._lock = asyncio.Lock()
        self._model = self._session = None
        self._session_id = None
        self._faulted = self._closed = False
        self._epoch = 0
        self._output_muted = False

    async def _run(self, fn, *args):
        if self._closed:
            raise RuntimeError('Haru backend is closed')
        future = asyncio.get_running_loop().run_in_executor(self._executor, fn, *args)
        try:
            return await asyncio.shield(future)
        except asyncio.CancelledError:
            self._faulted = True
            # Observe exceptions from the still-running job without delivering
            # its stale frame after the owner has cancelled the await.
            future.add_done_callback(lambda done: done.exception() if not done.cancelled() else None)
            raise

    def _load(self):
        if self._model is None:
            from .haru_mlx import load_model
            self._model = load_model(str(self.checkpoint), quantize=self.quantize)
            if (self._model.config.sample_rate, self._model.config.frame_samples) != (SAMPLE_RATE, FRAME_SAMPLES):
                self._model = None
                raise ValueError('Checkpoint does not have the expected Haru audio geometry')

    async def load(self):
        async with self._lock:
            await self._run(self._load)

    @staticmethod
    def _pcm(value, *, frame=False):
        audio = np.asarray(value)
        if audio.ndim != 1 or (frame and len(audio) != FRAME_SAMPLES):
            raise ValueError('Expected mono 24 kHz PCM; each frame has 3200 samples')
        if not frame and not 3 * SAMPLE_RATE <= len(audio) <= 180 * SAMPLE_RATE:
            raise ValueError('Voice reference must contain 3 to 180 seconds of mono 24 kHz PCM')
        if not np.issubdtype(audio.dtype, np.floating) or not np.isfinite(audio).all() or np.any(np.abs(audio) > 1):
            raise ValueError('PCM must be finite floating point samples in [-1, 1]')
        return np.array(audio, dtype=np.float32, copy=True)

    def _start(self, prompt, reference, seed, max_frames, speak_first):
        from .haru_mlx import DuplexConfig, DuplexSession
        self._load()
        self._session = DuplexSession(self._model, system_prompt=prompt, reference=reference,
            config=DuplexConfig(seed=seed, max_frames=max_frames, speak_first=speak_first))
        return self._session.start()

    async def start(self, *, system_prompt: str, reference_audio, seed=0, max_frames=4500, speak_first=False):
        if not isinstance(system_prompt, str) or not system_prompt.strip() or len(system_prompt) > 16000:
            raise ValueError('A bounded character/system prompt is required')
        if type(max_frames) is not int or not 1 <= max_frames <= 27000:
            raise ValueError('max_frames must be between 1 and 27000')
        if type(seed) is not int or not 0 <= seed < 2**32 or type(speak_first) is not bool:
            raise ValueError('Invalid session sampling configuration')
        reference = self._pcm(reference_audio)
        async with self._lock:
            if self._session_id is not None:
                raise RuntimeError('Close the current conversation before starting another')
            if self._faulted:
                raise RuntimeError('Recreate the backend after cancelled or failed inference')
            self._session_id = 'haru_' + uuid4().hex
            epoch = self._epoch
            try:
                frame = await self._run(self._start, system_prompt, reference, seed, max_frames, speak_first)
                return self._output(frame, epoch)
            except BaseException:
                self._faulted = True
                raise

    def _output(self, frame, epoch):
        suppressed = self._output_muted or epoch != self._epoch
        audio = np.zeros(FRAME_SAMPLES, dtype=np.float32) if suppressed else np.array(frame.audio, dtype=np.float32, copy=True)
        if audio.shape != (FRAME_SAMPLES,) or not np.isfinite(audio).all() or np.any(np.abs(audio) > 1):
            self._faulted = True
            raise RuntimeError('Haru produced an invalid PCM frame')
        return DuplexOutput(self._session_id, frame.index, frame.index * FRAME_SAMPLES,
                            epoch, audio, frame.text, frame.seconds, frame.done, suppressed)

    def _step(self, audio):
        return self._session.step(audio)

    async def step(self, user_audio):
        audio = self._pcm(user_audio, frame=True)
        # Reject producer backlog instead of playing old microphone audio later.
        if self._lock.locked():
            raise RuntimeError('Haru frame backpressure: an operation is already in flight')
        async with self._lock:
            if self._session_id is None or self._faulted:
                raise RuntimeError('An active, healthy Haru conversation is required')
            if self._session.index >= self._session.config.max_frames:
                raise RuntimeError('Haru conversation reached its frame budget')
            epoch = self._epoch
            try:
                frame = await self._run(self._step, audio)
                return self._output(frame, epoch)
            except BaseException:
                self._faulted = True
                raise

    def interrupt_playback(self):
        """Fence old audio immediately, without cancelling listening or Bot work.

        The client must also clear its local queue. Haru has no discrete model
        response cancellation API; generation keeps advancing in duplex mode.
        """
        self._epoch += 1
        self._output_muted = True
        return self._epoch

    def resume_playback(self):
        # A second fence prevents audio generated while muted arriving late.
        self._epoch += 1
        self._output_muted = False
        return self._epoch

    def _release(self):
        had_model = self._model is not None or self._session is not None
        self._session = self._model = None
        if had_model:
            import mlx.core as mx
            mx.clear_cache()

    async def close(self):
        async with self._lock:
            if self._closed:
                return
            self.interrupt_playback()
            await self._run(self._release)
            self._session_id = None
            self._closed = True
            self._executor.shutdown(wait=True)

    async def __aenter__(self):
        try:
            await self.load()
            return self
        except BaseException:
            await self.close()
            raise

    async def __aexit__(self, *_):
        await self.close()
