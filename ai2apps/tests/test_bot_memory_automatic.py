"""Queued Bot memory on real Todo/AgentRuntime, models are deterministic fixtures."""
import asyncio,json
import pytest
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P
from test_app_chat_durable import response,bind_identity

async def until(predicate):
    for _ in range(200):
        value=predicate()
        if value:return value
        await asyncio.sleep(.05)
    raise AssertionError('Condition not reached')

def candidate(value='Old name',**extra):
    return {'subject':'user','predicate':'preferred_name','value':value,'text':'Call the user '+value,'intent':'explicit',**extra}

@pytest.mark.asyncio
async def test_explicit_memory_is_queued_and_saved_without_additional_model_call(runtime):
    bot,sid,_,_=setup(runtime);calls=[]
    async def model(request):
        calls.append(request)
        return response(text=json.dumps({'kind':'reply','text':'Will remember','memory_candidates':[candidate()]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        d=runtime.messager_dialogue
        rid=d.submit(P(),bot['id'],sid,'remember-one','Remember my preferred name','fixture',[])
        await wait(runtime,rid,'completed')
        notes=await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        assert notes[0]['text']=='Call the user Old name' and len(calls)==1
        m=runtime.messager_bots.memory_tasks
        assert m.pending('local',bot['id'])['counts']['applied']==1
        with runtime.database.transaction() as db:
            row=db.execute('SELECT task_id,run_id FROM messager_memory_batches').fetchone()
            assert row['task_id'] and row['run_id']
        assert runtime.agents.get_run(row['run_id']).input.get('authorization') is None
        page=runtime.app_chat.message_page(P(),sid)['items']
        assert any('排队' in i['content'] for i in page) and any('Memory saved' in i['content'] for i in page)
        assert m.enqueue(runtime.agents.get_run(rid),runtime.app_chat.binding(sid),[candidate()])
        assert m.pending('local',bot['id'])['counts']['applied']==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_photo_answer_persists_without_vision_and_is_hydrated_after_long_chat(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);d=runtime.messager_dialogue
    question=d.append(sid,'assistant','Please provide your own photo for our composite.','portrait-question')
    p=tmp_path/'me.png';p.write_bytes(b'fixture portrait')
    attachment=runtime.documents.create_reference(sid,p,filename='me.png',media_type='image/png')
    calls=[]
    async def model(request):
        calls.append(request)
        return response(text=json.dumps({'kind':'reply','text':'Photo received','memory_candidates':[{'subject':'user','predicate':'portrait','kind':'resource','value':'selected photo','text':'User composite portrait','intent':'answer','attachment_id':attachment.id,'question_id':question.value.message.id}]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=d.submit(P(),bot['id'],sid,'photo-answer','Here is my photo','fixture',[attachment.id]);await wait(runtime,rid,'completed')
        notes=await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        assert len(calls)==1;p.unlink()
        for n in range(25):d.append(sid,'user','Unrelated '+str(n),'unrelated-'+str(n))
        run=runtime.agents.get_run(rid)
        run.input['memory_selection']=[{'id':notes[0]['id'],'revision':1}]
        target=sid
        usage=runtime.messager_bots.memory_tasks.hydrate({'id':'fixture-job','actor':'local','bot_id':bot['id']},run,target)
        asset=runtime.workspace.get_artifact(sid,usage[0]['resource']['artifact_id'])
        assert runtime.workspace.artifact_path(asset).read_bytes()==b'fixture portrait'
        assert runtime.messager_bots.memory_tasks.hydrate({'id':'fixture-job','actor':'local','bot_id':bot['id']},run,target)==usage
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_clear_and_undo_block_old_sources_without_resurrection(runtime):
    bot,sid,_,_=setup(runtime);values=[candidate()]
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':values}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.todo.max_concurrent_runs=0
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'before-forget','Remember this','fixture',[]);await wait(runtime,rid,'completed')
        m=runtime.messager_bots.memory_tasks
        assert m.pending('local',bot['id'])['items'][0]['state']=='queued'
        runtime.messager_bots.memory.clear('local',bot['id'])
        runtime.todo.max_concurrent_runs=3;runtime.todo.dispatch_queue();await asyncio.sleep(.2)
        assert runtime.messager_bots.memory.context('local',bot['id'])==[]
        with pytest.raises(ValueError):m.enqueue(runtime.agents.get_run(rid),runtime.app_chat.binding(sid),values)
        next_run=runtime.messager_dialogue.submit(P(),bot['id'],sid,'after-forget','Remember this again','fixture',[]);await wait(runtime,next_run,'completed')
        await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        records=runtime.messager_bots.memory.records;change=records.changes('local',bot['id'])['items'][0]
        records.undo('local',bot['id'],change['change_id'],request_id='undo-auto-memory')
        source=runtime.agents.get_run(next_run)
        with pytest.raises(ValueError):m.enqueue(source,runtime.app_chat.binding(sid),values)
        assert runtime.messager_bots.memory.context('local',bot['id'])==[]
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_recall_is_one_bounded_round_beyond_recent_window(runtime):
    from test_bot_memory_history import seed
    bot,sid,_,_=setup(runtime)
    for n in range(25):seed(runtime,bot,sid,'recall-'+str(n),'帽子熊猫' if n==0 else 'Other '+str(n))
    calls=[]
    async def model(request):
        calls.append(request)
        if len(calls)==1:return response(text=json.dumps({'kind':'recall','text':'Look up earlier work','recall_query':'帽子'}))
        assert 'recall-0' in request['messages'][0]['content']
        return response(text=json.dumps({'kind':'reply','text':'Found the earlier hat panda task.'}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'recall-old','Find our earlier hat panda','fixture',[])
        await wait(runtime,rid,'completed');assert len(calls)==2
        with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM messager_memory_recalls WHERE run_id=?',(rid,)).fetchone()[0]==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_explicit_replace_and_uncertain_candidate_review_do_not_block_chat(runtime):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory_tasks
    state={'value':candidate()}
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'ok','memory_candidates':[state['value']]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        async def send(key):
            rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,key,'Remember requested preference','fixture',[]);await wait(runtime,rid,'completed');return rid
        await send('name-old');await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        state['value']=candidate('New name',mode='replace',revision=1)
        await send('name-new');await until(lambda:runtime.messager_bots.memory.context('local',bot['id'])[0]['text']=='Call the user New name')
        state['value']=candidate('Possible fact',predicate='uncertain_fact',intent='candidate')
        await send('maybe-fact');pending=m.pending('local',bot['id'])['items'];assert len(pending)==1 and pending[0]['state']=='review'
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        m.decide('local',bot['id'],pending[0]['id'],'cancel');assert m.pending('local',bot['id'])['items']==[]
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_ambiguous_photo_answer_and_stale_foreground_epoch_are_rejected(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);d=runtime.messager_dialogue
    question=d.append(sid,'assistant','Please upload your own photo.','question')
    d.append(sid,'user','Unrelated answer','intervening')
    p=tmp_path/'x.png';p.write_bytes(b'photo');a=runtime.documents.create_reference(sid,p,filename='x.png',media_type='image/png')
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'ok'}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=d.submit(P(),bot['id'],sid,'ambiguous-photo','Photo','fixture',[a.id]);await wait(runtime,rid,'completed')
        value={'subject':'user','predicate':'portrait','kind':'resource','value':'photo','text':'User photo','intent':'answer','attachment_id':a.id,'question_id':question.value.message.id}
        with pytest.raises(ValueError,match='ambiguous'):runtime.messager_bots.memory_tasks.enqueue(runtime.agents.get_run(rid),runtime.app_chat.binding(sid),[value])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_selected_portrait_reaches_worker_with_frozen_local_resource(runtime,tmp_path):
    from test_bot_dialogue import job_wait
    bot,sid,_,_=setup(runtime);p=tmp_path/'portrait.png';p.write_bytes(b'portrait bytes')
    asset=runtime.workspace.import_artifact(sid,p,name='me.png',media_type='image/png')
    note=runtime.messager_bots.memory.records.apply('local',bot['id'],request_id='remember-resource',subject='user',predicate='portrait',kind='resource',text='My portrait',value={'session_id':sid,'artifact_id':asset.id})
    observed=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:
            return response(text=json.dumps({'kind':'task','text':'Queued','title':'Composite','use_memories':[note['memory_id']]}))
        observed.append(request);assert 'recalled_memories' in json.dumps(request)
        return response(text='Fixture composite completed')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'use-portrait','Make a composite with me','fixture',[])
        await wait(runtime,rid,'completed');job=await job_wait(runtime,rid,'completed');assert len(observed)==1
        with runtime.database.transaction() as db:usage=json.loads(db.execute('SELECT value_json FROM messager_memory_usage WHERE job_id=?',(job['id'],)).fetchone()[0])
        ref=usage[0]['resource'];assert ref['session_id']==job['worker_session'] and ref['artifact_id']!=asset.id
        assert runtime.workspace.artifact_path(runtime.workspace.get_artifact(ref['session_id'],ref['artifact_id'])).read_bytes()==b'portrait bytes'
        runtime.messager_bots.memory.clear('local',bot['id'])
        with pytest.raises(PermissionError):runtime.messager_bots.memory_tasks.check_usage('local',bot['id'],usage)
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_unstarted_maintenance_claim_recovers_once_after_restart(runtime):
    from ai2apps.todo.service import TodoService
    bot,sid,_,_=setup(runtime)
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[candidate()]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.todo.max_concurrent_runs=0
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'restart-memory','Remember preference','fixture',[]);await wait(runtime,rid,'completed')
        with runtime.todo.store.connect() as db:
            row=db.execute("SELECT * FROM runs WHERE status='queued'").fetchone();data=json.loads(row['data']);data['todo_queued']=False
            db.execute("UPDATE runs SET status='running',data=? WHERE id=?",(json.dumps(data),row['id']))
        await runtime.todo.shutdown();runtime.todo=TodoService(runtime);await runtime.todo.startup()
        await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        runtime.messager_bots.memory_tasks.recover()
        with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM messager_memory_changes').fetchone()[0]==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_candidate_api_review_origin_owner_and_double_cancel(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    bot,sid,_,_=setup(runtime)
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Possible fact','memory_candidates':[candidate(intent='candidate')]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'api-candidate','This might be useful','fixture',[]);await wait(runtime,rid,'completed')
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        base='/messager/bots/'+bot['id']+'/memory-candidates'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            items=(await c.get(base)).json()['items'];ref=items[0]['id'];route=base+'/'+ref+'/cancel'
            assert (await c.post(route)).status_code==403
            assert (await c.post(route.replace(bot['id'],'foreign'),headers={'Origin':'http://test'})).status_code==404
            assert (await c.post(route,headers={'Origin':'http://test'})).status_code==200
            assert (await c.post(route,headers={'Origin':'http://test'})).status_code==200
            assert (await c.get(base)).json()['items']==[]
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_only_bound_maintenance_run_can_commit_and_cancelled_turn_cannot_source(runtime):
    from types import SimpleNamespace
    from ai2apps.messager.memory_tasks import KEY
    bot,sid,_,_=setup(runtime)
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[candidate()]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.todo.max_concurrent_runs=0
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'forgery-source','Remember me','fixture',[]);await wait(runtime,rid,'completed')
        with runtime.database.transaction() as db:batch=dict(db.execute('SELECT * FROM messager_memory_batches').fetchone())
        fake=runtime.agents.create_run(session_id=sid,agent_key=KEY,input={'batch_id':batch['id'],'actor':'local','bot_id':bot['id']},idempotency_key='forged-maintenance')[0]
        result=await runtime.messager_bots.memory_tasks(SimpleNamespace(run=fake))
        assert result.code=='memory_binding_changed'
        with runtime.database.transaction(write=True) as db:db.execute('UPDATE agent_runs SET cancel_requested=1 WHERE id=?',(rid,))
        with pytest.raises(ValueError,match='original user turn'):runtime.messager_bots.memory_tasks.enqueue(runtime.agents.get_run(rid),runtime.app_chat.binding(sid),[candidate()])
        assert runtime.messager_bots.memory.context('local',bot['id'])==[]
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_slow_memory_resource_copy_does_not_block_foreground_chat(runtime,tmp_path,monkeypatch):
    import threading
    bot,sid,_,_=setup(runtime);entered=threading.Event();release=threading.Event()
    p=tmp_path/'photo.png';p.write_bytes(b'fixture photograph')
    a=runtime.documents.create_reference(sid,p,filename='photo.png',media_type='image/png')
    original=runtime.workspace.import_artifact
    def delayed(*args,**kwargs):
        entered.set();assert release.wait(10);return original(*args,**kwargs)
    monkeypatch.setattr(runtime.workspace,'import_artifact',delayed)
    async def model(request):
        if request['messages'][-1]['content']=='hello':return response(text=json.dumps({'kind':'reply','text':'Hello while memory is processing'}))
        return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[{'subject':'user','predicate':'portrait','value':'photo','kind':'resource','text':'User chosen portrait','intent':'explicit','attachment_id':a.id}]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first=runtime.messager_dialogue.submit(P(),bot['id'],sid,'slow-photo','Remember my photo','fixture',[a.id]);await wait(runtime,first,'completed')
        await until(entered.is_set)
        second=runtime.messager_dialogue.submit(P(),bot['id'],sid,'chat-during-copy','hello','fixture',[]);await wait(runtime,second,'completed')
        assert not release.is_set() and runtime.messager_bots.memory.context('local',bot['id'])==[]
        release.set();await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
    finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_cancelling_one_memory_preserves_other_fields_from_same_message(runtime):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory_tasks
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[candidate(),candidate('Blue',predicate='favorite_color')]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.todo.max_concurrent_runs=0
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'two-fields','Remember my name and color','fixture',[]);await wait(runtime,rid,'completed')
        pending=m.pending('local',bot['id'])['items'];name=next(i for i in pending if i['value']['predicate']=='preferred_name')
        m.decide('local',bot['id'],name['id'],'cancel')
        runtime.todo.max_concurrent_runs=3;runtime.todo.dispatch_queue()
        notes=await until(lambda:runtime.messager_bots.memory.context('local',bot['id']))
        assert len(notes)==1 and 'Blue' in notes[0]['text']
        assert m.pending('local',bot['id'])['counts']['cancelled']==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_explicit_observed_output_can_be_remembered_but_invented_id_cannot(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);p=tmp_path/'output.png';p.write_bytes(b'generated fixture')
    a=runtime.workspace.import_artifact(sid,p,name='hat-panda.png',media_type='image/png')
    runtime.messager_dialogue.append(sid,'assistant','Observed image','observed-output',{'artifacts':[{'session_id':sid,'artifact_id':a.id,'filename':a.name}]})
    chosen={'id':a.id}
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[{'subject':'user','predicate':'chosen_avatar','value':'chosen output','text':'Chosen panda avatar','kind':'resource','intent':'explicit','artifact_id':chosen['id']}]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'remember-output','Remember this image as my avatar','fixture',[]);await wait(runtime,rid,'completed')
        notes=await until(lambda:runtime.messager_bots.memory.context('local',bot['id']));assert len(notes)==1
        chosen['id']='invented-artifact'
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'invented-output','Remember another output','fixture',[]);await wait(runtime,rid,'completed')
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_fresh_explicit_evidence_after_forgetting_creates_new_record(runtime):
    bot,sid,_,_=setup(runtime);value={'name':'First'}
    async def model(request):return response(text=json.dumps({'kind':'reply','text':'Queued','memory_candidates':[candidate(value['name'])]}))
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        d=runtime.messager_dialogue
        first=d.submit(P(),bot['id'],sid,'remember-before-clear','Remember First','fixture',[]);await wait(runtime,first,'completed')
        old=(await until(lambda:runtime.messager_bots.memory.context('local',bot['id'])))[0]
        runtime.messager_bots.memory.clear('local',bot['id'])
        value['name']='Second'
        second=d.submit(P(),bot['id'],sid,'remember-new-evidence','Remember Second','fixture',[]);await wait(runtime,second,'completed')
        new=(await until(lambda:runtime.messager_bots.memory.context('local',bot['id'])))[0]
        assert new['id']!=old['id'] and 'Second' in new['text']
        with pytest.raises(ValueError):runtime.messager_bots.memory_tasks.enqueue(runtime.agents.get_run(first),runtime.app_chat.binding(sid),[candidate('First')])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_provider_without_usage_does_not_break_memory_or_chat(runtime):
    bot,sid,_,_=setup(runtime)
    async def model(request):
        value=response(text=json.dumps({'kind':'reply','text':'Hello'}));value['usage']=None;return value
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'no-usage','Hello','fixture',[]);await wait(runtime,rid,'completed')
        stats=runtime.messager_bots.memory_tasks.pending('local',bot['id'])
        assert stats['incremental_tokens'] is None and stats['maintenance_model_calls']==0
    finally:await runtime.stop_background_tasks()
