"""Durable, actor-scoped browser task admission. Browser commands stay in BiDi."""
from __future__ import annotations
import json
import time
import uuid

ACTIVE = ('starting', 'running', 'waiting_input', 'interrupted', 'cancelling')
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
        context = result['browser_context']
        result['paused'] = bool(context.get('admission_paused')) and result['status'] == 'waiting_input'
        result['holds_browser_slot'] = (not context.get('admission_paused') and result['status'] in ACTIVE or bool(result['status'] in TERMINAL and result['run_id'] and (context.get('created_by_run') or context.get('owned_contexts')) and context.get('cleanup', {}).get('state', 'pending') == 'pending'))
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

    def enqueue(self, owner, profile, agent, capability, generation, name, parameters, *, session_id="", idempotency_key=None, program=None, caller_app_id="", retain_pages_reason="", parent_task_id="", reuse_page=False, model_profile="normal", parallel_limit=1, timeout_seconds=None):
        if not isinstance(parallel_limit,int) or not 1<=parallel_limit<=3 or (parallel_limit>1 and (not parent_task_id or not caller_app_id)):raise ValueError('Parallel children require a trusted owning Task')
        if model_profile not in {'normal', 'privacy'}: raise ValueError('Unknown model profile')
        if reuse_page and not parent_task_id:raise ValueError('Page reuse requires an owning parent Task')
        import hashlib
        task_id = 'btask_' + (hashlib.sha256((owner+'\0'+idempotency_key).encode()).hexdigest() if idempotency_key else uuid.uuid4().hex)
        now = time.time()
        # This shared repository stores a generic time budget; Source policy
        # interpretation belongs to the trusted WebAgent submission owner.
        import math
        if timeout_seconds is not None and (isinstance(timeout_seconds,bool) or not isinstance(timeout_seconds,(int,float)) or not math.isfinite(timeout_seconds) or timeout_seconds<=0):
            raise ValueError('Invalid Task timeout_seconds')
        deadline=now+timeout_seconds if timeout_seconds is not None else None
        with self.database.transaction(write=True) as c:
            existing = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if existing:
                if existing['parent_task_id'] != parent_task_id:
                    raise ValueError('Idempotent browser task has another parent')
                return self.decode(existing)
            from .task_tree import TaskTreeRepository
            root_task_id = TaskTreeRepository.binding(c, owner, parent_task_id) if parent_task_id else 'webtask:'+task_id
            count = c.execute("SELECT count(*) FROM browser_tasks WHERE owner=? AND status='queued'", (owner,)).fetchone()[0]
            if count >= 100:
                raise ValueError('Task queue is full')
            c.execute('INSERT INTO browser_tasks(id,owner,profile_key,agent_id,capability,generation_id,name,input_json,browser_context_json,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (task_id, owner, profile, agent, capability, generation, name, json.dumps(parameters), '{}', 'queued', now, now))
            c.execute("UPDATE browser_tasks SET session_id=?,browser_context_json=? WHERE id=?", (session_id, json.dumps({'retain_pages_reason': str(retain_pages_reason or '').strip()[:500], 'reuse_scope': parent_task_id if reuse_page else '', 'model_profile': model_profile,'parallel_limit':parallel_limit, **({'task_deadline_at':deadline} if deadline is not None else {})}), task_id))
            execution = 'execution:'+task_id if parent_task_id else root_task_id
            TaskTreeRepository.create_in_transaction(c, owner, execution, name, parent_id=parent_task_id or None, kind='browser_execution' if parent_task_id else 'webagent', events=self.events)
            c.execute('UPDATE browser_tasks SET parent_task_id=?,root_task_id=?,execution_task_id=? WHERE id=?', (parent_task_id, root_task_id, execution, task_id))
            if program is not None or caller_app_id:
                c.execute('INSERT INTO browser_task_programs VALUES(?,?,?,?)', (task_id, owner, caller_app_id, json.dumps(program)))
            self._changed(c, owner, task_id)
        return self.get(owner, task_id)

    def program(self, owner, task_id):
        with self.database.transaction() as c:
            row = c.execute('SELECT ir_json,caller_app_id FROM browser_task_programs WHERE task_id=? AND owner=?', (task_id, owner)).fetchone()
        return (json.loads(row['ir_json']), row['caller_app_id']) if row else (None, None)

    @staticmethod
    def _active_groups(c, owner):
        rows = c.execute("SELECT id,root_task_id,profile_key FROM browser_tasks WHERE owner=? AND ((status IN ('starting','running','waiting_input','interrupted','cancelling') AND COALESCE(json_extract(browser_context_json,'$.admission_paused'),0)=0) OR (run_id!='' AND (json_extract(browser_context_json,'$.created_by_run') IS NOT NULL OR json_extract(browser_context_json,'$.owned_contexts') IS NOT NULL) AND status IN ('completed','failed','cancelled') AND COALESCE(json_extract(browser_context_json,'$.cleanup.state'),'pending')='pending'))", (owner,)).fetchall()
        return {(r['root_task_id'] or r['id'], r['profile_key']) for r in rows}

    @staticmethod
    def _admitted(groups, root, profile, overall, per_profile):
        # A new root/Profile acquires one lease; opted-in sibling caps are checked in claim.
        # Different Profiles of the same root each consume one global lease.
        return ((root, profile) not in groups and len(groups) < overall
                and sum(p == profile for _, p in groups) < per_profile)

    def claim(self, owner, worker):
        # BEGIN IMMEDIATE makes admission atomic across App windows.
        with self.database.transaction(write=True) as c:
            settings = c.execute('SELECT global_limit,profile_limit FROM browser_task_settings WHERE owner=?', (owner,)).fetchone()
            overall, per_profile = (settings[0], settings[1]) if settings else (4, 1)
            rows = self._active_groups(c, owner)
            candidates = c.execute("SELECT id,profile_key,root_task_id,parent_task_id FROM browser_tasks WHERE owner=? AND status='queued' ORDER BY created_at,id", (owner,)).fetchall()
            task = None
            from .task_tree import TaskTreeRepository
            for candidate in candidates:
                if candidate['parent_task_id']:
                    try:
                        TaskTreeRepository.binding(c, owner, candidate['parent_task_id'])
                    except ValueError:
                        c.execute("UPDATE browser_tasks SET status='cancelled',updated_at=? WHERE id=?", (time.time(), candidate['id']))
                        self._changed(c, owner, candidate['id'])
                        continue
                root=candidate['root_task_id'] or candidate['id'];profile=candidate['profile_key']
                siblings=c.execute("SELECT browser_context_json,status FROM browser_tasks WHERE owner=? AND root_task_id=? AND profile_key=? AND ((status IN ('starting','running','waiting_input','interrupted','cancelling') AND COALESCE(json_extract(browser_context_json,'$.admission_paused'),0)=0) OR (run_id!='' AND status IN ('completed','failed','cancelled') AND COALESCE(json_extract(browser_context_json,'$.cleanup.state'),'pending')='pending' AND json_extract(browser_context_json,'$.created_by_run')!=''))",(owner,root,profile)).fetchall()
                candidate_context=json.loads(c.execute('SELECT browser_context_json FROM browser_tasks WHERE id=?',(candidate['id'],)).fetchone()[0])
                cap=min([candidate_context.get('parallel_limit',1),*[json.loads(r['browser_context_json']).get('parallel_limit',1) for r in siblings]])
                within_group=(root,profile) in rows and len(siblings)<cap and all(r['status'] not in ('interrupted','cancelling') for r in siblings)
                if within_group or self._admitted(rows,root,profile,overall,per_profile):
                    task = candidate
                    break
            if task is None:
                return None
            c.execute("UPDATE browser_tasks SET browser_context_json=json_set(browser_context_json,'$.admission_paused',json('false')) WHERE id=?", (task['id'],))
            c.execute("UPDATE browser_tasks SET status='starting',worker=?,lease_until=?,updated_at=? WHERE id=?", (worker, time.time()+90, time.time(), task['id']))
            self._changed(c, owner, task['id'])
        return self.get(owner, task['id'])

    def update(self, owner, task_id, **values):
        allowed = {'status', 'worker', 'lease_until', 'run_id', 'message', 'browser_context_json', 'paused'}
        if not values or not set(values) <= allowed:
            raise ValueError('Invalid task update')
        with self.database.transaction(write=True) as c:
            before = c.execute('SELECT * FROM browser_tasks WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if before is None:
                raise KeyError('Browser task not found')
            # Cancellation/ambiguous interruption retain their conservative lease
            # until browser cleanup settles, even after a human pause.
            if values.get('status') in ('interrupted', 'cancelling'):
                values['paused'] = False
            paused = values.pop('paused', None)
            if 'browser_context_json' in values or paused is not None:
                previous=json.loads(before['browser_context_json'])
                context=json.loads(values.get('browser_context_json',before['browser_context_json']))
                context['parallel_limit']=previous.get('parallel_limit',1)
                context['admission_paused']=previous.get('admission_paused',False) if paused is None else bool(paused)
                values['browser_context_json']=json.dumps(context)
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
            groups = self._active_groups(c, owner)
            if not self._admitted(groups, task_id, profile, overall, per_profile):
                raise ValueError('WebAgent 并发名额已满，请在 AI 浏览器任务栏等待或取消现有任务。')
            now = time.time()
            c.execute('INSERT INTO browser_tasks(id,owner,profile_key,agent_id,capability,generation_id,name,input_json,browser_context_json,status,worker,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)', (task_id,owner,profile,agent,capability,generation,name,json.dumps(parameters),json.dumps(context),'starting','external',now,now))
            from .task_tree import TaskTreeRepository
            root = 'webtask:'+task_id
            TaskTreeRepository.create_in_transaction(c, owner, root, name, kind='webagent', events=self.events)
            c.execute('UPDATE browser_tasks SET root_task_id=?,execution_task_id=? WHERE id=?', (root, root, task_id))
            self._changed(c, owner, task_id)
        return self.get(owner, task_id)
