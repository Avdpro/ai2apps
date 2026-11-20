import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_voxcpm_adapter import CudaVoxCPMAdapter,CudaVoxSpeechEngine,MODELS
from ai2apps.model_worker import ModelWorkerError

def adapter():return CudaVoxCPMAdapter(SimpleNamespace())

@pytest.mark.asyncio
async def test_wrong_fixed_revision_rejected():
    key=next(iter(MODELS));variant,repo,revision=MODELS[key]
    with pytest.raises(ModelWorkerError) as error:
        await adapter().create_engine(SimpleNamespace(model_id=key,repo_id=repo,revision='0'*40,path=Path('/tmp')))
    assert error.value.code=='checkpoint_not_ready'

def test_controls_follow_mac_precedence():
    result=adapter().synthesis_options(next(iter(MODELS)),{'seed':5,'language':'zh'},
        speed=.7,emotion='calm',emotion_strength=1,instructions='Talk quickly.')
    assert result=={'speed':1.0,'language':'zh','seed':5,'instructions':
        'Talk quickly. Mandatory delivery controls override conflicting earlier style: sound calm and composed; speak much more slowly than normal.'}

@pytest.mark.asyncio
async def test_stopped_adapter_rejects_new_work():
    obj=adapter();await obj.stop()
    with pytest.raises(ModelWorkerError) as error:
        await obj.invoke(SimpleNamespace(request_id='next',payload={'model':next(iter(MODELS))}))
    assert error.value.code=='worker_stopping'

@pytest.mark.asyncio
async def test_duplicate_request_does_not_replace_cancellation():
    obj=adapter();sentinel=object();obj._cancellations['same']=sentinel
    with pytest.raises(ModelWorkerError) as error:
        await obj.invoke(SimpleNamespace(request_id='same',payload={'model':next(iter(MODELS))}))
    assert error.value.code=='request_conflict' and obj._cancellations['same'] is sentinel

@pytest.mark.asyncio
async def test_oom_releases_native_engine_and_next_request_reloads():
    import torch
    obj=CudaVoxSpeechEngine(None);closed=[]
    def fail(*args,**kwargs):raise torch.cuda.OutOfMemoryError('injected')
    obj.model=SimpleNamespace(generate=fail,close=lambda:closed.append(True))
    with pytest.raises(ModelWorkerError) as error:await obj.synthesize('hello')
    assert error.value.code=='resource_exhausted' and closed==[True] and obj.model is None
    async def reload():
        def generate(text,path,values,**kwargs):path.write_bytes(b'reloaded')
        obj.model=SimpleNamespace(generate=generate)
    obj.start=reload
    assert await obj.synthesize('hello')==b'reloaded'

@pytest.mark.asyncio
async def test_multipart_integer_fields_are_normalized_before_protocol(monkeypatch):
    from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter
    from ai2apps.model_worker.protocol import ModelWorkerRequest
    async def capture(self,request):return request.payload
    monkeypatch.setattr(CudaQwenTTSAdapter,'invoke',capture)
    payload=await adapter().invoke(ModelWorkerRequest('audio_speech',
        {'model':next(iter(MODELS)),'input':'hello','seed':'42','max_tokens':'256'},'multipart'))
    assert payload['seed']==42 and payload['max_tokens']==256

@pytest.mark.asyncio
@pytest.mark.parametrize('values',[{'seed':True},{'seed':'1e3'},{'max_tokens':'2001'}])
async def test_invalid_numeric_fields_fail_before_model_loading(values):
    from ai2apps.model_worker.protocol import ModelWorkerRequest
    with pytest.raises(ModelWorkerError) as error:
        await adapter().invoke(ModelWorkerRequest('audio_speech',
            {'model':next(iter(MODELS)),'input':'hello',**values},'bad'))
    assert error.value.status_code==400

@pytest.mark.asyncio
@pytest.mark.parametrize('canonical',list(MODELS))
@pytest.mark.parametrize('upstream',[False,True])
async def test_host_upstream_identity_maps_to_fixed_canonical(monkeypatch,canonical,upstream):
    from ai2apps.model_worker.protocol import ModelWorkerRequest
    from ai2apps.model_worker.cuda_audio import CudaQwenTTSAdapter
    async def capture(self,request):return request.payload
    monkeypatch.setattr(CudaQwenTTSAdapter,'invoke',capture)
    identity=MODELS[canonical][1] if upstream else canonical
    payload={'model':identity,'input':'Hello.','seed':'42','max_tokens':'256'}
    result=await adapter().invoke(ModelWorkerRequest('audio_speech',payload,'host-id'))
    assert result['model']==canonical and result['seed']==42
    assert payload['model']==identity

@pytest.mark.asyncio
async def test_unlisted_upstream_rejected():
    from ai2apps.model_worker.protocol import ModelWorkerRequest
    with pytest.raises(ModelWorkerError) as error:
        await adapter().invoke(ModelWorkerRequest('audio_speech',{'model':'openbmb/VoxCPM2-unpinned','input':'Hello.'},'unknown'))
    assert error.value.status_code==404


@pytest.mark.asyncio
async def test_original_dispatch_does_not_use_mac_loader(monkeypatch):
    import cuda_voxcpm_original_engine
    import cuda_voxcpm_engine
    key='ai2apps.model.voxcpm2-cuda/bf16';calls=[]
    class Original:
        def __init__(self,path,check):check();calls.append(path)
        def close(self):pass
    def forbidden(*args,**kwargs):raise AssertionError('Original checkpoint reached Mac loader')
    monkeypatch.setattr(cuda_voxcpm_original_engine,'CudaVoxCPMOriginalEngine',Original)
    monkeypatch.setattr(cuda_voxcpm_engine,'CudaVoxCPMEngine',forbidden)
    checkpoint=SimpleNamespace(model_id=key,repo_id=MODELS[key][1],revision=MODELS[key][2],path=Path('/tmp/original'))
    engine=await adapter().create_engine(checkpoint)
    await engine.start();assert calls==[checkpoint.path]
    await engine.stop();assert engine.model is None
