"""SAM2 request bounds and native cancellation ownership."""
import asyncio
import importlib.util
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('sam21_mac_adapter',ROOT/'packages/ai2apps-model-sam21-mlx/src/worker_adapter.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
sys.modules['sam21_mac_adapter']=shared
sys.path.insert(0,str(ROOT/'spark'))
from cuda_sam21_adapter import CudaSAM21Adapter, MODEL
from ai2apps.model_worker import ModelWorkerRequest

@pytest.mark.parametrize('controls',[
 {'points':[{'x':float('nan'),'y':2}]},
 {'points':[{'x':1,'y':2,'label':0}]},
 {'points':[{'x':1,'y':2}],'steps':10},
 {'points':[{'x':1,'y':2}],'threshold':float('inf')},
 {'points':[{'x':1,'y':2}],'prompt_frame':True},
])
def test_invalid_controls(controls):
 with pytest.raises(ValueError):CudaSAM21Adapter._validate({'parameters':controls})


def test_native_thread_is_drained_after_repeated_cancel(tmp_path,monkeypatch):
 (tmp_path/'sam2.1_hiera_small.safetensors').touch()
 selected=SimpleNamespace(path=tmp_path)
 adapter=CudaSAM21Adapter(SimpleNamespace(checkpoint_for=lambda _:selected))
 entered=threading.Event();release=threading.Event();calls=[]
 def render(request,*args):
  calls.append(request.request_id);entered.set();release.wait(5);return 'ok'
 monkeypatch.setattr(adapter,'_render',render)
 def request(identity):
  return ModelWorkerRequest('video_segmentation',{'model':MODEL,'points':[{'x':1,'y':2}]},identity,parts={'video':object()},output_root=tmp_path)
 async def run():
  first=asyncio.create_task(adapter.invoke(request('first')))
  await asyncio.to_thread(entered.wait,2)
  first.cancel();await asyncio.sleep(.02);first.cancel()
  second=asyncio.create_task(adapter.invoke(request('second')))
  await asyncio.sleep(.02)
  assert not first.done() and calls==['first']
  release.set()
  with pytest.raises(asyncio.CancelledError):await first
  assert await second=='ok'
  assert not adapter._pending
 asyncio.run(run())

@pytest.mark.parametrize('name', ['sam2.1_hiera_small.pt','sam2.1_hiera_small.safetensors','model.safetensors'])
def test_checkpoint_bytes_are_rejected_before_deserialization(tmp_path, monkeypatch, name):
 import torch
 from ai2apps.model_worker import ModelWorkerError
 p=tmp_path/name;p.write_bytes(b'untrusted')
 monkeypatch.setattr(torch,'load',lambda *a,**k:pytest.fail('Unverified bytes deserialized'))
 with pytest.raises(ModelWorkerError) as error:CudaSAM21Adapter.checkpoint_state(p)
 assert error.value.code=='invalid_checkpoint'
