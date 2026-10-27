import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import threading
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_yue2_adapter import CudaYuE2Adapter,CHECKPOINTS,MODEL
from ai2apps.model_worker import ModelWorkerRequest,ModelWorkerError


def context(root,wrong=False):
    entries={k:SimpleNamespace(path=root,repo_id=r,revision=('wrong' if wrong else v)) for k,r,v in CHECKPOINTS}
    return SimpleNamespace(checkpoint_for=entries.get)


def request(root):
    return ModelWorkerRequest('audio_generate',dict(model=MODEL,schema='ai2apps.audio-generation/v2',
        task='music',prompt='Piano',duration_mode='auto',generation={'max_semantic_tokens':3000}),
        'song',output_root=root)


def test_wrong_fixed_revision_rejected_before_native(tmp_path):
    async def run():
        with pytest.raises(ModelWorkerError) as error:await CudaYuE2Adapter(context(tmp_path,True)).invoke(request(tmp_path))
        assert error.value.code=='checkpoint_not_ready'
    asyncio.run(run())


def test_repeated_cancel_drains_late_writer(tmp_path):
    a=CudaYuE2Adapter(context(tmp_path));entered=threading.Event();release=threading.Event();paths=[]
    def render(work,event):
        paths.append(work.output);work.output.write_bytes(b'partial');entered.set()
        assert release.wait(3)
        work.output.write_bytes(b'late')
    a._owner.render=render
    async def run():
        job=asyncio.create_task(a.invoke(request(tmp_path)))
        try:
            assert await asyncio.to_thread(entered.wait,2)
            job.cancel();await asyncio.sleep(.01);job.cancel();await asyncio.sleep(.01)
            assert not job.done() and paths[0].exists()
        finally:release.set()
        with pytest.raises(asyncio.CancelledError):await job
        assert not paths[0].exists()
        await a.stop()
    asyncio.run(run())


def test_resource_failure_cleans_output_and_next_request_runs(tmp_path):
    a=CudaYuE2Adapter(context(tmp_path));paths=[]
    def render(work,event):
        paths.append(work.output)
        work.output.write_bytes(b'partial')
        if len(paths)==1:raise MemoryError('out of memory')
        return 'recovered'
    a._owner.render=render
    async def run():
        with pytest.raises(ModelWorkerError) as error:await a.invoke(request(tmp_path))
        assert error.value.code=='resource_exhausted' and error.value.status_code==503
        assert not paths[0].exists()
        assert await a.invoke(request(tmp_path))=='recovered'
        assert paths[1]!=paths[0]
        await a.stop()
    asyncio.run(run())
