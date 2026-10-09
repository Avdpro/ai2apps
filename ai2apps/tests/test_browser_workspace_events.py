import asyncio
import json
from types import SimpleNamespace

import pytest

from ai2apps.browser.tasks import BrowserTaskRepository
from ai2apps.browser.workspace_events import stream_workspace, workspace_snapshot
from ai2apps.browser.task_monitor import BrowserTaskMonitor
from ai2apps.events import EventStore, EventNotificationBus
from ai2apps.storage import PlatformDatabase


@pytest.fixture
def runtime(tmp_path):
    database = PlatformDatabase(tmp_path / 'events.sqlite3')
    database.initialize()
    notifications = EventNotificationBus()
    events = EventStore(database, notifications)
    return SimpleNamespace(database=database, notifications=notifications, events=events)


def enqueue(tasks, owner='alice'):
    return tasks.enqueue(owner, 'default', 'draft', 'read', 'gen', 'Reader', {})


def payload(message):
    return json.loads(next(line[6:] for line in message.splitlines() if line.startswith('data: ')))


def test_state_and_event_commit_or_rollback_together(runtime):
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    task = enqueue(tasks)
    event = runtime.events.list_after(subject_id=tasks.event_subject('alice'))[-1]
    assert event.payload['task'] == {key: value for key, value in task.items() if key != 'input'}
    before = event.sequence
    with pytest.raises(RuntimeError):
        with runtime.database.transaction(write=True) as c:
            c.execute("UPDATE browser_tasks SET status='failed' WHERE id=?", (task['id'],))
            tasks._changed(c, 'alice', task['id'])
            raise RuntimeError('rollback')
    assert tasks.get('alice', task['id'])['status'] == 'queued'
    assert not runtime.events.list_after(before)
    tasks.update('alice', task['id'], lease_until=999)
    tasks.update('alice', task['id'], status='queued')
    assert not runtime.events.list_after(before)  # no heartbeat or unchanged-state spam


@pytest.mark.asyncio
async def test_snapshot_then_updates_have_no_gap_and_are_owner_scoped(runtime):
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    first = enqueue(tasks)
    enqueue(tasks, 'bob')
    stream = stream_workspace(runtime, 'alice', heartbeat_seconds=.01)
    snapshot = await anext(stream)
    assert [t['id'] for t in payload(snapshot)['tasks']] == [first['id']]
    # Commit after bootstrap and before the stream subscribes: replay must find it.
    second = enqueue(tasks)
    message = await asyncio.wait_for(anext(stream), 1)
    assert payload(message)['payload']['task']['id'] == second['id']
    enqueue(tasks, 'bob')
    assert await anext(stream) == ': heartbeat\n\n'
    await stream.aclose()
    assert runtime.notifications.subscriber_count == 0


@pytest.mark.asyncio
async def test_reconnect_replays_only_events_after_cursor(runtime):
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    first = enqueue(tasks)
    cursor, _ = workspace_snapshot(tasks, 'alice')
    tasks.update('alice', first['id'], status='cancelled')
    stream = stream_workspace(runtime, 'alice', cursor, heartbeat_seconds=.01)
    event = payload(await anext(stream))
    assert event['sequence'] > cursor
    assert event['payload']['task']['status'] == 'cancelled'
    await stream.aclose()


@pytest.mark.asyncio
async def test_monitor_settles_run_and_pushes_without_any_http_request(runtime):
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    task = enqueue(tasks)
    tasks.claim('alice', 'external')
    tasks.update('alice', task['id'], run_id='run', status='running')
    runtime.agents = SimpleNamespace(get_run=lambda _: SimpleNamespace(
        status=SimpleNamespace(value='completed'), error=None))
    monitor = BrowserTaskMonitor(runtime)
    stream = stream_workspace(runtime, 'alice', heartbeat_seconds=.1)
    await anext(stream)
    await monitor.startup()
    event = payload(await asyncio.wait_for(anext(stream), 1))
    assert event['payload']['task']['status'] == 'completed'
    await monitor.shutdown()
    await stream.aclose()
    assert runtime.notifications.subscriber_count == 0
