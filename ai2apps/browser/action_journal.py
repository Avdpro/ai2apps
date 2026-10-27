"""Exactly-once admission and durable responses for backend browser actions.

A started command with no committed response is uncertain, never retryable merely
because a process or transport restarted. Reads use the same rule: a read can
navigate or dismiss blockers, so operation names are not a safe replay policy.
"""
from __future__ import annotations

import hashlib
import json
import re
import time


def _unicode_safe(value):
    """Repair JS UTF-16 strings before SQLite and Agent/model serialization.

    JS substring boundaries can leave a lone surrogate. Preserve real Unicode
    and paired surrogates; replace only invalid code units with U+FFFD.
    """
    if isinstance(value, str):
        if re.search(r'[\ud800-\udfff]', value):
            return value.encode('utf-16-le', errors='surrogatepass').decode('utf-16-le', errors='replace')
        return value
    if isinstance(value, dict):
        return {_unicode_safe(k): _unicode_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unicode_safe(item) for item in value]
    return value


class BrowserActionJournal:
    def __init__(self, database):
        self.database = database

    def claim(self, *, run_id, interaction_id, owner, context_id, request):
        # Context-free backend actions use the existing non-null empty value.
        # Normalize before both insertion and replay identity checks; do not
        # create a browser tab merely to satisfy the durable journal schema.
        context_id = '' if context_id is None else context_id
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
        response = _unicode_safe(response)
        encoded = json.dumps(response, ensure_ascii=False, separators=(',', ':'))
        with self.database.transaction(write=True) as c:
            row = c.execute('SELECT state,response_json FROM browser_action_executions WHERE interaction_id=?', (interaction_id,)).fetchone()
            if row is None:
                raise KeyError(interaction_id)
            if row['state'] == 'completed':
                if row['response_json'] != encoded:
                    raise ValueError('Browser action already has a different response')
                return response
            if row['state'] != 'started':
                raise ValueError('Uncertain browser action requires explicit resolution')
            c.execute("UPDATE browser_action_executions SET state='completed',response_json=?,finished_at=? WHERE interaction_id=?", (encoded, time.time(), interaction_id))
        return response

    def report_failure(self, interaction_id, response):
        """Commit a failure observation, never assume success or re-admit the action."""
        if response.get('outcome') != 'failed' or response.get('evidence', {}).get('action_outcome_unknown') is not True:
            raise ValueError('Unknown action requires a failure observation')
        response = _unicode_safe(response)
        encoded=json.dumps(response,ensure_ascii=False,separators=(',', ':'))
        with self.database.transaction(write=True) as c:
            row=c.execute('SELECT state,response_json FROM browser_action_executions WHERE interaction_id=?',(interaction_id,)).fetchone()
            if row is None:raise KeyError(interaction_id)
            if row['state']=='completed':
                return json.loads(row['response_json'])
            if row['state'] not in ('started','uncertain'):raise ValueError('Invalid action state')
            c.execute("UPDATE browser_action_executions SET state='completed',response_json=?,finished_at=? WHERE interaction_id=?",(encoded,time.time(),interaction_id))
        return response

    def complete_observation(self,interaction_id,response):
        """Commit a trusted executor's read-only recovery, never readmit execution."""
        response=_unicode_safe(response)
        with self.database.transaction(write=True) as db:
            row=db.execute('SELECT state,response_json FROM browser_action_executions WHERE interaction_id=?',(interaction_id,)).fetchone()
            if row is None:raise KeyError(interaction_id)
            if row['state']=='completed':return json.loads(row['response_json'])
            if row['state'] not in ('started','uncertain'):raise ValueError('Invalid action state')
            db.execute("UPDATE browser_action_executions SET state='completed',response_json=?,finished_at=? WHERE interaction_id=?",
                (json.dumps(response,ensure_ascii=False,separators=(',',':')),time.time(),interaction_id))
        return response

    def lookup(self, interaction_id):
        with self.database.transaction() as c:
            row = c.execute("SELECT * FROM browser_action_executions WHERE interaction_id=?", (interaction_id,)).fetchone()
        return dict(row) if row else None

    def recover(self):
        with self.database.transaction(write=True) as c:
            rows = c.execute("SELECT run_id,interaction_id FROM browser_action_executions WHERE state='started'").fetchall()
            c.execute("UPDATE browser_action_executions SET state='uncertain',finished_at=? WHERE state='started'", (time.time(),))
        return [dict(row) for row in rows]
