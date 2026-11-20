"""Real Bot directory, App Chat, read provider and Run; deterministic model."""
import json

import pytest

from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install, READ_TOOLS, REGISTRATION
from test_app_chat_durable import bind_identity, response
from test_app_interactions import runtime, wait
from bot_access_fixtures import restricted_bot


@pytest.mark.asyncio
async def test_bot_work_survives_detach_and_cannot_route_to_friend(runtime):
    install(runtime)
    directory = runtime.messager_bots
    bot = directory.create('local', 'Watch editor', 'Prepare watch news drafts')
    restricted_bot(runtime,bot,legacy_read=True)
    sibling = restricted_bot(runtime,directory.create('local', 'Editor', 'Review'))
    principal = RequestPrincipal.legacy_local()
    def open_bot(item):
        return runtime.app_chat.open(principal, REGISTRATION, {'bot_id': item['id']}, {})
    sid = open_bot(bot)
    assert sid != open_bot(sibling)
    assert directory.list('other') == []
    with pytest.raises(PermissionError):
        directory.scope('other', {'bot_id': bot['id']})
    ctx = runtime.tools.context_for_session(caller_id='test', session_id=sid)
    assert READ_TOOLS | {'messager.task.propose','messager.bot.configure'} <= set(runtime.app_chat.snapshot(principal,sid)['tools'])
    assert runtime.app_chat.visible(ctx, 'intelligence.refresh')
    # Discovery is not invocation authority; a direct call without a Run is denied.
    with pytest.raises(Exception):runtime.app_chat.authorize(ctx,'intelligence.refresh',{})
    called = False
    async def model(request):
        nonlocal called
        results = [m for m in request['messages'] if m['role']=='tool']
        if not results or json.loads(results[-1]['content']).get('error', {}).get('code') in ('tool_declaration_required','tool_not_available'):
            return response('intelligence.channels', {'limit': 10})
        assert 'error' not in json.loads(results[-1]['content'])
        called = True
        return response(text='Reviewed the saved channels; draft is ready.')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid = runtime.app_chat.submit(principal,sid,'bot-draft-request','Check my saved channels','fixture-model')
        await wait(runtime,rid,'completed')
        assert called and open_bot(bot)==sid
        restored=runtime.app_chat.snapshot(principal,sid)
        assert restored['runs'][0]['task_id']
        assert any('draft is ready' in m['content'] for m in restored['messages'])
        assert not runtime.app_chat.snapshot(principal,open_bot(sibling))['messages']
    finally:
        await runtime.stop_background_tasks()

def test_default_bot_stable_identity_and_owned_identity_update(runtime):
    install(runtime)
    directory=runtime.messager_bots
    ref=directory.ensure_default('local')
    assert directory.ensure_default('local')==ref
    directory.update('local',ref,'Renamed','New duty')
    assert directory.ensure_default('local')==ref
    assert directory.context('local',{'bot_id':ref})=={'name':'Renamed','duty':'New duty','long_term_memory':[],'managed_plans':{'items':[],'has_more':False}}
    with pytest.raises(PermissionError):directory.update('foreign',ref,'Forged','No')
    assert directory.ensure_default('foreign')!=ref

@pytest.mark.asyncio
async def test_avatar_api_presets_and_owned_gallery_images(runtime):
    import io,httpx
    from PIL import Image
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from ai2apps.gallery import GalleryRepository
    install(runtime);directory=runtime.messager_bots;bot=directory.create('local','Avatar fixture','Review')
    gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    stream=io.BytesIO();Image.new('RGB',(2,2),'blue').save(stream,format='PNG');stream.seek(0)
    own,_=gallery.import_stream('local',stream,name='avatar.png',media_type='image/png')
    stream.seek(0);foreign,_=gallery.import_stream('other',stream,name='private.png',media_type='image/png')
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        url='/messager/bots/'+bot['id']+'/avatar'
        assert (await c.put(url,json={'kind':'preset','preset':'robot','color':'#123456'})).status_code==200
        assert (await c.put(url,json={'kind':'preset','color':'javascript:bad'})).status_code==422
        assert (await c.put(url,json={'kind':'image','asset_id':foreign['id']})).status_code==404
        result=await c.put(url,json={'kind':'image','asset_id':own['id']});assert result.status_code==200,result.text
        assert next(b for b in directory.list('local') if b['id']==bot['id'])['avatar']['asset_id']==own['id']
        assert (await c.put('/messager/bots/not-owned/avatar',json={'kind':'preset'})).status_code==404

@pytest.mark.asyncio
async def test_bot_task_links_use_owned_todo_records_without_starting_work(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from test_todo import task
    from ai2apps.todo.service import TodoService
    runtime.todo = TodoService(runtime)
    install(runtime)
    directory = runtime.messager_bots
    bot = directory.create('local', 'Tasks', 'Help with work')
    sibling = directory.create('local', 'Other', 'Separate work')
    foreign = directory.create('other', 'Private', 'Private')
    t = task(runtime.todo.store, 'local', title='Owned project')
    private = task(runtime.todo.store, 'other', title='Private project')
    app = FastAPI()
    app.include_router(create_messager_router(lambda:runtime, RequestPrincipal.legacy_local))
    prefix = '/messager/bots/' + bot['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        candidates = (await client.get(prefix+'/task-candidates')).json()['items']
        assert [v['id'] for v in candidates] == [t['id']]
        assert set(candidates[0]) == {'id','title'}
        assert (await client.post(prefix+'/tasks', json={'task_id':private['id']})).status_code == 404
        assert (await client.get('/messager/bots/'+foreign['id']+'/tasks')).status_code == 404
        linked = await client.post(prefix+'/tasks', json={'task_id':t['id']})
        assert linked.status_code == 200, linked.text
        assert linked.json()['items'][0]['run'] is None
        assert runtime.todo.store.snapshot('local')['runs'] == []
        context = directory.context('local', {'bot_id':bot['id']})
        assert context['todo_tasks']['items'][0]['title'] == 'Owned project'
        assert 'todo_tasks' not in directory.context('local', {'bot_id':sibling['id']})
        assert (await client.post('/messager/bots/'+sibling['id']+'/tasks', json={'task_id':t['id']})).status_code == 409
        assert (await client.delete('/messager/bots/'+sibling['id']+'/tasks/'+t['id'])).status_code == 409
        assert (await client.delete(prefix+'/tasks/'+t['id'])).status_code == 200
        assert (await client.get(prefix+'/tasks')).json()['items'] == []

@pytest.mark.asyncio
async def test_foreground_bot_chat_remains_available_during_linked_todo_run(runtime, monkeypatch):
    import asyncio
    from test_todo import task
    install(runtime)
    bot = runtime.messager_bots.create('local', 'Parallel conversation', 'Report actual task state')
    await runtime.start_background_tasks(retention_interval_seconds=60)
    observed = False
    async def execute(id, owner, data):
        runtime.todo.store.run_update(id, 'waiting_input', log='Fixture task waiting for user reply')
        await asyncio.Event().wait()
    monkeypatch.setattr(runtime.todo, 'execute', execute)
    async def model(request):
        nonlocal observed
        rendered = json.dumps(request['messages'], ensure_ascii=False)
        assert 'todo_tasks' in rendered and 'waiting_input' in rendered
        observed = True
        return response(text='The linked Todo task is waiting for your reply. Open it in Todo to respond.')
    runtime.agent_runtime.bind_model_provider(model)
    try:
        t = task(runtime.todo.store, 'local', model='fixture-model')
        runtime.messager_bot_tasks.assign('local', bot['id'], t['id'])
        background = runtime.todo.launch('local', t['id'], principal=RequestPrincipal.legacy_local())['id']
        await asyncio.sleep(0)
        sid = runtime.app_chat.open(RequestPrincipal.legacy_local(), REGISTRATION, {'bot_id':bot['id']}, {})
        rid = runtime.app_chat.submit(RequestPrincipal.legacy_local(), sid, 'foreground-status', 'What is my task doing?', 'fixture-model')
        await wait(runtime, rid, 'completed')
        assert observed
        assert runtime.messager_bot_tasks.list('local', bot['id'])['items'][0]['run']['status'] == 'waiting_input'
        assert background in runtime.todo.jobs
    finally:
        await runtime.stop_background_tasks()
