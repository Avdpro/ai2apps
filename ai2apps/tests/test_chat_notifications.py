import json
from dataclasses import replace

import pytest

from ai2apps.chat.notifications import enqueue_completed_replies, authorize_conversation
from ai2apps.chat import turns
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import RequestPrincipal, IdentityRepository, OrganizationType
from test_direct_chat_turns import runtime, prepared, payload, result, wait


def ready(runtime, monkeypatch, owner='owner-a'):
    producer = runtime.remote.notifications
    monkeypatch.setattr(producer, 'identity', lambda: {'owner_id': owner, 'installation_id': 'installation-a',
        'device_id': 'device-a', 'access_epoch': 1, 'device_epoch': 1, 'credential_version': 1, 'cloud_origin': 'https://cloud.test'})
    monkeypatch.setattr(producer, 'supports_custom', lambda _: True)
    return producer


async def complete(runtime, scope='mobile-owner', owner='owner-a', key='first'):
    identities = IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='installation-a',cloud_device_id='device-a',organization_id='org-a',
        organization_type=OrganizationType.HOUSEHOLD,core_user_id=owner,billing_account_id='bill-a',access_epoch=1)
    principal = replace(identities.local_principal_for(owner), client_scope=scope)
    repo, sid, revision = prepared(runtime, principal)
    async def model(_): return result('Private answer that must not appear in the notification')
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.agent_runtime.start()
    run = turns.submit(runtime, repo, sid, **payload(revision, key))
    await wait(runtime, run.id, 'completed')
    return principal, repo, sid, run


@pytest.mark.asyncio
async def test_committed_reply_notifies_once_and_routes_exact_mobile_scope(runtime, monkeypatch):
    ready(runtime, monkeypatch)
    principal, repo, sid, run = await complete(runtime)
    try:
        assert enqueue_completed_replies(runtime) == 1
        assert enqueue_completed_replies(runtime) == 0
        with runtime.database.transaction() as db:
            rows = db.execute('SELECT body_json FROM notification_producer_outbox').fetchall()
        body = json.loads(rows[0][0])
        assert len(rows) == 1 and body['metadata']['run_id'] == run.id
        assert body['target'] == {'type': 'app_route', 'app_id': 'ai2apps.general-chat', 'route': 'conversation', 'id': sid}
        assert 'Private answer' not in rows[0][0] and 'reasoning' not in rows[0][0]
        assert authorize_conversation(runtime, principal, sid)['notification-resource'] == sid
        for other in [replace(principal, client_scope='desktop'), replace(principal, actor_user_id='other')]:
            with pytest.raises(ResourceNotFoundError): authorize_conversation(runtime, other, sid)
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_recovery_capability_owner_history_and_atomic_retry(runtime, monkeypatch):
    producer = ready(runtime, monkeypatch)
    principal, repo, sid, run = await complete(runtime)
    try:
        with runtime.database.transaction(write=True) as db:
            saved=db.execute('SELECT updated_at FROM agent_runs WHERE id=?',(run.id,)).fetchone()[0]
            db.execute("UPDATE agent_runs SET updated_at='2020-01-01T00:00:00.000000Z' WHERE id=?",(run.id,))
        assert enqueue_completed_replies(runtime) == 0
        with runtime.database.transaction(write=True) as db:
            db.execute('UPDATE agent_runs SET updated_at=? WHERE id=?',(saved,run.id))
        monkeypatch.setattr(producer, 'supports_custom', lambda _: False)
        assert enqueue_completed_replies(runtime) == 0
        ready(runtime, monkeypatch, owner='other')
        assert enqueue_completed_replies(runtime) == 0
        ready(runtime, monkeypatch)
        original = runtime.events.append_in_transaction
        def fail(db, **kwargs):
            if kwargs['event_type'] == 'chat.reply.notification_queued': raise RuntimeError('crash before commit')
            return original(db, **kwargs)
        monkeypatch.setattr(runtime.events, 'append_in_transaction', fail)
        with pytest.raises(RuntimeError): enqueue_completed_replies(runtime)
        with runtime.database.transaction() as db:
            assert db.execute('SELECT count(*) FROM notification_producer_outbox').fetchone()[0] == 0
        monkeypatch.setattr(runtime.events, 'append_in_transaction', original)
        assert enqueue_completed_replies(runtime) == 1
        # Startup does not move the activation fence or replay committed notices.
        from ai2apps.chat.notifications import install
        install(runtime)
        assert enqueue_completed_replies(runtime) == 0
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_agent_chat_notifies_and_archived_route_is_rejected(runtime, monkeypatch):
    ready(runtime, monkeypatch)
    principal, repo, sid, first = await complete(runtime)
    try:
        assert enqueue_completed_replies(runtime)==1
        # Actual General Agent executor persists its final assistant message.
        run, _ = runtime.agents.create_run(session_id=sid, agent_key='ai2apps.general-agent',
            input={'model':'fixture-model','prompt':'Reply briefly','tools':[]}, idempotency_key='agent-fixture')
        runtime.agent_runtime.wake()
        done=await wait(runtime, run.id, 'completed')
        assert done.output['message_id']
        assert enqueue_completed_replies(runtime)==1
        with runtime.database.transaction() as db:
            body=json.loads(db.execute('SELECT body_json FROM notification_producer_outbox WHERE event_id=?',('chat.reply:'+run.id,)).fetchone()[0])
        assert body['metadata']['run_id']==run.id
        replacement,_=repo.create_thread(title='Replacement home')
        repo.set_home_thread(replacement.session.id,expected_revision=replacement.session.revision)
        with runtime.database.transaction(write=True) as db:
            db.execute("UPDATE sessions SET status='archived' WHERE id=?", (sid,))
        assert enqueue_completed_replies(runtime)==0
        with pytest.raises(ValueError):authorize_conversation(runtime,principal,sid)
    finally:
        await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_signed_mobile_resolves_with_its_own_principal_not_owner_desktop(runtime, monkeypatch):
    ready(runtime,monkeypatch)
    principal,repo,sid,run=await complete(runtime,scope='mobile-agent')
    try:
        from ai2apps.web.mobile_agent_gateway import dispatch, business_target
        assert business_target('POST','/chat/notification-target')=='/notifications/resolve-target'
        target={'type':'app_route','app_id':'ai2apps.general-chat','route':'conversation','id':sid}
        response=await dispatch(runtime,principal,'POST','/notifications/resolve-target',json.dumps({'target':target}).encode(),{'content-type':'application/json'})
        assert response.status_code==200,response.body
        assert json.loads(response.body)['parameters']['notification-resource']==sid
        response=await dispatch(runtime,replace(principal,client_scope='owner-home'),'POST','/notifications/resolve-target',json.dumps({'target':target}).encode(),{'content-type':'application/json'})
        assert response.status_code in (403,404)
    finally:
        await runtime.agent_runtime.stop()
