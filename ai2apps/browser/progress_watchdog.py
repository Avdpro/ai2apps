"""Progress deadlines independent of leases, log churn and UI polling."""
from __future__ import annotations
import hashlib
import json
import time

NO_PROGRESS_SECONDS = 300


class ProgressDeadline:
    def __init__(self, signature=None, *, now=None, timeout=NO_PROGRESS_SECONDS):
        self.signature=signature
        self.last_progress=time.monotonic() if now is None else now
        self.timeout=timeout
        self.waiting=False
        self.timed_out=False

    def observe(self, signature, *, now=None, waiting=False):
        now=time.monotonic() if now is None else now
        if waiting or self.waiting or signature!=self.signature:
            self.signature=signature
            self.last_progress=now
        self.waiting=waiting
        if not waiting and now-self.last_progress>=self.timeout:self.timed_out=True
        return self.timed_out


def browser_activity(runtime, *, owner, root_id):
    """Separate blocked leaves from executing leaves in one owner/root scope.

    A browser command awaiting a response still needs the watchdog. A queued
    sibling must never hide another leaf's execution stall.
    """
    from .task_presentation import browser_task_wait_presentation
    with runtime.database.transaction() as db:
        rows = db.execute(
            "SELECT status,run_id,browser_context_json FROM browser_tasks "
            "WHERE owner=? AND root_task_id=? AND status IN "
            "('queued','starting','running','waiting_input','interrupted','cancelling')",
            (owner, root_id),
        ).fetchall()
    blocked = running = 0
    for row in rows:
        context = json.loads(row['browser_context_json'] or '{}')
        waiting = row['status'] == 'queued' or context.get('admission_paused', False)
        if row['run_id'] and row['status'] not in ('interrupted', 'cancelling'):
            run = runtime.agents.get_run(row['run_id'])
            status = getattr(run.status, 'value', run.status)
            waiting = waiting or status == 'queued'
            if status == 'waiting_input':
                waiting = waiting or browser_task_wait_presentation(
                    runtime.agents.list_interactions(row['run_id'])
                ).get('requires_user', False)
        if waiting:
            blocked += 1
        else:
            running += 1
    return {'blocked': blocked, 'running': running}


def completed_steps(database, *, owner, task_id=None, root_id=None):
    """Only committed completed steps; lease/heartbeat/status updates are ignored.

    Identical action/output pairs do not count again when a polling step repeats.
    Owner scope is mandatory even for an explicit root or browser task ID.
    """
    column='id' if task_id else 'root_task_id'
    identifier=task_id or root_id
    with database.transaction() as c:
        rows=c.execute(f"SELECT s.action_key,s.kind,s.output_json FROM run_steps s JOIN browser_tasks b ON b.run_id=s.run_id WHERE b.owner=? AND b.{column}=? AND s.status='completed' AND s.kind!='internal'",(owner,identifier)).fetchall()
    pairs=sorted({(r['action_key'],r['kind'],r['output_json'] or '') for r in rows})
    return hashlib.sha256(json.dumps(pairs,ensure_ascii=False).encode()).hexdigest()
