import asyncio
from pathlib import Path
import sys,threading
from types import SimpleNamespace
import pytest
ROOT=Path(__file__).parents[1]
sys.path.insert(0,str(ROOT/'spark'));sys.path.insert(0,str(ROOT/'packages/omlx-model-detailed-transcription/src'))
from cuda_detailed_adapter import CudaDetailedAdapter,PREFIX,PINS
from cuda_detailed_process import DetailedCancelled
from ai2apps.model_worker.protocol import ModelWorkerError


class Context:
    def checkpoint_for(self,key):
        variant=key.removeprefix(PREFIX);repo,revision=PINS[variant]
        return SimpleNamespace(path=Path('/tmp/checkpoint'),repo_id=repo,revision=revision)


def request(key):
    return SimpleNamespace(request_id=key,operation='audio_detailed_transcription',payload={'model':PREFIX+'compact'},part=lambda _:SimpleNamespace(path=Path('/tmp/input.wav')))


class Engine:
    def __init__(self):self.started=threading.Event();self.exited=threading.Event();self.calls=0;self.block=True
    def transcribe_wav(self,path,event,**options):
        self.calls+=1;self.started.set()
        if self.block:
            assert event.wait(5),'test cancellation deadline'
            self.exited.set();raise DetailedCancelled('cancelled')
        return {'features':{'transcription':{},'alignment':{},'diarization':{}}}


async def started(engine):
    assert await asyncio.to_thread(engine.started.wait,2)


@pytest.mark.asyncio
async def test_duplicate_stop_queued_reject_and_restart():
    e=Engine();adapter=CudaDetailedAdapter(Context(),None,engine_factory=lambda *_:e)
    active=asyncio.create_task(adapter.invoke(request('a')));await started(e)
    original=adapter._events['a']
    with pytest.raises(ModelWorkerError) as caught:await adapter.invoke(request('a'))
    assert caught.value.status_code==409 and adapter._events['a'] is original
    queued=asyncio.create_task(adapter.invoke(request('b')));await asyncio.sleep(0)
    await adapter.stop()
    for task in (active,queued):
        with pytest.raises(ModelWorkerError) as caught:await task
        assert caught.value.status_code==499
    assert e.exited.is_set() and e.calls==1 and not adapter._events
    with pytest.raises(ModelWorkerError) as caught:await adapter.invoke(request('c'))
    assert caught.value.status_code==503
    await adapter.start();e.block=False
    result=await adapter.invoke(request('d'))
    assert result['features']['transcription']['revision']==PINS['compact'][1]


@pytest.mark.asyncio
async def test_transport_cancellation_waits_for_engine_cleanup():
    e=Engine();adapter=CudaDetailedAdapter(Context(),None,engine_factory=lambda *_:e)
    task=asyncio.create_task(adapter.invoke(request('a')));await started(e);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert e.exited.is_set() and not adapter._events and not adapter._owner.locked()


@pytest.mark.asyncio
async def test_explicit_cancel_does_not_change_other_event():
    e=Engine();adapter=CudaDetailedAdapter(Context(),None,engine_factory=lambda *_:e)
    task=asyncio.create_task(adapter.invoke(request('a')));await started(e)
    adapter.cancel('missing');assert not adapter._events['a'].is_set()
    adapter.cancel('a')
    with pytest.raises(ModelWorkerError) as caught:await task
    assert caught.value.status_code==499 and not adapter._events


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value',[('prompt',{}),('language',[]),('timestamps','raw'),('response_format','text')])
async def test_invalid_options_rejected_before_engine_creation(field,value):
    def forbidden(*_):raise AssertionError('Invalid request reached engine creation')
    adapter=CudaDetailedAdapter(Context(),None,engine_factory=forbidden)
    req=request('bad');req.payload[field]=value
    with pytest.raises(ModelWorkerError) as caught:await adapter.invoke(req)
    assert caught.value.status_code==400 and not adapter._events


@pytest.mark.asyncio
@pytest.mark.parametrize('profile',['compact','quality'])
async def test_host_upstream_alias_selects_pinned_profile(profile):
    e=Engine();e.block=False;seen={}
    def factory(stages,checkpoints):
        seen['checkpoints']=checkpoints
        return e
    adapter=CudaDetailedAdapter(Context(),None,engine_factory=factory)
    req=request('host-alias');req.payload['model']=PINS[profile][0]
    result=await adapter.invoke(req)
    assert result['features']['transcription']['revision']==PINS[profile][1]
    assert e.calls==1 and not adapter._events


@pytest.mark.asyncio
@pytest.mark.parametrize('model',[PINS['forced-aligner'][0],PINS['diarizer'][0],'Qwen/arbitrary'])
async def test_helper_or_unpinned_alias_cannot_invoke(model):
    adapter=CudaDetailedAdapter(Context(),None,engine_factory=lambda *_:pytest.fail('must reject before engine'))
    req=request('bad-alias');req.payload['model']=model
    with pytest.raises(ModelWorkerError) as caught:await adapter.invoke(req)
    assert caught.value.status_code==404


def test_installed_diarizer_snapshot_resolves_official_archive(tmp_path):
    class Installed(Context):
        def checkpoint_for(self,key):
            row=super().checkpoint_for(key)
            if key==PREFIX+'diarizer':row.path=tmp_path
            return row
    adapter=CudaDetailedAdapter(Installed(),None)
    with pytest.raises(ModelWorkerError) as caught:adapter._checkpoint('diarizer')
    assert caught.value.status_code==503
    archive=tmp_path/'diar_streaming_sortformer_4spk-v2.1.nemo'
    archive.write_bytes(b'fixture')
    assert adapter._checkpoint('diarizer')==archive
