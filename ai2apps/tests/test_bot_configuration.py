"""Host-reviewed Bot configuration; real services/SQLite, synthetic model."""
import json
from dataclasses import replace
import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.identity import RequestPrincipal
from ai2apps.messager.bots import install, REGISTRATION
from ai2apps.messager.configuration import CONFIGURE
from test_app_interactions import runtime,wait
from test_app_chat_durable import bind_identity,response

P=RequestPrincipal.legacy_local


def setup(runtime):
    install(runtime);d=runtime.messager_bots;bot=d.create('local','Configuration fixture','Original duty')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    rid=runtime.app_chat.submit(P(),sid,'fixture-source','Explicit configuration request','fixture-model')
    ctx=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=rid)
    return bot,sid,rid,ctx,runtime.messager_bot_configuration


@pytest.mark.asyncio
async def test_real_model_loop_proposes_but_only_host_can_apply_memory(runtime):
    install(runtime);bot=runtime.messager_bots.create('local','Memory','Save preferences')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    async def model(request):
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if not results or results[-1].get('error',{}).get('code') in ('tool_declaration_required','tool_not_available'):return response(CONFIGURE,{'kind':'memory','text':'Prefer concise summaries'})
        return response(text='The proposed memory awaits your review.')
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        rid=runtime.app_chat.submit(P(),sid,'remember','Remember my summary preference','fixture-model');await wait(runtime,rid,'completed')
        assert runtime.messager_bots.memory.context('local',bot['id'])==[]
        service=runtime.messager_bot_configuration;proposal=service.pending('local',bot['id'])[0]
        app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
        url=f"/messager/bots/{bot['id']}/configurations/{proposal['id']}/approve"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            assert (await c.post(url,json={'review_hash':proposal['review_hash']})).status_code==403
            result=await c.post(url,json={'review_hash':proposal['review_hash']},headers={'Origin':'http://test'})
            assert result.status_code==200,result.text
            assert result.json()['status']=='applied'
            assert (await c.post(url,json={'review_hash':proposal['review_hash']},headers={'Origin':'http://test'})).json()==result.json()
        assert len(runtime.messager_bots.memory.context('local',bot['id']))==1
        assert runtime.messager_bot_permissions.current('local',bot['id'])[1].get('todo.read') is None
        with runtime.database.transaction() as db:
            assert db.execute("SELECT count(*) FROM messages WHERE session_id=? AND idempotency_key=?",(sid,'bot-configuration-result:'+proposal['id'])).fetchone()[0]==1
    finally:await runtime.agent_runtime.stop()


def test_identity_reject_stale_review_isolation_and_cleanup(runtime,monkeypatch):
    bot,sid,rid,ctx,s=setup(runtime);d=runtime.messager_bots
    proposed=s.propose({'kind':'identity','duty':'New duty'},replace(ctx,invocation_id='identity'))
    # Repeated Tool invocation cannot create a second proposal.
    assert s.propose({'kind':'identity','duty':'New duty'},replace(ctx,invocation_id='identity'))['proposal_id']==proposed['proposal_id']
    row=s.pending('local',bot['id'])[0]
    with pytest.raises(ValueError):s.decide('local',bot['id'],row['id'],'0'*64,'approve')
    with pytest.raises(PermissionError):s.decide('foreign',bot['id'],row['id'],row['review_hash'],'approve')
    d.update('local',bot['id'],'Changed elsewhere','Current duty')
    with pytest.raises(ValueError):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert s.decide('local',bot['id'],row['id'],row['review_hash'],'reject')['status']=='rejected'
    assert d.identity('local',{'bot_id':bot['id']})['duty']=='Current duty'
    s.propose({'kind':'identity','duty':'Confirmed duty'},replace(ctx,invocation_id='identity-2'))
    row=s.pending('local',bot['id'])[0];result=s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert result['result']['name']=='Changed elsewhere' and result['result']['duty']=='Confirmed duty'
    s.propose({'kind':'identity','duty':'Racy duty'},replace(ctx,invocation_id='identity-race'))
    row=s.pending('local',bot['id'])[0];original_before=s.before
    def concurrent_ui_save(*args):
        snapshot=original_before(*args)
        d.update('local',bot['id'],'Changed elsewhere','Concurrent UI duty')
        return snapshot
    monkeypatch.setattr(s,'before',concurrent_ui_save)
    with pytest.raises(ValueError,match='before saving'):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert d.identity('local',{'bot_id':bot['id']})['duty']=='Concurrent UI duty'


def test_background_and_old_epoch_cannot_propose_or_apply(runtime):
    bot,sid,rid,ctx,s=setup(runtime)
    s.propose({'kind':'memory','text':'User fact'},replace(ctx,invocation_id='memory'))
    row=s.pending('local',bot['id'])[0]
    original_provider=s.provider
    s.provider=replace(s.provider,version='changed')
    with pytest.raises(PermissionError):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    s.provider=original_provider
    with runtime.database.transaction(write=True) as db:db.execute("UPDATE agent_runs SET input_json=json_set(input_json,'$.execution_origin','hook') WHERE id=?",(rid,))
    with pytest.raises(PermissionError):s.propose({'kind':'memory','text':'Hook fact'},replace(ctx,invocation_id='hook'))
    runtime.messager_bot_permissions.invalidate('local',bot['id'])
    with pytest.raises(PermissionError):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert s.decide('local',bot['id'],row['id'],row['review_hash'],'reject')['status']=='rejected'


def make_scheduled(runtime,bot,ctx,key):
    from ai2apps.todo.service import TodoService
    if runtime.todo is None:runtime.todo=TodoService(runtime)
    tasks=runtime.messager_task_execution
    ref=tasks.propose({'title':'Daily news','prompt':'Read saved articles','schedule':{'frequency':'daily','hour':6,'timezone':'Asia/Shanghai'}},replace(ctx,invocation_id=key))
    row=tasks.proposal('local',bot['id'],ref['proposal_id'])
    return tasks.decide('local',bot['id'],row['id'],row['review_hash'],'approve')['task_id']


def test_schedule_disable_receipt_recovers_cross_database_gap_without_replay(runtime,monkeypatch):
    bot,sid,rid,ctx,s=setup(runtime);task=make_scheduled(runtime,bot,ctx,'daily')
    assert s.plans('local',bot['id'])[0]['schedule']['hour']==6
    s.propose({'kind':'pause_schedule','task_id':task},replace(ctx,invocation_id='pause'))
    row=s.pending('local',bot['id'])[0]
    original=runtime.todo.store.disable_schedule
    def after_commit(*args):original(*args);raise RuntimeError('Synthetic stop after durable Todo commit')
    monkeypatch.setattr(runtime.todo.store,'disable_schedule',after_commit)
    with pytest.raises(RuntimeError):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    monkeypatch.setattr(runtime.todo.store,'disable_schedule',lambda *args:pytest.fail('Must read original receipt, never replay'))
    result=s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert result['status']=='applied' and not result['result']['active_runs_cancelled']
    assert runtime.todo.store.get('local',task)['next_due'] is None
    with runtime.todo.store.connect() as db:assert db.execute('SELECT count(*) FROM schedule_disable_receipts').fetchone()[0]==1
    assert runtime.todo.store.snapshot('local')['runs']==[]


def test_configuration_rejects_foreign_tasks_and_changed_task_revision(runtime):
    bot,sid,rid,ctx,s=setup(runtime);task=make_scheduled(runtime,bot,ctx,'scheduled')
    sibling=runtime.messager_bots.create('local','Other Bot','Separate work')
    with pytest.raises(PermissionError):s.before('local',sibling['id'],{'kind':'pause_schedule','task_id':task})
    s.propose({'kind':'pause_schedule','task_id':task},replace(ctx,invocation_id='review-pause'))
    row=s.pending('local',bot['id'])[0]
    with runtime.todo.store.connect() as db:db.execute('UPDATE tasks SET revision=revision+1 WHERE id=?',(task,))
    with pytest.raises(ValueError):s.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    assert runtime.todo.store.get('local',task)['next_due'] is not None


def test_generic_schedule_disable_owner_receipt_and_admission_guard(tmp_path):
    from test_todo import service
    store_service=service(tmp_path)
    task=store_service.store.save('local',{'title':'Unrelated owner schedule','model':'fixture','schedule':{'frequency':'daily','hour':6}},create_inbox=True)
    with pytest.raises(KeyError):store_service.store.disable_schedule('foreign',task['id'],1,'other-owner')
    result=store_service.store.disable_schedule('local',task['id'],task['revision'],'unique-pause')
    assert store_service.store.disable_schedule('local',task['id'],task['revision'],'unique-pause')==result
    with pytest.raises(ValueError):store_service.store.disable_schedule('local',task['id'],999,'unique-pause')
    with pytest.raises(ValueError,match='disabled'):store_service.launch('local',task['id'],'2026-11-04T00:00:00+00:00',principal=P())
    assert store_service.store.snapshot('local')['runs']==[]
