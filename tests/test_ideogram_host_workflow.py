import asyncio,json,sys
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'spark'))
from ideogram_host_workflow import IdeogramHostWorkflow,CaptionWorkflowError


def workflow(invocation,release):
 return IdeogramHostWorkflow(invocation,caption_model='qwen',image_model='ideogram',build_messages=lambda p,a:[{'role':'user','content':p}],normalize_caption=lambda s:s,verify_caption=lambda v:[] if v.get('scene') else ['missing scene'],release_idle=release)


def test_identity_order_and_failed_caption_never_starts_image():
 async def run():
  calls=[];context=object()
  class Invocation:
   async def invoke_foreground_json(self,model,op,payload,**kwargs):
    assert kwargs['context'] is context
    calls.append((model,op,kwargs['request_id']))
    if model=='qwen':return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}).encode())
    raise AssertionError('image must not start')
  async def release(model):calls.append(('release',model))
  with pytest.raises(CaptionWorkflowError,match='did not finish'):
   await workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='request',context=context)
  assert len(calls)==2 and calls[-1]==('release','qwen')
 asyncio.run(run())


def test_cancel_retries_before_registration_and_waits_for_cleanup():
 async def run():
  active=asyncio.Event();finish=asyncio.Event();calls=[]
  class Invocation:
   async def invoke_foreground_json(self,model,op,payload,**kwargs):
    calls.append(('invoke',model));active.set();await finish.wait()
    return NS(status_code=499,body=b'cancelled')
   async def cancel_request(self,model,request,**kwargs):
    calls.append(('cancel',model))
    if calls.count(('cancel',model))==2:finish.set()
  async def release(model):
   assert finish.is_set();calls.append(('release',model))
  work=asyncio.create_task(workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='cancel',context=object()))
  await active.wait();work.cancel()
  with pytest.raises(asyncio.CancelledError):await work
  assert calls.count(('cancel','qwen'))==2 and calls[-1]==('release','qwen')
  assert ('invoke','ideogram') not in calls
 asyncio.run(run())


def test_caption_released_before_image_and_context_preserved():
 async def run():
  calls=[];context=object();response=NS(status_code=200,body=b'image')
  class Invocation:
   async def invoke_foreground_json(self,model,op,payload,**kwargs):
    assert kwargs['context'] is context;calls.append(('invoke',model))
    if model=='qwen':return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"scene":"teapot"}'}}]}).encode())
    assert calls[-2]==('release','qwen') and json.loads(payload['prompt'])['scene']=='teapot'
    return response
  async def release(model):calls.append(('release',model))
  result=await workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='ok',context=context)
  assert result is response and calls[-1]==('release','ideogram')
 asyncio.run(run())


def test_duplicate_caption_rejected_before_normalization():
 async def run():
  class Invocation:
   async def invoke_foreground_json(self,model,*args,**kwargs):
    assert model=='qwen'
    return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"scene":"good","scene":"bad"}'}}]}).encode())
  async def release(model):pass
  with pytest.raises(CaptionWorkflowError,match='Invalid caption response'):
   await workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='duplicate',context=object())
 asyncio.run(run())


def test_cancel_during_caption_release_joins_and_skips_image():
 async def run():
  entered=asyncio.Event();finish=asyncio.Event();calls=[]
  class Invocation:
   async def invoke_foreground_json(self,model,*args,**kwargs):
    calls.append(model)
    return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"scene":"teapot"}'}}]}).encode())
  async def release(model):
   entered.set();await finish.wait();calls.append('released')
  task=asyncio.create_task(workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='release',context=object()))
  await entered.wait();task.cancel();await asyncio.sleep(0);assert not task.done()
  finish.set()
  with pytest.raises(asyncio.CancelledError):await task
  assert calls==['qwen','released']
 asyncio.run(run())


def test_structured_prompt_preserved_without_caption_model():
 async def run():
  prompt='{"scene": "teapot"}';calls=[]
  class Invocation:
   async def invoke_foreground_json(self,model,op,payload,**kwargs):
    assert model=='ideogram' and payload['prompt']==prompt;calls.append(model)
    return NS(status_code=200,body=b'image')
  async def release(model):calls.append('released')
  await workflow(Invocation(),release).generate({'prompt':prompt},request_id='structured',context=object())
  assert calls==['ideogram','released']
 asyncio.run(run())


def test_image_cancel_keeps_lease_until_worker_finishes_and_releases():
 async def run():
  entered=asyncio.Event();finished=asyncio.Event();calls=[]
  class Invocation:
   async def invoke_foreground_json(self,model,op,payload,**kwargs):
    calls.append(('invoke',model))
    if model=='qwen':
     return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"scene":"teapot"}'}}]}).encode())
    entered.set();await finished.wait();calls.append(('finished',model))
    return NS(status_code=499,body=b'cancelled')
   async def cancel_request(self,model,request,**kwargs):
    assert model=='ideogram' and request.endswith('-image')
    calls.append(('cancel',model));finished.set()
  async def release(model):
   if model=='ideogram':assert ('finished',model) in calls
   calls.append(('release',model))
  task=asyncio.create_task(workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='image-cancel',context=object()))
  await entered.wait();task.cancel()
  with pytest.raises(asyncio.CancelledError):await task
  assert calls==[('invoke','qwen'),('release','qwen'),('invoke','ideogram'),('cancel','ideogram'),('finished','ideogram'),('release','ideogram')]
 asyncio.run(run())


def test_idle_release_refusal_prevents_next_stage():
 async def run():
  calls=[]
  class Invocation:
   async def invoke_foreground_json(self,model,*args,**kwargs):
    calls.append(model)
    return NS(status_code=200,body=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{"scene":"teapot"}'}}]}).encode())
  async def release(model):raise RuntimeError('worker_busy')
  with pytest.raises(RuntimeError,match='worker_busy'):
   await workflow(Invocation(),release).generate({'prompt':'teapot'},request_id='busy',context=object())
  assert calls==['qwen']
 asyncio.run(run())


def test_real_host_queued_cancel_never_starts_or_reclaims_worker(monkeypatch):
 async def run():
  from ai2apps.model_invocation import ModelInvocationService,ModelInvocationContext
  from ai2apps.model_providers import PackageModel
  from ai2apps.worker_scheduler import WorkerJobScheduler,WorkloadClass
  scheduler=WorkerJobScheduler()
  blocker=await scheduler.acquire('qwen-service',WorkloadClass.LOCAL_FOREGROUND,request_id='other-request',actor_id='other-user')
  model=PackageModel(id='qwen',display_name='Qwen',model_type='vlm',upstream_id='upstream',capabilities=('conversation',),endpoints={'chat_completions':'/v1/chat/completions'},context_window=8192,metadata={},audio_capabilities=None,video_capabilities=None,image_capabilities=None,service_key='qwen-service',provider_key='qwen-service',endpoint=None,scheduler=scheduler)
  class Invocation(ModelInvocationService):
   def model(self,identity):
    assert identity=='qwen';return model
  async def forbidden(*args,**kwargs):raise AssertionError('Queued cancelled work must not start a Worker')
  monkeypatch.setattr('ai2apps.model_providers._ensure_package_model_ready',forbidden)
  async def release(model):raise AssertionError('Queued work must not reclaim another request\'s Worker')
  context=ModelInvocationContext(actor_user_id='alice',consumer_app_id='studio',session_id='session-a',installation_id='fixture',organization_id='fixture',billing_account_id='fixture',membership_epoch=1,authentication_type='fixture')
  task=asyncio.create_task(workflow(Invocation(NS()),release).generate({'prompt':'teapot'},request_id='queued-cancel',context=context))
  for _ in range(50):
   if (await scheduler.snapshot())['queued']==1:break
   await asyncio.sleep(0)
  else:raise AssertionError('Not queued')
  task.cancel()
  with pytest.raises(asyncio.CancelledError):await asyncio.wait_for(task,1)
  state=await scheduler.snapshot()
  assert state['running']==1 and state['queued']==0 and state['cancelled']==1 and state['failed']==0
  await blocker.release()
 asyncio.run(run())
