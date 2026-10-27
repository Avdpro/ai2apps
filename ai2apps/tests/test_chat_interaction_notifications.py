import json
from dataclasses import replace

import pytest

from ai2apps.agents import InteractionAction, CompleteAction, InteractionKind
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import IdentityRepository, OrganizationType
from ai2apps.chat import ChatRepository
from ai2apps.chat.notifications import enqueue_pending_interactions, authorize_interaction, interaction_still_pending
from test_app_interactions import runtime, wait
from test_chat_notifications import ready


async def waiting(runtime, key='arbitrary.alpha', kind=InteractionKind.FORM):
    identities=IdentityRepository(runtime.database)
    identities.bind_installation(installation_id='installation-a',cloud_device_id='device-a',organization_id='org-a',
        organization_type=OrganizationType.HOUSEHOLD,core_user_id='owner-a',billing_account_id='bill-a',access_epoch=1)
    principal=replace(identities.local_principal_for('owner-a'),client_scope='mobile-agent')
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Private title')
    runtime.agents.ensure_definition(agent_key=key,package_version='1',display_name='Arbitrary',executor_key=key,max_steps=10,timeout_seconds=300)
    def execute(context):
        if context.interactions:return CompleteAction({'done':True})
        return InteractionAction('need-input',kind,'Private prompt never sent to notifications',
            {'type':'object','properties':{'value':{'type':'string'}},'required':['value']})
    runtime.agent_runtime.bind_executor(key,execute)
    await runtime.agent_runtime.start()
    run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key=key,input={})
    runtime.agent_runtime.wake()
    await wait(runtime,run.id,'waiting_capability' if kind==InteractionKind.APPROVAL else 'waiting_input')
    return principal,run,runtime.agents.list_interactions(run.id)[0]


def body(runtime, iid):
    with runtime.database.transaction() as db:
        return json.loads(db.execute('SELECT body_json FROM notification_producer_outbox WHERE event_id=?',('chat.interaction:'+iid,)).fetchone()[0])


@pytest.mark.asyncio
@pytest.mark.parametrize('key,kind',[('arbitrary.alpha',InteractionKind.FORM),('totally.different',InteractionKind.APPROVAL)])
async def test_pending_notification_owned_idempotent_and_precise_route(runtime,monkeypatch,key,kind):
    ready(runtime,monkeypatch)
    principal,run,item=await waiting(runtime,key,kind)
    try:
        assert enqueue_pending_interactions(runtime)==1
        assert enqueue_pending_interactions(runtime)==0
        notice=body(runtime,item.id)
        assert notice['target']=={'type':'app_route','app_id':'ai2apps.general-chat','route':'interaction','id':item.id}
        assert 'Private' not in json.dumps(notice)
        assert interaction_still_pending(runtime,notice)
        route=authorize_interaction(runtime,principal,item.id)
        assert route['notification-session']==run.session_id and route['notification-run']==run.id
        with pytest.raises(ResourceNotFoundError):authorize_interaction(runtime,replace(principal,client_scope='desktop'),item.id)
        with pytest.raises(ValueError):authorize_interaction(runtime,replace(principal,actor_user_id='other'),item.id)
        runtime.agents.request_cancel(run.id)
        assert not interaction_still_pending(runtime,notice)
        with pytest.raises(ValueError):authorize_interaction(runtime,principal,item.id)
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_submitted_expired_owner_and_atomic_failure(runtime,monkeypatch):
    producer=ready(runtime,monkeypatch)
    principal,run,item=await waiting(runtime)
    try:
        ready(runtime,monkeypatch,owner='other')
        assert enqueue_pending_interactions(runtime)==0
        ready(runtime,monkeypatch)
        original=runtime.events.append_in_transaction
        def fail(db,**kwargs):
            if kwargs['event_type']=='chat.interaction.notification_queued':raise RuntimeError('crash')
            return original(db,**kwargs)
        monkeypatch.setattr(runtime.events,'append_in_transaction',fail)
        with pytest.raises(RuntimeError):enqueue_pending_interactions(runtime)
        with runtime.database.transaction() as db:assert db.execute('SELECT count(*) FROM notification_producer_outbox').fetchone()[0]==0
        monkeypatch.setattr(runtime.events,'append_in_transaction',original)
        assert enqueue_pending_interactions(runtime)==1
        notice=body(runtime,item.id)
        runtime.agents.respond_interaction(run.id,item.id,response={'value':'user-entered'},response_id='response-1')
        assert not interaction_still_pending(runtime,notice)
        with pytest.raises(ValueError):authorize_interaction(runtime,principal,item.id)
        assert enqueue_pending_interactions(runtime)==0
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
async def test_expired_interaction_is_not_enqueued(runtime,monkeypatch):
    ready(runtime,monkeypatch)
    principal,run,item=await waiting(runtime)
    try:
        with runtime.database.transaction(write=True) as db:
            db.execute("UPDATE agent_interactions SET deadline_at='2020-01-01T00:00:00.000000Z' WHERE id=?",(item.id,))
        assert enqueue_pending_interactions(runtime)==0
        with pytest.raises(ValueError):authorize_interaction(runtime,principal,item.id)
    finally:await runtime.agent_runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('unavailable',[False,True])
async def test_generic_delivery_guards_fail_closed_without_sending(tmp_path,unavailable):
    import httpx
    from test_ai2apps_notification_producer import setup
    calls=[]
    producer,remote,identities,cloud,ids=setup(tmp_path,lambda request:calls.append(request) or httpx.Response(500))
    producer.enqueue(event_id='arbitrary.guarded',kind='action.required',target_id='arbitrary-task')
    def guard(body):
        if unavailable:raise RuntimeError('owner temporarily unavailable')
        return False
    producer.register_delivery_guard(guard)
    await producer.drain_once()
    with producer.database.transaction() as db:
        row=db.execute('SELECT state,attempts,error_code FROM notification_producer_outbox').fetchone()
    assert row['state']==('retry' if unavailable else 'cancelled') and row['attempts']==0
    assert not calls
    await cloud.close()
