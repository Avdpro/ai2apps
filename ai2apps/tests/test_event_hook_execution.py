"""Real SQLite, Gateway, Task and Run; model and Package catalog are fixtures."""
import asyncio
from dataclasses import replace
import json
import time
import pytest
from ai2apps.events.business import EventType
from ai2apps.events.hooks import ConsumerType,HookError
from ai2apps.events.causality import cause_scope,current_cause
from ai2apps.services.capability_routing import CapabilityProvider
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity,response

@pytest.fixture
def env(runtime):
 r=runtime;h=r.event_hooks;s={'allowed':True,'calls':0,'reads':0};counter=[0]
 cap='sample.record_detail';pid='different.reader.detail'
 definition=EventType('sample.record.changed','independent.owner','Changed','record',
  {'type':'object','properties':{'n':{'type':'integer'}},'required':['n'],'additionalProperties':False},('n',),'fixture',
  lambda actor,subject:actor=='local' and subject=='r1',details=(cap,pid,'1'))
 publisher=r.business_events.register(definition)
 async def read(args,ctx):
  s['reads']+=1;e=r.business_events.read(ctx.actor_user_id,args['event_id']);return {'event_id':e['id'],'n':e['data']['n']}
 r.app_capability_router.register(CapabilityProvider(pid,cap,'different.reader',read,version='1'))
 t=r.services.get_tool('voice.event_details')
 r.services.ensure_tool(service_id=t.service_id,qualified_name=cap,display_name='Detail',description='Fixture detail',
  input_schema={'type':'object','properties':{'event_id':{'type':'string'}}},output_schema={'type':'object'})
 async def routed(args,ctx):return await r.app_capability_router.invoke(cap,args,ctx)
 r.service_registry.bind_tool(cap,provider_key=r.service_registry.bound_tool('voice.event_details').provider_key,handler=routed)
 def validate(actor,b):
  if actor!='local' or b!={'id':'worker'} or not s['allowed']:raise PermissionError('Consumer revoked')
  return dict(b)
 def prepare(actor,b,settings):
  validate(actor,b)
  if settings:raise ValueError('Unknown settings')
  return {}
 async def execute(work,ctx):
  s['calls']+=1;return work.report({'details':await work.details()})
 h.register_consumer(ConsumerType('unrelated.worker','app','ai2apps.intelligence','1',validate,prepare,execute))
 def emit(n=1,cause=None):
  counter[0]+=1
  with cause_scope(cause if cause is not None else current_cause.get()),r.database.transaction(write=True) as db:
   return publisher.publish(db,owner='local',subject_id='r1',occurrence_key=str(counter[0]),data={'n':n})
 def proposal(reg='unrelated.worker'):
  return dict(consumer={'registration':reg,'binding':{'id':'worker'}},event_type=definition.name,subjects=['r1'],filters=[],execution={'settings':{},'expires_in':3600})
 def enable(value=None):
  p=h.preview('local',value or proposal());return h.save('local',p['preview_ref'],'enable-'+str(time.time_ns()))
 return r,h,s,emit,proposal,enable

async def settled(r,rule,state='succeeded'):
 for _ in range(300):
  with r.database.transaction() as db:
   rows=[dict(x) for x in db.execute('SELECT e.* FROM hook_executions e JOIN hook_deliveries d ON d.id=e.delivery_id WHERE d.rule_id=? ORDER BY d.event_sequence',(rule['id'],))]
  if rows and rows[-1]['state']==state:return rows[-1]
  if rows and rows[-1]['state'] in ('failed','suppressed') and rows[-1]['state']!=state:raise AssertionError(rows)
  await asyncio.sleep(.025)
 raise AssertionError(rows)

@pytest.mark.asyncio
async def test_worker_reads_aaat_and_durable_task_receipt(env):
 r,h,s,emit,proposal,enable=env;rule=enable();eid=emit()
 await r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(r,rule);assert json.loads(row['result_json'])['details']['event_id']==eid
  assert s['calls']==s['reads']==1
  with r.database.transaction(write=True) as db:
   assert db.execute('SELECT count(*) FROM system_task_acceptances').fetchone()[0]==1
   db.execute("UPDATE hook_executions SET state='admitting',task_id=NULL WHERE delivery_id=?",(row['delivery_id'],))
  r.hook_execution.admit();h.scan();r.hook_execution.admit()
  assert s['calls']==1 and h.deliveries('local',rule['id'])['items'][0]['executed']
 finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_cycle_blocked_and_new_root_allowed(env):
 r,h,s,emit,proposal,enable=env;rule=enable();emit()
 await r.start_background_tasks(retention_interval_seconds=60)
 try:
  done=await settled(r,rule);cause=r.hook_execution.work(done['delivery_id']).cause
  emit(2,cause);h.scan();r.hook_execution.admit();row=await settled(r,rule,'suppressed');assert row['error']=='rule_reentry'
  emit(3);h.scan();r.hook_execution.admit();await settled(r,rule);assert s['calls']==2
 finally:await r.stop_background_tasks()

@pytest.mark.parametrize('depth,count',[(8,0),(0,20)])
def test_root_budgets(env,depth,count):
 r,h,s,emit,proposal,enable=env;rule=enable();cause={'owner':'local','root_id':'root','depth':depth,'ancestry':[]}
 with r.database.transaction(write=True) as db:
  for i in range(count):db.execute('INSERT INTO hook_root_claims VALUES(?,?,?,?)',('local','root',str(i),'fixture'))
 emit(cause=cause);h.scan();r.hook_execution.admit()
 with r.database.transaction() as db:row=db.execute('SELECT * FROM hook_executions').fetchone()
 assert row['state']=='suppressed' and row['error']=='cause_budget' and s['calls']==0

def test_unknown_cause_and_paused_rule_never_admit(env):
 r,h,s,emit,proposal,enable=env;rule=enable();eid=emit()
 with r.database.transaction(write=True) as db:db.execute('UPDATE business_event_facts SET cause_json=NULL WHERE event_id=?',(eid,))
 h.scan();r.hook_execution.admit()
 with r.database.transaction() as db:assert db.execute('SELECT state FROM hook_executions').fetchone()[0]=='failed'
 emit();h.scan();h.change('local',rule['id'],'pause',1,'pause-rule-1');r.hook_execution.admit()
 with r.database.transaction() as db:assert db.execute('SELECT count(*) FROM system_task_acceptances').fetchone()[0]==0

@pytest.mark.asyncio
async def test_exact_read_scope_cache_and_revocation(env):
 r,h,s,emit,proposal,enable=env;rule=enable();eid=emit();other=emit();h.scan();r.hook_execution.admit()
 with r.database.transaction() as db:delivery=db.execute('SELECT id FROM hook_deliveries ORDER BY event_sequence LIMIT 1').fetchone()[0]
 work=r.hook_execution.work(delivery)
 from ai2apps.system_tasks.sessions import execution_session
 ctx=r.tools.context_for_session(caller_id='fixture',session_id=execution_session(r,'local','ai2apps.intelligence'))
 with cause_scope(work.cause,delivery):
  for name,args in [('intelligence.refresh',{'channel_id':'r1'}),('sample.record_detail',{'event_id':other}),('sample.record_detail',{'event_id':eid,'provider':'other.provider'})]:
   with pytest.raises(Exception):await r.tools.execute(name,args,context=ctx)
  result=await work.details();assert result['event_id']==eid
  assert await work.details()==result and s['reads']==1
  s['allowed']=False
  with pytest.raises(PermissionError):await work.details()

@pytest.mark.asyncio
async def test_tool_budget_and_direct_router_guard(env):
 r,h,s,emit,proposal,enable=env;enable();eid=emit();h.scan();r.hook_execution.admit()
 with r.database.transaction() as db:delivery=db.execute('SELECT id FROM hook_deliveries LIMIT 1').fetchone()[0]
 work=r.hook_execution.work(delivery)
 from ai2apps.system_tasks.sessions import execution_session
 ctx=r.tools.context_for_session(caller_id='fixture',session_id=execution_session(r,'local','ai2apps.intelligence'))
 with cause_scope(work.cause,delivery):
  for i in range(12):await r.tools.execute('sample.record_detail',{'event_id':eid},context=ctx)
  with pytest.raises(Exception):await r.tools.execute('sample.record_detail',{'event_id':eid},context=ctx)
  with pytest.raises(Exception):await r.app_capability_router.invoke('intelligence.refresh',{},ctx)
 with r.database.transaction() as db:assert db.execute("SELECT count(*) FROM hook_steps WHERE step LIKE 'tool:%'").fetchone()[0]==12

def test_expired_delegation(env):
 r,h,s,emit,proposal,enable=env;rule=enable();emit();h.scan();h.clock=lambda:time.time()+4000;r.hook_execution.admit()
 with r.database.transaction() as db:assert db.execute('SELECT state FROM hook_executions').fetchone()[0]=='failed'
 with pytest.raises(HookError):h._validate('local',h.get('local',rule['id'])['revisions'][0]['spec'])

@pytest.mark.asyncio
async def test_bot_actual_turn_with_aaat_details_and_origin(env):
 r,h,s,emit,proposal,enable=env
 from ai2apps.messager.bots import install,REGISTRATION
 install(r);bot=r.messager_bots.create('local','Reviewer','Summarize new records')
 value=proposal('messager.bot.observe');value['consumer']['binding']={'bot_id':bot['id']};value['execution']['settings']={'model':'fixture-model','prompt':'Review this update'}
 rule=enable(value);eid=emit();seen=[]
 async def model(request):
  seen.append(request);assert any(eid in str(m.get('content','')) for m in request['messages'])
  from ai2apps.agents.general import _tool_alias
  assert {t['function']['name'] for t in request.get('tools',[])}<={_tool_alias('agent.ask_user')}
  return response(text='Reviewed record update.')
 r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(r,rule);report=json.loads(row['result_json']);sid=report['session_id']
  snapshot=r.app_chat.snapshot(RequestPrincipal.legacy_local(),sid)
  assert len(snapshot['runs'])==1 and snapshot['runs'][0]['origin']=='hook'
  assert any('Reviewed record' in m['content'] for m in snapshot['messages'])
  assert r.app_chat.open(RequestPrincipal.legacy_local(),REGISTRATION,{'bot_id':bot['id']},{})==sid
  assert s['reads']==1 and len(seen)==1
 finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_messager_app_actual_worker_for_future_voice(runtime):
 from ai2apps.messager.bots import install,APP
 from ai2apps.system_tasks.sessions import execution_session
 from ai2apps.storage.repositories import SessionRepository
 from ai2apps.readaloud.repository import ReadAloudRepository
 from ai2apps.events.builtin import VOICE
 install(runtime);r=runtime
 instance=SessionRepository(r.database).get(execution_session(r,'local',APP)).app_instance_id
 proposal=dict(consumer={'registration':'messager.app.observe','binding':{'app_instance_id':instance}},event_type=VOICE,
  subjects=[],scope='owned_collection',filters=[],execution={'settings':{}})
 p=r.event_hooks.preview('local',proposal);rule=r.event_hooks.save('local',p['preview_ref'],'app-background-1')
 profile=ReadAloudRepository(r.database,r.events).create_voice_profile('local',name='Private voice',source_type='synthetic_designed',model_id=None,provider_voice_id=None,reference_transcript='private text',rights_scope={})
 await r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(r,rule);report=json.loads(row['result_json'])
  assert report['handler']=='event-inbox/v1' and report['details']['profile']['id']==profile['id']
  assert 'private text' not in row['result_json']
 finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_mini_background_without_mount_then_actual_inbox_and_digest_revocation(env,monkeypatch):
 from types import SimpleNamespace
 from ai2apps.studio.event_hooks import REGISTRATION
 from ai2apps.studio.capability_broker import StudioCapabilityBroker
 from ai2apps.system_tasks.sessions import execution_session
 from ai2apps.storage.repositories import SessionRepository
 r,h,s,emit,proposal,enable=env;p=RequestPrincipal.legacy_local()
 instance=SessionRepository(r.database).get(execution_session(r,'local','ai2apps.video-studio')).app_instance_id
 binding={'studio_id':'ai2apps.video-studio','mini_app_id':'fixture.record-watcher','app_id':'ai2apps.video-studio','digest':'fixture-signed-digest','app_instance_id':instance}
 declaration={'id':binding['mini_app_id'],'provider':{'appId':binding['app_id'],'digest':binding['digest']},'requirements':{'capabilities':['events.subscribe','events.background']}}
 monkeypatch.setattr(r.extension_manager,'list_studio_mini_apps',lambda *a,**kw:[declaration])
 value=proposal(REGISTRATION);value['consumer']['binding']=binding;rule=enable(value);eid=emit()
 # No mount exists while the server-side Mini-App handler runs.
 await r.start_background_tasks(retention_interval_seconds=60)
 try:
  row=await settled(r,rule);assert s['reads']==1
  mounted=SimpleNamespace(mount={'app_key':binding['app_id'],'app_instance_id':instance,'effective_digest':binding['digest']},declaration=declaration)
  monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**kw:mounted)
  items=r.mini_app_hooks.inbox(p,binding['studio_id'],'fixture-mount')['items']
  assert len(items)==1 and items[0]['result']['details']['event_id']==eid
  with r.database.transaction(write=True) as db:db.execute('DELETE FROM business_event_facts WHERE event_id=?',(eid,))
  unavailable=r.mini_app_hooks.inbox(p,binding['studio_id'],'fixture-mount')['items'][0]
  assert unavailable['state']=='unavailable' and 'result' not in unavailable
  r.mini_app_hooks.inbox(p,binding['studio_id'],'fixture-mount',ack=row['delivery_id'])
  assert not r.mini_app_hooks.inbox(p,binding['studio_id'],'fixture-mount')['items']
  declaration['provider']['digest']='upgraded-digest'
  with pytest.raises(PermissionError):r.mini_app_hooks.validate('local',binding)
 finally:await r.stop_background_tasks()

def test_background_requires_desktop_role_and_no_arbitrary_settings(env):
 r,h,s,emit,proposal,enable=env
 value=proposal();value['execution']['settings']={'command':'run arbitrary code'}
 with pytest.raises(ValueError):h.preview('local',value)
 value=proposal();value['execution']['expires_in']=604801
 with pytest.raises(HookError):h.preview('local',value)

def test_provider_version_change_fails_closed(env):
 r,h,s,emit,proposal,enable=env;enable();emit();h.scan();r.hook_execution.admit()
 with r.database.transaction() as db:delivery=db.execute('SELECT id FROM hook_deliveries LIMIT 1').fetchone()[0]
 work=r.hook_execution.work(delivery)
 r.app_capability_router.providers['different.reader.detail']=replace(r.app_capability_router.providers['different.reader.detail'],version='2')
 from ai2apps.services import ToolCallContext
 ctx=ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='fixture')
 with cause_scope(work.cause,delivery),pytest.raises(PermissionError):r.hook_execution.authorize(ctx,'sample.record_detail',{'event_id':work.event['id']})

@pytest.mark.asyncio
async def test_two_workers_cannot_form_a_b_a_loop(env):
 r,h,s,emit,proposal,enable=env;base=h.consumers['unrelated.worker']
 async def a(work,ctx):
  await work.details();emit(2);return work.report({'worker':'a'})
 async def b(work,ctx):
  await work.details();emit(1);return work.report({'worker':'b'})
 h.register_consumer(replace(base,id='another.alpha',execute=a));h.register_consumer(replace(base,id='another.beta',execute=b))
 va=proposal('another.alpha');va['filters']=[{'field':'n','op':'eq','value':1}]
 vb=proposal('another.beta');vb['filters']=[{'field':'n','op':'eq','value':2}]
 ra=enable(va);rb=enable(vb);emit(1)
 await r.start_background_tasks(retention_interval_seconds=60)
 try:
  await settled(r,rb);await settled(r,ra,'suppressed')
  with r.database.transaction() as db:
   rows=[tuple(x) for x in db.execute('SELECT state,error FROM hook_executions')]
  assert len(rows)==3 and sum(x[0]=='succeeded' for x in rows)==2 and ('suppressed','rule_reentry') in rows
  assert s['reads']==2
 finally:await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_pausing_active_bot_cancels_original_run_without_new_turn(env):
 r,h,s,emit,proposal,enable=env
 from ai2apps.messager.bots import install
 install(r);bot=r.messager_bots.create('local','Reviewer','Read updates')
 value=proposal('messager.bot.observe');value['consumer']['binding']={'bot_id':bot['id']};value['execution']['settings']={'model':'fixture-model'}
 rule=enable(value);emit();entered=asyncio.Event();release=asyncio.Event()
 async def model(request):entered.set();await release.wait();return response(text='Late result')
 r.agent_runtime.bind_model_provider(model);await r.start_background_tasks(retention_interval_seconds=60)
 try:
  await asyncio.wait_for(entered.wait(),timeout=10)
  with r.database.transaction() as db:rid=db.execute('SELECT run_id FROM hook_run_bindings').fetchone()[0]
  h.change('local',rule['id'],'pause',1,'pause-active-bot')
  await settled(r,rule,'failed')
  assert r.agents.get_run(rid).cancel_requested
  with r.database.transaction() as db:
   assert db.execute('SELECT count(*) FROM hook_run_bindings').fetchone()[0]==1
   assert db.execute('SELECT count(*) FROM hook_reports').fetchone()[0]==0
 finally:release.set();await r.stop_background_tasks()

@pytest.mark.asyncio
async def test_http_background_requires_desktop_and_current_role(env):
 from fastapi import FastAPI
 from httpx import AsyncClient,ASGITransport
 from ai2apps.api.hooks import create_hook_router
 from ai2apps.identity import MemberRole
 r,h,s,emit,proposal,enable=env;current=[RequestPrincipal.legacy_local()]
 app=FastAPI();app.include_router(create_hook_router(lambda:r,lambda:current[0]))
 async with AsyncClient(transport=ASGITransport(app=app),base_url='http://fixture') as client:
  current[0]=replace(current[0],role=MemberRole.MEMBER)
  assert (await client.post('/hooks/preview',json=proposal())).status_code==403
  current[0]=RequestPrincipal.legacy_local()
  preview=(await client.post('/hooks/preview',json=proposal())).json()
  body={'preview_ref':preview['preview_ref'],'request_id':'http-background-1'}
  current[0]=replace(current[0],client_scope='mobile')
  assert (await client.post('/hooks',json=body)).status_code==403
  assert (await client.post('/hooks/preview',json=proposal())).status_code==403
  current[0]=RequestPrincipal.legacy_local();result=await client.post('/hooks',json=body)
  assert result.status_code==201 and result.json()['mode']=='background'
  rule=result.json();current[0]=replace(current[0],client_scope='mobile')
  result=await client.post('/hooks/'+rule['id']+'/pause',json={'expected_revision':1,'request_id':'mobile-pause-1'})
  assert result.status_code==200 and result.json()['mode']=='background'
  result=await client.post('/hooks/'+rule['id']+'/resume',json={'expected_revision':2,'request_id':'mobile-resume-1'})
  assert result.status_code==403

def test_new_delegation_skips_expired_old_revision_without_poisoning_new_rule(env):
 r,h,s,emit,proposal,enable=env;rule=enable();emit()
 h.clock=lambda:time.time()+4000
 p=h.preview('local',proposal());updated=h.save('local',p['preview_ref'],'reapprove-expired-1',rule_id=rule['id'],expected_revision=1)
 wanted=emit(2);h.scan();r.hook_execution.admit()
 state=h.get('local',rule['id']);assert state['status']=='active' and state['revision']==2
 assert state['revisions'][0]['scan_state']=='skipped'
 assert [x['event_id'] for x in h.deliveries('local',rule['id'])['items']]==[wanted]

@pytest.mark.parametrize('studio',['ai2apps.video-studio','ai2apps.ai-browser'])
def test_mini_event_requirements_probe_as_host_features_without_model(runtime,studio):
 from ai2apps.studio.capability_broker import StudioCapabilityBroker
 declaration={'id':'example.event-consumer','requirements':{'capabilities':['events.subscribe','events.background']}}
 probe=StudioCapabilityBroker(runtime).probe_declaration(studio,declaration)
 assert {item['capability'] for item in probe['items']}=={'events.subscribe','events.background'}
 assert all(item['implemented'] and item['ready'] for item in probe['items'])
