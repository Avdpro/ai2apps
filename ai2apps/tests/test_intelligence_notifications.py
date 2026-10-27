import json
import time

import pytest

from ai2apps.intelligence.models import ChannelInput, SourceInput
from ai2apps.intelligence.notifications import enqueue_refresh_notifications
from ai2apps.intelligence.store import IntelligenceStore


class Producer:
    def __init__(self, owner='alice'):
        self.owner = owner
        self.events = {}
        self.unavailable = False

    def identity(self):
        if self.unavailable:
            raise ValueError('unbound')
        return {'owner_id': self.owner}

    def enqueue(self, **event):
        assert event['expected_owner_id'] == self.owner
        old = self.events.setdefault(event['event_id'], event)
        assert old == event


@pytest.fixture
def refresh(tmp_path):
    store = IntelligenceStore(tmp_path)
    channel = store.save_channel('alice', ChannelInput(name='测试', interests='新品').model_dump())
    store.save_source('alice', channel['id'], SourceInput(name='源', url='https://example.com').model_dump())
    with store.connect() as db:
        db.execute('CREATE TABLE collection_jobs(run_id TEXT PRIMARY KEY, owner TEXT, data TEXT)')

    def start():
        run = store.claim('alice', channel['id'])
        with store.connect() as db:
            db.execute('INSERT INTO collection_jobs VALUES(?,?,?)',
                       (run['id'], 'alice', json.dumps({'system_task_id': 'stask_' + run['id']})))
        return run['id']

    return store, start, Producer()


def article(id='a', body='正文'):
    return {'update_article_id': id, 'title': '标题', 'body': body, 'sources': []}


def test_incremental_replay_aggregates_once_after_finish(refresh):
    store, start, producer = refresh
    run = start()
    for item in [article(), article(), article('b')]:
        store.finish('alice', run, [], [item], [], final=False)
    assert enqueue_refresh_notifications(store, producer) == 0
    store.finish('alice', run, [], [article(), article('b')], [])
    assert enqueue_refresh_notifications(store, producer) == 1
    assert enqueue_refresh_notifications(store, producer) == 0
    event = next(iter(producer.events.values()))
    assert event == {'event_id': 'intelligence.new_articles:' + run, 'kind': 'task.completed',
                     'target_id': 'stask_' + run, 'app_id': 'ai2apps.intelligence',
                     'expected_owner_id': 'alice', 'result_count': 2}
    assert set(store.get('runs', 'alice', run)['new_article_ids']) == {'a', 'b'}


def test_no_new_articles_and_updates_do_not_notify(refresh):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    enqueue_refresh_notifications(store, producer)
    run = start()
    store.finish('alice', run, [], [article(body='新正文')], [])
    assert enqueue_refresh_notifications(store, producer) == 0
    run = start()
    store.finish('alice', run, [], [], [])
    assert enqueue_refresh_notifications(store, producer) == 0
    assert len(producer.events) == 1


def test_partial_success_notifies_saved_results(refresh):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [{'status': 'success'}, {'status': 'failed'}])
    assert store.get('runs', 'alice', run)['status'] == 'partial'
    assert enqueue_refresh_notifications(store, producer) == 1


def test_restart_between_outbox_commit_and_ack_is_idempotent(refresh):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    enqueue_refresh_notifications(store, producer)
    with store.connect() as db:
        db.execute("UPDATE runs SET data=json_remove(data,'$.notification_enqueued') WHERE id=?", (run,))
    reopened = IntelligenceStore(store.root)
    assert enqueue_refresh_notifications(reopened, producer) == 1
    assert len(producer.events) == 1


def test_binding_unavailable_or_other_owner_never_leaks(refresh):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    producer.unavailable = True
    assert enqueue_refresh_notifications(store, producer) == 0
    producer.unavailable = False
    producer.owner = 'bob'
    assert enqueue_refresh_notifications(store, producer) == 0
    producer.owner = 'alice'
    assert enqueue_refresh_notifications(store, producer) == 1


def test_enqueue_failure_keeps_saved_articles_and_retries_later(refresh, monkeypatch):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    enqueue = producer.enqueue
    attempts = []
    def fail(**kwargs):
        attempts.append(kwargs)
        raise OSError('queue temporarily unavailable')
    monkeypatch.setattr(producer, 'enqueue', fail)
    now = time.time()
    assert enqueue_refresh_notifications(store, producer, now=now) == 0
    assert enqueue_refresh_notifications(store, producer, now=now + 30) == 0
    assert len(attempts) == 1
    assert store.get('articles', 'alice', 'a')['body'] == '正文'
    monkeypatch.setattr(producer, 'enqueue', enqueue)
    assert enqueue_refresh_notifications(store, producer, now=now + 61) == 1


def test_later_failure_still_reports_committed_news_without_claiming_success(refresh):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [], final=False)
    store.progress('alice', run, 'later source failed', 'failed')
    assert enqueue_refresh_notifications(store, producer) == 1
    event = next(iter(producer.events.values()))
    assert event['kind'] == 'task.failed'
    assert event['result_count'] == 1


@pytest.mark.parametrize('case', ['expired', 'legacy', 'cancelled', 'deleted_channel'])
def test_no_historic_or_unsuccessful_push(refresh, case):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    with store.connect() as db:
        if case == 'expired':
            db.execute("UPDATE runs SET data=json_set(data,'$.finished_at','2000-01-01T00:00:00Z') WHERE id=?", (run,))
        elif case == 'legacy':
            db.execute("UPDATE runs SET data=json_remove(data,'$.new_article_ids') WHERE id=?", (run,))
        elif case == 'deleted_channel':
            db.execute('DELETE FROM channels')
        else:
            db.execute('UPDATE runs SET status=? WHERE id=?', (case, run))
    assert enqueue_refresh_notifications(store, producer) == 0


def test_rich_snapshot_is_frozen_before_enqueue_and_retry(refresh, monkeypatch):
    store, start, producer = refresh
    monkeypatch.setattr(producer, 'supports_intelligence', lambda: True, raising=False)
    run = start()
    store.finish('alice', run, [], [article('a'), article('b')], [{'status': 'failed'}, {'status': 'success'}])
    original = producer.enqueue
    monkeypatch.setattr(producer, 'enqueue', lambda **kw: (_ for _ in ()).throw(OSError('temporary')))
    now = time.time()
    assert enqueue_refresh_notifications(store, producer, now=now) == 0
    frozen = store.get('runs', 'alice', run)['notification_snapshot']
    assert frozen['kind'] == 'intelligence.updated'
    assert frozen['target_id'] == store.get('runs', 'alice', run)['channel_id']
    assert frozen['template_params'] == {'channel_name': '测试', 'new_article_count': 2,
                                        'headlines': ['标题', '标题'], 'refresh_status': 'partial'}
    with store.connect() as db:
        db.execute("UPDATE channels SET data=json_set(data,'$.name','renamed')")
        db.execute("UPDATE articles SET data=json_set(data,'$.title','edited')")
    monkeypatch.setattr(producer, 'enqueue', original)
    assert enqueue_refresh_notifications(store, producer, now=now + 61) == 1
    event = next(iter(producer.events.values()))
    assert event['template_params'] == frozen['template_params']
    assert event['metadata']['run_id'] == run
    assert 'result_count' not in event


def test_old_outbox_event_is_acknowledged_without_rewriting(refresh, monkeypatch):
    store, start, producer = refresh
    run = start()
    store.finish('alice', run, [], [article()], [])
    monkeypatch.setattr(producer, 'has_event', lambda event_id, owner: True, raising=False)
    monkeypatch.setattr(producer, 'supports_intelligence', lambda: True, raising=False)
    assert enqueue_refresh_notifications(store, producer) == 1
    assert not producer.events


def test_snapshot_plain_text_limits():
    from ai2apps.intelligence.notifications import plain_text
    assert plain_text(' A\u202e<bold>\x00\n B ', 80) == 'Abold B'
    assert len(plain_text('😀' * 110, 100)) == 100
    assert plain_text('👩\u200d💻', 100) == '👩\u200d💻'
