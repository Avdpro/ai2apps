from __future__ import annotations

import asyncio
import io
from pathlib import Path
import threading
import time
import wave

import pytest

from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter, CudaQwenTTSEngine
from ai2apps.model_worker.protocol import ModelWorkerCheckpoint, ModelWorkerContext, ModelWorkerRequest


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b'\0\0' * 2400)
    return buffer.getvalue()


class FakeEngine:
    def __init__(self, event):
        self.cancelled = event
        self.stopped = False

    async def start(self):
        pass

    async def stop(self):
        self.cancelled.set()
        self.stopped = True

    async def synthesize(self, text, **kwargs):
        assert not self.cancelled.is_set()
        return wav_bytes()


@pytest.mark.asyncio
async def test_model_switch_does_not_cancel_new_request(tmp_path):
    checkpoints = tuple(ModelWorkerCheckpoint(name,name,'huggingface',name,'a'*40,tmp_path,{}) for name in ('first','second'))
    context = ModelWorkerContext('test',tmp_path,tmp_path,tuple({'id':x.model_id} for x in checkpoints),checkpoints)
    engines = []
    class Adapter(CudaQwenTTSAdapter):
        async def create_engine(self, checkpoint, runtime_options=None):
            engine = FakeEngine(self._current_event)
            engines.append(engine)
            return engine
    adapter = Adapter(context)
    for index, model in enumerate(('first','second','second')):
        response = await adapter.invoke(ModelWorkerRequest('audio_speech',{'model':model,'input':'hello'},str(index)))
        assert response.media_type == 'audio/wav'
    assert len(engines) == 2
    assert engines[0].stopped
    assert not engines[1].cancelled.is_set()
    await adapter.stop()
    assert engines[1].stopped


@pytest.mark.asyncio
async def test_cancel_waits_for_native_thread_before_returning():
    engine = CudaQwenTTSEngine(None)
    started, finished = threading.Event(), threading.Event()
    def native_generation():
        started.set()
        assert engine.cancelled.wait(2)
        time.sleep(.02)
        finished.set()
    task = asyncio.create_task(engine._run(native_generation))
    assert await asyncio.to_thread(started.wait, 2)
    task.cancel()
    await asyncio.sleep(.005)
    task.cancel()  # Repeated transport cancellation must not release the lock.
    with pytest.raises(asyncio.CancelledError):
        await task
    assert engine.cancelled.is_set()
    assert finished.is_set()


def test_cancel_hook_is_removed_and_does_not_poison_next_request():
    import torch
    from ai2apps.model_worker.cuda_audio import _cancel_on_forward
    from ai2apps.model_worker.protocol import ModelWorkerError
    talker = torch.nn.Linear(1, 1)
    event = threading.Event()
    with _cancel_on_forward(talker, event):
        talker(torch.ones(1, 1))
        event.set()
        with pytest.raises(ModelWorkerError) as error:
            talker(torch.ones(1, 1))
        assert error.value.code == 'request_cancelled'
    assert not talker._forward_pre_hooks
    talker(torch.ones(1, 1))


@pytest.mark.asyncio
async def test_default_decoding_is_repeatable_but_explicit_sampling_is_preserved():
    from types import SimpleNamespace
    import numpy as np
    import torch
    calls = []
    def synthesize(**kwargs):
        calls.append(kwargs)
        return [np.ones(240, dtype=np.float32) * .1], 24000
    engine = CudaQwenTTSEngine(None)
    engine.model = SimpleNamespace(
        model=SimpleNamespace(talker=torch.nn.Linear(1,1),tts_model_type='custom_voice',tts_model_size='0b6'),
        generate_custom_voice=synthesize)
    await engine.synthesize('hello')
    await engine.synthesize('hello', temperature=.8)
    assert calls[0]['do_sample'] is False and calls[0]['subtalker_dosample'] is False
    assert calls[1]['temperature'] == .8 and 'do_sample' not in calls[1]
    engine.model.model.tts_model_type = 'base'
    engine.model.generate_voice_clone = synthesize
    await engine.synthesize('hello', ref_audio='reference.wav', ref_text='reference')
    assert calls[2]['temperature'] == .8 and 'do_sample' not in calls[2]
