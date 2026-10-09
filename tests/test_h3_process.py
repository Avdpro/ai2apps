"""Queue ownership, cancellation and artifact confinement for H3 children."""
import asyncio

import httpx
import pytest

from ai2apps.model_worker.h3_process import H3Process
from ai2apps.model_worker.protocol import ModelWorkerError


def test_output_cannot_escape_private_directory(tmp_path):
    worker=H3Process(tmp_path,tmp_path,tmp_path)
    (worker.root/'output').mkdir()
    outside=tmp_path/'outside.mp4'
    outside.write_bytes(b'not a real video')
    (worker.root/'output'/'link.mp4').symlink_to(outside)
    with pytest.raises(ModelWorkerError,match='Invalid H3 output'):
        worker.output_path('link.mp4')
    with pytest.raises(ModelWorkerError,match='Invalid H3 output'):
        worker.output_path(str(outside))


def test_cancel_waits_for_idle_before_releasing_serialization(tmp_path):
    async def scenario():
        worker=H3Process(tmp_path,tmp_path,tmp_path)
        interrupted=asyncio.Event()
        allow_idle=asyncio.Event()
        submitted=asyncio.Event()
        cancelled=asyncio.Event()
        calls=[]

        async def handle(request):
            calls.append(request.url.path)
            if request.url.path=='/prompt':
                submitted.set()
                return httpx.Response(200,json={'prompt_id':'p1'})
            if request.url.path=='/interrupt':
                interrupted.set()
                return httpx.Response(200,content=b'')
            if request.url.path=='/queue':
                return httpx.Response(200,json={'queue_running':[] if allow_idle.is_set() else [[0,'p1']], 'queue_pending':[]})
            return httpx.Response(200,json={})

        worker.client=httpx.AsyncClient(transport=httpx.MockTransport(handle),base_url='http://private')
        async def start():pass
        worker.start=start
        worker.check_alive=lambda:None
        task=asyncio.create_task(worker.run({},cancelled))
        await asyncio.wait_for(submitted.wait(),1)
        cancelled.set()
        await asyncio.wait_for(interrupted.wait(),1)
        assert worker.lock.locked()
        assert not task.done()
        allow_idle.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task,1)
        assert not worker.lock.locked()
        assert calls.count('/interrupt')==1
        await worker.client.aclose()
    asyncio.run(scenario())


def test_unknown_submission_outcome_resets_child(tmp_path):
    async def scenario():
        worker=H3Process(tmp_path,tmp_path,tmp_path)
        stopped=[]
        async def handle(request):
            raise httpx.ReadTimeout('Submission response lost',request=request)
        worker.client=httpx.AsyncClient(transport=httpx.MockTransport(handle),base_url='http://private')
        async def start():pass
        async def stop():stopped.append(True)
        worker.start=start
        worker.stop=stop
        with pytest.raises(httpx.ReadTimeout):
            await worker.run({},asyncio.Event())
        assert stopped==[True]
        assert not worker.lock.locked()
        await worker.client.aclose()
    asyncio.run(scenario())


def test_failed_interrupt_also_reaps_child(tmp_path):
    async def scenario():
        worker=H3Process(tmp_path,tmp_path,tmp_path)
        stopped=[]
        worker.check_alive=lambda:None
        async def stop():stopped.append(True)
        worker.stop=stop
        async def handle(request):
            raise httpx.ReadTimeout('Interrupt response lost',request=request)
        worker.client=httpx.AsyncClient(transport=httpx.MockTransport(handle),base_url='http://private')
        with pytest.raises(httpx.ReadTimeout):await worker.interrupt_and_wait('p1')
        assert stopped==[True]
        await worker.client.aclose()
    asyncio.run(scenario())
