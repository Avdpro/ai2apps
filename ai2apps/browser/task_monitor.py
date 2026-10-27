"""Reconcile durable browser task state without a foreground workspace page."""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from .task_presentation import browser_task_wait_presentation
from .tasks import ACTIVE, TERMINAL, BrowserTaskRepository
from .progress_watchdog import ProgressDeadline, completed_steps

logger = logging.getLogger(__name__)


def reconcile_browser_tasks(runtime, tasks, owner):
    watches=getattr(runtime,'_browser_progress_deadlines',None)
    if watches is None:runtime._browser_progress_deadlines=watches={}
    for task in tasks.list(owner):
        identity=(owner,task['id'])
        deadline=task.get('browser_context',{}).get('task_deadline_at')
        if task['status']=='queued':
            if deadline is not None and time.time()>=deadline:
                if task['run_id']:runtime.agent_runtime.cancel(task['run_id'])
                tasks.update(owner,task['id'],status='failed',message='Browser Task total time budget expired')
            watches.pop(identity,None)
            continue
        if task['status'] not in ACTIVE:
            watches.pop(identity,None)
            continue
        deadline=task.get('browser_context',{}).get('task_deadline_at')
        if deadline is not None and time.time()>=deadline and not task['run_id']:
            tasks.update(owner,task['id'],status='failed',message='Browser Task total time budget expired')
            watches.pop(identity,None)
            continue
        if task['run_id']:
            run = runtime.agents.get_run(task['run_id'])
            status = run.status.value
            if status in TERMINAL:
                stalled=watches.get(identity)
                tasks.update(owner, task['id'], status='failed' if stalled and stalled.timed_out else 'cancelled' if task['status']=='cancelling' else status,
                    message=task['message'] if stalled and stalled.timed_out else str((run.error or {}).get('message') or ''))
                watches.pop(identity,None)
                continue
            if deadline is not None and time.time()>=deadline:
                runtime.agent_runtime.cancel(task['run_id'])
                tasks.update(owner,task['id'],status='failed',message='Browser Task total time budget expired')
                watches.pop(identity,None)
                continue
            if task['status'] == 'cancelling':
                runtime.agent_runtime.cancel(task['run_id'])
                continue
            if task['status'] != 'interrupted' and status in ('queued', 'running', 'waiting_input'):
                presentation = browser_task_wait_presentation(runtime.agents.list_interactions(task['run_id'])) if status == 'waiting_input' else {}
                if task['worker']=='local-background':
                    signature=completed_steps(runtime.database,owner=owner,task_id=task['id'])
                    watch=watches.setdefault(identity,ProgressDeadline(signature))
                    waiting = (task['status']=='queued' or status=='queued'
                               or task['browser_context'].get('admission_paused',False)
                               or bool(presentation.get('requires_user')))
                    if watch.observe(signature,waiting=waiting):
                        tasks.update(owner,task['id'],status='cancelling',message='任务连续 5 分钟无有效进展，正在停止并清理页面；最后任务：'+task['name'])
                        runtime.agent_runtime.cancel(task['run_id'])
                        continue
                if task['worker'] == 'local-background' and presentation.get('requires_user'):
                    # Retain the task's pages, but yield its execution lease while
                    # a human handles login, verification or confirmation.
                    tasks.update(owner, task['id'], status='waiting_input', paused=True, message=presentation['message'])
                    continue
                if task['browser_context'].get('admission_paused'):
                    # A human response can wake AgentRun before this projection.
                    # Browser actions must reacquire admission, never steal a slot.
                    tasks.update(owner, task['id'], status='queued', message='')
                    continue
                if task['status'] == 'queued':
                    continue
                tasks.update(owner, task['id'], status=status if status != 'queued' else task['status'], message=presentation.get('message',''))
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
        from .task_tree import TaskTreeRepository
        tree = TaskTreeRepository(self.runtime.database, self.runtime.events)
        tasks = BrowserTaskRepository(self.runtime.database, self.runtime.events)
        owners=tasks.owners()
        for owner in owners:
            reconcile_browser_tasks(self.runtime, tasks, owner)
        watches=getattr(self.runtime,'_browser_progress_deadlines',{})
        for identity in list(watches):
            if identity[0] not in owners:watches.pop(identity,None)
        tree.reconcile()

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
