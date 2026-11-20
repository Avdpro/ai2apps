"""Lifecycle/control tests with a deterministic frame model; no GPU claims."""
import asyncio
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from ai2apps.model_worker.haru_duplex import HaruDuplexBackend, FRAME_SAMPLES


class FixtureBackend(HaruDuplexBackend):
    def __init__(self, path):
        super().__init__(path)
        self.threads = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.block_step = False

    def record(self):
        self.threads.append(threading.get_ident())

    def _load(self):
        self.record()
        self._model = 'fixture'

    def frame(self, index):
        return SimpleNamespace(index=index, audio=np.ones(FRAME_SAMPLES, dtype=np.float32) * .1,
                               text='测试', seconds=.01, done=False)

    def _start(self, prompt, reference, seed, max_frames, speak_first):
        self.record()
        self._session = SimpleNamespace(index=1, config=SimpleNamespace(max_frames=max_frames))
        return self.frame(0)

    def _step(self, audio):
        self.record()
        if self.block_step:
            self.entered.set()
            assert self.release.wait(5)
        index = self._session.index
        self._session.index += 1
        return self.frame(index)

    def _release(self):
        self.record()
        self._session = self._model = None


@pytest.fixture
def backend(tmp_path):
    for name in ('config.json', 'tokenizer.json', 'model.safetensors'):
        (tmp_path / name).touch()
    return FixtureBackend(tmp_path)


VOICE = np.zeros(3 * 24000, dtype=np.float32)
SILENCE = np.zeros(FRAME_SAMPLES, dtype=np.float32)


@pytest.mark.asyncio
async def test_single_thread_continuous_frames_and_playback_independence(backend):
    async with backend:
        first = await backend.start(system_prompt='测试角色', reference_audio=VOICE)
        assert first.index == 0 and not first.suppressed
        epoch = backend.interrupt_playback()
        muted = await backend.step(SILENCE)
        assert muted.index == 1 and muted.playback_epoch == epoch and muted.suppressed
        assert not np.any(muted.audio)
        epoch = backend.resume_playback()
        resumed = await backend.step(SILENCE)
        assert resumed.index == 2 and resumed.playback_epoch == epoch and not resumed.suppressed
        assert np.any(resumed.audio)
    assert len(set(backend.threads)) == 1
    assert backend.threads[0] != threading.get_ident()
    await backend.close()
    with pytest.raises(RuntimeError, match='closed'):
        await backend.load()


async def wait_entered(backend):
    for _ in range(100):
        if backend.entered.is_set():
            return
        await asyncio.sleep(.005)
    raise AssertionError('Fixture frame did not start')


@pytest.mark.asyncio
async def test_inflight_frame_fenced_across_interrupt_and_resume(backend):
    async with backend:
        await backend.start(system_prompt='测试', reference_audio=VOICE)
        backend.block_step = True
        task = asyncio.create_task(backend.step(SILENCE))
        await wait_entered(backend)
        with pytest.raises(RuntimeError, match='backpressure'):
            await backend.step(SILENCE)
        backend.interrupt_playback()
        backend.resume_playback()
        backend.release.set()
        stale = await task
        assert stale.playback_epoch == 0 and stale.suppressed
        assert not np.any(stale.audio)


@pytest.mark.asyncio
async def test_cancelled_frame_requires_new_backend_and_close_drains_worker(backend):
    await backend.load()
    await backend.start(system_prompt='测试', reference_audio=VOICE)
    backend.block_step = True
    task = asyncio.create_task(backend.step(SILENCE))
    await wait_entered(backend)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(RuntimeError, match='healthy'):
        await backend.step(SILENCE)
    backend.release.set()
    await backend.close()
    assert backend._session is None and backend._model is None


@pytest.mark.asyncio
async def test_invalid_input_and_session_budget(backend):
    async with backend:
        with pytest.raises(ValueError, match='3 to 180'):
            await backend.start(system_prompt='测试', reference_audio=np.zeros(100, dtype=np.float32))
        await backend.start(system_prompt='测试', reference_audio=VOICE, max_frames=1)
        for bad in (np.zeros((3200, 1)), np.zeros(10), np.full(3200, np.nan), np.ones(3200, dtype=np.int16)):
            with pytest.raises(ValueError):
                await backend.step(bad)
        with pytest.raises(RuntimeError, match='budget'):
            await backend.step(SILENCE)
        with pytest.raises(RuntimeError, match='current conversation'):
            await backend.start(system_prompt='测试', reference_audio=VOICE)
    assert not backend.capabilities['tool_calls']
    assert not backend.capabilities['async_result_injection']


def test_missing_checkpoint_never_downloads(tmp_path):
    with pytest.raises(ValueError, match='missing'):
        HaruDuplexBackend(tmp_path)
