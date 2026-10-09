"""Actor-scoped task projection over the durable platform event stream."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import aclosing

from .task_presentation import browser_task_wait_presentation
from .tasks import BrowserTaskRepository


def workspace_snapshot(tasks: BrowserTaskRepository, owner: str) -> tuple[int, dict]:
    # Read the projection and high-water mark in the SAME SQLite snapshot.
    # An update concurrent with bootstrap is either included here or replayed.
    with tasks.database.transaction() as c:
        cursor = c.execute('SELECT COALESCE(MAX(sequence),0) FROM events').fetchone()[0]
        rows = c.execute("SELECT * FROM browser_tasks WHERE owner=? AND (status NOT IN ('completed','failed','cancelled') OR id IN (SELECT id FROM browser_tasks WHERE owner=? AND status IN ('completed','failed','cancelled') ORDER BY created_at DESC LIMIT 200)) ORDER BY created_at DESC", (owner, owner)).fetchall()
        settings = c.execute('SELECT global_limit,profile_limit FROM browser_task_settings WHERE owner=?', (owner,)).fetchone()
    projection = [tasks.decode(row) for row in rows]
    for task in projection:
        task.pop('input', None)
    return cursor, {'tasks': projection,
                    'settings': dict(settings) if settings else {'global_limit': 4, 'profile_limit': 1}}


async def stream_workspace(runtime, owner: str, after: int | None = None, *, heartbeat_seconds=15.0) -> AsyncIterator[str]:
    from ai2apps.events.stream import stream_events
    tasks = BrowserTaskRepository(runtime.database, runtime.events)
    def decorate(task):
        if task['status'] == 'waiting_input' and task.get('run_id'):
            task.update(browser_task_wait_presentation(runtime.agents.list_interactions(task['run_id'])))
        return task

    if after is None:
        import asyncio
        after, snapshot = await asyncio.to_thread(workspace_snapshot, tasks, owner)
        snapshot["tasks"] = [decorate(task) for task in snapshot["tasks"]]
        yield f'id: {after}\nevent: browser.workspace.snapshot\ndata: {json.dumps(snapshot, separators=(",", ":"))}\n\n'
    async with aclosing(stream_events(runtime.events, runtime.notifications,
            after_sequence=after, subject_id=tasks.event_subject(owner),
            heartbeat_seconds=heartbeat_seconds)) as messages:
        async for message in messages:
            if message.startswith('id:'):
                # Preserve the durable event ID while enriching its UI projection.
                lines = message.splitlines()
                event = json.loads(next(line[6:] for line in lines if line.startswith('data: ')))
                if event['payload'].get('task'):
                    decorate(event['payload']['task'])
                message = '\n'.join(line if not line.startswith('data: ') else 'data: ' + json.dumps(event, separators=(',', ':')) for line in lines) + '\n\n'
            yield message
