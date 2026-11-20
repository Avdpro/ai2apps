"""Real Runtime/SQLite; deterministic models only, no paid service calls."""
import asyncio,json
import pytest
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait
from test_bot_capability_discovery import setup,P

async def job_wait(r,source,status):
    for _ in range(300):
        with r.database.transaction() as db:row=db.execute('SELECT * FROM messager_dialogue_jobs WHERE source_run=?',(source,)).fetchone()
        if row and row['status']==status:return dict(row)
        await asyncio.sleep(.05)
    assert False,dict(row) if row else r.agents.get_run(source)

@pytest.mark.asyncio
async def test_direct_reply_while_independent_task_waits_for_original_approval(runtime):
    bot,sid,calls,provider=setup(runtime)
    duty='When given a project name, compile a project status report using the available tools.'
    runtime.messager_bots.update('local',bot['id'],bot['name'],duty)
    async def model(request):
        system='\n'.join(m['content'] for m in request['messages'] if m.get('role')=='system')
        if not request.get('tools') and 'Decide quickly' in system:
            assert duty in system and 'Use the configured Bot Role' in system
            text=request['messages'][-1]['content']
            assert text in ('Compiler','hello')
            direct=text=='hello'
            return response(text=json.dumps({'kind':'reply' if direct else 'task','text':'hello back' if direct else 'Queued; you can keep chatting.','title':'Fixture work'}))
        assert 'Use the configured Role (duty)' in system
        assert any(duty in message['content'] for message in request['messages']
                   if message.get('role')=='user' and isinstance(message.get('content'),str))
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results):return response(text='Job finished')
        if not any(x.get('providers') for x in results):return response('app.describe',{'capability':provider.capability})
        return response(provider.capability,{'prompt':'fixture'})
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        service=runtime.messager_dialogue
        rid=service.submit(P(),bot['id'],sid,'first-request','Compiler','fixture',[])
        listed=next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])
        assert listed['reply_status'] is not None and listed['task_status'] is None
        assert not listed['needs_user_assistance']
        assert service.submit(P(),bot['id'],sid,'first-request','Compiler','fixture',[])==rid
        await wait(runtime,rid,'completed')
        job=await job_wait(runtime,rid,'running');await wait(runtime,job['worker_run'],'waiting_capability')
        other=service.submit(P(),bot['id'],sid,'second-request','hello','fixture',[])
        listed=next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])
        assert listed['reply_status'] is not None and listed['task_status']=='waiting_capability'
        assert listed['needs_user_assistance']
        assert runtime.messager_bots.list('other')==[]
        await wait(runtime,other,'completed')
        listed=next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])
        assert listed['reply_status'] is None and listed['task_status']=='waiting_capability'
        messages=runtime.app_chat.message_page(P(),sid)['items'];assert any(m['content']=='hello back' for m in messages);assert not calls
        snap=service.snapshot(P(),bot['id'],sid);pending=next(x for x in snap['runs'] if x.get('job_id'))['interactions'][0]
        active=next(x for x in snap['runs'] if x['id']==job['worker_run'])
        assert active['task_context']=={'task':'Fixture work','step':'Fixture work','request':'Compiler'}
        with runtime.database.transaction(write=True) as db:db.execute('UPDATE messager_dialogue_jobs SET worker_run=NULL WHERE id=?',(job['id'],))
        restored=service.restore('local','fixture-todo-run',{'execution_binding':{'binding':{'job_id':job['id']}}})
        assert restored['agent_run_id']==job['worker_run']
        access=runtime.messager_bot_app_access;review=access.request('local',bot['id'],job['worker_run'],pending['id'])
        result=access.allow('local',bot['id'],job['worker_run'],pending['id'],review['request_hash']);assert result['continued']
        # Approval from a foreground task grants that task tree, not the Bot.
        assert 'ai2apps.gallery' not in access.current('local',bot['id'])[1]
        await wait(runtime,job['worker_run'],'completed');await job_wait(runtime,rid,'completed')
        assert len(calls)==1
        assert not next(b for b in runtime.messager_bots.list('local') if b['id']==bot['id'])['needs_user_assistance']
        assert any(m['content']=='Job finished' for m in runtime.app_chat.message_page(P(),sid)['items'])
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_jobs_are_serial_while_dialogue_accepts_more_work(runtime):
    bot,sid,_,_=setup(runtime);entered=asyncio.Event();release=asyncio.Event();workers=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:return response(text=json.dumps({'kind':'task','text':'Queued','title':'Job'}))
        workers.append(1)
        if len(workers)>1:assert any(m.get('content')=='done' for m in request['messages'])
        entered.set();await release.wait();return response(text='done')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        s=runtime.messager_dialogue;first=s.submit(P(),bot['id'],sid,'serial-first','work1','fixture',[]);await wait(runtime,first,'completed');await asyncio.wait_for(entered.wait(),10)
        second=s.submit(P(),bot['id'],sid,'serial-next','work2','fixture',[]);await wait(runtime,second,'completed');await job_wait(runtime,second,'queued');assert len(workers)==1
        release.set();await job_wait(runtime,first,'completed');await job_wait(runtime,second,'completed');assert len(workers)==2
    finally:release.set();await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_role_input_starts_fresh_work_even_with_failed_same_topic(runtime):
    bot,sid,_,_=setup(runtime)
    service=runtime.messager_dialogue
    runtime.messager_bots.update('local',bot['id'],bot['name'],'When given a region, compile its activity report.')
    with runtime.database.transaction(write=True) as db:
        db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'failed',NULL,NULL,NULL)",
                   ('old-work','local',bot['id'],sid,'old-turn','North region activity'))
    service.sessions.link(service.row('old-work'))
    service.sessions.halt('old-work')

    async def model(request):
        system=request['messages'][0]['content']
        if 'Decide quickly' in system:
            assert 'old-work' in system and 'North region activity' in system
            assert 'A matching topic or recent task title alone is not evidence of continuation' in system
            assert request['messages'][-1]['content']=='North'
            return response(text=json.dumps({'kind':'task','title':'North region activity','text':'Queued'}))
        return response(text='Fixture report ready')

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=service.submit(P(),bot['id'],sid,'fresh-region','North','fixture',[])
        await wait(runtime,source,'completed')
        job=await job_wait(runtime,source,'completed')
        assert service.sessions.for_job(job['id'])['id']!='old-work'
        assert service.sessions.get('local',bot['id'],'old-work',sid)['halted']
    finally:
        await runtime.stop_background_tasks()


def test_media_is_projected_on_its_message_and_copied_once_between_owned_task_sessions(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);service=runtime.messager_dialogue
    source=tmp_path/'image.png';source.write_bytes(b'fixture-image')
    asset=runtime.workspace.import_artifact(sid,source,name='result.png',media_type='image/png')
    ref={'session_id':sid,'artifact_id':asset.id,'filename':'untrusted-name','media_type':'text/html','url':'https://untrusted.invalid'}
    service.append(sid,'assistant','Generated','media-result',{'artifacts':[ref,{'session_id':'foreign','artifact_id':asset.id}]})
    item=runtime.app_chat.message_page(P(),sid)['items'][-1]
    assert item['artifacts'][0]['filename']=='result.png' and item['artifacts'][0]['media_type']=='image/png'
    assert item['artifacts'][0]['url'].startswith('/v1/platform/sessions/'+sid+'/')
    assert len(item['artifacts'])==1
    other=runtime.messager_bots.create('local','Other','Help');target=runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':other['id']},{})
    mapping,outputs=service.copy_outputs([ref],sid,target);_,repeated=service.copy_outputs([ref],sid,target)
    assert repeated==outputs and mapping[asset.id]==outputs[0]['artifact_id']
    assert outputs[0]['session_id']==target


@pytest.mark.asyncio
async def test_queued_task_has_frozen_access_and_revocation_prevents_execution(runtime):
    bot,sid,_,_=setup(runtime);release=asyncio.Event();entered=asyncio.Event();workers=[]
    async def model(request):
        if 'Decide quickly' in request['messages'][0]['content']:return response(text=json.dumps({'kind':'task','text':'Queued','title':'Work'}))
        workers.append(1);entered.set();await release.wait();return response(text='done')
    runtime.agent_runtime.bind_model_provider(model);await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        s=runtime.messager_dialogue;a=s.submit(P(),bot['id'],sid,'revoke-one','work1','fixture',[]);await wait(runtime,a,'completed');await asyncio.wait_for(entered.wait(),10)
        b=s.submit(P(),bot['id'],sid,'revoke-two','work2','fixture',[]);await wait(runtime,b,'completed');await job_wait(runtime,b,'queued')
        runtime.messager_bot_permissions.invalidate('local',bot['id']);release.set()
        for _ in range(200):
            with runtime.database.transaction() as db:row=db.execute('SELECT status FROM messager_dialogue_jobs WHERE source_run=?',(b,)).fetchone()
            if row['status'] not in ('queued','running'):break
            await asyncio.sleep(.05)
        assert row['status'] in ('failed','cancelled','interrupted');assert len(workers)==1
    finally:release.set();await runtime.stop_background_tasks()


def test_worker_session_cannot_be_opened_for_another_bot_or_repurposed(runtime):
    bot,sid,_,_=setup(runtime);service=runtime.messager_dialogue
    with pytest.raises(PermissionError):runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id'],'dialogue_job':'forged'}, {})
    rid=service.submit(P(),bot['id'],sid,'bound-request','original work','fixture',[])
    with runtime.database.transaction(write=True) as db:db.execute("INSERT INTO messager_dialogue_jobs VALUES('job','local',?,?,?,'Work','queued',NULL,NULL,NULL)",(bot['id'],sid,rid))
    worker=runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':bot['id'],'dialogue_job':'job'}, {})
    with pytest.raises(PermissionError):runtime.app_chat.submit(P(),worker,'arbitrary-request','different work','fixture')
    other=runtime.messager_bots.create('local','Different','Help')
    with pytest.raises(PermissionError):runtime.app_chat.open(P(),'ai2apps.messager.bots',{'bot_id':other['id'],'dialogue_job':'job'}, {})


@pytest.mark.asyncio
async def test_desktop_api_admission_is_same_origin_owned_and_idempotent(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    bot,sid,_,_=setup(runtime);app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    body={'session_id':sid,'request_id':'api-dialogue','text':'hello','model':'fixture','attachments':[]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        endpoint='/messager/bots/'+bot['id']+'/dialogue/turns'
        assert (await c.post(endpoint,json=body)).status_code==403
        first=await c.post(endpoint,json=body,headers={'Origin':'http://test','X-AI2Apps-Timezone':'America/Los_Angeles'});assert first.status_code==202,first.text
        again=await c.post(endpoint,json=body,headers={'Origin':'http://test'});assert again.json()==first.json()
        saved=runtime.agents.get_run(first.json()['run_id']).input['request_time']
        assert saved['timezone']=='America/Los_Angeles'
        state=await c.get('/messager/bots/'+bot['id']+'/dialogue/state',params={'session_id':sid});assert state.status_code==200
        assert state.json()['runs'][0]['dialogue']


def test_selected_attachments_are_verified_but_not_parsed_before_task_queue(runtime,tmp_path,monkeypatch):
    bot,sid,_,_=setup(runtime);source=tmp_path/'selected.txt';source.write_text('fixture selected text')
    item=runtime.documents.create_reference(sid,source,filename='selected.txt',media_type='text/plain')
    def unexpected(*args,**kwargs):raise AssertionError('Main dialogue must not parse attachments')
    monkeypatch.setattr(runtime.app_chat,'attachment_content',unexpected)
    rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'defer-attachment','inspect attachment','fixture',[item.id])
    assert runtime.agents.get_run(rid).input['selected_materials']['files'][0]['id']==item.id
    projected=runtime.app_chat.message_page(P(),sid)['items'][-1]['attachments'][0]
    assert projected=={'id':item.id,'filename':item.filename,'media_type':'text/plain','size_bytes':item.size_bytes}


@pytest.mark.parametrize(('media_type', 'name'), [('audio/wav', 'selected.wav'), ('image/png', 'selected.png')])
def test_selected_media_is_readable_in_its_task_session(runtime, tmp_path, media_type, name):
    from ai2apps.core import ResourceNotFoundError

    bot, sid, _, _ = setup(runtime)
    source = tmp_path / name
    source.write_bytes(b'selected media fixture')
    original = runtime.documents.create_reference(sid, source, media_type=media_type)
    unselected = runtime.documents.create_reference(sid, source, filename='unselected-'+name, media_type=media_type)
    service = runtime.messager_dialogue
    rid = service.submit(P(), bot['id'], sid, 'media-request', 'process the attachment', 'fixture', [original.id])
    with runtime.database.transaction(write=True) as db:
        db.execute("INSERT INTO messager_dialogue_jobs VALUES('job-media','local',?,?,?,'Process media','queued',NULL,NULL,NULL)", (bot['id'], sid, rid))

    job = service.start('job-media')
    worker = job['worker_session']
    run = runtime.agents.get_run(job['worker_run'])
    selected, = run.input['selected_materials']['files']
    attached, = runtime.documents.list(worker)
    assert attached.id == selected['id'] != original.id
    model_input = json.dumps(run.input['content'])
    assert 'attachment_id='+attached.id in model_input
    assert original.id not in model_input and unselected.id not in model_input
    assert attached.blob_id == original.blob_id
    assert runtime.documents.source_path(worker, attached.id).read_bytes() == source.read_bytes()
    assert runtime.documents.link_selected(sid, worker, original.id).id == attached.id
    with pytest.raises(ResourceNotFoundError):
        runtime.documents.get(worker, unselected.id)

@pytest.mark.parametrize('media_type,name',[('image/png','arbitrary.png'),('audio/mpeg','different.mp3')])
def test_task_multimodal_result_keeps_parts_and_repairs_exact_legacy_projection(runtime,tmp_path,media_type,name):
    from types import SimpleNamespace
    from ai2apps.storage import MessagePartInput
    from ai2apps.storage.repositories import MessageRepository
    bot,sid,_,_=setup(runtime);s=runtime.messager_dialogue
    worker=sid
    path=tmp_path/name;path.write_bytes(b'fixture-media');asset=runtime.workspace.import_artifact(worker,path,name=name,media_type=media_type)
    content=[{'type':'text','text':'完成了。\n\nA readable caption.'},{'type':'image_url','image_url':{'url':'/v1/platform/sessions/'+worker+'/artifacts/'+asset.id+'/download','artifact_id':asset.id}}]
    refs=[{'session_id':worker,'artifact_id':asset.id}]
    for ref in ('typed-job','legacy-job'):
        with runtime.database.transaction(write=True) as db:db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',?,?,NULL)",(ref,'local',bot['id'],sid,'source-'+ref,'Typed result',worker,None))
        s.sessions.link(s.row(ref))
        run=SimpleNamespace(id='result-'+ref,status=SimpleNamespace(value='completed'),output={'content':content,'artifacts':refs},error=None)
        if ref=='legacy-job':
            mapping,outputs=s.copy_outputs(refs,worker,sid)
            metadata={'task_session_id':ref,'origin':'bot_agent_chat_task','agent_run_id':run.id,'bot_job_id':ref,'artifacts':outputs}
            s.append(sid,'assistant',s.remap(str(content),mapping),'bot-job-result:'+ref,metadata)
        s.settle(ref,run);s.settle(ref,run)
        record=MessageRepository(runtime.database).get_by_idempotency_key(sid,'bot-job-result:'+ref)
        assert record.parts[0].kind=='openai_content'
        item=next(x for x in runtime.app_chat.message_page(P(),sid)['items'] if x['id']==record.message.id)
        assert item['content']=='完成了。\n\nA readable caption.' and len(item['artifacts'])==1
        assert "'type':" not in item['content']

def test_historical_image_attachment_display_uses_owned_record_metadata(runtime,tmp_path):
    bot,sid,_,_=setup(runtime)
    source=tmp_path/'photo.png'
    source.write_bytes(b'fixture-image-bytes')
    item=runtime.documents.create_reference(sid,source,filename='reference.png',media_type='image/png')
    rid=runtime.messager_dialogue.submit(P(),bot['id'],sid,'image-display','Please see attachment','fixture',[item.id])
    # Persisted input intentionally remains id/name only, as in old conversations.
    assert runtime.agents.get_run(rid).input['selected_materials']['files']==[{'id':item.id,'filename':'reference.png'}]
    attachment=runtime.app_chat.message_page(P(),sid)['items'][-1]['attachments'][0]
    assert attachment['media_type']=='image/png' and attachment['size_bytes']==item.size_bytes

@pytest.mark.asyncio
async def test_clock_context_reaches_reply_and_reviewed_task(runtime, monkeypatch):
    from datetime import datetime, timedelta, UTC
    from ai2apps.core import clock
    from ai2apps.messager.tasks import PROPOSE
    from ai2apps.todo.models import resolve_schedule, next_due

    bot, sid, _, _ = setup(runtime)
    bot_id = bot['id']
    from types import SimpleNamespace
    from ai2apps import model_providers
    from ai2apps.messager.conversation_profile import settings
    package = SimpleNamespace(metadata={'reasoning': {'mode': 'optional',
        'effort_control': {'format': 'chat_template', 'efforts': ['medium']}}})
    monkeypatch.setattr(model_providers, 'resolve_package_model', lambda r, model: package if model == 'fixture' else None)
    settings(runtime, 'local', bot_id, model_id='fixture', expected_revision=0, reasoning_effort='medium')
    dialogue = runtime.messager_dialogue
    instant = datetime.now(UTC).replace(microsecond=0)
    sampled = instant

    def now():
        return sampled

    monkeypatch.setattr(clock, 'utc_now', now)
    seen = []

    async def model(request):
        assert request.get('reasoning_effort') == 'medium'
        messages = request['messages']
        if 'Decide quickly' in messages[0]['content']:
            data = json.loads(messages[-2]['content'].removeprefix('Host request_time: '))
            assert data['timezone'] == 'America/Los_Angeles'
            assert not request.get('tools')
            if messages[-1]['content'] == 'What time is it?':
                return response(text=json.dumps({'kind':'reply', 'text':data['local']}))
            return response(text=json.dumps({'kind':'task', 'text':'Queued', 'title':'Clock task'}))
        results = [json.loads(m['content']) for m in messages if m['role'] == 'tool']
        if not results:
            assert 'execution_time' in json.dumps(messages)
            return response('agent.current_time', {})
        if any(str(m.get('content')).startswith('Reviewed schedule\n\n') for m in messages):
            assert results[-1]['timezone'] == 'America/Los_Angeles'
            return response(text='Reviewed task clock read.')
        if len(results) == 1:
            seen.append(results[0])
            assert results[0]['timezone'] == 'America/Los_Angeles'
            return response('app.describe', {'capability':PROPOSE})
        if not any('proposal_id' in result for result in results):
            return response(PROPOSE, {'title':'Reviewed schedule', 'prompt':'Summarize saved material',
                                      'delay_minutes':5})
        return response(text='Review the schedule.')

    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        first = dialogue.submit(P(),bot_id,sid,'clock-question','What time is it?','fixture',[],
                                client_timezone='America/Los_Angeles')
        await wait(runtime,first,'completed')
        assert runtime.agents.get_run(first).output['content'] == clock.time_snapshot('America/Los_Angeles')['local']
        assert dialogue.submit(P(),bot_id,sid,'clock-question','What time is it?','fixture',[],
                               client_timezone='America/Los_Angeles') == first
        second = dialogue.submit(P(),bot_id,sid,'clock-schedule','Run in five minutes','fixture',[],
                                 client_timezone='America/Los_Angeles')
        sampled += timedelta(seconds=30)
        await wait(runtime,second,'completed')
        await job_wait(runtime,second,'completed')
        assert seen and datetime.fromisoformat(seen[0]['utc']) == sampled
        proposal = runtime.messager_task_execution.work('local',bot_id)['proposals'][0]
        schedule = proposal['proposal']['schedule']
        assert schedule['timezone'] == 'America/Los_Angeles'
        assert datetime.fromisoformat(schedule['once_at']) == instant + timedelta(minutes=5)
        assert proposal['next_due'] == schedule['once_at']
        assert all(task['title'] != 'Reviewed schedule' for task in runtime.todo.store.snapshot('local')['tasks'])
        receipt = runtime.messager_task_execution.decide('local',bot_id,proposal['id'],proposal['review_hash'],'approve')
        launched = runtime.todo.launch('local',receipt['task_id'],principal=P(),request_key='clock-fixture-launch')
        from test_bot_todo_execution import until
        finished = await until(lambda: next((row for row in runtime.todo.store.snapshot('local')['runs']
                               if row['id'] == launched['id'] and row['status'] == 'completed'), None))
        assert finished['agent_run_id']
        daily = resolve_schedule({'frequency':'daily','hour':7}, reference=instant, timezone='America/Los_Angeles')
        amended = resolve_schedule({'hour':8}, reference=instant, timezone='Asia/Shanghai', previous=daily.model_dump())
        assert amended.timezone == daily.timezone
        assert next_due(amended.model_dump(), instant) > instant
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_thinking_level_reaches_dialogue_and_task_from_same_admission(runtime, monkeypatch):
    from ai2apps.messager.conversation_profile import settings

    bot, sid, _, _ = setup(runtime)
    bot_id = bot['id']
    model_id = 'cloud/test-provider/conversation'
    monkeypatch.setattr(runtime.model_manager, 'resolve_cloud_model', lambda model: {
        'capabilities': {'reasoningControl': {'format': 'thinking', 'efforts': ['low', 'high'],
                                              'aliases': {'medium': 'high'}, 'can_disable': True}},
    } if model == model_id else None)
    saved = settings(runtime, 'local', bot_id, model_id=model_id, expected_revision=0, reasoning_effort='high')
    assert saved['supported_reasoning_efforts'] == ['none', 'low', 'high']
    assert saved['reasoning_effort'] == 'high'
    with pytest.raises(ValueError, match='unavailable'):
        settings(runtime, 'local', bot_id, model_id=model_id, expected_revision=1, reasoning_effort='max')
    requests = []

    async def model(request):
        requests.append(request)
        if 'Decide quickly' in request['messages'][0]['content']:
            if request['messages'][-1]['content'] == 'Do some work':
                # Change the profile while the Bot is deciding what Task to start.
                settings(runtime, 'local', bot_id, model_id=model_id, expected_revision=1, reasoning_effort=None)
                return response(text=json.dumps({'kind': 'task', 'text': 'Queued', 'title': 'Thinking fixture'}))
            return response(text=json.dumps({'kind': 'reply', 'text': 'Hello'}))
        if not any(m.get('role') == 'tool' for m in request['messages']):
            value = response('agent.current_time', {})
            value['choices'][0]['message']['reasoning_content'] = 'fixture opaque reasoning'
            return value
        assert any(m.get('reasoning_content') == 'fixture opaque reasoning'
                   and m.get('tool_calls') for m in request['messages'])
        return response(text='Done')

    async def cloud_model(request, *, context=None):
        return await model(request)

    runtime.agent_runtime.bind_model_provider(model)
    monkeypatch.setattr(runtime.model_invocations, "invoke_agent_cloud_json", cloud_model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        service = runtime.messager_dialogue
        run = service.submit(P(), bot_id, sid, 'thinking-task', 'Do some work', model_id, [])
        await wait(runtime, run, 'completed')
        await job_wait(runtime, run, 'completed')
        assert len(requests) >= 3
        assert not any('fixture opaque reasoning' in str(m['content']) for m in runtime.app_chat.message_page(P(), sid)['items'])
        assert all(request['reasoning_effort'] == 'high' for request in requests)
        default_run = service.submit(P(), bot_id, sid, 'thinking-default', 'Hello', model_id, [])
        await wait(runtime, default_run, 'completed')
        assert 'reasoning_effort' not in requests[-1]
    finally:
        await runtime.stop_background_tasks()
