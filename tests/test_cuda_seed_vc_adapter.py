import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from cuda_seed_vc_adapter import CudaSeedVCAdapter,MODEL_ID,CHECKPOINT
from ai2apps.model_worker import ModelWorkerError

@pytest.mark.asyncio
@pytest.mark.parametrize('identity',[MODEL_ID,CHECKPOINT[0]])
async def test_identity_retains_revision_gate(identity):
 adapter=CudaSeedVCAdapter(SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=Path('/unused'),repo_id=CHECKPOINT[0],revision='bad')))
 with pytest.raises(ModelWorkerError) as error:
  await adapter.invoke(SimpleNamespace(request_id='x',operation='audio_process',payload={'model':identity}))
 assert error.value.code=='model_not_supported' and adapter.pipeline is None

@pytest.mark.asyncio
@pytest.mark.parametrize('payload',[{'profile':'unknown'},{'profile':['voice_quality']},{'diffusion_steps':1.5},{'guidance_similarity':float('nan')},{'seed':True},{'length_adjust':0},{'mode':'unknown'}])
async def test_controls_rejected_before_model_loading(payload):
 adapter=CudaSeedVCAdapter(SimpleNamespace(checkpoint_for=lambda _:SimpleNamespace(path=Path('/unused'),repo_id=CHECKPOINT[0],revision=CHECKPOINT[1])))
 with pytest.raises(ModelWorkerError) as error:
  await adapter.invoke(SimpleNamespace(request_id='x',operation='audio_process',payload={'model':MODEL_ID,**payload}))
 assert error.value.code=='invalid_request' and adapter.pipeline is None and not adapter.events
