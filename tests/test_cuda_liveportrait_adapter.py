"""Cancellation must retain the native operation lock and request roots."""
import asyncio
import importlib.util
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/omlx-model-liveportrait/src'))
sys.path.insert(0,str(ROOT/'spark'))
from cuda_liveportrait_adapter import CudaLivePortraitAdapter, MODEL
from mlx_liveportrait.worker_adapter import MLXLivePortraitAdapter
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerError


def request(identity='one', **payload):
    return ModelWorkerRequest('video_generation', {'model':MODEL,**payload},identity)


@pytest.mark.parametrize('payload', [{'precision':'fp16'}, {'parameters':'not-json'}, {'parameters':'[]'}, {'model':'wrong'}])
def test_rejects_invalid_before_loading(payload):
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request(**payload))
        assert error.value.status_code in (400,404)
        assert not adapter._pending
    asyncio.run(run())


def test_transport_cancellation_drains_native_thread(monkeypatch):
    started=threading.Event();release=threading.Event();calls=[]
    def native(identity):
        calls.append(identity);started.set();release.wait(timeout=5)
        return identity
    async def invoke(self, req):return await asyncio.to_thread(native, req.request_id)
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        first=asyncio.create_task(adapter.invoke(request()))
        await asyncio.to_thread(started.wait,2)
        first.cancel();await asyncio.sleep(.02)
        first.cancel();await asyncio.sleep(.02)
        second=asyncio.create_task(adapter.invoke(request('two')))
        await asyncio.sleep(.02)
        assert calls==['one'] and not first.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):await first
        assert await second=='two'
        assert not adapter._pending
    asyncio.run(run())


def test_queued_cancel_never_enters_native(monkeypatch):
    entered=asyncio.Event();release=asyncio.Event();calls=[]
    async def invoke(self, req):
        calls.append(req.request_id);entered.set();await release.wait();return 'ok'
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        first=asyncio.create_task(adapter.invoke(request()))
        await entered.wait()
        second=asyncio.create_task(adapter.invoke(request('two')))
        await asyncio.sleep(0);adapter.cancel('two');release.set()
        assert await first=='ok'
        with pytest.raises(ModelWorkerError) as error:await second
        assert error.value.status_code==499 and calls==['one']
    asyncio.run(run())


def test_upstream_id_maps_to_host_checkpoint_identity(monkeypatch):
    async def invoke(self, req):return req.payload['model']
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    assert asyncio.run(adapter.invoke(request(model='KlingTeam/LivePortrait')))==MODEL


def test_duplicate_does_not_replace_cancellation_event(monkeypatch):
    entered=asyncio.Event();release=asyncio.Event()
    async def invoke(self, req):entered.set();await release.wait();return 'ok'
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        first=asyncio.create_task(adapter.invoke(request()))
        await entered.wait();original=adapter._pending['one']
        with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request())
        assert error.value.status_code==409 and adapter._pending['one'] is original
        adapter.cancel('one');assert original.is_set();release.set()
        with pytest.raises(ModelWorkerError) as error:await first
        assert error.value.status_code==499 and not adapter._pending
    asyncio.run(run())


def test_stop_rejects_then_start_restores_admission(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    async def invoke(self, req):return 'ok'
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        await adapter.stop()
        with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request())
        assert error.value.status_code==503
        await adapter.start();assert await adapter.invoke(request())=='ok'
    asyncio.run(run())


def test_start_waits_for_stopping_native_owner(monkeypatch):
    import torch
    monkeypatch.setattr(torch.cuda,'is_available',lambda:False)
    entered=asyncio.Event();release=asyncio.Event()
    async def invoke(self, req):entered.set();await release.wait();return 'ok'
    monkeypatch.setattr(MLXLivePortraitAdapter,'invoke',invoke)
    adapter=CudaLivePortraitAdapter(SimpleNamespace())
    async def run():
        first=asyncio.create_task(adapter.invoke(request()))
        await entered.wait()
        stopping=asyncio.create_task(adapter.stop());await asyncio.sleep(0)
        starting=asyncio.create_task(adapter.start());await asyncio.sleep(0)
        assert adapter._closing and not stopping.done() and not starting.done()
        with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request('new'))
        assert error.value.status_code==503
        release.set()
        with pytest.raises(ModelWorkerError) as error:await first
        assert error.value.status_code==499
        await stopping;await starting
        assert not adapter._closing and not adapter._pending
        assert await adapter.invoke(request('after'))=='ok'
    asyncio.run(run())


@pytest.mark.parametrize('nested',[False,True])
@pytest.mark.parametrize('mode',['pre_cropped','auto'])
def test_explicit_driving_framing_and_metadata(mode,nested):
    controls={'driving_crop_mode':mode}
    payload={'parameters':controls} if nested else controls
    params=CudaLivePortraitAdapter._parameters(payload,'video_generation')
    assert params['driving_crop_mode']==mode and controls=={'driving_crop_mode':mode}
    assert CudaLivePortraitAdapter._metadata(params,audio_applied='none')['applied_controls']['driving_crop_mode']=={'requested':mode,'applied':mode}


def test_official_default_and_mac_default_are_independent():
    assert CudaLivePortraitAdapter._parameters({},'video_generation')['driving_crop_mode']=='pre_cropped'
    assert 'driving_crop_mode' not in MLXLivePortraitAdapter._parameters({},'video_generation')


@pytest.mark.parametrize('value',[None,True,'guess',{},[]])
def test_invalid_driving_mode_is_rejected(value):
    from mlx_liveportrait.worker_adapter import UnsupportedControlError
    with pytest.raises(UnsupportedControlError):CudaLivePortraitAdapter._parameters({'driving_crop_mode':value},'video_generation')


def test_image_does_not_accept_video_framing_control():
    from mlx_liveportrait.worker_adapter import UnsupportedControlError
    with pytest.raises(UnsupportedControlError):CudaLivePortraitAdapter._parameters({'driving_crop_mode':'auto'},'image_edit')


def test_pre_cropped_preserves_frame_without_redetection(monkeypatch):
    adapter=CudaLivePortraitAdapter(SimpleNamespace());frame=object()
    assert adapter._driving_crop(None,None,frame,{'driving_crop_mode':'pre_cropped'}) is frame
    marker=object()
    monkeypatch.setattr(MLXLivePortraitAdapter,'_driving_crop',lambda self,*args:marker)
    assert adapter._driving_crop(None,None,frame,{'driving_crop_mode':'auto'}) is marker

@pytest.mark.parametrize('schema,mode,landmark,valid', [
 ('v1',None,False,True), ('v2','yunet203',True,True),
 ('v2','yunet203',False,False), ('v2','unknown',True,False),
 ('v3','yunet203',True,False)])
def test_versioned_source_crop_checkpoint(tmp_path,schema,mode,landmark,valid):
    import json
    from cuda_liveportrait_adapter import WEIGHTS
    for name in ['models.yaml','face_detection_yunet_2023mar.onnx',*(x+'.safetensors' for x in WEIGHTS)]:
        (tmp_path/name).touch()
    if landmark:(tmp_path/'landmark.onnx').touch()
    (tmp_path/'ai2apps-checkpoint.json').write_text(json.dumps({
        'schema':'ai2apps.cuda-liveportrait-checkpoint/'+schema,'source_crop':mode}))
    adapter=CudaLivePortraitAdapter(SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=tmp_path)))
    if valid:
        assert adapter._ensure_checkpoint(MODEL)==tmp_path
        assert adapter._source_crop==('yunet203' if schema=='v2' else 'arcface5')
    else:
        with pytest.raises(ValueError):adapter._ensure_checkpoint(MODEL)
        assert adapter._root is None

@pytest.mark.parametrize('mode,expected',[('arcface5','legacy'),('yunet203','official')])
def test_compositor_routes_by_checkpoint_contract(monkeypatch,mode,expected):
    monkeypatch.setattr(MLXLivePortraitAdapter,'_paste_face',staticmethod(lambda *a,**k:'legacy'))
    monkeypatch.setitem(sys.modules,'liveportrait_landmark203',SimpleNamespace(paste_portrait=lambda *a:'official'))
    adapter=CudaLivePortraitAdapter(SimpleNamespace());adapter._source_crop=mode
    assert adapter._paste_face(None,None,None,erosion_fraction=.035)==expected


def test_durable_task_payload_translates_named_parts():
    from cuda_liveportrait_adapter import task_payload
    req=SimpleNamespace(operation='video_generation',part=lambda name: name)
    payload={'model':MODEL,'reference_parts':[{'kind':'image','part_name':'reference_00_image'},{'kind':'video','part_name':'reference_01_video'}], 'reference_00_image':'source.jpg','reference_01_video':'driver.mp4','resolution':'source','ratio':'source','preset':'fast','fast':'true','fast_max':'false'}
    result=task_payload(req,payload)
    assert result['precision']=='bf16'
    assert result['inputs']['reference_video']=={'part_name':'reference_01_video'}
    assert CudaLivePortraitAdapter._parameters(result,'video_generation')['precision']=='bf16'
    assert 'reference_parts' in payload
    for bad in ({'preset':'fast_max'},{'fast':'false'},{'resolution':'512x512'},{'precision':'fp32'},{'inputs':{'reference_image':{}}},{'reference_parts':[{'kind':'image','part_name':'a'},{'kind':'image','part_name':'b'}]}):
        with pytest.raises(ValueError):task_payload(req,{**payload,**bad})
    with pytest.raises(Exception,match='unsupported controls'):
        CudaLivePortraitAdapter._parameters(task_payload(req,{**payload,'unknown':True}),'video_generation')


def test_task_frame_rate_matches_actual_video(tmp_path):
    import av
    import numpy as np
    from cuda_liveportrait_adapter import task_payload
    video=tmp_path/'driver.mp4'
    with av.open(str(video),'w') as container:
        stream=container.add_stream('libx264',rate=25)
        stream.width=stream.height=16
        stream.pix_fmt='yuv420p'
        for _ in range(2):
            frame=av.VideoFrame.from_ndarray(np.zeros((16,16,3),dtype=np.uint8),format='rgb24')
            for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode():container.mux(packet)
    req=SimpleNamespace(operation='video_generation',part=lambda name:SimpleNamespace(path=video))
    payload={'model':MODEL,'reference_parts':[{'kind':'image','part_name':'reference_00_image'},{'kind':'video','part_name':'reference_01_video'}],'framespersecond':25,'fps':25}
    assert task_payload(req,payload)['precision']=='fp32'
    for bad in ({'framespersecond':30,'fps':30},{'framespersecond':float('nan'),'fps':None},{'framespersecond':float('inf'),'fps':None},{'framespersecond':True,'fps':None},{'fps':24}):
        with pytest.raises(ValueError):task_payload(req,{**payload,**bad})
