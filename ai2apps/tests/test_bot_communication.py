"""Owned consultation flow: real Runtime/SQLite/API, deterministic models only."""
import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from fastapi import FastAPI
from ai2apps.api.messager import create_messager_router
from ai2apps.messager.communication import CONSULT,DIRECTORY,EXECUTOR
from test_bot_configuration import setup,P
from test_app_chat_durable import bind_identity,response
from test_app_interactions import runtime,wait


def fixture(r):
    source,sid,rid,ctx,_=setup(r)
    target=r.messager_bots.create('local','Reviewer','Give concise advice')
    ctx=replace(ctx,invocation_id='consult-original')
    return source,target,sid,rid,ctx,r.messager_bot_communication


def propose(r):
    source,target,sid,rid,ctx,s=fixture(r)
    ref=s.propose({'target_bot_id':target['id'],'question':'Compare the two supplied titles: A and B'},ctx)['request_id']
    return source,target,sid,rid,ctx,s,s.work('local',source['id'])[0]


@pytest.mark.asyncio
async def test_review_then_one_readonly_answer_returns_to_origin_and_survives_recovery(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    calls=[]
    runtime.messager_bots.memory.save('local',target['id'],'PRIVATE RECEIVER MEMORY')
    async def model(request):
        calls.append(request)
        assert not request.get('tools')
        assert 'PRIVATE RECEIVER MEMORY' not in json.dumps(request)
        return response(text='Title B is clearer from the supplied text.')
    runtime.agent_runtime.bind_model_provider(model)
    # Approval creates one durable run; a duplicate approval cannot create another.
    assert not s.get('local',source['id'],card['id'])['run_id']
    accepted=s.decide('local',source['id'],card['id'],card['review_hash'],'approve')
    assert s.decide('local',source['id'],card['id'],card['review_hash'],'approve')==accepted
    await runtime.agent_runtime.start()
    try:
        await wait(runtime,accepted['run_id'],'completed')
        s.work('local',source['id']);s.work('local',source['id'])
        messages=runtime.app_chat.message_page(P(),sid)['items']
        answer=[m for m in messages if 'Title B is clearer' in m['content']]
        assert len(answer)==1 and 'Reviewer' in answer[0]['content']
        assert len(calls)==1
        assert runtime.agents.get_run(accepted['run_id']).session_id!=sid
        assert runtime.messager_bot_permissions.current('local',target['id'])[1]=={}
        with runtime.database.transaction() as db:
            assert db.execute("SELECT count(*) FROM agent_runs WHERE agent_definition_id=(SELECT id FROM agent_definitions WHERE agent_key=?)",(EXECUTOR,)).fetchone()[0]==1
    finally:await runtime.agent_runtime.stop()


def test_recipient_isolation_idempotency_and_no_authority_inheritance(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    args={'target_bot_id':target['id'],'question':'Compare the two supplied titles: A and B'}
    assert s.propose(args,ctx)['request_id']==card['id']
    with pytest.raises(ValueError):s.propose({**args,'question':'different'},ctx)
    foreign=runtime.messager_bots.create('other','Foreign','Private')
    with pytest.raises(PermissionError):s.propose({'target_bot_id':foreign['id'],'question':'hello'},replace(ctx,invocation_id='foreign'))
    with pytest.raises(ValueError):s.propose({'target_bot_id':source['id'],'question':'loop'},replace(ctx,invocation_id='loop'))
    assert foreign['id'] not in {t['id'] for t in s.targets('local',source['id'])}
    with pytest.raises(PermissionError):s.get('other',source['id'],card['id'])
    with pytest.raises(PermissionError):s.get('local',target['id'],card['id'])
    with pytest.raises(ValueError):s.decide('local',source['id'],card['id'],'0'*64,'approve')
    assert s.decide('local',source['id'],card['id'],card['review_hash'],'reject')['status']=='rejected'
    assert s.work('local',source['id'])==[]
    assert s.get('local',source['id'],card['id'])['run_id'] is None


@pytest.mark.parametrize('change',['target_identity','target_epoch','source_epoch','expired'])
def test_stale_authority_or_review_never_sends(runtime,change):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    if change=='target_identity':runtime.messager_bots.update('local',target['id'],'Changed','New duty')
    elif change in ('target_epoch','source_epoch'):
        bot=target if change=='target_epoch' else source
        with runtime.database.transaction(write=True) as db:db.execute('UPDATE messager_bot_permissions SET revision=revision+1 WHERE bot_id=?',(bot['id'],))
    else:
        with runtime.database.transaction(write=True) as db:db.execute("UPDATE messager_bot_consultations SET expires_at='2000-01-01' WHERE id=?",(card['id'],))
    with pytest.raises((PermissionError,ValueError)):s.decide('local',source['id'],card['id'],card['review_hash'],'approve')
    assert s.get('local',source['id'],card['id'])['run_id'] is None
    assert s.work('local',source['id'])==[]


@pytest.mark.asyncio
async def test_receiver_cannot_emit_tools_and_queued_cancellation_does_not_call_model(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    run=s.decide('local',source['id'],card['id'],card['review_hash'],'approve')['run_id']
    await s.cancel('local',source['id'],card['id'])
    calls=[]
    async def model(request):calls.append(request);return response('any.tool',{})
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        await wait(runtime,run,'cancelled');s.work('local',source['id']);assert not calls
        # Another explicitly approved request returning a Tool call is terminal failure, not routed execution.
        ref=s.propose({'target_bot_id':target['id'],'question':'Give advice'},replace(ctx,invocation_id='second'))['request_id']
        row=s.get('local',source['id'],ref);next_run=s.decide('local',source['id'],ref,row['review_hash'],'approve')['run_id']
        for _ in range(300):
            observed=runtime.agents.get_run(next_run)
            if observed.status.value=='failed':break
            await asyncio.sleep(.01)
        assert observed.error['code']=='bot_consultation_answer'
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_api_requires_origin_and_preserves_request_identity(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    base='/messager/bots/'+source['id']+'/communication/'+card['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        assert (await c.post(base+'/decisions/approve',json={'review_hash':card['review_hash']})).status_code==403
        result=await c.post(base+'/decisions/reject',json={'review_hash':card['review_hash']},headers={'Origin':'http://test'})
        assert result.status_code==200,result.text
        # Explicit cancel path must not be consumed by a generic decision route.
        assert (await c.post(base+'/cancel',headers={'Origin':'http://test'})).status_code==200
        targets=await c.get('/messager/bots/'+source['id']+'/communication/targets')
        assert targets.status_code==200 and target['id'] in {b['id'] for b in targets.json()['items']}


@pytest.mark.asyncio
async def test_actual_bot_model_discovers_and_proposes_without_sending_or_blocking_dialogue(runtime):
    source,target,sid,rid,ctx,s=fixture(runtime)
    async def model(request):
        tools=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any('request_id' in t and t.get('sent') is False for t in tools):return response(text='The consultation awaits your review here.')
        return response(CONSULT,{'target_bot_id':target['id'],'question':'Is title B clear?'})
    runtime.agent_runtime.bind_model_provider(model);await runtime.agent_runtime.start()
    try:
        await wait(runtime,rid,'completed')
        work=s.work('local',source['id']);assert len(work)==1 and work[0]['status']=='pending'
        assert s.get('local',source['id'],work[0]['id'])['run_id'] is None
        assert runtime.app_chat.execution_authorization(rid)['mode']=='foreground'
    finally:await runtime.agent_runtime.stop()

@pytest.mark.asyncio
async def test_background_observer_delivers_without_open_view_and_revocation_cancels(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    async def model(request):return response(text='Persisted while the conversation is closed.')
    runtime.agent_runtime.bind_model_provider(model)
    accepted=s.decide('local',source['id'],card['id'],card['review_hash'],'approve')
    # Reconcile an admission gap before the observer starts; dedup retains one observer.
    s.recover();s.recover()
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,accepted['run_id'],'completed')
        for _ in range(150):
            row=s.get('local',source['id'],card['id'])
            if row['projected']:break
            await asyncio.sleep(.02)
        assert row['projected']==1
        assert any('conversation is closed' in m['content'] for m in runtime.app_chat.message_page(P(),sid)['items'])
    finally:await runtime.stop_background_tasks()


def test_revocation_and_lifecycle_review_include_communication_requests(runtime):
    source,target,sid,rid,ctx,s,card=propose(runtime)
    review=runtime.messager_bot_lifecycle.review('local',target['id'])
    assert any(c['id']==card['id'] for c in review['consultations'])
    runtime.messager_bot_permissions.invalidate('local',target['id'])
    row=s.get('local',source['id'],card['id'])
    assert row['status']=='cancelled' and row['run_id'] is None and row['projected']
    assert s.decide('local',source['id'],card['id'],card['review_hash'],'approve')['status']=='cancelled'
