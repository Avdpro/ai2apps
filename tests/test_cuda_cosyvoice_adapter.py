import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_cosyvoice_adapter import CudaCosyVoiceAdapter,CudaCosySpeechEngine,MODELS,S3_ID,S3_SPEC
from ai2apps.model_worker import ModelWorkerError


def setup(declared=True,revision=None):
 key=next(iter(MODELS));_,repo,rev=MODELS[key]
 checkpoint=SimpleNamespace(model_id=key,repo_id=repo,revision=rev,path=Path('/tmp/model'))
 s3=SimpleNamespace(repo_id=S3_SPEC[0],revision=revision or S3_SPEC[1],path=Path('/tmp/s3'))
 obj=CudaCosyVoiceAdapter(SimpleNamespace(checkpoint_for=lambda name:s3 if name==S3_ID else None))
 obj.model_declaration=lambda key:{'metadata':{'required_model_ids':[S3_ID] if declared else []}}
 return obj,checkpoint

@pytest.mark.asyncio
async def test_requires_declared_exact_s3():
 for declared,revision in [(False,None),(True,'0'*40)]:
  obj,checkpoint=setup(declared,revision)
  with pytest.raises(ModelWorkerError) as error:await obj.create_engine(checkpoint)
  assert error.value.code=='checkpoint_not_ready'
 obj,checkpoint=setup();engine=await obj.create_engine(checkpoint)
 assert engine.tokenizer_checkpoint.revision==S3_SPEC[1]

@pytest.mark.asyncio
async def test_duplicate_preserves_request_owner():
 obj,_=setup();event=object();obj._cancellations['same']=event
 with pytest.raises(ModelWorkerError) as error:await obj.invoke(SimpleNamespace(request_id='same',payload={}))
 assert error.value.code=='request_conflict' and obj._cancellations['same'] is event

@pytest.mark.asyncio
async def test_stopped_rejects_new_work():
 obj,_=setup();await obj.stop()
 with pytest.raises(ModelWorkerError) as error:await obj.invoke(SimpleNamespace(request_id='new',payload={}))
 assert error.value.code=='worker_stopping'

@pytest.mark.asyncio
async def test_reference_required_before_model_load():
 engine=CudaCosySpeechEngine(None,None)
 with pytest.raises(ModelWorkerError) as error:await engine.synthesize('hello')
 assert error.value.status_code==400 and engine.model is None

@pytest.mark.asyncio
@pytest.mark.parametrize('seed',[True,-1,2**32,'1e3'])
async def test_invalid_seed_before_model_load(seed):
 obj,_=setup()
 with pytest.raises(ModelWorkerError) as error:
  await obj.invoke(SimpleNamespace(request_id='bad',payload={'model':next(iter(MODELS)),'seed':seed}))
 assert error.value.status_code==400

def test_speed_and_emotion_use_mac_qualitative_controls():
 obj,checkpoint=setup()
 result=obj.synthesis_options(checkpoint.model_id,{'seed':7,'language':'zh'},speed=.7,emotion='calm',emotion_strength=1,instructions='Be gentle.')
 assert result=={'speed':1.0,'language':'zh','seed':7,'instructions':'Be gentle. Speak with a calm emotion. Speak much more slowly than normal.'}
