"""Actor-scoped, durable partial search results; events carry status only."""
import json


def ensure(c):
    c.execute('''CREATE TABLE IF NOT EXISTS browser_search_progress (
        task_id TEXT PRIMARY KEY, owner TEXT NOT NULL, result_json TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES browser_tasks(id) ON DELETE CASCADE)''')


def publish(tasks, owner, task_id, result):
    value=json.dumps({**result, 'partial':True},ensure_ascii=False)
    if len(value.encode())>4_000_000:
        return
    with tasks.database.transaction(write=True) as c:
        ensure(c)
        task=c.execute('SELECT status FROM browser_tasks WHERE owner=? AND id=?',(owner,task_id)).fetchone()
        if not task or task['status'] in ('completed','failed','cancelled'):
            return
        existing=c.execute('SELECT result_json FROM browser_search_progress WHERE owner=? AND task_id=?',(owner,task_id)).fetchone()
        if existing and existing['result_json']==value:
            return
        c.execute('INSERT INTO browser_search_progress VALUES (?,?,?) ON CONFLICT(task_id) DO UPDATE SET result_json=excluded.result_json',(task_id,owner,value))
        tasks._changed(c,owner,task_id)


def read(database, owner, task_id):
    with database.transaction() as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='browser_search_progress'").fetchone():
            return None
        row=c.execute('SELECT result_json FROM browser_search_progress WHERE owner=? AND task_id=?',(owner,task_id)).fetchone()
    return json.loads(row['result_json']) if row else None
