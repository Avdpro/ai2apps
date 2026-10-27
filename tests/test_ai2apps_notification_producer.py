import asyncio
import json
import time
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.remote import create_remote_router
from ai2apps.identity import MemberRole
from ai2apps.remote.notifications import NotificationProducer
from test_ai2apps_remote import _projection_manager


def setup(tmp_path, handler):
    def transport(request):
        if request.url.path.endswith('/producer-policy'):
            return httpx.Response(404)
        return handler(request)
    remote, identities, cloud, ids = _projection_manager(tmp_path, transport)
    return remote.notifications, remote, identities, cloud, ids


def enqueue(p, event='test-1'):
    return p.enqueue(event_id=event, kind='system.notice', target_id=event)


def row(p):
    return p.status()['items'][0]


@pytest.mark.asyncio
async def test_restart_replays_same_body_and_no_cookie(tmp_path):
    requests = []
    notification = str(uuid4())
    def handler(request):
        requests.append(request)
        assert 'cookie' not in request.headers
        assert request.headers['authorization'].startswith('Device ')
        assert request.headers['idempotency-key'] == 'test-1'
        assert request.url.path == '/api/v1/notifications/events'
        if len(requests) == 1:
            raise httpx.ReadTimeout('unknown result', request=request)
        return httpx.Response(202, json={'notification_id': notification})
    p, remote, _, cloud, _ = setup(tmp_path, handler)
    cloud._get_client().cookies.set('ai2apps_session', 'must-not-send')
    enqueue(p)
    await p.drain_once()
    assert row(p)['state'] == 'retry'
    with p.database.transaction(write=True) as c:
        c.execute('UPDATE notification_producer_outbox SET next_attempt=0')
    resumed = NotificationProducer(remote)
    enqueue(resumed)
    await resumed.drain_once()
    assert requests[0].content == requests[1].content
    assert row(resumed)['notification_id'] == notification
    assert row(resumed)['state'] == 'submitted'
    await cloud.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('code,state', [(401,'credentials_required'), (403,'authorization_required'), (409,'conflict'), (400,'failed'), (302,'failed')])
async def test_permanent_errors_do_not_loop(tmp_path, code, state):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code, json={'error':{'message':'do not expose arbitrary text'}})
    p, _, _, _, _ = setup(tmp_path, handler)
    enqueue(p)
    await p.drain_once()
    await p.drain_once()
    assert len(calls) == 1
    assert row(p)['state'] == state
    assert 'arbitrary' not in json.dumps(p.status())
    if code in (401,403):
        p.resume()
        await p.drain_once()
        assert len(calls) == 2


@pytest.mark.asyncio
async def test_403_pauses_other_events_and_429_delays_entire_queue(tmp_path):
    codes = [403,429]
    def handler(request):
        return httpx.Response(codes.pop(0), headers={'Retry-After':'600'}, json={})
    p, *_ = setup(tmp_path, handler)
    enqueue(p, 'one'); enqueue(p, 'two')
    await p.drain_once()
    enqueue(p, 'three')
    assert {i['state'] for i in p.status()['items']} == {'authorization_required'}
    p.resume()
    await p.drain_once()
    assert all(i['next_attempt'] > time.time()+590 for i in p.status()['items'])
    await p.drain_once()
    assert not codes


@pytest.mark.asyncio
async def test_identity_change_never_replays(tmp_path):
    calls = []
    p, _, repo, _, _ = setup(tmp_path, lambda r: calls.append(r))
    enqueue(p)
    old = repo.get_installation()
    repo.get_installation = lambda: replace(old, core_user_id=str(uuid4()))
    await p.drain_once()
    assert not calls
    with p.database.transaction() as c:
        assert c.execute('SELECT state FROM notification_producer_outbox').fetchone()[0] == 'cancelled'


@pytest.mark.asyncio
async def test_expiration_offline_and_retry_limit(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(503)
    p, _, _, cloud, _ = setup(tmp_path, handler)
    enqueue(p)
    cloud.offline_mode = lambda: True
    await p.drain_once()
    assert not calls
    cloud.offline_mode = lambda: False
    with p.database.transaction(write=True) as c:
        c.execute('UPDATE notification_producer_outbox SET attempts=11')
    await p.drain_once()
    assert row(p)['state'] == 'failed'
    enqueue(p, 'expired')
    with p.database.transaction(write=True) as c:
        c.execute("UPDATE notification_producer_outbox SET expires_at=0 WHERE event_id='expired'")
    await p.drain_once()
    assert len(calls) == 1
    assert row(p)['state'] == 'expired'


def test_business_transaction_rollback_and_idempotency(tmp_path):
    p, *_ = setup(tmp_path, lambda r: httpx.Response(202))
    with pytest.raises(RuntimeError):
        with p.database.transaction(write=True) as c:
            p.enqueue(event_id='terminal', kind='task.completed', target_id='task_123', connection=c)
            raise RuntimeError('business rollback')
    assert p.status()['items'] == []
    enqueue(p)
    enqueue(p)
    assert len(p.status()['items']) == 1
    with pytest.raises(ValueError):
        p.enqueue(event_id='test-1', kind='task.failed', target_id='different')
    with pytest.raises(ValueError):
        p.enqueue(event_id='bad', kind='task.completed', target_id='ok', result_count=True)


def test_local_routes_owner_only_and_no_automatic_publish(tmp_path):
    p, remote, _, _, ids = setup(tmp_path, lambda r: pytest.fail('must not send from read/queue route'))
    principal = SimpleNamespace(role=MemberRole.OWNER, is_core=True, authentication_type='local_session',
        actor_user_id=ids['core_user_id'], installation_id=ids['installation_id'])
    app = FastAPI()
    app.include_router(create_remote_router(lambda: SimpleNamespace(remote=remote), lambda: principal))
    with TestClient(app) as client:
        response = client.get('/remote/notifications')
        assert response.status_code == 200, response.text
        assert client.post('/remote/notifications/test', json={'event_id':'test-route'}).status_code == 202
        principal.is_core = False
        assert client.post('/remote/notifications/test', json={'event_id':'other'}).status_code == 403
        principal.is_core = True
        principal.authentication_type = 'remote_session'
        assert client.get('/remote/notifications').status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [True, False])
async def test_automatic_policy_preserves_explicit_off(tmp_path, enabled):
    p, remote, _, cloud, ids = setup(tmp_path, lambda r: httpx.Response(403))
    enqueue(p)
    await p.drain_once()
    assert row(p)['state'] == 'authorization_required'
    event_requests = []
    def handler(request):
        if request.url.path.endswith('/producer-policy'):
            assert request.method == 'GET' and 'cookie' not in request.headers
            current = p.identity()
            return httpx.Response(200, json={'policy_version':2,'automatic_owner_publish':True,
                'enabled':enabled,'installation_id':current['installation_id'], 'account_id':current['owner_id'],
                'credential_version':current['credential_version'], 'access_epoch':current['access_epoch']})
        event_requests.append(request)
        return httpx.Response(202,json={'notification_id':str(uuid4())})
    cloud.transport = httpx.MockTransport(handler)
    await p.drain_once()
    assert row(p)['state'] == ('submitted' if enabled else 'authorization_required')
    assert len(event_requests) == int(enabled)


@pytest.mark.asyncio
async def test_rotation_waits_for_policy_then_replays_identical_event(tmp_path):
    p, remote, repo, cloud, _ = setup(tmp_path, lambda r: httpx.Response(503))
    enqueue(p)
    with p.database.transaction() as c:
        original = c.execute('SELECT body_json FROM notification_producer_outbox').fetchone()[0]
    device = remote.repository.get(p.identity()['device_id'])
    remote.repository.get = lambda _: replace(device, credential_version=device.credential_version+1)
    await p.drain_once()
    with p.database.transaction() as c:
        assert c.execute('SELECT state FROM notification_producer_outbox').fetchone()[0] == 'credentials_required'
    def handler(request):
        if request.url.path.endswith('/producer-policy'):
            current = p.identity()
            return httpx.Response(200,json={'policy_version':2,'automatic_owner_publish':True,'enabled':True,
                'installation_id':current['installation_id'],'account_id':current['owner_id'],
                'credential_version':current['credential_version'],'access_epoch':current['access_epoch']})
        assert json.loads(request.content) == json.loads(original)
        return httpx.Response(202,json={'notification_id':str(uuid4())})
    cloud.transport = httpx.MockTransport(handler)
    p._policy_checked = 0
    await p.drain_once()
    assert row(p)['state'] == 'submitted'


@pytest.mark.asyncio
async def test_intelligence_refresh_enters_real_outbox_once(tmp_path):
    from ai2apps.intelligence.models import ChannelInput, SourceInput
    from ai2apps.intelligence.store import IntelligenceStore
    from ai2apps.intelligence.notifications import enqueue_refresh_notifications

    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(202, json={'notification_id': str(uuid4())})
    producer, remote, _, cloud, ids = setup(tmp_path, handler)
    owner = ids['core_user_id']
    store = IntelligenceStore(tmp_path / 'intel')
    channel = store.save_channel(owner, ChannelInput(name='Private channel name', interests='news').model_dump())
    store.save_source(owner, channel['id'], SourceInput(name='source', url='https://example.com').model_dump())
    run = store.claim(owner, channel['id'])['id']
    with store.connect() as db:
        db.execute('CREATE TABLE collection_jobs(run_id TEXT PRIMARY KEY, owner TEXT, data TEXT)')
        db.execute('INSERT INTO collection_jobs VALUES(?,?,?)', (run, owner, json.dumps({'system_task_id': 'stask_test'})))
    store.finish(owner, run, [], [{'title': 'Private headline', 'body': 'Secret text', 'sources': []}], [])
    assert enqueue_refresh_notifications(store, producer) == 1
    # Simulate a crash after the platform commit, before the business ack.
    with store.connect() as db:
        db.execute("UPDATE runs SET data=json_remove(data,'$.notification_enqueued') WHERE id=?", (run,))
    assert enqueue_refresh_notifications(store, producer) == 1
    with producer.database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM notification_producer_outbox').fetchone()[0] == 1
    await producer.drain_once()
    assert row(producer)['state'] == 'submitted'
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body['target'] == {'type': 'task', 'id': 'stask_test', 'app_id': 'ai2apps.intelligence'}
    assert body['metadata'] == {'result_count': 1}
    assert 'Private' not in requests[0].content.decode()
    assert 'Secret' not in requests[0].content.decode()
    assert 'cookie' not in requests[0].headers
    await cloud.close()


def test_expected_notification_owner_is_checked_at_enqueue(tmp_path):
    producer, _, _, _, ids = setup(tmp_path, lambda r: httpx.Response(500))
    with pytest.raises(ValueError, match='Installation Owner'):
        producer.enqueue(event_id='owner-mismatch', kind='task.completed', target_id='task',
                         expected_owner_id=ids['member_user_id'])
    with producer.database.transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM notification_producer_outbox').fetchone()[0] == 0


@pytest.mark.asyncio
async def test_rich_capability_and_frozen_retries(tmp_path):
    from ai2apps.remote.notifications import INTELLIGENCE_CAPABILITY
    bodies = []
    def handler(request):
        bodies.append(request.content)
        if len(bodies) == 1:
            raise httpx.ReadTimeout('ambiguous', request=request)
        return httpx.Response(202, json={'notification_id': str(uuid4())})
    p, remote, _, cloud, _ = setup(tmp_path, handler)
    event = dict(event_id='rich-1', kind='intelligence.updated', target_id='channel-1',
                 app_id='ai2apps.intelligence',
                 template_params={'channel_name':'腕表', 'new_article_count':2,
                                  'headlines':['新表发布','机芯更新'], 'refresh_status':'partial'},
                 metadata={'run_id':'run-1', 'system_task_id':'task-1'})
    with pytest.raises(ValueError, match='capability'):
        p.enqueue(**event)
    identity = p.identity()
    p._policy_identity = p._encoded(identity)
    p._policy_checked = time.time()
    p._policy_value = {'enabled':True, 'event_capabilities':[INTELLIGENCE_CAPABILITY]}
    p.enqueue(**event)
    assert p.has_event('rich-1', identity['owner_id'])
    await p.drain_once()
    with p.database.transaction(write=True) as c:
        c.execute('UPDATE notification_producer_outbox SET next_attempt=0')
    resumed = NotificationProducer(remote)
    await resumed.drain_once()  # frozen rich events send without re-negotiation/rewrite
    assert bodies[0] == bodies[1]
    body = json.loads(bodies[0])
    assert body['target']['type'] == 'intelligence_channel'
    assert body['template_params']['refresh_status'] == 'partial'
    assert 'result_count' not in body['metadata']
    await cloud.close()


@pytest.mark.asyncio
async def test_policy_requires_exact_capability_and_current_identity(tmp_path):
    from ai2apps.remote.notifications import INTELLIGENCE_CAPABILITY
    p, _, _, cloud, _ = setup(tmp_path, lambda _: httpx.Response(500))
    identity = p.identity()
    policy = {'policy_version':2, 'contract_version':'1.2.0',
              'automatic_owner_publish':True, 'enabled':True,
              'installation_id':identity['installation_id'], 'account_id':identity['owner_id'],
              'credential_version':identity['credential_version'], 'access_epoch':identity['access_epoch'],
              'event_capabilities':[INTELLIGENCE_CAPABILITY]}
    async def fetch(_): return policy
    p._policy = fetch
    await p.refresh_policy(force=True)
    assert p.supports_intelligence()
    assert p.status()['producer_policy']['contract_version'] == '1.2.0'
    p._policy_value['event_capabilities'] = [{**INTELLIGENCE_CAPABILITY, 'version':2}]
    assert not p.supports_intelligence()
    p._policy_value['event_capabilities'] = [INTELLIGENCE_CAPABILITY]
    p._policy_checked -= 121
    assert not p.supports_intelligence()
    await cloud.close()
