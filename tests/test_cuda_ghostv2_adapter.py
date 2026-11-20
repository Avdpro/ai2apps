import asyncio,threading,sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'spark'))
from cuda_ghostv2_adapter import CudaGhostV2Adapter
from cuda_ghostv2_contract import BINDINGS,MODEL
from ai2apps.model_worker import ModelWorkerError,ModelWorkerArtifact


class Controlled(CudaGhostV2Adapter):
    def __init__(self,root):
        super().__init__(SimpleNamespace(checkpoints=[SimpleNamespace(model_id=v,path=root) for v in BINDINGS.values()]))
        self.entered=threading.Event();self.exited=threading.Event();self.block=True;self.calls=0
    def _render(self,request,source,target,options,roots,event):
        self.calls+=1;self.entered.set()
        try:
            if self.block:
                assert event.wait(5)
                raise InterruptedError('cancel')
            p=request.output_root/'out.png';p.write_bytes(b'fixture')
            return ModelWorkerArtifact(p,'image/png',p.name)
        finally:self.exited.set()


def req(root,key):
    return SimpleNamespace(request_id=key,operation='image_edit',payload={'model':MODEL},output_root=root,part=lambda _:SimpleNamespace(path=root/'input'))


@pytest.mark.asyncio
async def test_duplicate_stop_queued_and_restart(tmp_path):
    a=Controlled(tmp_path);task=asyncio.create_task(a.invoke(req(tmp_path,'one')))
    assert await asyncio.to_thread(a.entered.wait,2)
    with pytest.raises(ModelWorkerError) as e:await a.invoke(req(tmp_path,'one'))
    assert e.value.status_code==409
    queued=asyncio.create_task(a.invoke(req(tmp_path,'two')));await asyncio.sleep(0)
    await a.stop()
    for t in [task,queued]:
        with pytest.raises(ModelWorkerError) as e:await t
        assert e.value.status_code==499
    assert a.exited.is_set() and a.calls==1 and not a._events
    with pytest.raises(ModelWorkerError) as e:await a.invoke(req(tmp_path,'three'))
    assert e.value.status_code==503
    await a.start();a.block=False
    assert (await a.invoke(req(tmp_path,'four'))).path.exists()


@pytest.mark.asyncio
async def test_transport_cancellation_holds_owner_until_thread_exits(tmp_path):
    a=Controlled(tmp_path);task=asyncio.create_task(a.invoke(req(tmp_path,'one')))
    assert await asyncio.to_thread(a.entered.wait,2);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert a.exited.is_set() and not a._events and not a._owner.locked()


@pytest.mark.asyncio
async def test_queued_cancel_does_not_enter_renderer(tmp_path):
    a=Controlled(tmp_path);task=asyncio.create_task(a.invoke(req(tmp_path,'one')))
    assert await asyncio.to_thread(a.entered.wait,2)
    queued=asyncio.create_task(a.invoke(req(tmp_path,'two')));await asyncio.sleep(0)
    a.cancel('two');a.cancel('one')
    for t in [task,queued]:
        with pytest.raises(ModelWorkerError) as e:await t
        assert e.value.status_code==499
    assert a.calls==1


@pytest.mark.asyncio
async def test_cancel_error_does_not_retain_native_frame_payload(tmp_path):
    import weakref,gc
    refs=[]
    class Payload:pass
    class Failing(Controlled):
        def _render(self,*args):
            payload=Payload();refs.append(weakref.ref(payload))
            raise InterruptedError('native cancelled')
    a=Failing(tmp_path)
    with pytest.raises(ModelWorkerError) as caught:await a.invoke(req(tmp_path,'cancel'))
    assert caught.value.status_code==499
    gc.collect()
    # Keep the public exception/traceback alive as the HTTP layer may do.
    assert refs[0]() is None
    assert caught.value.__cause__.__traceback__ is not None


def test_factory_profile_rejects_missing_or_wrong_service(tmp_path):
    from cuda_ghostv2_adapter import _runtime_profile
    with pytest.raises(RuntimeError,match='profile is required'):_runtime_profile(tmp_path,'ai2apps.model.face-swap-cuda')
    with pytest.raises(RuntimeError,match='service identity'):_runtime_profile(tmp_path,'other')


def test_factory_profile_rejects_package_shadow(tmp_path,monkeypatch):
    import json,importlib.util
    from cuda_ghostv2_adapter import _runtime_profile
    site=tmp_path/'profiles/ghostv2/site-packages';site.mkdir(parents=True)
    meta=tmp_path/'META';meta.mkdir()
    (meta/'framework-profiles.json').write_text(json.dumps({'format':'ai2apps.framework-profiles/v1','profiles':{'ghostv2':{'site_packages':'profiles/ghostv2/site-packages'}},'services':{'ai2apps.model.face-swap-cuda':'ghostv2'}}))
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:SimpleNamespace(origin=str(tmp_path/'package'/f'{name}.py')))
    with pytest.raises(RuntimeError,match='not Runtime-owned'):_runtime_profile(tmp_path,'ai2apps.model.face-swap-cuda')
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:SimpleNamespace(origin=str(site/f'{name}.py')))
    assert _runtime_profile(tmp_path,'ai2apps.model.face-swap-cuda')==site


def test_namespace_profile_rejects_mixed_locations(tmp_path,monkeypatch):
    import json,importlib.util
    from cuda_ghostv2_adapter import _runtime_profile
    site=tmp_path/'profile';site.mkdir();(tmp_path/'META').mkdir()
    (tmp_path/'META/framework-profiles.json').write_text(json.dumps({'format':'ai2apps.framework-profiles/v1','profiles':{'g':{'site_packages':'profile'}},'services':{'ai2apps.model.face-swap-cuda':'g'}}))
    monkeypatch.setattr(importlib.util,'find_spec',lambda _:SimpleNamespace(origin=None,submodule_search_locations=[str(site)]))
    assert _runtime_profile(tmp_path,'ai2apps.model.face-swap-cuda')==site
    monkeypatch.setattr(importlib.util,'find_spec',lambda _:SimpleNamespace(origin=None,submodule_search_locations=[str(site),str(tmp_path/'package')]))
    with pytest.raises(RuntimeError,match='not Runtime-owned'):_runtime_profile(tmp_path,'ai2apps.model.face-swap-cuda')
