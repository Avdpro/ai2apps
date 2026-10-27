"""Real SQLite/Run/Gateway; deterministic model decisions, no external services."""
import asyncio,json
from dataclasses import replace
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.agents.general import _tool_alias
from ai2apps.todo.aaat import store
from test_app_interactions import runtime,wait
P=RequestPrincipal.legacy_local
@pytest.fixture(autouse=True)
def bind_identity(runtime):
 from ai2apps.identity import IdentityRepository,OrganizationType
 IdentityRepository(runtime.database).bind_installation(installation_id='local',cloud_device_id='local-device',organization_id='local',organization_type=OrganizationType.HOUSEHOLD,core_user_id='local',billing_account_id='local',access_epoch=1)


def open_chat(r):
 s=store(r);d=s.directory('local','Chat acceptance');t=s.save('local',{'title':'Bound','directory_id':d['id'],'progress':20,'status':'in_progress'})
 sid=r.app_chat.open(P(),'ai2apps.todo.chat',{'directory_id':d['id']},{'selectedProjectId':t['id']})
 return sid,d,t

def response(name=None,args=None,text=None):
 m={'role':'assistant','content':text}
 if name:m['tool_calls']=[{'id':'call-1','type':'function','function':{'name':_tool_alias(name),'arguments':json.dumps(args or {})}}]
 return {'choices':[{'message':m,'finish_reason':'tool_calls' if name else 'stop'}],'usage':{'total_tokens':10}}

@pytest.mark.asyncio
async def test_query_update_detach_restore_idempotency(runtime):
 sid,d,t=open_chat(runtime);entered=asyncio.Event();release=asyncio.Event()
 async def model(request):
  names={x['function']['name'] for x in request.get('tools',[])}
  assert names<=({_tool_alias(n) for n in runtime.app_chat.owners['ai2apps.todo.chat'].capabilities}|{_tool_alias('agent.ask_user')})
  results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
  success=[r for r in results if 'error' not in r]
  if not success:return response('todo.search',{'progress_gt':10})
  if len(success)==1:return response('todo.update',{'task_id':t['id'],'revision':t['revision'],'patch':{'progress':35}})
  entered.set();await release.wait();return response(text='已查询并修改为35%。')
 runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'request-first','查询并修改当前进度','fixture-model')
  assert runtime.app_chat.submit(P(),sid,'request-first','查询并修改当前进度','fixture-model')==rid
  with pytest.raises(ValueError):runtime.app_chat.submit(P(),sid,'request-first','changed','fixture-model')
  for _ in range(200):
   if entered.is_set():break
   run=runtime.agents.get_run(rid)
   assert run.status.value not in ('failed','waiting_input','waiting_capability'), (run.error,runtime.agents.list_steps(rid))
   await asyncio.sleep(.05)
  assert entered.is_set(),runtime.agents.get_run(rid)
  # No browser/page/subscription owns this operation.
  assert store(runtime).get('local',t['id'])['progress']==35
  release.set();await wait(runtime,rid,'completed')
  assert runtime.app_chat.open(P(),'ai2apps.todo.chat',{'directory_id':d['id']},{})==sid
  snap=runtime.app_chat.snapshot(P(),sid)
  assert any(m['content']=='已查询并修改为35%。' for m in snap['messages'])
  assert len(snap['runs'])==1 and snap['runs'][0]['task_id']
  assert not runtime.agents.list_interactions(rid)
  assert len([s for s in runtime.agents.list_steps(rid) if s.tool_name=='todo.update' and s.status.value=='completed'])==1
 finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_ui_ack_stale_mount_no_replay(runtime):
 sid,d,t=open_chat(runtime);service=runtime.app_chat;ui={'selectedProjectId':t['id']};mount='mount-123456'
 service.heartbeat(P(),sid,mount,ui)
 ctx=replace(runtime.tools.context_for_session(caller_id='test',session_id=sid),invocation_id='ui-invocation')
 operation=asyncio.create_task(service.ui_action(ctx,{'action':'set_search','query':'Bound'}));await asyncio.sleep(.03)
 command=service.snapshot(P(),sid)['commands'][0]
 service.acknowledge(P(),sid,command['id'],mount,command['revision'],{'search':'Bound'},True)
 assert (await operation)['status']=='applied'
 assert service.acknowledge(P(),sid,command['id'],mount,command['revision'],{},True)['status']=='applied'
 assert not service.snapshot(P(),sid)['commands']
 operation=asyncio.create_task(service.ui_action(replace(ctx,invocation_id='ui-stale'),{'action':'set_search','query':'new'}));await asyncio.sleep(.03)
 command=service.snapshot(P(),sid)['commands'][0];service.heartbeat(P(),sid,'new-mount-123',ui)
 service.acknowledge(P(),sid,command['id'],'new-mount-123',command['revision'],{},True)
 with pytest.raises(ValueError,match='not applied'):await operation

@pytest.mark.asyncio
async def test_scope_blocks_foreign_tool_directory_provider_and_metadata(runtime):
 sid,d,t=open_chat(runtime);s=store(runtime);other=s.directory('local','Other');foreign=s.save('local',{'title':'Outside','directory_id':other['id']})
 ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid)
 for name,args in [('knowledge.search',{'query':'x'}),('todo.get',{'task_id':foreign['id']}),('todo.search',{'directory_id':other['id']}),('todo.search',{'provider':'foreign'})]:
  with pytest.raises(Exception):await runtime.tools.execute(name,args,context=ctx)
 with pytest.raises(Exception):await runtime.app_capability_router.invoke('todo.get',{'task_id':foreign['id']},ctx)
 with pytest.raises(Exception):runtime.app_chat.access(replace(P(),actor_user_id='other'),sid)
 from ai2apps.chat import ChatRepository
 ordinary,_=ChatRepository(runtime.database,runtime.events).create_thread(title='fake',metadata={'app_chat':True,'registration':'ai2apps.todo.chat'})
 ordinary_ctx=runtime.tools.context_for_session(caller_id='test',session_id=ordinary.session.id)
 assert runtime.app_chat.authorize(ordinary_ctx,'todo.update',{}) is False

@pytest.mark.parametrize('app_id,capability',[('ai2apps.knowledge','fixture.alpha'),('ai2apps.gallery','fixture.beta')])
@pytest.mark.asyncio
async def test_arbitrary_owner_scope_provider_version(runtime,app_id,capability):
 from ai2apps.app_chat.service import AppChatOwner
 from ai2apps.services.capability_routing import CapabilityProvider
 calls=[]
 async def handler(args,ctx):calls.append(ctx.session_id);return {'ok':True}
 provider=CapabilityProvider(capability+'.owner',capability,app_id,handler);runtime.app_capability_router.register(provider)
 source=runtime.services.get_tool('todo.get');instance=runtime.services.get_instance_for_service(source.service_id)
 runtime.services.ensure_tool(service_id=source.service_id,qualified_name=capability,display_name='Fixture',description='fixture',input_schema={'type':'object'},output_schema={'type':'object'},effects=(),required_capabilities=())
 async def invoke(a,c):return await runtime.app_capability_router.invoke(capability,a,c)
 runtime.service_registry.bind_tool(capability,provider_key=instance.provider_key,handler=invoke)
 owner=AppChatOwner(capability,app_id,'1',(capability,),lambda a,s:s,lambda *a:None,{'type':'object'});runtime.app_chat.register(owner)
 sid=runtime.app_chat.open(P(),owner.id,{},{});ctx=runtime.tools.context_for_session(caller_id='test',session_id=sid)
 await runtime.tools.execute(capability,{},context=ctx)
 assert calls==[sid] and not runtime.app_chat.visible(ctx,'todo.get')
 runtime.app_capability_router.providers[provider.id]=replace(provider,version='2')
 with pytest.raises(Exception):await runtime.tools.execute(capability,{},context=ctx)
 assert calls==[sid]
