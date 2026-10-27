import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('next_image',Path(__file__).resolve().parents[1]/'spark/cuda_next_image_adapter.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Adapter=module.CudaImageGenerationAdapter
QWEN='Qwen/Qwen-Image-2512'
Z='Tongyi-MAI/Z-Image-Turbo'

@pytest.mark.parametrize('patch',[
    {'steps':True},{'steps':2.5},{'seed':-1},{'guidance':float('nan')},
    {'guidance':True},{'prompt':42},{'size':'2049x512'},
    {'quantization':'q4'},{'negative_prompt':123}, {'imageDataUrls':['reference']},
])
def test_reject_unsupported_parameters(patch):
    with pytest.raises((ValueError,TypeError)):
        Adapter.parameters({'prompt':'test',**patch},QWEN)

def test_family_specific_geometry_and_cfg():
    assert Adapter.parameters({'prompt':'test','size':'528x512'},QWEN)[1:5]==(528,512,20,4.)
    with pytest.raises(ValueError):Adapter.parameters({'prompt':'test','size':'528x512'},Z)
    assert Adapter.parameters({'prompt':'test'},Z)[3:5]==(9,0.)
    with pytest.raises(ValueError):Adapter.parameters({'prompt':'test','guidance':4},Z)
    with pytest.raises(ValueError):Adapter.parameters({'prompt':'test','negative_prompt':'blur'},Z)

@pytest.mark.asyncio
async def test_edit_rejected_before_checkpoint_access():
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    with pytest.raises(ModelWorkerError) as error:
        await Adapter(None).invoke(SimpleNamespace(operation='image_edit'))
    assert error.value.code=='operation_not_supported'

def test_edit_defaults_and_reference_limits():
    edit=module.CudaQwenImageEditAdapter
    assert edit.parameters({'prompt':'edit'},'Qwen/Qwen-Image-Edit-2511')[3:5]==(30,2.5)
    for refs in ([],['x']*4,'x',None):
        with pytest.raises(ValueError):edit.inputs({'imageDataUrls':refs})

def test_edit_decodes_three_formats_without_changing_generation_contract():
    import base64,io
    from PIL import Image
    refs=[]
    for fmt in ('PNG','JPEG','WEBP'):
        buf=io.BytesIO();Image.new('RGB',(16,16),'red').save(buf,format=fmt)
        refs.append('data:image/'+fmt.lower()+';base64,'+base64.b64encode(buf.getvalue()).decode())
    images=module.CudaQwenImageEditAdapter.inputs({'imageDataUrls':refs})['image']
    assert len(images)==3 and all(im.size==(16,16) and im.mode=='RGB' for im in images)
    with pytest.raises(ValueError):Adapter.parameters({'prompt':'test','imageDataUrls':refs},QWEN)

@pytest.mark.asyncio
async def test_edit_adapter_rejects_generation_before_checkpoint_access():
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    with pytest.raises(ModelWorkerError) as error:
        await module.CudaQwenImageEditAdapter(None).invoke(SimpleNamespace(operation='image_generation'))
    assert error.value.code=='operation_not_supported'


def test_edit_low_resolution_canvas_does_not_change_generation_or_rectangles():
    edit=module.CudaQwenImageEditAdapter
    assert edit.pipeline_dimensions(512,512)==(1024,1024)
    assert edit.pipeline_dimensions(1024,1024)==(1024,1024)
    assert edit.pipeline_dimensions(2048,2048)==(2048,2048)
    assert edit.pipeline_dimensions(512,1024)==(512,1024)
    assert Adapter.pipeline_dimensions(512,512)==(512,512)

@pytest.mark.asyncio
async def test_base_invocation_forwards_official_cfg_negative_and_seed(monkeypatch,tmp_path):
    import sys
    from types import SimpleNamespace
    from PIL import Image
    from ai2apps.model_worker.protocol import ModelWorkerError
    base='Tongyi-MAI/Z-Image'
    calls=[]
    class Generator:
        def __init__(self,device):assert device=='cuda'
        def manual_seed(self,seed):self.seed=seed;return self
    monkeypatch.setitem(sys.modules,'torch',SimpleNamespace(bfloat16='bf16',Generator=Generator,cuda=SimpleNamespace(empty_cache=lambda:None)))
    class Pipeline:
        @classmethod
        def from_pretrained(cls,path,**kw):
            assert path==str(tmp_path) and kw=={'torch_dtype':'bf16','local_files_only':True}
            return cls()
        def to(self,device):assert device=='cuda';return self
        def __call__(self,**kw):
            assert 'true_cfg_scale' not in kw
            assert kw['guidance_scale']==4 and kw['negative_prompt']=='blur, watermark'
            assert kw['cfg_normalization'] is False
            assert kw['num_inference_steps']==30 and kw['generator'].seed==42
            calls.append(kw)
            kw['callback_on_step_end'](self,0,1,{})
            return SimpleNamespace(images=[Image.new('RGB',(512,512),'red')])
    monkeypatch.setattr(Adapter,'pipeline_factory',staticmethod(lambda upstream:Pipeline))
    checkpoint=SimpleNamespace(path=tmp_path,repo_id=base,upstream_id=base,revision=Adapter.revisions[base])
    adapter=Adapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    request=SimpleNamespace(operation='image_generation',request_id='base',payload={'model':base,'prompt':'teapot','size':'512x512','negative_prompt':'blur, watermark','seed':42},progress=None)
    result=await adapter.invoke(request)
    assert result['image']['size']=='512x512' and len(calls)==1
    request.payload['size']='528x512'
    with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request)
    assert error.value.code=='invalid_request' and len(calls)==1
    assert adapter.events=={}
    await adapter.stop()

@pytest.mark.asyncio
@pytest.mark.parametrize("upstream", [Z, QWEN, "Tongyi-MAI/Z-Image"])
async def test_shared_image_lifecycle_stops_thread_and_preserves_cancel(monkeypatch, upstream):
    import threading
    from PIL import Image
    from ai2apps.model_worker.protocol import ModelWorkerError
    import asyncio
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    entered, release = threading.Event(), threading.Event()
    loads = []

    class Pipeline:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            loads.append(args)
            return cls()
        def to(self, device):
            return self
        def __call__(self, **kwargs):
            entered.set()
            assert release.wait(5), 'test failed to release generation thread'
            kwargs['callback_on_step_end'](self, 0, None, {})
            return SimpleNamespace(images=[Image.new('RGB', (256, 256), 'red')])

    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(
        bfloat16='bf16', cuda=SimpleNamespace(empty_cache=lambda: None),
        Generator=lambda device: SimpleNamespace(manual_seed=lambda seed: None)))
    monkeypatch.setattr(Adapter, 'pipeline_factory', staticmethod(lambda _: Pipeline))
    checkpoint = SimpleNamespace(path=Path('/test/fixed'), upstream_id=upstream, repo_id=upstream, revision=Adapter.revisions[upstream])
    adapter = Adapter(SimpleNamespace(checkpoint_for=lambda _: checkpoint))
    def request(identity):
        return SimpleNamespace(request_id=identity, operation='image_generation',
            payload={'model':'fixed', 'prompt':'red teapot', 'size':'256x256'}, progress=None)
    active = asyncio.create_task(adapter.invoke(request('same')))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        original_event = adapter.events['same']
        with pytest.raises(ModelWorkerError) as duplicate:
            await adapter.invoke(request('same'))
        assert duplicate.value.status_code == 409
        assert adapter.events['same'] is original_event
        queued = asyncio.create_task(adapter.invoke(request('queued')))
        await asyncio.sleep(0)
        stopping = asyncio.create_task(adapter.stop())
        await asyncio.sleep(0)
        assert not stopping.done()
        with pytest.raises(ModelWorkerError) as rejected:
            await adapter.invoke(request('late'))
        assert rejected.value.status_code == 503
        release.set()
        outcomes = await asyncio.gather(active, queued, return_exceptions=True)
        assert all(isinstance(e, ModelWorkerError) and e.status_code == 499 for e in outcomes)
        await stopping
        assert adapter.events == {} and adapter.pipeline is None
        assert len(loads) == 1  # queued request never entered model generation
        await adapter.start()
        recovered = await adapter.invoke(request('recovery'))
        assert recovered['image']['size'] == '256x256'
        assert len(loads) == 2
        await adapter.stop()
    finally:
        release.set()
        await asyncio.gather(active, return_exceptions=True)

@pytest.mark.asyncio
async def test_qwen_service_switch_releases_previous_pipeline_and_checks_model():
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    records = []
    checkpoints = {'gen': SimpleNamespace(path=Path('/fixed/gen'), upstream_id=QWEN),
                   'edit': SimpleNamespace(path=Path('/fixed/edit'), upstream_id='Qwen/Qwen-Image-Edit-2511')}
    adapter = module.CudaQwenImageAdapter(SimpleNamespace(checkpoint_for=checkpoints.get))
    class Engine:
        def __init__(self, name): self.name = name
        async def start(self): records.append(('start', self.name))
        async def stop(self): records.append(('stop', self.name))
        async def invoke(self, request): records.append(('invoke', self.name)); return self.name
        def cancel(self, request_id): pass
    adapter.adapters = {op: Engine(op) for op in adapter.adapters}
    def req(op, model): return SimpleNamespace(operation=op, payload={'model': model}, request_id=model)
    assert await adapter.invoke(req('image_generation', 'gen')) == 'image_generation'
    with pytest.raises(ModelWorkerError): await adapter.invoke(req('image_edit', 'gen'))
    assert await adapter.invoke(req('image_edit', 'edit')) == 'image_edit'
    await adapter.stop()
    assert records == [('start','image_generation'),('invoke','image_generation'),
                       ('stop','image_generation'),('start','image_edit'),
                       ('invoke','image_edit'),('stop','image_edit')]
    assert not adapter.pending and adapter.active is None

@pytest.mark.asyncio
async def test_qwen_service_cancel_queued_edit_does_not_load_second_model():
    import asyncio
    from types import SimpleNamespace
    from ai2apps.model_worker.protocol import ModelWorkerError
    entered, release = asyncio.Event(), asyncio.Event()
    context = SimpleNamespace(checkpoint_for=lambda model: SimpleNamespace(path=Path('/fixed'), upstream_id=QWEN if model=='gen' else 'Qwen/Qwen-Image-Edit-2511'))
    adapter = module.CudaQwenImageAdapter(context)
    class Engine:
        async def start(self): pass
        async def stop(self): pass
        async def invoke(self, request): entered.set(); await release.wait(); return 'done'
        def cancel(self, request_id): pass
    class Unused(Engine):
        async def start(self): raise AssertionError('Cancelled queued edit loaded')
    adapter.adapters = {'image_generation':Engine(), 'image_edit':Unused()}
    def req(op, model): return SimpleNamespace(operation=op,payload={'model':model},request_id=model)
    active = asyncio.create_task(adapter.invoke(req('image_generation','gen')))
    await entered.wait()
    queued = asyncio.create_task(adapter.invoke(req('image_edit','edit')))
    await asyncio.sleep(0)
    adapter.cancel('edit'); release.set()
    assert await active == 'done'
    with pytest.raises(ModelWorkerError) as error: await queued
    assert error.value.status_code == 499
    assert not adapter.pending
    await adapter.stop()
