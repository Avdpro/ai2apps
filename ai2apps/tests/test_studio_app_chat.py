"""Studio scoped lifecycle tests; no external model calls."""
import asyncio
from dataclasses import replace
import pytest
from ai2apps.identity import RequestPrincipal,IdentityRepository,OrganizationType
from test_app_interactions import runtime
P=RequestPrincipal.legacy_local
CASES=[('ai2apps.imagine-studio','ai2apps.imagine.text-to-image','image.generate'),('ai2apps.video-studio','ai2apps.video.text-to-video','video.generate'),('ai2apps.readaloud','ai2apps.audio.quick-read','voice.quick_read')]
@pytest.fixture(autouse=True)
def identity(runtime):
 IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='test-device',organization_id='local',organization_type=OrganizationType.HOUSEHOLD,core_user_id='local',billing_account_id='local',access_epoch=1)

@pytest.mark.parametrize('app,mini,cap',CASES)
def test_exact_studio_scope(runtime,app,mini,cap):
 s=runtime.app_chat;sid=s.open(P(),app+'.chat',{'mini_app_id':mini},{'miniAppId':mini})
 ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid)
 tools={t.qualified_name for t in runtime.tools.list_tools(ctx,include_requiring_approval=True)}
 assert cap in tools and 'studio.ui' in tools
 assert not {'todo.search','web.fetch','browser.navigate'} & tools
 assert not (set(c[2] for c in CASES)-{cap}) & tools
 assert s.open(P(),app+'.chat',{'mini_app_id':mini},{})==sid
 with pytest.raises(Exception):s.open(P(),app+'.chat',{'mini_app_id':'unregistered.mini'}, {})

@pytest.mark.parametrize('app,mini,cap',CASES)
@pytest.mark.asyncio
async def test_studio_ui_ack_restore(runtime,app,mini,cap):
 s=runtime.app_chat;sid=s.open(P(),app+'.chat',{'mini_app_id':mini},{'miniAppId':mini})
 ui={'miniAppId':mini,'context':{'prompt':'original'}};s.heartbeat(P(),sid,'mount-1234',ui)
 ctx=replace(runtime.tools.context_for_session(caller_id='test',session_id=sid),invocation_id='patch-'+app)
 assert (await runtime.app_capability_router.invoke('studio.ui',{'action':'read'},ctx))['ui']==ui
 values={'text':'updated'} if app=='ai2apps.readaloud' else {'prompt':'updated'}
 op=asyncio.create_task(runtime.app_capability_router.invoke('studio.ui',{'action':'update_draft','values':values},ctx));await asyncio.sleep(.02)
 command=s.snapshot(P(),sid)['commands'][0]
 s.acknowledge(P(),sid,command['id'],'mount-1234',command['revision'],{'updated':True},True)
 assert (await op)['status']=='applied' and not s.snapshot(P(),sid)['commands']
 with pytest.raises(Exception):await runtime.app_capability_router.invoke('studio.ui',{'action':'update_draft','values':{'arbitrary_js':'eval'}},ctx)

@pytest.mark.parametrize('app,mini,cap',CASES)
@pytest.mark.asyncio
async def test_background_run_resumes_same_history_without_confirmation(runtime,app,mini,cap,monkeypatch):
 """Actual scoped scheduler/Gateway; only functional producer/inference is a fixture."""
 import json
 from ai2apps.agents.general import _tool_alias
 from test_app_interactions import wait
 s=runtime.app_chat;sid=s.open(P(),app+'.chat',{'mini_app_id':mini},{'miniAppId':mini})
 entered=asyncio.Event();release=asyncio.Event();calls=[]
 providers=[p for p in runtime.app_capability_router.providers.values() if p.capability==cap and p.mini_app_id==mini]
 async def produce(args,ctx):
  calls.append(ctx.invocation_id);entered.set();await release.wait()
  return {'status':'completed','shared_output':True,'output_id':'fixture-output'}
 for provider in providers:runtime.app_capability_router.providers[provider.id]=replace(provider,handler=produce,prepare=None)
 # Explicit test provider descriptors avoid external model catalog/network access.
 async def describe(*a):return {'effective_schema':{'type':'object'},'selection_required':True}
 for provider in providers:
  current=runtime.app_capability_router.providers[provider.id]
  runtime.app_capability_router.providers[provider.id]=replace(current,describe=describe)
 args={'prompt':'fixture','model':'fixture'} if app!=CASES[2][0] else {'text':'fixture','model_id':'fixture'}
 async def model(request):
  outputs=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
  if any(o.get('status')=='completed' for o in outputs):message={'role':'assistant','content':'后台结果已保存'}
  else:message={'role':'assistant','content':None,'tool_calls':[{'id':'next','type':'function','function':{'name':_tool_alias(cap),'arguments':json.dumps(args)}}]}
  return {'choices':[{'message':message,'finish_reason':'tool_calls' if 'tool_calls' in message else 'stop'}]}
 runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=s.submit(P(),sid,'studio-request-1','Execute fixture','fixture-model')
  await asyncio.wait_for(entered.wait(),15)
  # Browser/HTTP caller is gone. Only the Local Run owns execution.
  assert not runtime.agents.list_interactions(rid)
  release.set();await wait(runtime,rid,'completed')
  assert s.open(P(),app+'.chat',{'mini_app_id':mini},{})==sid
  snap=s.snapshot(P(),sid)
  assert any(m['content']=='后台结果已保存' for m in snap['messages']) and len(calls)==1
  assert snap['runs'][0]['task_id'] and not runtime.agents.list_interactions(rid)
 finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.parametrize('app,mini,cap',CASES)
def test_restores_text_from_multimodal_result(runtime,app,mini,cap):
 from ai2apps.storage import MessagePartInput
 from ai2apps.core import MessageRole
 from ai2apps.storage.repositories import MessageRepository
 sid=runtime.app_chat.open(P(),app+'.chat',{'mini_app_id':mini},{})
 MessageRepository(runtime.database).append(session_id=sid,role=MessageRole.ASSISTANT,
  parts=(MessagePartInput(kind='openai_content',content={'content':[
   {'type':'text','text':'结果已进入共享输出'},
   {'type':'image_url','image_url':{'url':'javascript:untrusted'}}]}),))
 restored=runtime.app_chat.snapshot(P(),sid)['messages']
 assert restored[-1]['content']=='结果已进入共享输出'
 assert 'javascript:' not in str(restored)
