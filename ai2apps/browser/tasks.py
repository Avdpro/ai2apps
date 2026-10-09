"""Durable, actor-scoped browser task admission. Browser commands stay in BiDi."""
from __future__ import annotations
import json
import time
import uuid

ACTIVE = ('starting', 'running', 'waiting_input', 'interrupted')
TERMINAL = ('completed', 'failed', 'cancelled')

class BrowserTaskRepository:
    def __init__(self, database, events=None):
        from ai2apps.events import EventStore
        self.database = database
        self.events = events or EventStore(database)

    @staticmethod
    def event_subject(owner):
        import hashlib
        return 'browser-workspace:' + hashlib.sha256(owner.encode()).hexdigest()

    def _changed(self, connection, owner, task_id=None):
        payload = {}
        if task_id is not None:
            row = connection.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            payload['task'] = self.decode(row)
            # Inputs can contain very large text/files; status events do not need them.
            payload['task'].pop('input', None)
        else:
            payload['settings_changed'] = True
        self.events.append_in_transaction(connection,
            event_type='browser.workspace.changed',
            subject_id=self.event_subject(owner), payload=payload)

    def owners(self):
        with self.database.transaction() as c:
            rows = c.execute("SELECT DISTINCT owner FROM browser_tasks WHERE status NOT IN ('completed','failed','cancelled')").fetchall()
        return [row['owner'] for row in rows]


    @staticmethod
    def decode(row):
        result = dict(row)
        for key in ('input', 'browser_context'):
            result[key] = json.loads(result.pop(key + '_json'))
        return result

    def settings(self, owner):
        with self.database.transaction() as c:
            row = c.execute('SELECT global_limit,profile_limit FROM browser_task_settings WHERE owner=?', (owner,)).fetchone()
        return dict(row) if row else {'global_limit': 4, 'profile_limit': 1}

    def configure(self, owner, global_limit, profile_limit):
        if not 1 <= global_limit <= 16 or not 1 <= profile_limit <= global_limit:
            raise ValueError('Invalid concurrency limits')
        with self.database.transaction(write=True) as c:
            c.execute('INSERT INTO browser_task_settings VALUES(?,?,?) ON CONFLICT(owner) DO UPDATE SET global_limit=excluded.global_limit,profile_limit=excluded.profile_limit', (owner, global_limit, profile_limit))
            self._changed(c, owner)
        return self.settings(owner)

    def list(self, owner):
        with self.database.transaction() as c:
            rows = c.execute("SELECT * FROM browser_tasks WHERE owner=? AND (status NOT IN ('completed','failed','cancelled') OR id IN (SELECT id FROM browser_tasks WHERE owner=? AND status IN ('completed','failed','cancelled') ORDER BY created_at DESC LIMIT 200)) ORDER BY created_at DESC", (owner, owner)).fetchall()
        return [self.decode(row) for row in rows]

    def get(self, owner, task_id):
        with self.database.transaction() as c:
            row = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
        if row is None:
            raise KeyError('Browser task not found')
        return self.decode(row)

    def enqueue(self, owner, profile, agent, capability, generation, name, parameters, *, session_id="", idempotency_key=None, program=None, caller_app_id=""):
        import hashlib
        task_id = 'btask_' + (hashlib.sha256((owner+'\0'+idempotency_key).encode()).hexdigest() if idempotency_key else uuid.uuid4().hex)
        now = time.time()
        with self.database.transaction(write=True) as c:
            existing = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if existing:
                return self.decode(existing)
            count = c.execute("SELECT count(*) FROM browser_tasks WHERE owner=? AND status='queued'", (owner,)).fetchone()[0]
            if count >= 100:
                raise ValueError('Task queue is full')
            c.execute('INSERT INTO browser_tasks(id,owner,profile_key,agent_id,capability,generation_id,name,input_json,browser_context_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (task_id, owner, profile, agent, capability, generation, name, json.dumps(parameters), '{}', 'queued', now, now))
            c.execute("UPDATE browser_tasks SET session_id=? WHERE id=?", (session_id, task_id))
            if program is not None or caller_app_id:
                c.execute('INSERT INTO browser_task_programs VALUES(?,?,?,?)', (task_id, owner, caller_app_id, json.dumps(program)))
            self._changed(c, owner, task_id)
        return self.get(owner, task_id)

    def program(self, owner, task_id):
        with self.database.transaction() as c:
            row = c.execute('SELECT ir_json,caller_app_id FROM browser_task_programs WHERE task_id=? AND owner=?', (task_id, owner)).fetchone()
        return (json.loads(row['ir_json']), row['caller_app_id']) if row else (None, None)

    def claim(self, owner, worker):
        # BEGIN IMMEDIATE makes admission atomic across App windows.
        with self.database.transaction(write=True) as c:
            settings = c.execute('SELECT global_limit,profile_limit FROM browser_task_settings WHERE owner=?', (owner,)).fetchone()
            overall, per_profile = (settings[0], settings[1]) if settings else (4, 1)
            rows = c.execute("SELECT profile_key,count(*) n FROM browser_tasks WHERE owner=? AND status IN ('starting','running','waiting_input','interrupted') GROUP BY profile_key", (owner,)).fetchall()
            counts = {r['profile_key']: r['n'] for r in rows}
            if sum(counts.values()) >= overall:
                return None
            candidates = c.execute("SELECT id,profile_key FROM browser_tasks WHERE owner=? AND status='queued' ORDER BY created_at,id", (owner,)).fetchall()
            task = next((r for r in candidates if counts.get(r['profile_key'], 0) < per_profile), None)
            if task is None:
                return None
            c.execute("UPDATE browser_tasks SET status='starting',worker=?,lease_until=?,updated_at=? WHERE id=?", (worker, time.time()+90, time.time(), task['id']))
            self._changed(c, owner, task['id'])
        return self.get(owner, task['id'])

    def update(self, owner, task_id, **values):
        allowed = {'status', 'worker', 'lease_until', 'run_id', 'message', 'browser_context_json'}
        if not values or not set(values) <= allowed:
            raise ValueError('Invalid task update')
        with self.database.transaction(write=True) as c:
            before = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if before is None:
                raise KeyError('Browser task not found')
            if before['status'] in TERMINAL and values.get('status') in ACTIVE:
                return self.decode(before)
            if all(before[key] == value for key, value in values.items()):
                return self.decode(before)
            cursor = c.execute('UPDATE browser_tasks SET '+','.join(k+'=?' for k in values)+',updated_at=? WHERE owner=? AND id=?', (*values.values(), time.time(), owner, task_id))
            if cursor.rowcount != 1:
                raise KeyError('Browser task not found')
            # Lease renewal alone is not a visible state change.
            if set(values) != {'lease_until'}:
                self._changed(c, owner, task_id)
        return self.get(owner, task_id)

    def reserve_external(self, owner, profile, agent, capability, generation, name, parameters, context, key=None):
        """Apply the same admission gate to Sidebar/API root runs (no auto-queue)."""
        import hashlib
        task_id = 'direct_' + (hashlib.sha256((owner+'\0'+key).encode()).hexdigest() if key else uuid.uuid4().hex)
        with self.database.transaction(write=True) as c:
            existing = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if existing:
                return self.decode(existing)
            # Reconcile terminal records before admission, including their durable events.
            settled = c.execute("SELECT id FROM browser_tasks WHERE owner=? AND status NOT IN ('completed','failed','cancelled') AND EXISTS(SELECT 1 FROM agent_runs WHERE id=browser_tasks.run_id AND status IN ('completed','failed','cancelled'))", (owner,)).fetchall()
            c.execute("UPDATE browser_tasks SET status=(SELECT status FROM agent_runs WHERE agent_runs.id=browser_tasks.run_id) WHERE owner=? AND run_id!='' AND EXISTS(SELECT 1 FROM agent_runs WHERE id=browser_tasks.run_id AND status IN ('completed','failed','cancelled'))", (owner,))
            for row in settled:
                self._changed(c, owner, row['id'])
            settings = c.execute('SELECT global_limit,profile_limit FROM browser_task_settings WHERE owner=?', (owner,)).fetchone()
            overall, per_profile = (settings[0], settings[1]) if settings else (4, 1)
            counts = c.execute("SELECT profile_key FROM browser_tasks WHERE owner=? AND status IN ('starting','running','waiting_input','interrupted')", (owner,)).fetchall()
            if len(counts) >= overall or sum(r['profile_key'] == profile for r in counts) >= per_profile:
                raise ValueError('WebAgent 并发名额已满，请在 AI 浏览器任务栏等待或取消现有任务。')
            now = time.time()
            c.execute('INSERT INTO browser_tasks(id,owner,profile_key,agent_id,capability,generation_id,name,input_json,browser_context_json,status,worker,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (task_id,owner,profile,agent,capability,generation,name,json.dumps(parameters),json.dumps(context),'starting','external',now,now))
            self._changed(c, owner, task_id)
        return self.get(owner, task_id)
