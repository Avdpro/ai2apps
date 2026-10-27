from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_echomimic_adapter import inputs,CudaEchoMimicAdapter,MODEL_ID
from ai2apps.model_worker import ModelWorkerRequest,ModelWorkerPart,ModelWorkerError


def request(params=None,**changes):
    parts={name:ModelWorkerPart(name,Path('/tmp')/name,media,name,1,'a'*64)
        for name,media in [('image','image/png'),('audio','audio/wav')]}
    payload={'model':MODEL_ID,'parameters':params or {}}
    payload.update(changes)
    return ModelWorkerRequest('video_generation',payload,'request',parts,Path('/tmp/output'))


def test_generic_multipart_reference_and_string_payload():
    req=request({'width':768,'height':768,'long':'true'},reference_parts='[{"kind":"image","part_name":"image"}]',inputs='{"prompt":"Hello"}')
    image,audio,params=inputs(req)
    assert image.name=='image' and audio.name=='audio'
    assert params==dict(resolution=768,seed=43,long=True,preset='exact',prompt='Hello')


@pytest.mark.parametrize('params',[{'width':True},{'seed':False},{'fps':30},{'width':768},{'preset':'fast','long':True},{'checkpoint_path':'/tmp/unowned'},{'seed':-1}])
def test_invalid_contract(params):
    with pytest.raises(ValueError):inputs(request(params))


def test_ambiguous_reference_rejected():
    with pytest.raises(ValueError):inputs(request(inputs={'reference_image':{'part_name':'image'}},reference_parts=[{'kind':'image','part_name':'image'}]))


def test_host_video_controls_with_nested_parameters():
    _,_,params=inputs(request({'seed':17},resolution='768x768',ratio='1:1',
        framespersecond=25,preset='fast',output_format='mp4',
        audio_output_mode='preserve_driving_audio'))
    assert params==dict(resolution=768,seed=17,long=False,preset='fast',prompt='A person is speaking.')


@pytest.mark.parametrize('params,host',[
    ({'width':512,'height':512},{'resolution':'768x768'}),
    ({'resolution':'512x512'},{'resolution':'768x768'}),
    ({'fps':25},{'framespersecond':30}),
    ({},{'resolution':'1024x1024'}),
    ({},{'ratio':'16:9'}),
    ({},{'output_format':'webm'}),
    ({},{'audio_output_mode':'none'}),
    ({},{'checkpoint_path':'/tmp/unowned'}),
])
def test_host_controls_reject_conflicts_and_unsupported_modes(params,host):
    with pytest.raises(ValueError):inputs(request(params,**host))


@pytest.mark.asyncio
async def test_missing_host_checkpoint_rejected_before_gpu(tmp_path):
    adapter=CudaEchoMimicAdapter(SimpleNamespace(data_root=tmp_path,checkpoint_for=lambda _:None))
    with pytest.raises(ModelWorkerError) as exc:await adapter.invoke(request())
    assert exc.value.code=='checkpoint_not_ready'
    assert adapter._engine is None
    await adapter.stop()
