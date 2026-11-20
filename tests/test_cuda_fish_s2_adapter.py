import importlib.util
from pathlib import Path
import pytest
from ai2apps.model_worker import ModelWorkerError


def adapter_module():
    path=Path(__file__).resolve().parents[1]/'spark/cuda_fish_s2_adapter.py'
    spec=importlib.util.spec_from_file_location('fish_adapter_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_speaker_identity_reused_and_instructions_wrapped():
    m=adapter_module()
    assert m.prepare_text(['Hello','Hi','Again'],['alice','bob','alice'],'[happy]') == '<|speaker:0|>[happy] Hello <|speaker:1|>[happy] Hi <|speaker:0|>[happy] Again'


@pytest.mark.parametrize('text,voice',[
    (['hello']*6,['a','b','c','d','e','f']),
    (['hello','again'],['a']),
    ('hello','preset'),
    ([''],['a']),
])
def test_invalid_voice_contract_rejected(text,voice):
    with pytest.raises(ModelWorkerError):adapter_module().prepare_text(text,voice,None)


@pytest.mark.parametrize('value',[True,'true','1.0','-1',' 42','４２','12345678901',2**32])
def test_multipart_integer_rejects_invalid_scalars(value):
    with pytest.raises(ModelWorkerError):adapter_module().integer_option(value,42,0,2**32-1,'seed')


@pytest.mark.parametrize('value,expected',[(None,42),('42',42),(42,42),('4294967295',2**32-1),('0',0)])
def test_multipart_integer_preserves_seed(value,expected):
    assert adapter_module().integer_option(value,42,0,2**32-1,'seed')==expected


def test_emotion_and_instruction_tags_survive_official_speaker_boundaries():
    m=adapter_module()
    text=m.prepare_text(['Hello','Hi'],['a','b'],'low voice','excited')
    assert text=='<|speaker:0|>[excited] [low voice] Hello <|speaker:1|>[excited] [low voice] Hi'
    assert m.prepare_text('Hello',None,None,'neutral')=='Hello'
    assert m.prepare_text('Hello',None,None,'sad')=='[sad] Hello'
    with pytest.raises(ModelWorkerError):m.prepare_text('Hello',None,None,'unknown')
