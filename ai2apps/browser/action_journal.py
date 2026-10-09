"""Exactly-once admission and durable responses for backend browser actions.

A started command with no committed response is uncertain, never retryable merely
because a process or transport restarted. Reads use the same rule: a read can
navigate or dismiss blockers, so operation names are not a safe replay policy.
"""
from __future__ import annotations

import hashlib
import json
import time


class BrowserActionJournal:
    def __init__(self, database):
        self.database = database

    def claim(self, *, run_id, interaction_id, owner, context_id, request):
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False,
                                         separators=(',', ':')).encode()).hexdigest()
        with self.database.transaction(write=True) as c:
            existing = c.execute('SELECT * FROM browser_action_executions WHERE interaction_id=?',
                                 (interaction_id,)).fetchone()
            if existing is not None:
                if (existing['run_id'], existing['owner'], existing['context_id'], existing['request_hash']) != (run_id, owner, context_id, digest):
                    raise ValueError('Browser action identity changed')
                return dict(existing), False
            interaction = c.execute('SELECT run_id,status,request_json FROM agent_interactions WHERE id=?', (interaction_id,)).fetchone()
            if interaction is None or interaction['run_id'] != run_id or interaction['status'] != 'pending':
                raise ValueError('Browser action is no longer pending')
            if json.loads(interaction['request_json']) != request:
                raise ValueError('Browser action request changed')
            run = c.execute('SELECT input_json,status FROM agent_runs WHERE id=?', (run_id,)).fetchone()
            if not run or json.loads(run['input_json']).get('parameters', {}).get('owner_user_id') != owner:
                raise ValueError('Browser action owner mismatch')
            if run['status'] != 'waiting_input':
                raise ValueError('Browser run is not waiting for an action')
            c.execute('INSERT INTO browser_action_executions VALUES(?,?,?,?,?,?,NULL,?,NULL)',
                      (interaction_id, run_id, owner, context_id, digest, 'started', time.time()))
            row = c.execute('SELECT * FROM browser_action_executions WHERE interaction_id=?', (interaction_id,)).fetchone()
            return dict(row), True

    def complete(self, interaction_id, response):
        encoded = json.dumps(response, ensure_ascii=False, separators=(',', ':'))
        with self.database.transaction(write=True) as c:
            row = c.execute('SELECT state,response_json FROM browser_action_executions WHERE interaction_id=?', (interaction_id,)).fetchone()
            if row is None:
                raise KeyError(interaction_id)
            if row['state'] == 'completed':
                if row['response_json'] != encoded:
                    raise ValueError('Browser action already has a different response')
                return
            if row['state'] != 'started':
                raise ValueError('Uncertain browser action requires explicit resolution')
            c.execute("UPDATE browser_action_executions SET state='completed',response_json=?,finished_at=? WHERE interaction_id=?", (encoded, time.time(), interaction_id))

    def lookup(self, interaction_id):
        with self.database.transaction() as c:
            row = c.execute("SELECT * FROM browser_action_executions WHERE interaction_id=?", (interaction_id,)).fetchone()
        return dict(row) if row else None

    def recover(self):
        with self.database.transaction(write=True) as c:
            rows = c.execute("SELECT run_id,interaction_id FROM browser_action_executions WHERE state='started'").fetchall()
            c.execute("UPDATE browser_action_executions SET state='uncertain',finished_at=? WHERE state='started'", (time.time(),))
        return [dict(row) for row in rows]
