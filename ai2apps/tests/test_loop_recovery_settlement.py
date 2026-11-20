"""Fault injection uses deterministic models; processes run real local commands."""
import json
from types import SimpleNamespace as NS
import pytest
from ai2apps.agents.loop_guard import repeated_failure
from ai2apps.agents.tool_recovery import recoverable
from ai2apps.processes import TestSandboxAdapter
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,P,response
from ai2apps.messager.bots import REGISTRATION


def test_recovery_is_not_a_run_lifetime_error_counter():
 for n in (0,3,100):
  assert recoverable('invalid_app_interaction',effects=(),enabled=True,prior_errors=n,preflight=True)
  assert recoverable('provider_error',effects=(),enabled=True,prior_errors=n)
  assert not recoverable('provider_error',effects=('write',),enabled=True,prior_errors=n)
  assert not recoverable('capability_denied',effects=(),enabled=True,prior_errors=n,preflight=True)
  assert not recoverable('tool_cancelled',effects=(),enabled=True,prior_errors=n)

@pytest.mark.parametrize('name',['arbitrary.lookup','independent.inspect'])
def test_rejected_call_identity_survives_new_request_ids(name):
 step=NS(kind='tool',status=NS(value='failed'),tool_name=name,input={'request_id':'first','capability':'x','parameters':{'limit':5}},error={'phase':'prepare','code':'invalid_app_interaction','message':'Unsupported path'})
 assert repeated_failure([step],name,{**step.input,'request_id':'second'})
 assert not repeated_failure([step],name,{**step.input,'parameters':{'limit':6}})
 step.error['outcome_uncertain']=True
 assert not repeated_failure([step],name,step.input)
 step.error={'phase':'prepare','code':'provider_binding_changed'}
 assert not repeated_failure([step],name,step.input)
 step.error={'phase':'prepare','code':'tool_declaration_required'}
 assert not repeated_failure([step],name,step.input)
 step.error={'phase':'prepare','code':'invalid_app_interaction','rejection_kind':'unsupported_interaction'}
 assert repeated_failure([step],name,{**step.input,'parameters':{'limit':6}})
 assert not repeated_failure([step],name,{**step.input,'capability':'different.route'})

@pytest.mark.asyncio
async def test_bad_du_reports_stderr_then_corrects_and_recovers_unsupported_handoff(runtime):
 runtime.processes.sandbox=TestSandboxAdapter()
 bot=runtime.messager_bots.create('local','Loop acceptance','Read only inspection')
 sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
 turns=[]
 async def model(req):
  results=[json.loads(m['content']) for m in req['messages'] if m['role']=='tool']
  processes=[r for r in results if r.get('capability')=='process.start']
  errors=[r['error'] for r in results if 'error' in r and isinstance(r['error'],dict)
          and r['error'].get('code') in ('invalid_app_interaction','repeated_tool_error')]
  turns.append((len(processes),len(errors)))
  if not processes:return response('process.start',{'argv':['du','-ah','-d','2','.']})
  if len(processes)==1:
   assert processes[0]['exit_code']!=0 and 'usage:' in processes[0]['stderr']
   return response('process.start',{'argv':['du','-h','-d','2','.']})
  assert processes[1]['exit_code']==0 and processes[1]['stdout']
  if not errors:return response('app.interact',{'request_id':'bad-path','capability':'gallery.search','parameters':{}})
  if not any(e['code']=='repeated_tool_error' for e in errors):
   assert errors[0]['rejection_kind']=='unsupported_interaction'
   return response('app.interact',{'request_id':'fresh-id','capability':'gallery.search','parameters':{'limit':5}})
  assert any(e['code']=='invalid_app_interaction' for e in errors)
  # Complete from actual evidence; no invalid handoff dispatch occurred.
  return response(text='Verified workspace total: '+processes[1]['stdout'])
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'loop-recovery','Inspect workspace only; do not delete','fixture')
  import asyncio
  for _ in range(600):
   run=runtime.agents.get_run(rid)
   if run.status.value=='failed':raise AssertionError(run.error)
   if run.status.value=='completed':break
   if run.status.value=='waiting_capability':
    item=next(i for i in runtime.agents.list_interactions(rid) if i.status.value=='pending')
    runtime.agents.respond_interaction(rid,item.id,response_id='approve-'+item.id,response={'decision':'approve','scope':'once'})
    runtime.agent_runtime.wake()
   await asyncio.sleep(.03)
  else:raise AssertionError(run.status)
  assert 'Verified workspace total' in run.output['content']
  steps=runtime.agents.list_steps(rid)
  assert any((s.error or {}).get('code')=='repeated_tool_error' for s in steps)
  with runtime.database.transaction() as db:
   assert db.execute("SELECT count(*) FROM tool_invocations WHERE trace_id=? AND qualified_name='app.interact'",(rid,)).fetchone()[0]==0
 finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_run_delivers_after_more_than_three_distinct_preflight_errors(runtime):
 bot=runtime.messager_bots.create('local','Recovery budget acceptance','Answer from verified evidence')
 sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
 seen=[]
 async def model(req):
  errors=[json.loads(m['content'])['error'] for m in req['messages'] if m['role']=='tool' and 'error' in json.loads(m['content'])]
  seen.append(len(errors))
  if len(errors)<5:
   return response('agent.ask_user',{'question_id':'invalid-'+str(len(errors)),'question':str(len(errors)),'options':['only-one']})
  return response(text='Five rejected preparations preserved; no operation dispatched.')
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'five-errors','Fixture recovery','fixture')
  import asyncio
  for _ in range(800):
   run=runtime.agents.get_run(rid)
   if run.status.value in ('completed','failed'):break
   await asyncio.sleep(.025)
  assert run.status.value=='completed',run.error
  assert seen[-1]==5
 finally:await runtime.stop_background_tasks()
