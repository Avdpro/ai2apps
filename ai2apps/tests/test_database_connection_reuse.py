import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from ai2apps.storage import PlatformDatabase


@pytest.fixture
def database(tmp_path):
    value = PlatformDatabase(tmp_path / 'db.sqlite3')
    value.initialize()
    with value.transaction(write=True) as db:
        db.execute('CREATE TABLE reuse_test(id INTEGER PRIMARY KEY, value INTEGER)')
    yield value
    value.close()


def test_reuse_rollback_baseexception_and_commit_hook_boundaries(database):
    called = []
    class Cancel(BaseException):
        pass
    with database.transaction(write=True) as db:
        first = db
        db.execute('INSERT INTO reuse_test VALUES(1,10)')
        database.after_commit(db, lambda: called.append('committed'))
    with pytest.raises(Cancel):
        with database.transaction(write=True) as db:
            assert db is first
            db.execute('UPDATE reuse_test SET value=20')
            database.after_commit(db, lambda: called.append('must not run'))
            raise Cancel()
    with database.transaction() as db:
        assert db is first
        assert db.execute('SELECT value FROM reuse_test').fetchone()[0] == 10
        assert not database._commit_hooks
    assert called == ['committed']


def test_nested_transactions_use_distinct_connections_and_foreign_keys_reset(database):
    with database.transaction() as outer:
        with database.transaction() as inner:
            assert outer is not inner
            assert inner.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    # Reuse may cross API worker threads but must never lease a handle twice.
    def write(value):
        with database.transaction(write=True) as db:
            db.execute('INSERT INTO reuse_test VALUES(?,?)', (value, value))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(write, range(40)))
    with database.transaction() as db:
        assert db.execute('SELECT count(*) FROM reuse_test').fetchone()[0] == 40
        assert db.execute('PRAGMA foreign_keys').fetchone()[0] == 1


def test_close_discards_idle_and_checked_out_connections(database):
    with database.transaction() as db:
        database.close()
        assert db.execute('SELECT 1').fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute('SELECT 1')
    assert not database._idle_connections
    # Shutdown callers may still perform a final short transaction, unpooled.
    with database.transaction() as last:
        assert last.execute('SELECT 1').fetchone()[0] == 1
    assert not database._idle_connections


def test_idle_connection_retention_is_bounded(database):
    from contextlib import ExitStack
    with ExitStack() as stack:
        connections = [stack.enter_context(database.transaction()) for _ in range(12)]
        assert len({id(c) for c in connections}) == 12
    assert len(database._idle_connections) == 8


@pytest.mark.asyncio
async def test_browser_lease_lock_wait_leaves_event_loop_responsive(database):
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    from ai2apps.browser.tasks import BrowserTaskRepository
    tasks = BrowserTaskRepository(database)
    task = tasks.enqueue('alice', 'default', 'agent', 'cap', 'gen', 'Read', {})
    tasks.update('alice', task['id'], status='running', worker='local-background')
    runner = BackgroundBrowserRunner(SimpleNamespace(database=database, events=None))
    lock = database.connect()
    lock.execute('BEGIN IMMEDIATE')
    try:
        renewal = asyncio.create_task(asyncio.to_thread(runner.renew_leases))
        await asyncio.sleep(.03)
        # The lock is intentionally still held while the event loop runs here.
        assert not renewal.done()
    finally:
        lock.rollback()
        lock.close()
    await asyncio.wait_for(renewal, 2)
    assert tasks.get('alice', task['id'])['lease_until'] > 0
    renewed = tasks.get('alice', task['id'])['lease_until']
    await asyncio.to_thread(runner.renew_leases)
    assert tasks.get('alice', task['id'])['lease_until'] == renewed
