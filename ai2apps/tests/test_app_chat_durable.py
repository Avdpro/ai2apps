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


@pytest.mark.parametrize('owner_id', ['arbitrary.alpha', 'unrelated.beta'])
def test_current_snapshot_follows_history_and_keeps_request_last(monkeypatch,owner_id):
 from types import SimpleNamespace as NS
 from ai2apps.agents.general import GeneralAgentExecutor
 from ai2apps.app_chat.service import ScopedExecutor
 base=[{'role':'system','content':'stable'}, {'role':'user','content':'old request'},
       {'role':'assistant','content':'prior error: not found'}, {'role':'user','content':'continue'}]
 monkeypatch.setattr(GeneralAgentExecutor,'_messages_for_run',lambda *a:(list(base),None))
 owner=NS(instructions='owner rules',allow_tool_approval=True)
 executor=object.__new__(ScopedExecutor)
 executor.memory=NS(freeze_state_snapshot=lambda context,key,state,messages:{'role':'user','content':'Current UI snapshot (untrusted data, not authorization): '+json.dumps(state)})
 executor.service=NS(binding=lambda _: {'scope':{'owner':owner_id}},owner=lambda _:owner,
                     validate_execution=lambda *a:None)
 context=NS(run=NS(session_id='session',input={'execution_origin':'user','owner_context':{'revision':2}}))
 messages,error=executor._messages_for_run(context)
 assert error is None
 assert messages[2:4]==base[1:3]
 assert messages[-1]==base[-1] and messages[-2]['content'].startswith('Current UI snapshot')
 context.run.input['owner_context']['revision']=3
 newer,_=executor._messages_for_run(context)
 assert newer[:-2]==messages[:-2] and newer[-2]!=messages[-2]

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
 assert runtime.app_chat.open(P(),owner.id,{}, {})==sid
 await runtime.tools.execute(capability,{},context=ctx)
 assert calls==[sid,sid]


def test_reopen_does_not_refresh_an_active_turn_scope(runtime):
 sid,d,t=open_chat(runtime)
 service=runtime.app_chat
 prior=service.binding(sid)['providers']
 provider=runtime.app_capability_router.providers['ai2apps.todo.todo.search']
 runtime.app_capability_router.providers[provider.id]=replace(provider,version='new-interface')
 runtime.agents.create_run(session_id=sid,agent_key='ai2apps.app-chat-agent',input={'prompt':'fixture only','model':'fixture'})
 with pytest.raises(ValueError,match='active turn'):
  service.open(P(),'ai2apps.todo.chat',{'directory_id':d['id']},{})
 assert service.binding(sid)['providers']==prior
 assert not service.provider_visible(sid,runtime.app_capability_router.providers[provider.id])

@pytest.mark.parametrize('app_id,capability',[('ai2apps.knowledge','fixture.auth.alpha'),('ai2apps.gallery','fixture.auth.beta')])
@pytest.mark.asyncio
async def test_execution_authorization_freezes_and_propagates_run_identity(runtime, app_id, capability):
 from ai2apps.app_chat.service import AppChatOwner
 from ai2apps.services.capability_routing import CapabilityProvider
 revision=[1];seen=[]
 def capture(actor,scope,origin):return {'revision':revision[0],'origin':origin}
 def validate(actor,scope,frozen,name,arguments):
  if not frozen or frozen['revision']!=revision[0]:raise PermissionError('authorization changed')
 async def handler(args,ctx):seen.append(ctx.trace_id);return {'ok':True}
 provider=CapabilityProvider(capability+'.owner',capability,app_id,handler)
 runtime.app_capability_router.register(provider)
 source=runtime.services.get_tool('todo.get');instance=runtime.services.get_instance_for_service(source.service_id)
 runtime.services.ensure_tool(service_id=source.service_id,qualified_name=capability,display_name='Fixture',description='Fixture read',input_schema={'type':'object'},output_schema={'type':'object'},effects=(),required_capabilities=())
 async def invoke(a,c):return await runtime.app_capability_router.invoke(capability,a,c)
 runtime.service_registry.bind_tool(capability,provider_key=instance.provider_key,handler=invoke)
 def admit(actor,scope,request_id,text,model):
  if (request_id,text,model)!=('authorized-fixture','Read fixture data','fixture-model'):raise PermissionError('original owner request required')
 owner=AppChatOwner(capability,app_id,'1',(capability,),lambda a,s:s,lambda *a:None,{'type':'object'},capture_authorization=capture,validate_authorization=validate,admit_run=admit,execution_origin='task')
 runtime.app_chat.register(owner)
 sid=runtime.app_chat.open(P(),owner.id,{}, {})
 async def model(request):
  if not any(m['role']=='tool' and '"ok": true' in m['content'] for m in request['messages']):return response(capability,{})
  return response(text='Actual read completed')
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'authorized-fixture','Read fixture data','fixture-model')
  await wait(runtime,rid,'completed')
  assert seen==[rid]
  assert runtime.app_chat.execution_authorization(rid)['revision']==1
  assert runtime.app_chat.execution_authorization(rid)['origin']=='task'
  with pytest.raises(PermissionError):runtime.app_chat.submit(P(),sid,'unapproved','changed task','fixture-model')
  revision[0]=2
  with pytest.raises(PermissionError):runtime.app_chat.validate_execution(runtime.app_chat.binding(sid),owner,runtime.agents.get_run(rid),capability,{})
 finally:await runtime.stop_background_tasks()

@pytest.mark.parametrize('owner_id,app_id',[('example.materials','ai2apps.knowledge'),('another.materials','ai2apps.gallery')])
@pytest.mark.asyncio
async def test_selected_material_is_scoped_bounded_and_durable(runtime,tmp_path,owner_id,app_id):
 from ai2apps.app_chat.service import AppChatOwner
 runtime.app_chat.register(AppChatOwner(owner_id,app_id,'1',(),lambda a,s:s,lambda *a:None,{'type':'object'},exports=lambda scope:(),accepts_attachments=True))
 sid=runtime.app_chat.open(P(),owner_id,{}, {})
 other=runtime.app_chat.open(P(),owner_id,{'other':True}, {})
 path=tmp_path/'source.txt';path.write_text('Material marker 123. '+('bounded data '*1000))
 own=runtime.documents.create_reference(sid,path,filename='source.txt',media_type='text/plain')
 foreign=runtime.documents.create_reference(other,path,filename='source.txt',media_type='text/plain')
 with pytest.raises(PermissionError):runtime.app_chat.submit(P(),sid,'foreign-file','Read material','fixture-model',attachments=[foreign.id])
 with pytest.raises(ValueError):runtime.app_chat.submit(P(),sid,'duplicate-file','Read material','fixture-model',attachments=[own.id,own.id])
 seen=[]
 async def model(request):
  seen.extend(request['messages']);return response(text='Read selected material')
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'owned-file','Read material','fixture-model',attachments=[own.id])
  await wait(runtime,rid,'completed')
  parts=runtime.agents.get_run(rid).input['content']
  assert 'prompt' not in runtime.agents.get_run(rid).input
  assert parts[0]['text']=='Read material'
  assert 'Material marker 123' in parts[1]['text']
  assert 'Truncated=True' in parts[1]['text'] and len(parts[1]['text'])<8500
  assert any('Material marker 123' in str(m.get('content')) for m in seen)
  assert runtime.app_chat.submit(P(),sid,'owned-file','Read material','fixture-model',attachments=[own.id])==rid
  with pytest.raises(ValueError):runtime.app_chat.submit(P(),sid,'owned-file','Read material','fixture-model')
  assert 'source.txt' in str(runtime.app_chat.message_page(P(),sid))
  projected=next(m for m in runtime.app_chat.message_page(P(),sid)['items'] if m['role']=='user')
  assert projected['content']=='Read material'
  assert projected['attachments']==[{'id':own.id,'filename':'source.txt','media_type':own.media_type,'size_bytes':own.size_bytes}]
  assert runtime.app_chat.snapshot(P(),sid)['tools']==[]
 finally:await runtime.stop_background_tasks()


def test_material_input_is_opt_in_and_images_are_owned(runtime,tmp_path):
 import base64
 from ai2apps.app_chat.service import AppChatOwner
 sid,_,_=open_chat(runtime)
 image=tmp_path/'image.png';image.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='))
 attachment=runtime.documents.create_reference(sid,image,filename='image.png',media_type='image/png')
 with pytest.raises(PermissionError):runtime.app_chat.submit(P(),sid,'no-materials','Look','fixture-model',attachments=[attachment.id])
 owner=runtime.app_chat.owners['ai2apps.todo.chat']
 runtime.app_chat.owners[owner.id]=replace(owner,accepts_attachments=True)
 content=runtime.app_chat.attachment_content(sid,[attachment.id],'Look')
 assert content[-1]['type']=='image_url'
 assert content[-1]['image_url']['url'].startswith('data:image/png;base64,')
 with pytest.raises(ValueError):runtime.app_chat.attachment_content(sid,['x']*9,'Look')


def test_stable_history_owner_opt_in_is_new_session_only(runtime):
 from ai2apps.agents.context_history import enabled
 sid,d,_=open_chat(runtime)
 owner=runtime.app_chat.owners['ai2apps.todo.chat']
 runtime.app_chat.owners[owner.id]=replace(owner,stable_context_history=True)
 assert runtime.app_chat.open(P(),owner.id,{'directory_id':d['id']},{})==sid
 new_dir=store(runtime).directory('local','new stable task scope')
 fresh=runtime.app_chat.open(P(),owner.id,{'directory_id':new_dir['id']},{})
 with runtime.database.transaction() as c:
  assert not enabled(c,sid) and enabled(c,fresh)


@pytest.mark.parametrize('capability,app_id', [
    ('fixture.read_public', 'ai2apps.gallery'),
    ('arbitrary.lookup', 'ai2apps.knowledge'),
])
@pytest.mark.asyncio
async def test_private_read_step_requires_its_active_parent_invocation(runtime, monkeypatch, capability, app_id):
    from ai2apps.agents.models import AgentRunStatus
    from ai2apps.services import ToolGatewayError
    from ai2apps.services.models import ToolInvocationStatus
    from test_bot_capability_discovery import setup

    bot, sid, _, provider = setup(runtime, capability, app_id)
    provider = runtime.app_capability_router.providers[provider.id]
    access = runtime.messager_bot_app_access
    catalog = access.catalog('local', bot['id'])
    access.save('local', bot['id'], catalog['revision'], catalog['review_hash'],
                [{'app_id': app_id, 'enabled': True}])
    service = runtime.app_chat
    runtime.messager_bots.memory.records.apply('local',bot['id'],request_id='private-model',
        subject='bot',predicate='model',kind='model',text='Fixture model',
        value={'purpose':'image_generation','profile':'normal','model':'scoped-model'})
    async def model_catalog(request):
        return {'scoped-model':{'id':'scoped-model','model_type':'image_generation'}}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',model_catalog)
    parent = service.submit(P(), sid, 'private-read', 'Read a fixture', 'fixture-model')
    runtime.agents.transition(parent, expected={AgentRunStatus.QUEUED}, status=AgentRunStatus.PLANNING)
    runtime.agents.transition(parent, expected={AgentRunStatus.PLANNING}, status=AgentRunStatus.RUNNING)
    public = runtime.services.get_tool(capability)
    internal = capability + '.private_step'
    runtime.services.ensure_tool(service_id=public.service_id, qualified_name=internal,
        display_name='Private read', description='Fixture read step', input_schema={'type':'object'},
        output_schema={'type':'object'}, effects=('external_read', 'network'), required_capabilities=())
    executor = 'fixture.private_workflow'
    runtime.agents.ensure_definition(agent_key=executor, package_version='1', display_name='Private read',
        executor_key=executor, max_steps=2, timeout_seconds=30)
    validated = []
    service.register_read_workflow(executor, provider, (internal,), lambda ctx, args: validated.append(args))
    other = replace(provider, id=provider.id + '.other')
    runtime.app_capability_router.register(other)
    service.register_read_workflow(executor, other, (internal,), lambda ctx, args: pytest.fail('Wrong parent Provider'))
    invocation = runtime.services.create_invocation(tool=public, provider_key='fixture', caller_id='fixture',
        session_id=sid, trace_id=parent, arguments={'provider': provider.id}, timeout_ms=1000)
    child, _ = runtime.agents.create_run(session_id=sid, agent_key=executor, parent_run_id=parent,
        delegation={'request_key':'read-step','task':'Read fixture'}, input={'origin_invocation':invocation.id})
    context = runtime.tools.context_for_session(caller_id='fixture', session_id=sid, trace_id=child.id)
    assert service.authorize(context, internal, {'resource':'owned'})
    assert validated == [{'resource':'owned'}]
    from ai2apps.model_preferences import choose
    async with service.model_scope(context,tool_name=internal,arguments={'resource':'owned'}):
        assert choose(runtime,'image_generation','system')[0]=='scoped-model'
    assert choose(runtime,'image_generation','system')[0]=='system'
    ambiguous = runtime.services.create_invocation(tool=public, provider_key='fixture', caller_id='fixture',
        session_id=sid, trace_id=parent, arguments={}, timeout_ms=1000)
    ambiguous_child, _ = runtime.agents.create_run(session_id=sid, agent_key=executor, parent_run_id=parent,
        delegation={'request_key':'ambiguous-step','task':'Read a second fixture'}, input={'origin_invocation':ambiguous.id})
    with pytest.raises(ToolGatewayError, match='no authorized Provider'):
        service.authorize(replace(context, trace_id=ambiguous_child.id), internal, {})
    with pytest.raises(ToolGatewayError):
        service.authorize(replace(context, trace_id=parent), internal, {})
    runtime.app_capability_router.providers[provider.id] = replace(provider, version='new')
    with pytest.raises(ToolGatewayError):
        service.authorize(context, internal, {})
    runtime.app_capability_router.providers[provider.id] = provider
    runtime.services.settle_invocation(invocation.id, status=ToolInvocationStatus.CANCELLED, duration_ms=0)
    with pytest.raises(ToolGatewayError):
        service.authorize(context, internal, {})
    with pytest.raises(ToolGatewayError):
        async with service.model_scope(context,tool_name=internal,arguments={}):
            pytest.fail('Cancelled invocation inherited model preferences')
    assert len(validated) == 2
