"""Real SQLite contention and execution-generation cleanup regressions."""
import asyncio
from contextlib import suppress
import threading
import time
from types import SimpleNamespace as NS

import pytest

from ai2apps.agents.models import AgentRunStatus
from ai2apps.agents.runtime import AgentRuntime
from ai2apps.events import EventStore, EventNotificationBus
from ai2apps.storage import PlatformDatabase
from ai2apps.system_tasks import SystemTaskService, TaskHandler
from ai2apps.system_tasks.service import TaskContext


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['admission', 'progress'])
async def test_sqlite_writer_wait_does_not_block_event_loop(tmp_path, operation):
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    runtime = NS(database=database, events=EventStore(database), notifications=EventNotificationBus())
    service = SystemTaskService(runtime)
    async def execute(ctx):
        return {'verified': True}
    service.register('arbitrary.work', TaskHandler('arbitrary.app', execute))
    record = service.submit('alice', 'arbitrary.app', 'arbitrary.work', 'Work', {})
    locked, release = threading.Event(), threading.Event()
    def writer():
        with database.transaction(write=True):
            locked.set()
            release.wait(3)
    thread = threading.Thread(target=writer)
    thread.start()
    work = None
    try:
        assert await asyncio.to_thread(locked.wait, 2)
        work = asyncio.create_task(service.tick() if operation == 'admission'
                                   else TaskContext(service, record).areport(message='saved'))
        start = time.monotonic()
        # An unrelated health request can be scheduled while the writer waits.
        await asyncio.sleep(.1)
        assert time.monotonic() - start < .8
        assert not work.done()
    finally:
        release.set()
        if work is not None:
            await work
        await asyncio.to_thread(thread.join)
        await asyncio.gather(*tuple(service.jobs.values()))
    result = service.get('alice', record['id'])
    assert result['status'] == ('completed' if operation == 'admission' else 'running')


def runtime_for_cleanup(repository):
    value = object.__new__(AgentRuntime)
    value.repository = repository
    value._tasks = {}
    value._completion_tasks = set()
    value._terminal_events = {}
    value._run_terminal_handlers = []
    value._wake = asyncio.Event()
    return value


@pytest.mark.asyncio
async def test_old_completion_cannot_remove_requeued_execution():
    value = runtime_for_cleanup(NS(get_run=lambda _: pytest.fail('stale callback queried Run')))
    old = asyncio.create_task(asyncio.sleep(0))
    await old
    replacement = asyncio.create_task(asyncio.Event().wait())
    value._tasks['same-run'] = replacement
    value._task_done('same-run', old)
    assert value._tasks['same-run'] is replacement
    assert not value._completion_tasks
    replacement.cancel()
    with suppress(asyncio.CancelledError):
        await replacement


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [AgentRunStatus.COMPLETED, AgentRunStatus.FAILED, AgentRunStatus.CANCELLED])
async def test_completion_reads_off_loop_and_notifies_terminal_status(status):
    loop_thread = threading.get_ident()
    def get_run(_):
        assert threading.get_ident() != loop_thread
        return NS(status=status)
    value = runtime_for_cleanup(NS(get_run=get_run))
    notified = []
    value._run_terminal_handlers.append(lambda run: notified.append((run, threading.get_ident())))
    finished = asyncio.create_task(asyncio.sleep(0))
    await finished
    value._tasks['run'] = finished
    value._task_done('run', finished)
    assert 'run' not in value._tasks
    await asyncio.gather(*tuple(value._completion_tasks))
    assert notified == [('run', loop_thread)]


@pytest.mark.asyncio
async def test_completion_read_cannot_notify_over_replacement():
    entered, release = threading.Event(), threading.Event()
    def get_run(_):
        entered.set()
        release.wait(2)
        return NS(status=AgentRunStatus.COMPLETED)
    value = runtime_for_cleanup(NS(get_run=get_run))
    value._run_terminal_handlers.append(lambda _: pytest.fail('replacement notified as terminal'))
    old = asyncio.create_task(asyncio.sleep(0))
    await old
    value._tasks['run'] = old
    value._task_done('run', old)
    assert await asyncio.to_thread(entered.wait, 1)
    replacement = asyncio.create_task(asyncio.Event().wait())
    value._tasks['run'] = replacement
    release.set()
    await asyncio.gather(*tuple(value._completion_tasks))
    assert value._tasks['run'] is replacement
    replacement.cancel()
    with suppress(asyncio.CancelledError):
        await replacement


@pytest.mark.asyncio
async def test_todo_stale_watcher_does_not_remove_replacement():
    from ai2apps.todo.service import TodoService
    value = object.__new__(TodoService)
    old = asyncio.create_task(asyncio.sleep(0))
    await old
    replacement = asyncio.create_task(asyncio.Event().wait())
    value.jobs = {'same-run': replacement}
    value.dispatch_queue = lambda: pytest.fail('stale watcher dispatched over replacement')
    value._job_done('same-run', old)
    assert value.jobs['same-run'] is replacement
    replacement.cancel()
    with suppress(asyncio.CancelledError):
        await replacement


@pytest.mark.asyncio
async def test_todo_schedule_sync_waits_off_loop(tmp_path):
    from test_todo import service, task
    from ai2apps.todo.system_schedules import SystemTodoSchedules
    todo = service(tmp_path)
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    todo.runtime.database = database
    todo.runtime.todo = todo
    todo.runtime.notifications = EventNotificationBus()
    todo.runtime.events = EventStore(database)
    todo.runtime.system_tasks = SystemTaskService(todo.runtime)
    schedules = SystemTodoSchedules(todo.runtime)
    todo.runtime.todo_system_schedules = schedules
    # A retired/unbound schedule still needs to be disabled in the platform DB.
    record = task(todo.store)
    with todo.store.connect() as db:
        db.execute('INSERT INTO task_system_schedules VALUES(?,?)', ('alice', record['id']))
    locked, release = threading.Event(), threading.Event()
    def writer():
        with database.transaction(write=True):
            locked.set()
            release.wait(3)
    thread = threading.Thread(target=writer)
    thread.start()
    scheduler = None
    try:
        assert await asyncio.to_thread(locked.wait, 2)
        scheduler = asyncio.create_task(todo.scheduler())
        start = time.monotonic()
        await asyncio.sleep(.1)
        assert time.monotonic() - start < .8
        assert not scheduler.done()
    finally:
        release.set()
        await asyncio.to_thread(thread.join)
        if scheduler:
            scheduler.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler


@pytest.mark.asyncio
@pytest.mark.parametrize('fails', [False, True])
async def test_cancellation_wins_while_terminal_worker_is_waiting(tmp_path, fails):
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    runtime = NS(database=database, events=EventStore(database), notifications=EventNotificationBus())
    service = SystemTaskService(runtime)
    async def execute(ctx):
        if fails:
            raise ValueError('fixture failure')
        return {'verified': True}
    service.register('arbitrary.work', TaskHandler('arbitrary.app', execute))
    record = service.submit('alice','arbitrary.app','arbitrary.work','Work',{})
    entered, release = threading.Event(), threading.Event()
    settle = service._settle_execution
    def delayed(*args, **kwargs):
        entered.set()
        release.wait(2)
        return settle(*args, **kwargs)
    service._settle_execution = delayed
    try:
        await service.tick()
        assert await asyncio.to_thread(entered.wait, 1)
        await asyncio.to_thread(service.cancel, 'alice', record['id'])
    finally:
        release.set()
        await asyncio.gather(*tuple(service.jobs.values()))
    assert service.get('alice',record['id'])['status'] == 'cancelling'
    assert service.attempts('alice',record['id'])[0]['status'] == 'running'
    await service.tick()
    assert service.get('alice',record['id'])['status'] == 'cancelled'
    assert service.attempts('alice',record['id'])[0]['status'] == 'cancelled'


@pytest.mark.asyncio
async def test_admin_identity_is_rechecked_off_loop():
    # Execute the real dependency without importing MLX's inference server.
    import ast
    from pathlib import Path
    from fastapi import HTTPException, Request
    from ai2apps.http_security import enforce_same_origin_cookie_request
    source = Path(__file__).resolve().parents[2] / 'omlx/admin/auth.py'
    tree = ast.parse(source.read_text())
    names = {'active_local_principal', 'verify_session', 'require_admin', '_RedirectToLogin'}
    nodes = [node for node in tree.body if getattr(node, 'name', '') in names]
    loop_thread = threading.get_ident()
    principal = [NS(is_core=True)]
    def resolve(token):
        assert token == 'fixture-session'
        assert threading.get_ident() != loop_thread
        return principal[0]
    scope = dict(asyncio=asyncio, Request=Request, HTTPException=HTTPException,
                 enforce_same_origin_cookie_request=enforce_same_origin_cookie_request,
                 _resolve_local_cookie_name=lambda: 'ai2apps_local_session',
                 _resolve_local_principal=resolve)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
    request = Request({'type':'http','method':'GET','path':'/admin',
                       'headers':[(b'host',b'localhost'),(b'cookie',b'ai2apps_local_session=fixture-session')]})
    assert await scope['require_admin'](request)
    principal[0] = NS(is_core=False)
    with pytest.raises(HTTPException) as member:
        await scope['require_admin'](request)
    assert member.value.status_code == 403
    principal[0] = None
    with pytest.raises(HTTPException) as revoked:
        await scope['require_admin'](request)
    assert revoked.value.status_code == 401
    route_source = source.with_name('routes.py')
    route_tree = ast.parse(route_source.read_text())
    shell = next(node for node in route_tree.body if getattr(node,'name','') == '_require_shell_access')
    scope.update(RequestPrincipal=object, _get_platform_runtime=lambda:NS(
        local_session_token_from_cookies=lambda cookies:cookies.get('ai2apps_local_session'),
        authorize_local_session=resolve))
    exec(compile(ast.Module(body=[shell],type_ignores=[]),str(route_source),'exec'),scope)
    principal[0] = NS(is_core=False)
    assert await scope['_require_shell_access'](request) is principal[0]
    principal[0] = None
    with pytest.raises(HTTPException) as revoked_shell:
        await scope['_require_shell_access'](request)
    assert revoked_shell.value.status_code == 401


@pytest.mark.asyncio
async def test_idle_worker_eviction_waits_off_loop(tmp_path):
    from ai2apps.packages.manager import ServicePackageManager
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    loop_thread = threading.get_ident()
    written = []
    def write_marker(name):
        assert threading.get_ident() != loop_thread
        with database.transaction(write=True):
            written.append(name)
        return 'operation'
    async def evict(*args, **kwargs):
        return {'status': 'evicted'}
    manager = object.__new__(ServicePackageManager)
    manager.packages = NS(active=lambda _: NS(protocol='ai2apps-model-worker/v1',package_digest='digest'),
                          begin_operation=lambda *a, **k: write_marker('begin'),
                          settle_operation=lambda *a, **k: write_marker('settled'))
    manager.supervisor = NS(evict=evict)
    manager.services = NS(get_service=lambda _:NS(id='service'),
                          get_instance_for_service=lambda _:NS(id='instance'),
                          set_instance_status=lambda *a, **k:write_marker('status'))
    locked, release = threading.Event(), threading.Event()
    def writer():
        with database.transaction(write=True):
            locked.set()
            release.wait(3)
    thread = threading.Thread(target=writer)
    thread.start()
    work = None
    try:
        assert await asyncio.to_thread(locked.wait, 2)
        work = asyncio.create_task(manager.evict('arbitrary.worker',reason='idle',expected_generation=1))
        start = time.monotonic()
        await asyncio.sleep(.1)
        assert time.monotonic()-start < .8
        assert not work.done()
    finally:
        release.set()
        if work:
            result = await work
        await asyncio.to_thread(thread.join)
    assert result == {'status':'evicted'}
    assert written == ['begin','status','settled']


@pytest.mark.asyncio
async def test_agent_wake_from_worker_resolves_waiter_on_owning_loop():
    value = runtime_for_cleanup(NS())
    loop = asyncio.get_running_loop()
    value._event_loop = loop
    debug = loop.get_debug()
    loop.set_debug(True)
    waiter = asyncio.create_task(value._wake.wait())
    try:
        await asyncio.sleep(0)
        await asyncio.to_thread(value.wake)
        assert await asyncio.wait_for(waiter, 1)
    finally:
        loop.set_debug(debug)
        if not waiter.done():
            waiter.cancel()
            with suppress(asyncio.CancelledError):
                await waiter


@pytest.mark.asyncio
async def test_background_schedule_pass_waits_off_loop(tmp_path):
    from ai2apps.agent_builder.scheduler import AgentScheduleRunner
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    entered, release = threading.Event(), threading.Event()
    def reconcile():
        with database.transaction(write=True):
            entered.set()
    runner = AgentScheduleRunner(NS(),NS(reconcile_dispatches=reconcile,claim_due_schedule=lambda:None))
    locked = threading.Event()
    def writer():
        with database.transaction(write=True):
            locked.set()
            release.wait(3)
    thread = threading.Thread(target=writer)
    thread.start()
    shutdown = None
    try:
        assert await asyncio.to_thread(locked.wait, 2)
        await runner.startup()
        start = time.monotonic()
        await asyncio.sleep(.1)
        assert time.monotonic()-start < .8
        assert not entered.is_set()
        shutdown = asyncio.create_task(runner.shutdown())
        await asyncio.sleep(0)
    finally:
        release.set()
        await asyncio.to_thread(thread.join)
        if shutdown:
            await asyncio.wait_for(shutdown, .8)
        else:
            await runner.shutdown()
    assert entered.is_set()
