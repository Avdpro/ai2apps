import asyncio
import sys
import pytest
from ai2apps.terminal import TerminalManager, TerminalServiceError


@pytest.mark.asyncio
async def test_managed_terminal_interaction_and_close_guard(tmp_path):
    manager = TerminalManager(default_cwd=tmp_path)
    await manager.startup()
    try:
        session = await manager.create(command=[sys.executable, '-c', 'print("QUESTION",flush=True); print("ANSWER:"+input(),flush=True)'],
                                       source_app='ai2apps.todo', source_task='Fixture task', managed_run='run-fixture')
        assert session.public()['close_protected']
        assert manager.list(owner='terminal')[0]['source_task'] == 'Fixture task'
        with pytest.raises(TerminalServiceError, match='belongs to a task'):
            await manager.close(session.id)
        manager.write(session.id, 'hello\n')
        await asyncio.wait_for(asyncio.shield(session.wait_task), 10)
        _, _, backlog = manager.subscribe(session.id)
        assert b'ANSWER:hello' in backlog
        assert not session.public()['close_protected']
        await manager.close(session.id)
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_managed_terminal_source_can_stop(tmp_path):
    manager = TerminalManager(default_cwd=tmp_path)
    await manager.startup()
    try:
        session = await manager.create(command=[sys.executable,'-c','import time; time.sleep(30)'],managed_run='run-fixture', source_app='ai2apps.todo')
        await manager.close(session.id, allow_managed=True)
        assert session.process.poll() is not None
    finally:
        await manager.shutdown()
