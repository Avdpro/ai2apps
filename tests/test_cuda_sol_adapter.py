import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_sol_adapter import CudaSoLAdapter, MODEL
from cuda_sol_resources import admit, GIB
from ai2apps.model_worker import ModelWorkerRequest, ModelWorkerError


@pytest.mark.parametrize('controls',[{'scale':True},{'seed':-1},{'seed':True},
                                    {'prompt':'new prompt'},{'steps':2},[]])
def test_controls_reject_unsupported_or_wrong_types(controls):
    with pytest.raises(ValueError): CudaSoLAdapter.parameters({'model':MODEL,'parameters':controls})


def test_cancelled_native_writer_finishes_before_output_removal(tmp_path):
    for name in ('model_index.json','context-metadata.json','default-prompt-context.safetensors'):
        (tmp_path/name).touch()
    adapter = CudaSoLAdapter(SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=tmp_path)))
    entered,release = threading.Event(),threading.Event()
    output = []
    def render(work,event):
        output.append(work.output)
        work.output.write_bytes(b'partial')
        entered.set()
        assert release.wait(3)
        work.output.write_bytes(b'late native write')
        return 'unused result'
    adapter._owner.render = render
    request = ModelWorkerRequest('image_upscaling',{'model':MODEL},'first',
                                parts={'image':SimpleNamespace(media_type='image/png',path=tmp_path/'in.png')},
                                output_root=tmp_path)
    async def run():
        active = asyncio.create_task(adapter.invoke(request))
        assert await asyncio.to_thread(entered.wait,2)
        active.cancel()
        await asyncio.sleep(.01)
        active.cancel()
        await asyncio.sleep(.01)
        assert output[0].exists() and not active.done()
        release.set()
        with pytest.raises(asyncio.CancelledError): await active
        assert not output[0].exists()
    asyncio.run(run())


@pytest.mark.parametrize('name,allowed',[('NVIDIA GB10',True),('discrete GPU',False)])
def test_uma_page_cache_is_available_but_discrete_vram_still_limits(tmp_path,monkeypatch,name,allowed):
    # Reproduce the real failed fixture: 10 GiB MemFree but 80 GiB MemAvailable.
    cuda = SimpleNamespace(is_available=lambda:True,mem_get_info=lambda:(10*GIB,120*GIB),
                           get_device_name=lambda:name)
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=cuda))
    import psutil
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(total=120*GIB,available=80*GIB))
    if allowed:
        assert admit(256,144,60,resident=True)>0
    else:
        with pytest.raises(MemoryError): admit(256,144,60,resident=True)


def test_custom_selection_accepts_prompt_without_relaxing_standard():
    from cuda_sol_adapter import CUSTOM_MODEL
    assert CudaSoLAdapter.parameters({'model':CUSTOM_MODEL,'parameters':'{"prompt":"portrait","seed":"2"}'}) == ('portrait',2)
    with pytest.raises(ValueError):
        CudaSoLAdapter.parameters({'model':MODEL,'prompt':'portrait'})


def test_model_variant_switch_releases_before_admission_even_with_same_root(tmp_path):
    from cuda_sol_adapter import CUSTOM_MODEL
    adapter=CudaSoLAdapter(SimpleNamespace())
    events=[]
    class Runner:
        def __init__(self,label): self.label=label;events.append('load-'+label)
        def close(self):events.append('release-'+self.label)
    def admit(*args,**kwargs):events.append(('admit',kwargs['resident'],kwargs['custom']))
    factories=(lambda *args:Runner('standard'),lambda *args:Runner('custom'))
    for model in (MODEL,MODEL,CUSTOM_MODEL,MODEL):
        work=SimpleNamespace(root=tmp_path,model=model)
        adapter._ensure_runner(work,64,64,1,lambda:None,admit,*factories)
    assert events==[('admit',False,False),'load-standard',('admit',True,False),
                    'release-standard',('admit',False,True),'load-custom',
                    'release-custom',('admit',False,False),'load-standard']


def test_custom_cold_admission_accounts_for_text_residency(monkeypatch):
    cuda=SimpleNamespace(is_available=lambda:True,mem_get_info=lambda:(70*GIB,120*GIB),get_device_name=lambda:'NVIDIA GB10')
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(cuda=cuda))
    import psutil
    monkeypatch.setattr(psutil,'virtual_memory',lambda:SimpleNamespace(total=120*GIB,available=70*GIB))
    assert admit(64,64,1,resident=False)>0
    with pytest.raises(MemoryError):admit(64,64,1,resident=False,custom=True)
    assert admit(64,64,1,resident=True,custom=True)>0


@pytest.mark.parametrize('state',['absent','incomplete','complete'])
def test_custom_uses_only_host_selected_custom_checkpoint(tmp_path,state):
    from cuda_sol_adapter import CUSTOM_MODEL
    standard=tmp_path/'standard';custom=tmp_path/'custom'
    standard.mkdir();custom.mkdir()
    for name in ('model_index.json','context-metadata.json','default-prompt-context.safetensors'):
        (standard/name).touch();(custom/name).touch()
    if state=='complete':
        for name in ('text_encoder/config.json','connectors/config.json','tokenizer/tokenizer_config.json'):
            path=custom/name;path.parent.mkdir();path.touch()
    selected=[];executed=[]
    def checkpoint_for(model):
        selected.append(model)
        if model==MODEL:return SimpleNamespace(path=standard)
        return None if state=='absent' else SimpleNamespace(path=custom)
    adapter=CudaSoLAdapter(SimpleNamespace(checkpoint_for=checkpoint_for))
    def render(work,event):
        executed.append((work.root,work.model,work.prompt));return 'custom-result'
    adapter._owner.render=render
    req=ModelWorkerRequest('image_upscaling',{'model':CUSTOM_MODEL,'prompt':'Keep natural details'},'custom',
        parts={'image':SimpleNamespace(media_type='image/png',path=tmp_path/'source.png')},output_root=tmp_path)
    async def run():
        if state=='complete':assert await adapter.invoke(req)=='custom-result'
        else:
            with pytest.raises(ModelWorkerError) as error:await adapter.invoke(req)
            assert error.value.status_code==503 and not executed
        assert selected==[CUSTOM_MODEL]
    asyncio.run(run())
    if state=='complete':assert executed==[(custom,CUSTOM_MODEL,'Keep natural details')]
