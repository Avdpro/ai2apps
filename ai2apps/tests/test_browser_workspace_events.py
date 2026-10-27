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
    assert payload(message)['payload']['task_node']['id'] == second['execution_task_id']
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

@pytest.mark.parametrize('control', ['browser_user_assistance', 'agent_confirmation'])
def test_human_pause_yields_profile_and_resumes_same_run_through_admission(runtime, control):
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    tasks.configure('alice',1,1)
    first=enqueue(tasks);tasks.claim('alice','local-background')
    tasks.update('alice',first['id'],run_id='existing-run',status='running',
        browser_context_json=json.dumps({'created_by_run':'existing-run','bidi_context':'human-tab'}))
    second=enqueue(tasks)
    interaction=SimpleNamespace(status='pending',request={'control':control},prompt='Please sign in')
    runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status=SimpleNamespace(value='waiting_input'),error=None),list_interactions=lambda _:[interaction])
    reconcile_browser_tasks(runtime,tasks,'alice')
    paused=tasks.get('alice',first['id'])
    assert paused['paused'] and not paused['holds_browser_slot']
    assert paused['browser_context']['bidi_context']=='human-tab'
    assert tasks.claim('alice','local-background')['id']==second['id']
    # Updating page metadata must not erase the scheduler-owned pause flag.
    tasks.update('alice',first['id'],browser_context_json=json.dumps({'bidi_context':'human-tab'}))
    assert tasks.get('alice',first['id'])['paused']
    runtime.agents.list_interactions=lambda _:[]
    reconcile_browser_tasks(runtime,tasks,'alice')
    waiting=tasks.get('alice',first['id'])
    assert waiting['status']=='queued' and not waiting['holds_browser_slot']
    assert tasks.claim('alice','local-background') is None
    tasks.update('alice',second['id'],status='completed')
    claimed=tasks.claim('alice','local-background')
    assert claimed['id']==first['id'] and claimed['run_id']=='existing-run'
    assert claimed['holds_browser_slot'] and not claimed['paused']
    assert claimed['browser_context']['bidi_context']=='human-tab'


def test_automatic_browser_wait_does_not_release_admission(runtime):
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    tasks.configure('alice',1,1)
    first=enqueue(tasks);tasks.claim('alice','local-background')
    tasks.update('alice',first['id'],run_id='run',status='running')
    enqueue(tasks)
    runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status=SimpleNamespace(value='waiting_input'),error=None),list_interactions=lambda _:[SimpleNamespace(status='pending',request={'control':'browser_bidi_action'},prompt='')])
    reconcile_browser_tasks(runtime,tasks,'alice')
    assert not tasks.get('alice',first['id'])['paused']
    assert tasks.get('alice',first['id'])['holds_browser_slot']
    assert tasks.claim('alice','local-background') is None


def test_dispatch_resumes_existing_run_without_creating_another(runtime, monkeypatch):
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    first=enqueue(tasks);tasks.claim('alice','local-background')
    tasks.update('alice',first['id'],run_id='saved-run',status='queued',paused=True,
        browser_context_json=json.dumps({'bidi_context':'original-tab'}))
    runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status=SimpleNamespace(value='waiting_input'),error=None),list_interactions=lambda _:[])
    def unexpected(*args,**kwargs):raise AssertionError('must not create a second AgentRun')
    monkeypatch.setattr('ai2apps.agent_builder.service.create_ir_run',unexpected)
    BackgroundBrowserRunner(runtime).dispatch_queue()
    resumed=tasks.get('alice',first['id'])
    assert resumed['status']=='running' and resumed['run_id']=='saved-run'
    assert resumed['holds_browser_slot'] and resumed['browser_context']['bidi_context']=='original-tab'


def test_no_progress_cancels_then_fails_without_replaying(runtime,monkeypatch):
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    clock=[0]
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.time.monotonic',lambda:clock[0])
    monkeypatch.setattr('ai2apps.browser.task_monitor.completed_steps',lambda *a,**kw:'same-result')
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    task=enqueue(tasks);tasks.claim('alice','local-background')
    tasks.update('alice',task['id'],status='running',run_id='existing-run',lease_until=99999999999)
    state=['running'];cancelled=[]
    runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status=SimpleNamespace(value=state[0]),error=None),list_interactions=lambda _:[])
    runtime.agent_runtime=SimpleNamespace(cancel=cancelled.append)
    reconcile_browser_tasks(runtime,tasks,'alice')
    clock[0]=299
    tasks.update('alice',task['id'],message='heartbeat',lease_until=99999999999)
    reconcile_browser_tasks(runtime,tasks,'alice')
    assert not cancelled
    clock[0]=300
    reconcile_browser_tasks(runtime,tasks,'alice')
    assert cancelled==['existing-run']
    assert tasks.get('alice',task['id'])['status']=='cancelling'
    state[0]='cancelled'
    reconcile_browser_tasks(runtime,tasks,'alice')
    result=tasks.get('alice',task['id'])
    assert result['status']=='failed' and result['run_id']=='existing-run'
    assert '5 分钟' in result['message']


def test_no_progress_watch_is_independent_for_sibling_tasks(runtime,monkeypatch):
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    clock=[0];signatures={};cancelled=[]
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.time.monotonic',lambda:clock[0])
    monkeypatch.setattr('ai2apps.browser.task_monitor.completed_steps',lambda *a,**kw:signatures.get(kw['task_id'],0))
    tasks=BrowserTaskRepository(runtime.database,runtime.events)
    one=enqueue(tasks);two=enqueue(tasks)
    for task in (one,two):
        tasks.update('alice',task['id'],status='running',worker='local-background',run_id=task['id'],lease_until=99999999999)
    runtime.agents=SimpleNamespace(get_run=lambda _:SimpleNamespace(status=SimpleNamespace(value='running'),error=None),list_interactions=lambda _:[])
    runtime.agent_runtime=SimpleNamespace(cancel=cancelled.append)
    reconcile_browser_tasks(runtime,tasks,'alice')
    clock[0]=250;signatures[two['id']]=1
    reconcile_browser_tasks(runtime,tasks,'alice')
    clock[0]=300
    reconcile_browser_tasks(runtime,tasks,'alice')
    assert cancelled==[one['id']]
    assert tasks.get('alice',two['id'])['status']=='running'


@pytest.mark.parametrize('pause', ['task_queue', 'agent_queue', 'admission'])
def test_watchdog_excludes_queue_and_restarts_after_admission(runtime, monkeypatch, pause):
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    clock = [0]
    cancelled = []
    monkeypatch.setattr('ai2apps.browser.progress_watchdog.time.monotonic', lambda: clock[0])
    monkeypatch.setattr('ai2apps.browser.task_monitor.completed_steps', lambda *a, **kw: 'same')
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    task = enqueue(tasks)
    tasks.update('alice', task['id'], status='running', worker='local-background', run_id='run', lease_until=99999999999)
    state = ['running']
    runtime.agents = SimpleNamespace(get_run=lambda _: SimpleNamespace(status=SimpleNamespace(value=state[0]), error=None), list_interactions=lambda _: [])
    runtime.agent_runtime = SimpleNamespace(cancel=cancelled.append)
    reconcile_browser_tasks(runtime, tasks, 'alice')
    clock[0] = 250
    if pause == 'task_queue':
        tasks.update('alice', task['id'], status='queued')
    elif pause == 'agent_queue':
        state[0] = 'queued'
    else:
        tasks.update('alice', task['id'], paused=True)
    reconcile_browser_tasks(runtime, tasks, 'alice')
    clock[0] = 1200
    reconcile_browser_tasks(runtime, tasks, 'alice')
    assert not cancelled
    tasks.update('alice', task['id'], status='running', paused=False)
    state[0] = 'running'
    reconcile_browser_tasks(runtime, tasks, 'alice')
    clock[0] = 1499
    reconcile_browser_tasks(runtime, tasks, 'alice')
    assert not cancelled
    clock[0] = 1500
    reconcile_browser_tasks(runtime, tasks, 'alice')
    assert cancelled == ['run']
