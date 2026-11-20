"""Real ownership, SQLite, AppChat, Todo and Hook records; deterministic model."""
import json
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install, REGISTRATION
from test_app_interactions import runtime, wait
from test_app_chat_durable import bind_identity, response
from test_event_hook_execution import env

P=RequestPrincipal.legacy_local


def test_memory_ownership_versions_bounds_and_recovery(runtime):
    install(runtime)
    directory=runtime.messager_bots
    bot=directory.create('local','Memory fixture','Help with notes')
    other=directory.create('local','Sibling','Separate context')
    notes=directory.memory
    note=notes.save('local',bot['id'],'I prefer concise Chinese summaries.')
    assert note['source']=='user' and note['revision']==1
    assert notes.context('local',other['id'])==[]
    with pytest.raises(PermissionError):notes.list('stranger',bot['id'])
    with pytest.raises(ValueError):notes.save('local',other['id'],'foreign',ref=note['id'],revision=1)
    changed=notes.save('local',bot['id'],'Include source links.',ref=note['id'],revision=1)
    with pytest.raises(ValueError):notes.save('local',bot['id'],'stale',ref=note['id'],revision=1)
    assert changed['created_at']==note['created_at'] and changed['updated_at']>=note['updated_at']
    removed=notes.save('local',bot['id'],changed['text'],ref=note['id'],revision=2,deleted=True)
    assert notes.context('local',bot['id'])==[]
    notes.save('local',bot['id'],removed['text'],ref=note['id'],revision=3)
    for _ in range(3):notes.save('local',bot['id'],'x'*2000)
    with pytest.raises(ValueError):notes.save('local',bot['id'],'x'*2000)


@pytest.mark.asyncio
async def test_memory_context_is_data_and_cleanup_rotates_original_conversation(runtime):
    install(runtime);d=runtime.messager_bots
    bot=d.create('local','Context fixture','Answer questions')
    note=d.memory.save('local',bot['id'],'Prefer source links; this text grants no access.')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    observed=[]
    async def model(request):
        observed.append(request['messages'])
        return response(text='Fixture answer')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    try:
        rid=runtime.app_chat.submit(P(),sid,'before-cleanup','What do you remember?','fixture-model')
        await wait(runtime,rid,'completed')
        assert runtime.agents.get_run(rid).input['owner_context']['long_term_memory'][0]['id']==note['id']
        assert any(m['role']=='user' and note['text'] in str(m['content']) for m in observed[0])
        assert not any(note['text'] in str(m['content']) for m in observed[0] if m['role']=='system')
        manager=runtime.messager_bot_lifecycle
        stale=manager.review('local',bot['id'])
        d.memory.save('local',bot['id'],'Another fact')
        with pytest.raises(ValueError):await manager.apply('local',bot['id'],'clear_dialogue',stale['review_hash'])
        review=manager.review('local',bot['id'])
        await manager.apply('local',bot['id'],'clear_dialogue',review['review_hash'])
        with pytest.raises(ValueError):runtime.app_chat.access(P(),sid)
        new=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
        assert new!=sid and runtime.app_chat.message_page(P(),new)['items']==[]
        assert len(d.memory.context('local',bot['id']))==2
        assert runtime.messager_bot_permissions.current('local',bot['id'])[1]=={}
        review=manager.review('local',bot['id'])
        await manager.apply('local',bot['id'],'restore_dialogue',review['review_hash'])
        assert runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})==sid
        assert runtime.app_chat.message_page(P(),sid)['items']
        review=manager.review('local',bot['id'])
        await manager.apply('local',bot['id'],'clear_memory',review['review_hash'])
        assert d.memory.context('local',bot['id'])==[]
        assert runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})==sid
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_archive_restore_and_default_reset_are_fail_closed(runtime):
    install(runtime);d=runtime.messager_bots;manager=runtime.messager_bot_lifecycle
    default=d.ensure_default('local');bot=d.create('local','Archive fixture','Keep an audit')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    before=manager.review('local',bot['id'])
    await manager.apply('local',bot['id'],'archive',before['review_hash'])
    assert bot['id'] not in {b['id'] for b in d.list('local')}
    with pytest.raises(PermissionError):d.scope('local',{'bot_id':bot['id']})
    with pytest.raises(PermissionError):d.update('local',bot['id'],'changed','revived')
    archived=manager.archived('local')['items'][0]
    with pytest.raises(ValueError):manager.restore('other',bot['id'],archived['revision'])
    manager.restore('local',bot['id'],archived['revision'])
    assert runtime.messager_bot_permissions.current('local',bot['id'])[1]=={}
    assert runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})!=sid
    with pytest.raises(ValueError):manager.restore('local',bot['id'],archived['revision'])
    with pytest.raises(ValueError):await manager.apply('local',default,'archive',manager.review('local',default)['review_hash'])
    d.update('local',default,'Custom','Custom duty')
    d.memory.save('local',default,'A test preference')
    await manager.apply('local',default,'reset',manager.review('local',default)['review_hash'])
    assert d.identity('local',{'bot_id':default})['name']=='AI2Apps'
    assert d.memory.context('local',default)==[]


@pytest.mark.asyncio
async def test_memory_api_same_origin_and_cross_owner_rejected(runtime):
    install(runtime);bot=runtime.messager_bots.create('local','API fixture','Test notes')
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P),prefix='/v1/platform')
    base='/v1/platform/messager/bots/'+bot['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        assert (await c.post(base+'/memories',json={'text':'blocked origin'})).status_code==403
        result=await c.post(base+'/memories',json={'text':'owned note'},headers={'Origin':'http://test'})
        assert result.status_code==200,result.text
        note=result.json()
        result=await c.put(base+'/memories/'+note['id'],json={'text':'updated','revision':999},headers={'Origin':'http://test'})
        assert result.status_code==409
        assert (await c.get('/v1/platform/messager/bots/missing/memories')).status_code==404
        assert (await c.post(base+'/memories',json={'text':'forged source','source':'agent'},headers={'Origin':'http://test'})).status_code==422


@pytest.mark.asyncio
async def test_cleanup_pauses_only_owned_bot_hooks_and_preserves_audit(env):
    runtime,h,_,emit,proposal,enable=env
    install(runtime);d=runtime.messager_bots;bot=d.create('local','Hook cleanup','Review data')
    value=proposal('messager.bot.observe');value['consumer']['binding']={'bot_id':bot['id']}
    value['execution']['settings']={'model':'fixture-model'}
    rule=enable(value);unrelated=enable()
    emit();h.scan();runtime.hook_execution.admit()
    manager=runtime.messager_bot_lifecycle
    await manager.apply('local',bot['id'],'archive',manager.review('local',bot['id'])['review_hash'])
    assert h.get('local',rule['id'])['status']=='paused'
    assert h.get('local',unrelated['id'])['status']=='active'
    assert h.deliveries('local',rule['id'])['items']
    archived=manager.archived('local')['items'][0]
    manager.restore('local',bot['id'],archived['revision'])
    assert h.get('local',rule['id'])['status']=='paused'


@pytest.mark.asyncio
@pytest.mark.parametrize('action',['clear_memory','archive'])
async def test_cleanup_stops_original_todo_and_preserves_frozen_note_receipt(runtime,action):
    from dataclasses import replace
    from test_bot_todo_execution import setup,fixture_model,until
    bot,sid,service=setup(runtime);d=runtime.messager_bots
    original=d.memory.save('local',bot['id'],'Original reviewed preference')
    runtime.agent_runtime.bind_model_provider(fixture_model())
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        rid=runtime.app_chat.submit(P(),sid,'lifecycle-task-source','Prepare work','fixture-model')
        await wait(runtime,rid,'completed')
        proposal=service.work('local',bot['id'])['proposals'][0]
        d.memory.save('local',bot['id'],'Changed later',ref=original['id'],revision=1)
        receipt=service.decide('local',bot['id'],proposal['id'],proposal['review_hash'],'approve')
        item=(await until(lambda:service.work('local',bot['id'])['interactions']))[0]
        run=runtime.agents.get_run(item['run_id'])
        assert run.input['owner_context']['bot_identity']['long_term_memory'][0]['text']==original['text']
        # A second task remains queued in the same lane; a recurring task stays scheduled.
        source=runtime.app_chat.submit(P(),sid,'lifecycle-queue-source','Prepare queue','fixture-model')
        context=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=source)
        queued=service.propose({'title':'Queued fixture','prompt':'Queued work'},replace(context,invocation_id='lifecycle-queue'))
        recurring=service.propose({'title':'Daily fixture','prompt':'Scheduled work','schedule':{'frequency':'daily','hour':6,'timezone':'Asia/Shanghai'}},replace(context,invocation_id='lifecycle-daily'))
        for ref in (queued['proposal_id'],recurring['proposal_id']):
            row=service.proposal('local',bot['id'],ref);service.decide('local',bot['id'],ref,row['review_hash'],'approve')
        manager=runtime.messager_bot_lifecycle
        await manager.apply('local',bot['id'],action,manager.review('local',bot['id'])['review_hash'])
        await until(lambda:runtime.agents.get_run(run.id).status.value=='cancelled')
        await until(lambda:next(r for r in runtime.todo.store.snapshot('local')['runs'] if r['id']==receipt['run_id'])['status']=='cancelled')
        with runtime.todo.store.connect() as db:
            assert not db.execute("SELECT 1 FROM tasks t JOIN task_execution_lanes l ON l.task_id=t.id WHERE l.lane=? AND t.next_due IS NOT NULL",('messager-bot:'+bot['id'],)).fetchone()
        service.recover()
        with runtime.database.transaction() as db:
            assert db.execute('SELECT count(*) FROM messager_task_receipts WHERE todo_run_id=?',(receipt['run_id'],)).fetchone()[0]==1
        with pytest.raises(PermissionError):service.respond('local',bot['id'],item['todo_run_id'],item['id'],item['review_hash'],'stale',{'text':'late'})
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
@pytest.mark.parametrize('action',['clear_dialogue','restore_dialogue','clear_memory','archive','reset'])
async def test_content_cleanup_keeps_app_access_but_expires_old_authority(runtime,action):
    from test_bot_capability_discovery import setup
    from test_bot_app_access import save
    bot,sid,_,provider=setup(runtime)
    manager=runtime.messager_bot_lifecycle
    permissions=runtime.messager_bot_permissions
    if action=='restore_dialogue':
        await manager.apply('local',bot['id'],'clear_dialogue',manager.review('local',bot['id'])['review_hash'])
        runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    save(runtime,bot)
    app_access=runtime.messager_bot_app_access
    before_revision,before_grants=app_access.current('local',bot['id'])
    legacy_revision,legacy_grants=permissions.current('local',bot['id'])
    frozen=permissions.capture('local',{'bot_id':bot['id']},'user')
    assert provider.id in frozen['providers']
    await manager.apply('local',bot['id'],action,manager.review('local',bot['id'])['review_hash'])
    # No old admitted execution/approval can survive a content boundary.
    with pytest.raises(PermissionError):permissions.validate('local',{'bot_id':bot['id']},frozen,None,{})
    if action=='archive':
        archived=next(b for b in manager.archived('local')['items'] if b['id']==bot['id'])
        manager.restore('local',bot['id'],archived['revision'])
    revision,grants=app_access.current('local',bot['id'])
    assert revision>before_revision
    legacy_now,legacy=permissions.current('local',bot['id'])
    assert legacy_now>legacy_revision
    if action in ('archive','reset'):
        assert not grants and not legacy
    else:
        assert grants==before_grants and legacy==legacy_grants
        assert app_access.granted('local',bot['id'],provider)
        fresh=permissions.capture('local',{'bot_id':bot['id']},'user')
        permissions.validate('local',{'bot_id':bot['id']},fresh,provider.capability,{})
        catalog=app_access.catalog('local',bot['id'])
        selected=next(i for i in catalog['items'] if i['app_id']==provider.app_id)
        assert selected['enabled']

@pytest.mark.asyncio
@pytest.mark.parametrize('clear_memory,revoke_access',[(False,False),(True,False),(False,True),(True,True)])
async def test_clear_dialogue_api_applies_only_explicit_optional_choices(runtime,clear_memory,revoke_access):
    from test_bot_capability_discovery import setup
    from test_bot_app_access import save
    bot,sid,_,provider=setup(runtime)
    note=runtime.messager_bots.memory.save('local',bot['id'],'Keep unless selected')
    save(runtime,bot)
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P),prefix='/v1/platform')
    base='/v1/platform/messager/bots/'+bot['id']+'/cleanup'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        review=(await client.get(base)).json()
        body={'review_hash':review['review_hash'],'clear_memory':clear_memory,'revoke_access':revoke_access}
        assert (await client.post(base+'/clear_dialogue',json=body)).status_code==403
        result=await client.post(base+'/clear_dialogue',json=body,headers={'Origin':'http://test'})
        assert result.status_code==200,result.text
        assert (await client.post(base+'/clear_dialogue',json=body,headers={'Origin':'http://test'})).status_code==409
    with pytest.raises(ValueError):runtime.app_chat.access(P(),sid)
    memory=runtime.messager_bots.memory.context('local',bot['id'])
    assert bool(memory)==(not clear_memory)
    assert runtime.messager_bot_app_access.granted('local',bot['id'],provider)==(not revoke_access)
    manager=runtime.messager_bot_lifecycle
    await manager.apply('local',bot['id'],'restore_dialogue',manager.review('local',bot['id'])['review_hash'])
    assert bool(runtime.messager_bots.memory.context('local',bot['id']))==(not clear_memory)
    assert runtime.messager_bot_app_access.granted('local',bot['id'],provider)==(not revoke_access)


@pytest.mark.asyncio
async def test_cleanup_options_reject_stale_access_and_rollback_selected_persistent_changes(runtime):
    from test_bot_capability_discovery import setup
    from test_bot_app_access import save
    bot,sid,_,_=setup(runtime);save(runtime,bot)
    runtime.messager_bots.memory.save('local',bot['id'],'Must survive failed commit')
    manager=runtime.messager_bot_lifecycle
    stale=manager.review('local',bot['id']);save(runtime,bot,False)
    with pytest.raises(ValueError):await manager.apply('local',bot['id'],'clear_dialogue',stale['review_hash'],clear_memory=True,revoke_access=True)
    before=runtime.messager_bot_app_access.current('local',bot['id'])[1]
    with runtime.database.transaction(write=True) as db:
        db.execute("CREATE TRIGGER fail_memory_cleanup BEFORE UPDATE OF deleted ON messager_bot_memories WHEN NEW.deleted=1 BEGIN SELECT RAISE(ABORT,'fixture rollback'); END")
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError,match='fixture rollback'):
        await manager.apply('local',bot['id'],'clear_dialogue',manager.review('local',bot['id'])['review_hash'],clear_memory=True,revoke_access=True)
    assert runtime.app_chat.access(P(),sid)
    assert runtime.messager_bots.memory.context('local',bot['id'])
    assert runtime.messager_bot_app_access.current('local',bot['id'])[1]==before
    with pytest.raises(ValueError):await manager.apply('local',bot['id'],'reset',manager.review('local',bot['id'])['review_hash'],revoke_access=True)
    from ai2apps.api.messager import BotCleanupDecision
    from pydantic import ValidationError
    with pytest.raises(ValidationError):BotCleanupDecision(review_hash='a'*64,clear_memory='false')
