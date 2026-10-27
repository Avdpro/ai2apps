"""Real thread barriers verify CUDA request ownership without requiring a GPU."""
import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_sol_lifecycle import SoLRequestOwner, check_cancel
from ai2apps.model_worker import ModelWorkerError


def request(name):
    return SimpleNamespace(request_id=name)


def test_repeated_cancellation_does_not_release_next_request():
    entered, release = threading.Event(), threading.Event()
    calls = []
    def render(req, event):
        calls.append(req.request_id)
        entered.set()
        assert release.wait(3)
        check_cancel(event)
        return req.request_id
    owner = SoLRequestOwner(render, lambda: None)
    async def run():
        first = asyncio.create_task(owner.invoke(request('first')))
        assert await asyncio.to_thread(entered.wait, 2)
        first.cancel()
        await asyncio.sleep(.01)
        first.cancel()
        second = asyncio.create_task(owner.invoke(request('second')))
        await asyncio.sleep(.02)
        assert not first.done() and calls == ['first']
        release.set()
        with pytest.raises(asyncio.CancelledError): await first
        assert await second == 'second'
        assert not owner._pending
    asyncio.run(run())


def test_queued_cancel_never_enters_engine_and_duplicate_id_rejected():
    entered, release = threading.Event(), threading.Event()
    calls = []
    def render(req, event):
        calls.append(req.request_id)
        entered.set()
        assert release.wait(3)
    owner = SoLRequestOwner(render, lambda: None)
    async def run():
        first = asyncio.create_task(owner.invoke(request('first')))
        assert await asyncio.to_thread(entered.wait, 2)
        with pytest.raises(ModelWorkerError) as duplicate:
            await owner.invoke(request('first'))
        assert duplicate.value.status_code == 409
        second = asyncio.create_task(owner.invoke(request('second')))
        await asyncio.sleep(.01)
        owner.cancel('second')
        release.set()
        await first
        with pytest.raises(ModelWorkerError) as cancelled: await second
        assert cancelled.value.status_code == 499
        assert calls == ['first'] and not owner._pending
    asyncio.run(run())


def test_stop_waiter_cancel_does_not_release_running_engine_early():
    entered, release = threading.Event(), threading.Event()
    order = []
    def render(req, event):
        entered.set()
        assert release.wait(3)
        order.append('native-exit')
        check_cancel(event)
    owner = SoLRequestOwner(render, lambda: order.append('model-release'))
    async def run():
        active = asyncio.create_task(owner.invoke(request('active')))
        assert await asyncio.to_thread(entered.wait, 2)
        stopping = asyncio.create_task(owner.stop())
        await asyncio.sleep(.01)
        stopping.cancel()
        with pytest.raises(asyncio.CancelledError): await stopping
        with pytest.raises(ModelWorkerError) as rejected: await owner.invoke(request('late'))
        assert rejected.value.status_code == 503 and not order
        release.set()
        with pytest.raises(ModelWorkerError) as cancelled: await active
        assert cancelled.value.status_code == 499
        await owner.stop()
        await owner.stop()
        assert order == ['native-exit', 'model-release']
    asyncio.run(run())


def test_cancellation_after_last_native_check_cannot_return_success():
    entered, release = threading.Event(), threading.Event()
    def render(req, event):
        check_cancel(event)
        entered.set()
        assert release.wait(3)
        return 'late result'
    owner = SoLRequestOwner(render, lambda: None)
    async def run():
        active = asyncio.create_task(owner.invoke(request('active')))
        assert await asyncio.to_thread(entered.wait, 2)
        owner.cancel('active')
        release.set()
        with pytest.raises(ModelWorkerError) as cancelled: await active
        assert cancelled.value.status_code == 499
    asyncio.run(run())
