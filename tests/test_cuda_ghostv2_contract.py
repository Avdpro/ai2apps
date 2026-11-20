from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'spark'))
from cuda_ghostv2_contract import MODEL,BINDINGS,host_roots,parse_request
from ai2apps.model_worker import ModelWorkerError


def req(**parameters):
    return SimpleNamespace(operation='video_generation',payload={'model':MODEL,'parameters':parameters},part=lambda n:SimpleNamespace(path=Path('/transport')/n))


@pytest.mark.parametrize('field,value',[('batch_size',True),('batch_size',1.5),('detection_interval','4'),('track_id',False),('track_id',1.5),('velocity_smoothing',float('nan')),('velocity_smoothing',True),('restoration','false'),('precision','int8'),('audio_output_mode','speech')])
def test_invalid_controls(field,value):
    with pytest.raises(ModelWorkerError) as caught:parse_request(req(**{field:value}))
    assert caught.value.status_code==400


def test_transport_roles_no_paths():
    r=req();r.payload['inputs']={'reference_image':{'path':'/tmp/private'}}
    with pytest.raises(ModelWorkerError):parse_request(r)
    r.payload['inputs']={'reference_image':{'part_name':'portrait'},'source_video':{'part_name':'movie'}}
    src,target,options=parse_request(r)
    assert src.path.name=='portrait' and target.path.name=='movie' and options['audio_mode']=='auto'


def test_exact_binding_not_upstream_alias_and_duplicates(tmp_path):
    records=[SimpleNamespace(model_id=v,path=tmp_path,upstream_id='shared-upstream') for v in BINDINGS.values()]
    context=SimpleNamespace(checkpoints=records)
    assert set(host_roots(context))==set(BINDINGS)
    context.checkpoints=records+[records[0]]
    with pytest.raises(ModelWorkerError):host_roots(context)
    context.checkpoints=[SimpleNamespace(model_id='other',path=tmp_path,upstream_id=MODEL)]+records[1:]
    with pytest.raises(ModelWorkerError):host_roots(context)


def test_image_rejects_video_controls_and_unknown_model():
    r=req(track_id=1);r.operation='image_edit'
    with pytest.raises(ModelWorkerError):parse_request(r)
    r=req();r.payload['model']='untrusted/model'
    with pytest.raises(ModelWorkerError) as caught:parse_request(r)
    assert caught.value.status_code==404


def test_http_multipart_json_and_transport_markers():
    r=req();r.parts={'identity':object(),'target':object()}
    r.payload.update(parameters='{"batch_size":4}',identity={'part':'identity'},target={'part':'target'})
    assert parse_request(r)[2]['batch_size']==4
    r.payload['identity']={'path':'/tmp/file'}
    with pytest.raises(ModelWorkerError):parse_request(r)
    del r.payload['identity'];r.payload['parameters']='null'
    with pytest.raises(ModelWorkerError):parse_request(r)


def test_host_upstream_alias_does_not_change_checkpoint_identity():
    from cuda_ghostv2_contract import UPSTREAM_MODEL
    r=req();r.payload['model']=UPSTREAM_MODEL
    assert parse_request(r)[2]['precision']=='fp16'
    assert BINDINGS['generator']==MODEL
    r.payload['model']='Avdpro/MLX-GhostV2'
    with pytest.raises(ModelWorkerError) as caught:parse_request(r)
    assert caught.value.status_code==404


def task_request(**fields):
    r=req()
    r.payload.update(reference_parts=[{'kind':'image','part_name':'reference_00_image'}],
                     resolution='source',ratio='source',preset='quality',fast=False,fast_max=False,
                     output_format='mp4',audio_output_mode='auto',**fields)
    return r


def test_durable_task_roles_and_presets():
    r=task_request();a,b,opts=parse_request(r)
    assert (a.path.name,b.path.name)==('reference_00_image','source_video')
    assert opts['batch_size']==2 and opts['detection_interval']==1
    r.payload['preset']='fast_export'
    assert parse_request(r)[2]['detection_interval']==4
    assert parse_request(r)[2]['batch_size']==8
    r.payload['parameters']={'batch_size':3}
    assert parse_request(r)[2]['batch_size']==3


@pytest.mark.parametrize('field,value', [('reference_parts',[]),('reference_parts',[{'kind':'video','part_name':'reference_00_video'}]),('inputs',{'source_video':{'part_name':'other'}}),('resolution','512x512'),('preset','fast'),('fast',True),('metadata','not-an-object'),('fps',float('nan')),('fps',True),('duration',1)])
def test_durable_invalid_controls(field,value):
    r=task_request();r.payload[field]=value
    with pytest.raises(ModelWorkerError) as caught:parse_request(r)
    assert caught.value.status_code==400


def test_task_metadata_from_multipart_and_conflicting_controls():
    r=task_request();r.payload['metadata']='{"retry_of":"task-id"}'
    assert parse_request(r)[2]['batch_size']==2
    r.payload['parameters']={'output_format':'mp4'}
    with pytest.raises(ModelWorkerError):parse_request(r)


def test_optional_occlusion_requires_exact_additional_host_binding(tmp_path):
    records=[SimpleNamespace(model_id=v,path=tmp_path) for v in BINDINGS.values()]
    context=SimpleNamespace(checkpoints=records)
    assert 'occlusion' not in host_roots(context)
    with pytest.raises(ModelWorkerError) as caught:host_roots(context,occlusion=True)
    assert caught.value.status_code==503
    records.append(SimpleNamespace(model_id='ai2apps.model.face-swap-cuda/occlusion',path=tmp_path))
    assert host_roots(context,occlusion=True)['occlusion']==tmp_path
    assert parse_request(req(occlusion=True))[2]['occlusion'] is True
    assert parse_request(req())[2]['occlusion'] is False
    with pytest.raises(ModelWorkerError):parse_request(req(occlusion='true'))
