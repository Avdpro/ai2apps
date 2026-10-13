"""Durable composite task ownership; browser execution remains in BrowserTaskRepository."""
import json
import time

TERMINAL = ('completed', 'failed', 'cancelled')


class TaskTreeRepository:
    def __init__(self, database, events=None):
        from ai2apps.events import EventStore
        self.database = database
        self.events = events or EventStore(database)

    def create(self, owner, task_id, name, *, parent_id=None, kind='composite'):
        with self.database.transaction(write=True) as c:
            return self.create_in_transaction(c, owner, task_id, name, parent_id=parent_id, kind=kind, events=self.events)

    @staticmethod
    def create_in_transaction(c, owner, task_id, name, *, parent_id=None, kind='composite', events=None):
        existing = c.execute('SELECT * FROM task_nodes WHERE id=? AND owner=?', (task_id, owner)).fetchone()
        if existing:
            if existing['parent_id'] != parent_id or existing['kind'] != kind:
                raise ValueError('Task identity already has another parent or kind')
            return dict(existing)
        root = TaskTreeRepository.binding(c, owner, parent_id) if parent_id else task_id
        now = time.time()
        c.execute('INSERT INTO task_nodes(id,owner,parent_id,root_id,kind,name,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (task_id, owner, parent_id, root, kind, name, 'running', now, now))
        if events is not None:
            TaskTreeRepository.changed(c, owner, task_id, events)
        return dict(c.execute('SELECT * FROM task_nodes WHERE id=? AND owner=?', (task_id, owner)).fetchone())

    @staticmethod
    def changed(c, owner, task_id, events):
        from .tasks import BrowserTaskRepository
        row = dict(c.execute('SELECT * FROM task_nodes WHERE owner=? AND id=?', (owner, task_id)).fetchone())
        row.pop('result_json', None)
        events.append_in_transaction(c, event_type='browser.workspace.changed',
            subject_id=BrowserTaskRepository.event_subject(owner), payload={'task_node':row})

    @staticmethod
    def projection(c, owner):
        # Results may contain full article evidence; status streams never carry it.
        rows = c.execute("SELECT id,owner,parent_id,root_id,kind,name,status,created_at,updated_at FROM task_nodes WHERE owner=? AND root_id IN (SELECT id FROM task_nodes WHERE owner=? AND parent_id IS NULL AND (status NOT IN ('completed','failed','cancelled') OR id IN (SELECT id FROM task_nodes WHERE owner=? AND parent_id IS NULL ORDER BY created_at DESC LIMIT 200))) ORDER BY created_at", (owner, owner, owner)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def binding(c, owner, parent_id):
        row = c.execute('SELECT * FROM task_nodes WHERE id=? AND owner=?', (parent_id, owner)).fetchone()
        if row is None:
            raise ValueError('Task parent not found for this owner')
        current = row
        while current:
            if current['status'] in (*TERMINAL, 'finishing'):
                raise ValueError('Task parent is already terminal')
            current = c.execute('SELECT * FROM task_nodes WHERE id=? AND owner=?', (current['parent_id'], owner)).fetchone() if current['parent_id'] else None
        return row['root_id']

    def list(self, owner):
        with self.database.transaction() as c:
            return self.projection(c, owner)

    def get(self, owner, task_id):
        with self.database.transaction() as c:
            row = c.execute('SELECT * FROM task_nodes WHERE owner=? AND id=?', (owner, task_id)).fetchone()
        if row is None:
            raise KeyError('Task not found')
        return dict(row)

    def finish(self, owner, task_id, status='completed', result=None):
        if status not in TERMINAL:
            raise ValueError('Invalid terminal task status')
        with self.database.transaction(write=True) as c:
            row = c.execute('SELECT * FROM task_nodes WHERE owner=? AND id=?', (owner, task_id)).fetchone()
            if row is None:
                raise KeyError('Task not found')
            if row['status'] in TERMINAL:
                return row['status'] == status
            if row['status'] == 'finishing' and json.loads(row['result_json']).get('requested_status') == 'cancelled':
                status, result = 'cancelled', {}
            c.execute("UPDATE task_nodes SET status='finishing',result_json=?,updated_at=? WHERE owner=? AND id=?", (json.dumps({'requested_status':status, 'result':result or {}}), time.time(), owner, task_id))
            if row['status'] != 'finishing':
                self.changed(c, owner, task_id, self.events)
            children = c.execute('SELECT status FROM task_nodes WHERE owner=? AND parent_id=?', (owner, task_id)).fetchall()
            browsers = c.execute('SELECT status,browser_context_json,run_id FROM browser_tasks WHERE owner=? AND (parent_task_id=? OR execution_task_id=?)', (owner, task_id, task_id)).fetchall()
            if any(r['status'] not in TERMINAL for r in (*children, *browsers)):
                return False
            # Completion is conservative: a bound browser run must prove cleanup.
            if any((context.get('created_by_run') or context.get('owned_contexts')) and context.get('cleanup', {}).get('state') not in ('verified', 'retained') for context in (json.loads(r['browser_context_json']) for r in browsers)):
                return False
            if any(context.get('reuse_scope') == task_id and context.get('cleanup', {}).get('state') != 'verified' for context in (json.loads(r['browser_context_json']) for r in browsers)):
                return False
            c.execute('UPDATE task_nodes SET status=?,result_json=?,updated_at=? WHERE owner=? AND id=?',
                      (status, json.dumps(result or {}), time.time(), owner, task_id))
            self.changed(c, owner, task_id, self.events)
            return True

    def settle_browser_executions(self):
        # Frames share the parent's Agent Run and browser lease. A terminal run
        # cancels unfinished frames; it never starts them again to settle a tree.
        with self.database.transaction(write=True) as c:
            rows = [dict(r) for r in c.execute("SELECT b.* FROM browser_tasks b JOIN task_nodes n ON n.id=b.execution_task_id AND n.owner=b.owner WHERE b.status IN ('completed','failed','cancelled') AND n.status NOT IN ('completed','failed','cancelled')")]
            for task in rows:
                descendants = c.execute("WITH RECURSIVE frames(id) AS (SELECT id FROM task_nodes WHERE owner=? AND parent_id=? AND kind='capability_call' UNION ALL SELECT n.id FROM task_nodes n JOIN frames f ON n.parent_id=f.id WHERE n.owner=?) SELECT id FROM frames", (task['owner'], task['execution_task_id'], task['owner'])).fetchall()
                for frame in descendants:
                    before = c.execute('SELECT status FROM task_nodes WHERE owner=? AND id=?', (task['owner'], frame['id'])).fetchone()
                    c.execute("UPDATE task_nodes SET status=?,result_json=?,updated_at=? WHERE owner=? AND id=? AND status NOT IN ('completed','failed','cancelled')", ('cancelled' if task['status']=='cancelled' else 'failed', json.dumps({'message':'Enclosing browser execution ended'}), time.time(), task['owner'], frame['id']))
                    if before['status'] not in TERMINAL:
                        self.changed(c, task['owner'], frame['id'], self.events)
        for task in rows:
            self.finish(task['owner'], task['execution_task_id'], task['status'], {'browser_task_id':task['id'], 'run_id':task['run_id']})

    def reconcile(self):
        self.settle_browser_executions()
        with self.database.transaction() as c:
            searches=[dict(r) for r in c.execute("SELECT * FROM task_nodes WHERE kind='search' AND status='running'")]
        for node in searches:
            expected=json.loads(node['result_json'] or '{}').get('expected_sources',0)
            with self.database.transaction() as c:
                children=c.execute('SELECT status FROM browser_tasks WHERE owner=? AND parent_task_id=?',(node['owner'],node['id'])).fetchall()
            if expected and len(children)>=expected and all(r['status'] in TERMINAL for r in children):
                status='completed' if any(r['status']=='completed' for r in children) else 'failed'
                self.finish(node['owner'],node['id'],status,{**json.loads(node['result_json'] or '{}'),'source_count':len(children)})
        with self.database.transaction() as c:
            pending = [dict(r) for r in c.execute("SELECT * FROM task_nodes WHERE status='finishing' ORDER BY created_at DESC")]
        for node in pending:
            desired = json.loads(node['result_json'])
            self.finish(node['owner'], node['id'], desired['requested_status'], desired['result'])

    def cancel(self, owner, task_id):
        """Cancel descendants atomically; caller cancels the returned Agent Runs."""
        self.get(owner, task_id)
        with self.database.transaction(write=True) as c:
            rows = c.execute('WITH RECURSIVE descendants(id) AS (SELECT id FROM task_nodes WHERE owner=? AND id=? UNION ALL SELECT n.id FROM task_nodes n JOIN descendants d ON n.parent_id=d.id WHERE n.owner=?) SELECT id FROM descendants', (owner, task_id, owner)).fetchall()
            ids = [r['id'] for r in rows]
            runs = []
            from .tasks import BrowserTaskRepository
            tasks = BrowserTaskRepository(self.database)
            for node in ids:
                for browser in c.execute("SELECT id,run_id FROM browser_tasks WHERE owner=? AND (parent_task_id=? OR execution_task_id=?) AND status NOT IN ('completed','failed','cancelled')", (owner, node, node)).fetchall():
                    if browser['run_id']:
                        runs.append(browser['run_id'])
                    c.execute("UPDATE browser_tasks SET status=?,updated_at=? WHERE id=?", ('cancelling' if browser['run_id'] else 'cancelled', time.time(), browser['id']))
                    tasks._changed(c, owner, browser['id'])
                c.execute("UPDATE task_nodes SET status='finishing',result_json=?,updated_at=? WHERE owner=? AND id=? AND status NOT IN ('completed','failed','cancelled')", (json.dumps({"requested_status":"cancelled", "result":{}}), time.time(), owner, node))
                self.changed(c, owner, node, self.events)
            return sorted(set(runs))
