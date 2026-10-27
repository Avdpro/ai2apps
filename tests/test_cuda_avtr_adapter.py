from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_avtr_adapter import inputs,CudaAVTRAdapter,MODEL_ID
from ai2apps.model_worker import ModelWorkerRequest,ModelWorkerPart,ModelWorkerError

def request(params=None,**changes):
    parts={name:ModelWorkerPart(name,Path('/tmp')/name,media,name,1,'a'*64)
        for name,media in [('image','image/png'),('audio','audio/wav')]}
    payload={'model':MODEL_ID,'parameters':params or {}};payload.update(changes)
    return ModelWorkerRequest('video_generation',payload,'request',parts,Path('/tmp/output'))

def test_multipart_and_json_params():
    image,audio,p=inputs(request(parameters='{"duration":6.4,"preset":"standard"}',reference_parts='[{"kind":"image","part_name":"image"}]'))
    assert image.name=='image' and audio.name=='audio'
    assert p==dict(seconds=6.4,steps=5,seed=42,output_mode='source',preset='standard')

@pytest.mark.parametrize('params',[{'preset':'unsupported'},{'fps':True},{'width':768},{'seconds':2,'duration':3},{'checkpoint_path':'/tmp/x'},{'steps':False}])
def test_unsupported_contract_rejected(params):
    with pytest.raises(ValueError):inputs(request(params))

def test_ambiguous_reference():
    with pytest.raises(ValueError):inputs(request(inputs={'reference_image':{'part_name':'image'}},reference_parts=[{'kind':'image','part_name':'image'}]))

@pytest.mark.asyncio
async def test_missing_checkpoint_no_gpu(tmp_path):
    adapter=CudaAVTRAdapter(SimpleNamespace(data_root=tmp_path,checkpoint_for=lambda _:None))
    with pytest.raises(ModelWorkerError) as error:await adapter.invoke(request())
    assert error.value.code=='checkpoint_not_ready' and adapter._engine is None
    await adapter.stop()


def test_host_declared_defaults_and_flat_seed():
    declared={'resolution':'512x512','ratio':'1:1','framespersecond':25,'preset':'standard','seed':42,'output_format':'mp4','audio_output_mode':'preserve_driving_audio'}
    assert inputs(request(declared))[2]['seed']==42
    req=request();req.payload.pop('parameters');req.payload['seed']=7
    assert inputs(req)[2]['seed']==7


@pytest.mark.parametrize('values',[{'resolution':'1024x1024'},{'audio_output_mode':'generate_audio'},{'ratio':'16:9'},{'output_format':'gif'}])
def test_unsupported_host_defaults(values):
    with pytest.raises(ValueError):inputs(request(values))


def test_fast_preset_is_preserved():
    assert inputs(request({'preset':'fast'}))[2]['preset']=='fast'


def test_host_top_level_controls_with_nested_parameters():
    params=inputs(request({'seed':7},preset='fast',duration=6.4,
        resolution='512x512',audio_output_mode='preserve_driving_audio'))[2]
    assert params['preset']=='fast' and params['seconds']==6.4 and params['seed']==7


@pytest.mark.parametrize('nested,host',[
    ({'preset':'standard'},{'preset':'fast'}),
    ({'duration':2},{'duration':3}),
    ({'seconds':2},{'duration':3}),
    ({},{'resolution':'768x768'}),
    ({},{'audio_output_mode':'none'}),
])
def test_conflicting_or_unsupported_top_level_controls(nested,host):
    with pytest.raises(ValueError):inputs(request(nested,**host))
