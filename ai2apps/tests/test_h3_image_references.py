"""Local H3-Image reference limits and Worker forwarding; no paid requests."""
import base64
from io import BytesIO
import pytest
from PIL import Image


def data(color):
    out=BytesIO();Image.new('RGB',(128,128),color).save(out,'PNG');return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def local_adapter():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[2]/'packages/ai2apps-model-minimax-h3-image-mlx/src/worker_adapter.py'
    spec=importlib.util.spec_from_file_location('fixture_h3_adapter',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize('count',[1,2,16])
def test_local_adapter_decodes_ordered_references(count):
    m=local_adapter();refs=[data((i*10,50,100)) for i in range(count)]
    images=m._references({'imageDataUrls':refs},True)
    assert [im.getpixel((0,0)) for im in images]==[(i*10,50,100) for i in range(count)]
    assert m._references({},False)==[]
    for bad in ([],refs*17):
        with pytest.raises(ValueError,match='1 to 16'):m._references({'imageDataUrls':bad},True)


@pytest.mark.asyncio
async def test_local_worker_passes_all_refs_to_existing_pipeline(tmp_path,monkeypatch):
    import sys,types
    from ai2apps.model_worker import ModelWorkerRequest
    from types import SimpleNamespace
    m=local_adapter();calls=[]
    def generate(*args,**kw):
        calls.append(kw);return Image.new('RGB',(512,512),'green')
    pipe=types.ModuleType('minimax_h3_mlx.image_pipeline');pipe.generate_image=generate;pipe.ImageReferenceCache=lambda:object()
    monkeypatch.setitem(sys.modules,'minimax_h3_mlx.image_pipeline',pipe)
    checkpoint=SimpleNamespace(path=tmp_path,revision='same-original-checkpoint')
    adapter=m.ImageAdapter(SimpleNamespace(checkpoint_for=lambda _:checkpoint))
    result=await adapter.invoke(ModelWorkerRequest('image_edit',{'model':m.MODEL,'prompt':'Combine Picture 1 and Picture 2','size':'512x512','imageDataUrls':[data('red'),data('blue')]},'fixture'))
    assert len(calls)==1 and len(calls[0]['references'])==2
    assert calls[0]['references'][0].getpixel((0,0))==(255,0,0)
    assert result['image']['size']=='512x512'
    await adapter.stop()


@pytest.mark.asyncio
async def test_local_model_descriptor_preserves_reference_limit(monkeypatch):
    from types import SimpleNamespace
    from ai2apps.images.parameters import models
    fake=SimpleNamespace(id='fixture/local',display_name='Fixture',capabilities=['image_generation','image_edit'],metadata={},image_capabilities={'inputs':{'reference_images':{'minimum':1,'maximum':16}}},checkpoint_ready=True)
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',lambda *a,**kw:[fake])
    result,_=await models(SimpleNamespace(model_manager=SimpleNamespace(enabled_cloud_models=lambda:[])),None,True)
    assert result[0]['referenceLimits']['maximum']==16
@pytest.mark.asyncio
@pytest.mark.parametrize('maximum',[4,16])
async def test_reference_aaat_schema_and_prepare_follow_model(maximum,monkeypatch):
    from ai2apps.images import parameters,mini_parameters
    from ai2apps.images.parameters import from_options,effective_schema
    from ai2apps.services.capability_routing import ProviderIncompatible
    m=from_options('fixture','Fixture',{'size':{'mode':'fixed','default':'1024x1024','presets':['1024x1024']},'quality':['auto'],'outputFormat':['png']});m['referenceLimits']={'minimum':1,'maximum':maximum}
    async def describe(*a,**kw):return {'model':m['id'],'models':[m],'schema':{},'effective_schema':effective_schema(m,True),'constraints':{'size':m['size']},'warnings':[]}
    monkeypatch.setattr(parameters,'describe',describe)
    d=await mini_parameters.describe(None,None,'ai2apps.imagine.reference-creation','fixture')
    assert d['effective_schema']['properties']['artifact_ids']['maxItems']==maximum
    args={'model':'fixture','artifact_ids':[f'actual-{i}' for i in range(16)],'prompt':'Combine all references in order'}
    call=mini_parameters.prepare(None,None,'ai2apps.imagine.reference-creation',args)
    if maximum==16:assert len((await call)['artifact_ids'])==16
    else:
        with pytest.raises(ProviderIncompatible):await call
