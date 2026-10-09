import asyncio
import sqlite3
import threading

from ai2apps.codex.manager import CodexManager, _emit_update
from ai2apps.todo.store import TodoStore


def test_locked_database_does_not_block_event_loop(tmp_path):
    store = TodoStore(tmp_path)
    locked = threading.Event()
    release = threading.Event()

    def hold_write_lock():
        connection = sqlite3.connect(tmp_path / 'todo.sqlite3')
        try:
            connection.execute('BEGIN IMMEDIATE')
            locked.set()
            release.wait(3)
        finally:
            connection.rollback()
            connection.close()

    async def check():
        writer = threading.Thread(target=hold_write_lock)
        writer.start()
        await asyncio.to_thread(locked.wait, 2)
        task = asyncio.create_task(_emit_update(
            lambda status, **fields: store.run_update('missing', status, **fields),
            'running', output='text',
        ))
        try:
            await asyncio.sleep(0.05)
            assert not task.done(), 'write must still be waiting on the database lock'
        finally:
            release.set()
            await task
            await asyncio.to_thread(writer.join)

    asyncio.run(asyncio.wait_for(check(), 2))


def test_stream_updates_are_coalesced_and_final_output_is_complete(monkeypatch):
    class Desktop:
        async def __aenter__(self):
            self.events = asyncio.Queue()
            for _ in range(100):
                self.events.put_nowait({'method': 'item/agentMessage/delta',
                                       'params': {'delta': 'x'}})
            self.events.put_nowait({'method': 'turn/completed',
                                   'params': {'turn': {'id': 'turn', 'status': 'completed'}}})
            return self

        async def __aexit__(self, *_):
            pass

        async def call(self, method, params, **kwargs):
            if method == 'thread/start':
                return {'thread': {'id': 'thread'}}
            if method == 'turn/start':
                return {'turn': {'id': 'turn'}}
            return {}

    monkeypatch.setattr('ai2apps.codex.transport.CodexDesktop', Desktop)
    updates = []

    async def update(status, **fields):
        updates.append((status, fields))

    async def bind(_):
        pass

    asyncio.run(CodexManager().execute(
        'run', 'owner', cwd='/tmp', title='test', prompt='test',
        on_update=update, on_thread=bind,
    ))
    assert sum('output' in fields for _, fields in updates) < 10
    assert updates[-1][0] == 'ended'
    assert updates[-1][1]['output'] == 'x' * 100
