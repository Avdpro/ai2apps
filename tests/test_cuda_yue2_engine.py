import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'spark'))
from cuda_yue2_engine import parameters, generation_settings, CheckedStage, MODEL
from ai2apps.model_worker import ModelWorkerError


def request(**changes):
    data = dict(model=MODEL, schema='ai2apps.audio-generation/v2', task='music',
                prompt='Piano song', lyrics='A new day', duration_mode='auto',
                generation={'max_semantic_tokens':3000})
    data.update(changes)
    return data


@pytest.mark.parametrize('count',[1,199,200,3000])
def test_token_limits_map_valid_minimum(count):
    p=parameters(request(generation={'max_semantic_tokens':count,'max_abc_tokens':1}))
    g=generation_settings(p)
    assert g['semantic']['min_tokens']<=g['semantic']['max_tokens']==count
    assert g['abc']=={'min_tokens':1,'max_tokens':1}
    assert g['ode_steps']==32


@pytest.mark.parametrize('generation',[{}, {'max_semantic_tokens':3001},
    {'max_semantic_tokens':True}, {'max_semantic_tokens':3000,'planning_mode':'off','abc':'X:1'}])
def test_unsupported_contract_rejected(generation):
    with pytest.raises(ModelWorkerError):parameters(request(generation=generation))


def test_alias_and_immutable_payload():
    original=request(model='m-a-p/YuE2-3B')
    assert parameters(original)['model']==MODEL
    assert original['model']=='m-a-p/YuE2-3B'


def test_tile_callback_propagates_cancel_before_next_stage_update():
    updates=[]
    def check():raise InterruptedError('cancel')
    stage=CheckedStage(SimpleNamespace(update=lambda *args:updates.append(args)),check)
    with pytest.raises(InterruptedError):stage.update(1,2)
    assert updates==[]
