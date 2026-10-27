import importlib.util
from pathlib import Path
from types import SimpleNamespace
import zipfile
import pytest

@pytest.mark.asyncio
async def test_cancellation_during_zip_cannot_return_a_success_artifact(tmp_path, monkeypatch):
    repo=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo/'packages/omlx-model-demucs/src'))
    monkeypatch.syspath_prepend(str(repo/'spark'))
    spec=importlib.util.spec_from_file_location('demucs_adapter_test',repo/'spark/cuda_demucs_adapter.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Backend:
        def __init__(self, checkpoint):pass
    monkeypatch.setattr(module,'CudaDemucsBackend',Backend)
    monkeypatch.setattr(module,'read_audio',lambda _:SimpleNamespace(frames=1,channels=2,duration=1))
    def separate(audio, root, **kwargs):
        root.mkdir();(root/'separation.json').write_text('{}')
        for name in ['drums','vocals']:(root/(name+'.wav')).write_bytes(b'fixture')
        return SimpleNamespace(schema='fixture',stems=[SimpleNamespace(type=n,path=n+'.wav') for n in ['drums','vocals']])
    monkeypatch.setattr(module,'separate_audio',separate)
    checkpoint=SimpleNamespace(path=tmp_path,repo_id='mlx-community/demucs-mlx',revision='d4519e24ddc2dd4a11d56a193092433d852c3961')
    adapter=module.CudaDemucsAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    write=zipfile.ZipFile.write
    def write_and_cancel(archive, path, arcname, **kwargs):
        write(archive,path,arcname,**kwargs)
        if arcname=='drums.wav':adapter.cancel('packing-request')
    monkeypatch.setattr(zipfile.ZipFile,'write',write_and_cancel)
    request=SimpleNamespace(operation='audio_process',payload={'model':'fixture','profile':'music_4stem'},
        request_id='packing-request',output_root=tmp_path,progress=None,part=lambda _:SimpleNamespace(path=tmp_path/'input.wav'))
    with pytest.raises(module.ModelWorkerError) as error:
        await adapter.invoke(request)
    assert error.value.status_code==499 and error.value.code=='request_cancelled'
    assert not adapter.events

@pytest.mark.asyncio
async def test_stop_drains_active_and_queued_and_rejects_late_or_duplicate(tmp_path, monkeypatch):
    import asyncio
    import threading
    import sys
    repo=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(repo/'packages/omlx-model-demucs/src'))
    monkeypatch.syspath_prepend(str(repo/'spark'))
    spec=importlib.util.spec_from_file_location('demucs_stop_test',repo/'spark/cuda_demucs_adapter.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    entered, release = threading.Event(), threading.Event()
    loads=[]
    class Backend:
        def __init__(self, checkpoint): loads.append(checkpoint)
    monkeypatch.setattr(module,'CudaDemucsBackend',Backend)
    monkeypatch.setattr(module,'read_audio',lambda _:SimpleNamespace(frames=1,channels=2,duration=1))
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=SimpleNamespace(empty_cache=lambda:None)))
    def separate(audio, root, **kwargs):
        entered.set(); assert release.wait(3)
        assert kwargs['backend'].cancelled.is_set()
        raise InterruptedError('cancelled')
    monkeypatch.setattr(module,'separate_audio',separate)
    checkpoint=SimpleNamespace(path=tmp_path,repo_id='mlx-community/demucs-mlx',revision='d4519e24ddc2dd4a11d56a193092433d852c3961')
    adapter=module.CudaDemucsAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    def request(identity):
        return SimpleNamespace(operation='audio_process',payload={'model':'fixture'},request_id=identity,
            output_root=tmp_path,progress=None,part=lambda _:SimpleNamespace(path=tmp_path/'input.wav'))
    active=asyncio.create_task(adapter.invoke(request('active')))
    assert await asyncio.to_thread(entered.wait,2)
    try:
        with pytest.raises(module.ModelWorkerError) as duplicate: await adapter.invoke(request('active'))
        assert duplicate.value.status_code==409
        queued=asyncio.create_task(adapter.invoke(request('queued')));await asyncio.sleep(0)
        stopping=asyncio.create_task(adapter.stop());await asyncio.sleep(0)
        assert not stopping.done()
        with pytest.raises(module.ModelWorkerError) as late: await adapter.invoke(request('late'))
        assert late.value.status_code==503
        release.set()
        results=await asyncio.gather(active,queued,return_exceptions=True)
        assert all(isinstance(e,module.ModelWorkerError) and e.status_code==499 for e in results)
        await stopping
        assert len(loads)==1 and not adapter.events and adapter.backend is None
        await adapter.start();assert not adapter.stopping
    finally:
        release.set();await asyncio.gather(active,return_exceptions=True)
