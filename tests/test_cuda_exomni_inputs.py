"""Ex-Omni media-only Host input contract, without loading dialogue or CUDA."""
import asyncio
from types import SimpleNamespace
import pytest
from spark.cuda_exomni_adapter import CudaExOmniAdapter, MODEL_ID
from ai2apps.model_worker import ModelWorkerError


def run(tmp_path, payload, helpers=None):
    parts = {k:SimpleNamespace(path=tmp_path/k) for k in ('reference_00_image','audio')}
    checkpoints={MODEL_ID:SimpleNamespace(path=tmp_path/'checkpoint')}
    checkpoints.update({'ai2apps.model.exomni-cuda/'+k:v for k,v in (helpers or {}).items()})
    adapter = CudaExOmniAdapter(SimpleNamespace(checkpoint_for=checkpoints.get))
    async def capture(work): return work
    adapter._owner.invoke=capture
    request=SimpleNamespace(operation='video_generation',payload=payload,output_root=tmp_path,
                            request_id='media-input',part=parts.__getitem__)
    return asyncio.run(adapter.invoke(request))


def standard():
    return {'model':MODEL_ID,'reference_parts':[{'kind':'image','part_name':'reference_00_image'}],
            'prompt':'A speaker smiles.','seed':73,'resolution':'source','ratio':'source',
            'framespersecond':25,'preset':'teacher','output_format':'mp4',
            'audio_output_mode':'preserve_driving_audio'}


def test_standard_host_roles_and_controls(tmp_path):
    work=run(tmp_path,standard())
    assert work.image==tmp_path/'reference_00_image' and work.audio==tmp_path/'audio'
    assert work.seed==73 and work.prompt=='A speaker smiles.'


def test_existing_development_input_preserved(tmp_path):
    work=run(tmp_path,{'inputs':{'reference_image':{'part_name':'reference_00_image'},
         'driving_audio':{'part_name':'audio'}},'parameters':{'seed':18}})
    assert work.seed==18


@pytest.mark.parametrize('change', [
 {'reference_parts':[]},{'reference_parts':[{'kind':'video','part_name':'reference_00_image'}]},
 {'resolution':'512x512'},{'framespersecond':30},{'audio_output_mode':'mute'},
 {'duration':5},{'steps':4},{'width':512},{'preset':'student'},{'seed':True},
])
def test_unsupported_standard_controls_rejected(tmp_path,change):
    with pytest.raises(ModelWorkerError):run(tmp_path,{**standard(),**change})


def test_four_host_roots_and_cache_identity(tmp_path):
    helpers={name:SimpleNamespace(path=tmp_path/name) for name in ('wan','omniavatar','speech_tokenizer')}
    work=run(tmp_path,standard(),helpers)
    assert work.components=={'teacher':tmp_path/'checkpoint',**{name:item.path for name,item in helpers.items()}}
    old=work.checkpoint_identity
    work.components['wan']=tmp_path/'replacement-wan'
    assert work.checkpoint_identity!=old
    assert run(tmp_path,standard()).components is None


@pytest.mark.parametrize('helpers', [{'wan':SimpleNamespace(path='wan')},
    {'wan':SimpleNamespace(path='wan'),'omniavatar':SimpleNamespace(path='base'),'speech_tokenizer':SimpleNamespace(path=None)}])
def test_partial_activation_rejected(tmp_path,helpers):
    with pytest.raises(ModelWorkerError,match='All Teacher component'):
        run(tmp_path,standard(),helpers)


def test_teacher_config_uses_each_exact_host_root(tmp_path):
    import yaml
    from spark.cuda_exomni_engine import teacher_config
    source=tmp_path/'source';(source/'configs').mkdir(parents=True)
    (source/'configs/inference.teacher.example.yaml').write_text(yaml.safe_dump({'video':{'fps':25,'steps':50}}))
    roots={name:tmp_path/name for name in ('teacher','wan','omniavatar','speech_tokenizer')}
    cfg=teacher_config(source,tmp_path/'unused-aggregate',roots)
    assert cfg['lora_checkpoint']==str(roots['teacher']/'video_generator/teacher.safetensors')
    assert cfg['base_checkpoint']==str(roots['omniavatar']/'pytorch_model.pt')
    assert cfg['speech_tokenizer_path']==str(roots['speech_tokenizer'])
    assert cfg['dit_path']==str(roots['wan']/'diffusion_pytorch_model.safetensors')
    assert cfg['fps']==25 and cfg['steps']==50
    with pytest.raises(ValueError,match='All four'):
        teacher_config(source,tmp_path,{})
