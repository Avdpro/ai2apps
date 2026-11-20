import asyncio
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_ace_adapter import CudaAceAdapter, MODEL, REVISION
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerError


def payload(**kwargs):
    return dict(model=MODEL,task='music',prompt='Piano',duration=10,**kwargs)


@pytest.mark.parametrize('change',[{'duration':9},{'duration':121},{'task':'sound_effects'},
    {'schema':'ai2apps.audio-generation/v2','duration_mode':'auto','duration':None},
    {'steps':True},{'stream':True},{'reference_audio':'file'}])
def test_rejects_unsupported_requests(change):
    p=payload();p.update(change)
    if change.get('duration_mode')=='auto':p.pop('duration')
    with pytest.raises(ModelWorkerError):CudaAceAdapter.parameters(p)


def test_full_mac_step_and_duration_bounds():
    for steps in (1,8,100):
        for duration in (10,120):
            p=payload(steps=steps);p['duration']=duration
            assert CudaAceAdapter.parameters(p)['steps']==steps


def test_native_writer_drains_before_cancelled_output_cleanup(tmp_path):
    context=SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=tmp_path,repo_id='ACE-Step/Ace-Step1.5',revision=REVISION))
    adapter=CudaAceAdapter(context)
    entered,release=threading.Event(),threading.Event()
    targets=[]
    def render(work,event):
        targets.append(work.output);work.output.write_bytes(b'partial');entered.set()
        assert release.wait(3)
        work.output.write_bytes(b'late write')
    adapter._owner.render=render
    async def run():
        req=ModelWorkerRequest('audio_generate',payload(),'cancel',output_root=tmp_path)
        job=asyncio.create_task(adapter.invoke(req))
        assert await asyncio.to_thread(entered.wait,2)
        job.cancel();await asyncio.sleep(.01);job.cancel();await asyncio.sleep(.01)
        assert targets[0].exists() and not job.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await job
        assert not targets[0].exists()
    asyncio.run(run())


def test_host_upstream_alias_is_canonicalized():
    from cuda_ace_adapter import UPSTREAM
    original=payload();original['model']=UPSTREAM
    assert CudaAceAdapter.parameters(original)['model']==MODEL
    assert original['model']==UPSTREAM
    for name in ('ace-step-1.5','other',MODEL+'/other'):
        original['model']=name
        with pytest.raises(ModelWorkerError) as error:CudaAceAdapter.parameters(original)
        assert error.value.code=='model_not_found' and error.value.status_code==404


def test_workspace_configuration_lifecycle(monkeypatch):
    import os
    monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG',raising=False)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda:False)))
    a=CudaAceAdapter(SimpleNamespace())
    async def run():
        await a.start();await a.start()
        assert os.environ['CUBLAS_WORKSPACE_CONFIG']==':4096:8'
        await a.stop();assert 'CUBLAS_WORKSPACE_CONFIG' not in os.environ
    asyncio.run(run())


def test_workspace_rejects_late_or_conflicting_configuration(monkeypatch):
    monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG',raising=False)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda:True)))
    async def run():
        with pytest.raises(ModelWorkerError):await CudaAceAdapter(SimpleNamespace()).start()
        monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG',':16:8')
        with pytest.raises(ModelWorkerError):await CudaAceAdapter(SimpleNamespace()).start()
    asyncio.run(run())


@pytest.mark.parametrize('previous', [None, ':4096:8'])
def test_cancelled_stop_waiter_preserves_native_cleanup_and_restoration(monkeypatch, previous):
    import os
    if previous is None:
        monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG', raising=False)
    else:
        monkeypatch.setenv('CUBLAS_WORKSPACE_CONFIG', previous)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False)))
    adapter = CudaAceAdapter(SimpleNamespace())
    entered, release = threading.Event(), threading.Event()
    calls = []
    def cleanup():
        calls.append('release')
        entered.set()
        assert release.wait(3)
        assert os.environ['CUBLAS_WORKSPACE_CONFIG'] == ':4096:8'
    adapter._owner.release = cleanup
    async def run():
        await adapter.start()
        first = asyncio.create_task(adapter.stop())
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert adapter._workspace_configured
            assert not adapter._stop_task.done()
        finally:
            release.set()
        await adapter.stop()
        await adapter.stop()
        assert calls == ['release']
        assert os.environ.get('CUBLAS_WORKSPACE_CONFIG') == previous
        assert not adapter._workspace_configured
    asyncio.run(run())


def test_stop_cleanup_error_still_restores_workspace(monkeypatch):
    import os
    monkeypatch.delenv('CUBLAS_WORKSPACE_CONFIG', raising=False)
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: False)))
    adapter = CudaAceAdapter(SimpleNamespace())
    def cleanup():
        raise RuntimeError('native cleanup failed')
    adapter._owner.release = cleanup
    async def run():
        await adapter.start()
        with pytest.raises(RuntimeError, match='native cleanup failed'):
            await adapter.stop()
        assert 'CUBLAS_WORKSPACE_CONFIG' not in os.environ
        assert not adapter._workspace_configured
    asyncio.run(run())
