"""Reconcile durable browser task state without a foreground workspace page."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from .task_presentation import browser_task_wait_presentation
from .tasks import ACTIVE, TERMINAL, BrowserTaskRepository

logger = logging.getLogger(__name__)


def reconcile_browser_tasks(runtime, tasks, owner):
    for task in tasks.list(owner):
        if task['status'] not in ACTIVE:
            continue
        if task['run_id']:
            run = runtime.agents.get_run(task['run_id'])
            status = run.status.value
            if status in TERMINAL:
                tasks.update(owner, task['id'], status=status,
                    message=str((run.error or {}).get('message') or ''))
                continue
            if task['status'] != 'interrupted' and status in ('running', 'waiting_input'):
                message = browser_task_wait_presentation(runtime.agents.list_interactions(task['run_id']))['message'] if status == 'waiting_input' else ''
                tasks.update(owner, task['id'], status=status, message=message)
        if task['worker'] != 'external' and task['lease_until'] < time.time() and task['status'] != 'interrupted':
            if task['run_id']:
                runtime.agent_runtime.pause(task['run_id'])
            # A lost action response is ambiguous; never replay a browser mutation.
            tasks.update(owner, task['id'], status='interrupted',
                         message='执行连接中断。请检查页面后继续或取消。')


class BrowserTaskMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self._stop = asyncio.Event()
        self._task = None

    async def startup(self):
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name='ai2apps-browser-task-monitor')

    async def shutdown(self):
        self._stop.set()
        self.runtime.notifications.notify()
        if self._task is not None:
            await self._task
        self._task = None

    def reconcile(self):
        tasks = BrowserTaskRepository(self.runtime.database, self.runtime.events)
        for owner in tasks.owners():
            reconcile_browser_tasks(self.runtime, tasks, owner)

    async def _loop(self):
        async with self.runtime.notifications.subscribe() as wake:
            while not self._stop.is_set():
                try:
                    await asyncio.to_thread(self.reconcile)
                except Exception:
                    logger.exception('Browser task reconciliation failed')
                # Commit events drive status updates; timeout only checks lease expiry.
                with suppress(TimeoutError):
                    await asyncio.wait_for(wake.get(), timeout=5.0)
