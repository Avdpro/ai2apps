import asyncio
import importlib.util
import threading
from pathlib import Path
import pytest
import yaml
from ai2apps.model_providers import validate_package_models
from ai2apps.model_worker.protocol import ModelWorkerContext,ModelWorkerCheckpoint,ModelWorkerRequest,ModelWorkerError
ROOT=Path(__file__).resolve().parents[1]/'packages/ai2apps-model-yue2-mlx'
def setup(tmp_path,vae=True):
 manifest=yaml.safe_load((ROOT/'service.yaml').read_text());models=validate_package_models(manifest['id'],manifest['models'],runtime_mode='managed_process',protocol='ai2apps-model-worker/v1')
 spec=importlib.util.spec_from_file_location('test_yue2_adapter',ROOT/'src/worker_adapter.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 checkpoints=tuple(ModelWorkerCheckpoint(m['id'],m['upstream_id'],'huggingface','test/model','a'*40,tmp_path,{}) for m in models if vae or not m['metadata'].get('internal'))
 return module,ModelWorkerContext(manifest['id'],ROOT,tmp_path,models,checkpoints)
def request(tmp_path,**changes):
 p={'schema':'ai2apps.audio-generation/v2','duration_mode':'auto','model':'ai2apps.model.yue2-mlx/default','task':'music','prompt':'Piano','lyrics':'Hello','generation':{'planning_mode':'full','max_semantic_tokens':250}};p.update(changes)
 return ModelWorkerRequest('audio_generate',p,'qa-request',output_root=tmp_path)
@pytest.mark.asyncio
async def test_both_checkpoints_and_workflow_required(tmp_path):
 module,context=setup(tmp_path,vae=False);adapter=module.AudioAdapter(context)
 with pytest.raises(ModelWorkerError) as e:await adapter.invoke(request(tmp_path))
 assert e.value.code=='checkpoint_not_ready'
 module,context=setup(tmp_path);adapter=module.AudioAdapter(context)
 for change in [{'generation':{'max_semantic_tokens':3001}}, {'schema':'ai2apps.audio-generation/v1','duration_mode':'fixed','duration':10}, {'model':'ai2apps.model.yue2-mlx/vae'}, {'generation':{'planning_mode':'off','abc':'X:1','max_semantic_tokens':250}}]:
  with pytest.raises(ModelWorkerError):await adapter.invoke(request(tmp_path,**change))
@pytest.mark.asyncio
async def test_cancel_joins_and_next_request_works(tmp_path):
 module,context=setup(tmp_path);started=threading.Event();exited=threading.Event()
 def engine(checkpoints,config,payload,output,check,report):
  assert len(checkpoints)==2;started.set()
  try:
   while not exited.wait(.002):check()
  finally:exited.set()
 adapter=module.AudioAdapter(context,engine=engine);job=asyncio.create_task(adapter.invoke(request(tmp_path)))
 assert await asyncio.to_thread(started.wait,2);job.cancel()
 with pytest.raises(asyncio.CancelledError):await job
 assert exited.is_set() and not adapter.tokens
 adapter.engine=lambda checkpoints,config,payload,output,check,report:output.write_bytes(b'RIFF-test')
 assert (await adapter.invoke(request(tmp_path))).path.read_bytes()==b'RIFF-test'
 await adapter.stop()
@pytest.mark.asyncio
async def test_early_cancel_never_invokes_engine(tmp_path):
 module,context=setup(tmp_path)
 def engine(*args):raise AssertionError('Cancelled request entered engine')
 adapter=module.AudioAdapter(context,engine=engine);adapter.cancel('qa-request')
 with pytest.raises(ModelWorkerError) as e:await adapter.invoke(request(tmp_path))
 assert e.value.status_code==499 and not adapter.tokens
