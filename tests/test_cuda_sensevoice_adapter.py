import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest
from ai2apps.model_worker.protocol import ModelWorkerError

path=Path(__file__).resolve().parents[1]/'spark/cuda_sensevoice_adapter.py'
spec=importlib.util.spec_from_file_location('sensevoice_cuda',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

@pytest.mark.asyncio
@pytest.mark.parametrize('body',[
    {'language':'xx'}, {'stream':True}, {'prompt':'bias this transcription'},
    {'diarization':True}, {'response_format':'srt'}, {'word_timestamps':'maybe'},
])
async def test_unsupported_requests_rejected_before_loading(body):
    adapter=module.CudaSenseVoiceAdapter(None)
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(SimpleNamespace(operation='audio_transcription',payload=body))
    assert error.value.status_code==400

@pytest.mark.asyncio
async def test_unpinned_checkpoint_rejected_before_file_access():
    checkpoint=SimpleNamespace(path=Path('/tmp/not-used'),repo_id='unexpected',revision='wrong')
    adapter=module.CudaSenseVoiceAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    with pytest.raises(ModelWorkerError) as error:
        await adapter.invoke(SimpleNamespace(operation='audio_transcription',payload={'model':'test'}))
    assert error.value.code=='model_not_supported'

@pytest.mark.asyncio
async def test_duplicate_stop_queue_and_restart(monkeypatch):
    import asyncio
    import sys
    checkpoint=SimpleNamespace(path=Path('/tmp/not-used'),repo_id='FunAudioLLM/SenseVoiceSmall',revision='3847d57b6bdf2dd8875cb1508d2af43d80a16bf7')
    adapter=module.CudaSenseVoiceAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda:None)))
    started=asyncio.Event();finished=asyncio.Event();calls=[]
    async def work(_):
        calls.append(1);started.set()
        while not adapter.events['active'].is_set():await asyncio.sleep(0)
        finished.set();adapter.check(adapter.events['active'])
    monkeypatch.setattr(module.asyncio,'to_thread',work)
    def req(key):return SimpleNamespace(request_id=key,operation='audio_transcription',payload={'model':'test'},part=lambda _:SimpleNamespace(path=Path('/tmp/audio')))
    active=asyncio.create_task(adapter.invoke(req('active')));await asyncio.wait_for(started.wait(),2)
    event=adapter.events['active']
    with pytest.raises(ModelWorkerError) as error:await adapter.invoke(req('active'))
    assert error.value.status_code==409 and adapter.events['active'] is event
    queued=asyncio.create_task(adapter.invoke(req('queued')));await asyncio.sleep(0)
    await adapter.stop()
    for task in (active,queued):
        with pytest.raises(ModelWorkerError) as error:await task
        assert error.value.status_code==499
    assert finished.is_set() and len(calls)==1 and not adapter.events
    with pytest.raises(ModelWorkerError) as error:await adapter.invoke(req('new'))
    assert error.value.status_code==503
    await adapter.start()
    async def success(_):return {'text':'recovered'}
    monkeypatch.setattr(module.asyncio,'to_thread',success)
    assert await adapter.invoke(req('new'))=={'text':'recovered'}
    await adapter.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize('kind,message,expected',[
    ('oom','allocation failed',503),
    ('accelerator','CUDA error: out of memory\nCUDA kernel errors might be asynchronous',503),
    ('accelerator','CUDA error: illegal memory access',None),
    ('other','out of memory in unrelated code',None),
])
async def test_oom_is_structured_without_retry_and_later_request_recovers(monkeypatch,kind,message,expected):
    import sys
    class OOM(RuntimeError):pass
    class Accelerator(RuntimeError):pass
    classes={'oom':OOM,'accelerator':Accelerator,'other':RuntimeError}
    error=classes[kind](message);cleared=[];calls=[]
    import weakref,gc
    refs=[]
    class PartialModel:pass
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(OutOfMemoryError=OOM,AcceleratorError=Accelerator,cuda=SimpleNamespace(empty_cache=lambda:cleared.append(True))))
    checkpoint=SimpleNamespace(path=Path('/tmp/not-used'),repo_id='FunAudioLLM/SenseVoiceSmall',revision='3847d57b6bdf2dd8875cb1508d2af43d80a16bf7')
    adapter=module.CudaSenseVoiceAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    adapter.model=object();adapter.path=checkpoint.path;adapter.vad=object();adapter.vad_path=Path('/tmp/vad')
    request=SimpleNamespace(request_id='oom',operation='audio_transcription',payload={'model':'test'},part=lambda _:SimpleNamespace(path=Path('/tmp/audio')))
    async def failure(_):
        partial=PartialModel();refs.append(weakref.ref(partial))
        calls.append(1);raise error
    monkeypatch.setattr(module.asyncio,'to_thread',failure)
    with pytest.raises(ModelWorkerError if expected else classes[kind]) as caught:await adapter.invoke(request)
    assert len(calls)==1 and not adapter.events and not adapter.lock.locked()
    if expected:
        gc.collect();assert refs[0]() is None
        assert caught.value.status_code==503 and caught.value.code=='resource_exhausted'
        assert adapter.model is adapter.path is adapter.vad is adapter.vad_path is None and cleared==[True]
        async def success(_):return {'text':'recovered'}
        monkeypatch.setattr(module.asyncio,'to_thread',success)
        assert await adapter.invoke(request)=={'text':'recovered'}
    else:assert caught.value is error and not cleared and adapter.model is not None

@pytest.mark.asyncio
@pytest.mark.parametrize('transport', [False, True])
async def test_cancelled_native_frames_release_while_exception_retained(monkeypatch, transport):
    import asyncio,gc,weakref
    checkpoint=SimpleNamespace(path=Path('/tmp/not-used'),repo_id='FunAudioLLM/SenseVoiceSmall',revision='3847d57b6bdf2dd8875cb1508d2af43d80a16bf7')
    adapter=module.CudaSenseVoiceAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    request=SimpleNamespace(request_id='cancel',operation='audio_transcription',payload={'model':'test'},part=lambda _:SimpleNamespace(path=Path('/tmp/audio')))
    entered=asyncio.Event();refs=[];errors=[]
    class TensorOwner:pass
    async def native(_):
        payload=TensorOwner();refs.append(weakref.ref(payload));entered.set()
        while not adapter.events['cancel'].is_set():await asyncio.sleep(0)
        error=ModelWorkerError('cancelled',code='request_cancelled',status_code=499)
        errors.append(error)
        raise error
    monkeypatch.setattr(module.asyncio,'to_thread',native)
    task=asyncio.create_task(adapter.invoke(request));await entered.wait()
    if transport:task.cancel()
    else:adapter.cancel('cancel')
    with pytest.raises(asyncio.CancelledError if transport else ModelWorkerError):await task
    gc.collect()
    assert refs[0]() is None
    assert any('Released native worker traceback' in note for note in errors[0].__notes__)
    assert not adapter.events and not adapter.lock.locked()


def test_release_traceback_breaks_function_closure_ownership():
    import weakref,gc
    class Payload:pass
    obj=Payload();ref=weakref.ref(obj)
    def bind(owner):
        def native():
            assert owner is not None
            raise RuntimeError('native failure')
        return native
    native=bind(obj);del obj
    try:native()
    except RuntimeError as error:held=error
    del native
    module.release_exception_frames(held);gc.collect()
    assert ref() is None and held.__traceback__ is None
    assert 'native' in held.__notes__[0]
