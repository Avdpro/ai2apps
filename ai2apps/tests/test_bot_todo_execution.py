"""Bot proposal→Todo→scoped Run→original interaction; deterministic model."""
import asyncio,json
import httpx,pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install,REGISTRATION,READ_TOOLS
from ai2apps.messager.tasks import PROPOSE,TASK_CHAT
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait
from bot_access_fixtures import restricted_bot
from agent_context_fixtures import owner_context
P=RequestPrincipal.legacy_local

async def until(check):
 for _ in range(500):
  value=check()
  if value:return value
  await asyncio.sleep(.02)
 raise AssertionError('Timed out waiting for actual task state')

def setup(runtime):
 install(runtime);bot=runtime.messager_bots.create('local','Task fixture','Approved work')
 restricted_bot(runtime,bot)
 permissions=runtime.messager_bot_permissions
 permissions.save('local',bot['id'],1,[{'id':'intelligence.read','foreground':True,'background':True}],review_hash=permissions.review_hash())
 return bot,runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{}),runtime.messager_task_execution

def fixture_model():
 async def model(request):
  task='task_access_mode' in owner_context(request)
  results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
  if task:
   if not any(r.get('answer') for r in results):return response('agent.ask_user',{'question_id':'deadline','question':'I am preparing the task. Which deadline should I use? I need your answer before proceeding.'})
   if not any('channels' in r or 'items' in r for r in results):return response('intelligence.channels',{'limit':10})
   return response(text='Task completed with your selected deadline and saved channels.')
  last=next((m.get('content') for m in reversed(request['messages']) if m.get('role')=='user'),'')
  if last=='What is the task doing?':
   assert 'waiting_input' in json.dumps(request['messages']);return response(text='The actual Todo task is waiting for your answer.')
  if any(r.get('proposal_id') for r in results):return response(text='Review the proposal in this conversation.')
  return response(PROPOSE,{'title':'Background fixture','prompt':'TASK_EXECUTION_FIXTURE: ask for deadline, then read saved channels.'})
 return model

@pytest.mark.asyncio
async def test_conversation_scoped_todo_original_reply_and_restart(runtime,tmp_path):
 bot,sid,service=setup(runtime);runtime.agent_runtime.bind_model_provider(fixture_model())
 await runtime.start_background_tasks(retention_interval_seconds=60)
 app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P));base='/messager/bots/'+bot['id']
 try:
  rid=runtime.app_chat.submit(P(),sid,'propose-one','Please prepare a task','fixture-model');await wait(runtime,rid,'completed')
  work=service.work('local',bot['id']);assert len(work['proposals'])==1
  assert runtime.todo.store.snapshot('local')['tasks']==[];proposal=work['proposals'][0]
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Origin':'http://test'}) as client:
   url=base+'/task-proposals/'+proposal['id']+'/approve'
   assert (await client.post(url,json={'review_hash':proposal['review_hash']},headers={'Origin':'null'})).status_code==403
   assert (await client.post(url,json={'review_hash':'0'*64})).status_code==409
   approved=await client.post(url,json={'review_hash':proposal['review_hash']});assert approved.status_code==200,approved.text
   receipt=approved.json();assert (await client.post(url,json={'review_hash':proposal['review_hash']})).json()==receipt
   item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
   assert 'TASK_EXECUTION_FIXTURE' in item['task_request']
   original=item['run_id'];assert runtime.agents.get_definition(runtime.agents.get_run(original).agent_definition_id).agent_key=='ai2apps.app-chat-agent'
   binding=runtime.app_chat.binding(runtime.agents.get_run(original).session_id);assert binding['registration']==TASK_CHAT
   expected=READ_TOOLS | {'messager.bot.directory','messager.bot.delegate'}
   # Discovery can list ungranted capabilities; it never grants execution.
   assert expected <= set(runtime.app_chat.snapshot(P(),binding['session_id'])['tools'])
   frozen=runtime.app_chat.execution_authorization(original)
   assert {pin['capability'] for pin in frozen['run_pins'].values()}==expected
   await until(lambda:runtime.todo.store.snapshot('local')['runs'][0]['status']=='waiting_input')
   assert next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])['task_status']=='waiting_input'
   status=runtime.app_chat.submit(P(),sid,'status-one','What is the task doing?','fixture-model');await wait(runtime,status,'completed')
   store=runtime.todo.store
   await runtime.stop_background_tasks()
   # Simulate a crash after AppChat admission but before the Todo backlink commit.
   with store.connect() as db:
    saved=db.execute('SELECT data FROM runs WHERE id=?',(receipt['run_id'],)).fetchone();data=json.loads(saved[0]);data.pop('agent_run_id',None)
    db.execute("UPDATE runs SET status='running',data=? WHERE id=?",(json.dumps(data),receipt['run_id']))
   with runtime.database.transaction(write=True) as db:db.execute('UPDATE messager_task_runs SET agent_run_id=NULL WHERE todo_run_id=?',(receipt['run_id'],))
   await runtime.start_background_tasks(retention_interval_seconds=60)
   restored=service.work('local',bot['id'])['interactions'][0];assert (restored['id'],restored['run_id'])==(item['id'],original)
   reply=base+'/task-runs/'+item['todo_run_id']+'/interactions/'+item['id']+'/respond'
   payload={'review_hash':restored['review_hash'],'response_id':'reply-one','response':{'answer':'Tomorrow'}}
   assert (await client.post(reply,json={**payload,'review_hash':'0'*64})).status_code==409
   result=await client.post(reply,json=payload);assert result.status_code==200,result.text
   assert (await client.post(reply,json=payload)).status_code==200
  await wait(runtime,original,'completed')
  with pytest.raises(PermissionError):runtime.app_chat.submit(P(),binding['session_id'],'rogue-request','Unapproved task instructions','fixture-model')
  await until(lambda:next((r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==receipt['run_id'] and r['status']=='completed'),None))
  service.recover();messages=runtime.app_chat.snapshot(P(),sid)['messages']
  assert sum('Task completed with your selected deadline' in m['content'] for m in messages)==1
  assert len(runtime.todo.store.snapshot('local')['tasks'])==len(runtime.todo.store.snapshot('local')['runs'])==1

  # Simulate a delivered legacy result from a completed worker with a poster.
  from ai2apps.storage.repositories import MessageRepository
  worker=binding['session_id'];poster=tmp_path/'briefing.png';poster.write_bytes(b'fixture-image')
  asset=runtime.workspace.import_artifact(worker,poster,name=poster.name,media_type='image/png')
  content=[{'type':'text','text':f'The briefing is ready.\n\n![Briefing](artifact://{asset.id})'}]
  output={**runtime.agents.get_run(original).output,'content':content,'artifacts':[
   {'session_id':worker,'artifact_id':asset.id},{'session_id':worker,'artifact_id':'art_missing'}]}
  key='bot-task-finished:'+receipt['run_id']
  repo=MessageRepository(runtime.database)
  record=repo.get_by_idempotency_key(sid,key)
  with runtime.database.transaction(write=True) as db:
   db.execute('UPDATE agent_runs SET output_json=? WHERE id=?',(json.dumps(output),original))
   db.execute('UPDATE message_parts SET content_json=? WHERE id=?',
      (json.dumps({'text':'任务「Background fixture」执行结束：completed。\n\n'+str(content)}),record.parts[0].id))
  store.run_update(receipt['run_id'],'completed',output=content)
  service.recover()
  service.recover()
  page=runtime.app_chat.message_page(P(),sid)['items']
  result=next(item for item in page if item['id']==record.message.id)
  assert result['content'].startswith('任务「Background fixture」已完成。\n\nThe briefing is ready.')
  assert len(result['artifacts'])==1 and result['artifacts'][0]['session_id']==sid
  assert result['artifacts'][0]['url'] in result['content']
  assert asset.id not in result['content'] and "'type':" not in result['content']
  assert len(runtime.workspace.list_artifacts(sid))==1
 finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_revoke_stops_waiting_task_and_regrant_does_not_restore_binding(runtime):
 bot,sid,service=setup(runtime);runtime.agent_runtime.bind_model_provider(fixture_model())
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'proposal-revoke','Please prepare a task','fixture-model');await wait(runtime,rid,'completed')
  proposal=service.work('local',bot['id'])['proposals'][0];receipt=service.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve','fixed')
  item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0];permissions=runtime.messager_bot_permissions
  permissions.save('local',bot['id'],2,[],review_hash=permissions.review_hash())
  assert runtime.agents.get_run(item['run_id']).status.value=='cancelled'
  with pytest.raises(PermissionError):service.respond('local',bot['id'],item['todo_run_id'],item['id'],item['review_hash'],'stale',{'answer':'No'})
  permissions.save('local',bot['id'],3,[{'id':'intelligence.read','foreground':True,'background':True}],review_hash=permissions.review_hash())
  await until(lambda:runtime.todo.store.snapshot('local')['runs'][0]['status']=='cancelled')
  with pytest.raises(PermissionError):runtime.todo.launch('local',receipt['task_id'],principal=P())
  task=runtime.todo.store.get('local',receipt['task_id']);from ai2apps.todo.models import TaskInput
  value={k:v for k,v in task.items() if k in TaskInput.model_fields};value['executor']='codex'
  runtime.todo.store.save('local',value,id=task['id'],revision=task['revision'])
  with pytest.raises(ValueError,match='owning execution adapter'):runtime.todo.launch('local',task['id'],principal=P())
 finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize("mode",["fixed","inherit"])
async def test_same_bot_queue_and_schedule_handle_access_change(runtime,mode):
 from dataclasses import replace
 bot,sid,service=setup(runtime)
 base_model=fixture_model()
 async def model(request):
  if 'task_access_mode' in owner_context(request):return await base_model(request)
  return response(text='Task proposals are ready for review.')
 runtime.agent_runtime.bind_model_provider(model)
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'queue-source','Prepare the reviewed queue','fixture-model')
  context=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=rid)
  from dataclasses import replace
  values=[{'title':'Background fixture','prompt':'TASK_EXECUTION_FIXTURE: ask then read'},
          {'title':'Background fixture 2','prompt':'TASK_EXECUTION_FIXTURE: queued work'},
          {'title':'Scheduled fixture','prompt':'Read tomorrow','schedule':{'frequency':'daily','hour':6,'timezone':'Asia/Shanghai'}}]
  proposals=[service.propose(value,replace(context,invocation_id='queue-invocation-'+str(i))) for i,value in enumerate(values)]
  approved=[]
  for p in proposals:
   item=next(v for v in service.work('local',bot['id'])['proposals'] if v['id']==p['proposal_id'])
   approved.append(service.decide('local',bot['id'],item['id'],item['review_hash'],'approve',mode))
  pending=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
  runs={r['id']:r for r in runtime.todo.store.snapshot('local')['runs']}
  assert runs[approved[1]['run_id']]['status']=='queued' and runs[approved[1]['run_id']]['todo_queued']
  assert 'agent_run_id' not in runs[approved[1]['run_id']]
  assert runtime.todo.store.get('local',approved[2]['task_id'])['next_due']
  tasks=runtime.messager_bot_tasks.list('local',bot['id'])['items']
  scheduled=next(task for task in tasks if task['id']==approved[2]['task_id'])
  assert scheduled['scheduled'] and scheduled['managed'] and scheduled['next_due']
  assert scheduled['run'] is None and scheduled['task_session_id'] is None
  runtime.messager_bot_permissions.save('local',bot['id'],2,[],review_hash=runtime.messager_bot_permissions.review_hash())
  assert runtime.agents.get_run(pending['run_id']).status.value=='cancelled'
  due=runtime.todo.store.get('local',approved[2]['task_id'])['next_due']
  if mode=='fixed':
   assert next(r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==approved[1]['run_id'])['status']=='cancelled'
   assert due is None
  else:
   assert due is not None
   def queued_run():
    with runtime.database.transaction() as db:
     return db.execute('SELECT authorization_json FROM messager_task_runs WHERE todo_run_id=?',(approved[1]['run_id'],)).fetchone()
   current=json.loads((await until(queued_run))[0])
   assert all(pin['capability'] not in READ_TOOLS for pin in current['run_pins'].values())
 finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_original_approval_is_reviewed_without_widening_grants(runtime):
 from ai2apps.agents.models import InteractionKind
 bot,sid,service=setup(runtime);runtime.agent_runtime.bind_model_provider(fixture_model())
 await runtime.start_background_tasks(retention_interval_seconds=60)
 app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
 try:
  rid=runtime.app_chat.submit(P(),sid,'approval-source','Prepare task','fixture-model');await wait(runtime,rid,'completed')
  proposal=service.work('local',bot['id'])['proposals'][0]
  receipt=service.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
  item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
  # Fixture for an original owner approval; no payment or sensitive effect executes.
  with runtime.database.transaction(write=True) as db:
   db.execute("UPDATE agent_interactions SET status='cancelled' WHERE id=?",(item['id'],))
  approval=runtime.agents.create_interaction(item['run_id'],request_key='fixture-owner-approval',kind=InteractionKind.APPROVAL,
      prompt='Fixture action requires your decision because it is sensitive.',
      response_schema={'type':'object','properties':{'decision':{'enum':['approve','deny']},'scope':{'enum':['once','run','app']}},'required':['decision'],'additionalProperties':False},
      request={'tool_name':'unrelated.fixture.action','arguments':{'target':'fixture'},'effects':['fixture.effect']})
  pending=next(v for v in service.work('local',bot['id'])['interactions'] if v['id']==approval.id)
  url='/messager/bots/'+bot['id']+'/task-runs/'+item['todo_run_id']+'/interactions/'+approval.id+'/respond'
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Origin':'http://test'}) as client:
   bad=await client.post(url,json={'review_hash':pending['review_hash'],'response_id':'bad-scope','response':{'decision':'approve','scope':'app'}})
   assert bad.status_code==409
   denied=await client.post(url,json={'review_hash':pending['review_hash'],'response_id':'owner-denied','response':{'decision':'deny'}})
   assert denied.status_code==200,denied.text
  assert runtime.agents.get_run(item['run_id']).status.value=='failed'
  await until(lambda:next(r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==receipt['run_id'])['status']=='failed')
  assert runtime.agents.get_run(item['run_id']).error['code']=='approval_denied'
 finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_task_without_background_access_can_ask_but_has_no_app_tools(runtime):
 bot,sid,service=setup(runtime)
 permissions=runtime.messager_bot_permissions
 permissions.save('local',bot['id'],2,[{'id':'intelligence.read','foreground':True,'background':False}],review_hash=permissions.review_hash())
 runtime.agent_runtime.bind_model_provider(fixture_model())
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'text-only','Prepare a text-only task','fixture-model');await wait(runtime,rid,'completed')
  proposal=service.work('local',bot['id'])['proposals'][0];assert proposal['access']==[]
  receipt=service.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve','fixed')
  item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
  run=runtime.agents.get_run(item['run_id']);assert run.input['execution_origin']=='task'
  assert runtime.app_chat.snapshot(P(),run.session_id)['tools']==[]
  context=runtime.tools.context_for_session(caller_id='fixture',session_id=run.session_id,trace_id=run.id)
  assert runtime.app_chat.visible(context,'agent.ask_user')
  assert not runtime.app_chat.visible(context,'intelligence.channels')
  with pytest.raises(Exception):await runtime.tools.execute('intelligence.channels',{'limit':1},context=context)
  await runtime.todo.cancel('local',receipt['run_id'])
 finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_approval_once_uses_original_run_but_cannot_expand_task_access(runtime):
 from ai2apps.agents.models import InteractionKind
 bot,sid,service=setup(runtime);runtime.agent_runtime.bind_model_provider(fixture_model())
 await runtime.start_background_tasks(retention_interval_seconds=60)
 try:
  rid=runtime.app_chat.submit(P(),sid,'approve-once-source','Prepare task','fixture-model');await wait(runtime,rid,'completed')
  proposal=service.work('local',bot['id'])['proposals'][0]
  receipt=service.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
  item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
  directory=runtime.todo.store.get('local',receipt['task_id'])['directory_id']
  with runtime.database.transaction(write=True) as db:db.execute("UPDATE agent_interactions SET status='cancelled' WHERE id=?",(item['id'],))
  approval=runtime.agents.create_interaction(item['run_id'],request_key='fixture-once-approval',kind=InteractionKind.APPROVAL,
      prompt='Fixture approval for this operation only.',response_schema={'type':'object','properties':{'decision':{'enum':['approve','deny']},'scope':{'enum':['once','run','app']}},'required':['decision'],'additionalProperties':False},
      request={'tool_name':'todo.create','arguments':{'title':'Must not execute','directory_id':directory},'capabilities':['workspace.write'],'effects':['workspace.write'],'resource_selector':{'directory_id':directory}})
  pending=next(v for v in service.work('local',bot['id'])['interactions'] if v['id']==approval.id)
  result=service.respond('local',bot['id'],item['todo_run_id'],approval.id,pending['review_hash'],'approved-once',{'decision':'approve','scope':'once'})
  assert result['status']=='approved'
  with runtime.database.transaction() as db:
   grant=db.execute("SELECT scope_id,evidence_json FROM grant_leases WHERE json_extract(evidence_json,'$.interaction_id')=?",(approval.id,)).fetchone()
  assert grant['scope_id']==item['run_id'] and json.loads(grant['evidence_json'])['single_use']
  context=runtime.tools.context_for_session(caller_id='fixture',session_id=runtime.agents.get_run(item['run_id']).session_id,trace_id=item['run_id'])
  with pytest.raises(Exception):await runtime.tools.execute('todo.create',{'title':'Must not execute','directory_id':directory},context=context)
  runtime.agents.request_cancel(item['run_id']);runtime.agent_runtime.wake()
  assert len(runtime.todo.store.snapshot('local')['tasks'])==1
 finally:await runtime.stop_background_tasks()


@pytest.mark.parametrize("mode", ["fresh", "legacy", "archived"])
def test_worker_proposal_result_reaches_original_conversation(runtime, mode):
    bot, sid, service = setup(runtime)
    actor, bot_id = "local", bot["id"]
    job_id, worker_run = "dialogue-job", "original-worker-run"
    todo_run = "managed-todo-run"
    with runtime.database.transaction(write=True) as db:
        db.execute("""INSERT INTO messager_dialogue_jobs
            (id,actor,bot_id,source_session,source_run,title,status,worker_run)
            VALUES (?,?,?,?,?,?,?,?)""",
            (job_id, actor, bot_id, sid, "initial-run", "Prepare proposal", "completed", worker_run))
    worker_sid = runtime.app_chat.open(P(), REGISTRATION, {"bot_id": bot_id, "dialogue_job": job_id}, {})
    service.append(sid, "assistant", "The proposal is ready.", "proposal-preview", {})
    cursor = runtime.app_chat.message_page(P(), sid)["after"]
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE messager_dialogue_jobs SET worker_session=? WHERE id=?", (worker_sid, job_id))
        db.execute("INSERT INTO messager_task_proposals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   ("proposal", actor, bot_id, worker_run, worker_sid, "proposal-key", "{}", "{}", "hash",
                    "approved", "task", todo_run, "2026-11-15T04:55:11.000000Z"))
        if mode == "legacy":
            db.execute("INSERT INTO messager_task_receipts VALUES (?, 'notified')", (todo_run,))
        if mode == "archived":
            db.execute("UPDATE app_chat_sessions SET registration='archived' WHERE session_id=?", (sid,))
    if mode == "archived":
        sid = runtime.app_chat.open(P(), REGISTRATION, {"bot_id": bot_id}, {})
        cursor = 0
    data = {"execution_binding": {"binding": {"proposal_id": "proposal", "bot_id": bot_id, "notify": True}},
            "snapshot": {"title": "Receipt fixture"}, "output": "REFERENCE-RESULT"}
    service.finished(actor, todo_run, "completed", data)
    service.finished(actor, todo_run, "completed", data)
    items = runtime.app_chat.message_page(P(), sid, after=cursor)["items"]
    if mode == "archived":
        assert items == []
    else:
        assert len(items) == 1
        assert items[0]["content"].endswith("REFERENCE-RESULT")
    assert runtime.app_chat.message_page(P(), worker_sid)["items"] == []
