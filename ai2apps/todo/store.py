import json
import sqlite3
import uuid
import unicodedata
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import TaskInput, emoji_key, next_due, normalize_task_state


def normalize_name(value):
    value = unicodedata.normalize('NFKC', value).casefold()
    return ' '.join(''.join(c if unicodedata.category(c)[0] in ('L','N','M') and c not in '\ufe0e\ufe0f' else ' ' for c in value).split())


def now_text():
    return datetime.now(UTC).isoformat()


class TodoStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS directory_order(owner TEXT NOT NULL, directory_id TEXT NOT NULL, position INTEGER NOT NULL, PRIMARY KEY(owner,directory_id));
                CREATE TABLE IF NOT EXISTS emoji_history(owner TEXT NOT NULL, task_id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(owner,task_id));
                CREATE TABLE IF NOT EXISTS directories(id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS linked_directories(owner TEXT NOT NULL, source TEXT NOT NULL, directory_id TEXT NOT NULL, PRIMARY KEY(owner,source));
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL, revision INTEGER NOT NULL, next_due TEXT, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS task_owner ON tasks(owner);
                CREATE TABLE IF NOT EXISTS task_creation_receipts(owner TEXT NOT NULL, request_key TEXT NOT NULL, input_json TEXT NOT NULL, task_id TEXT NOT NULL, PRIMARY KEY(owner,request_key));
                CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY, owner TEXT NOT NULL, task_id TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, owner TEXT NOT NULL, task_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS run_owner ON runs(owner,task_id);
                CREATE TABLE IF NOT EXISTS task_execution_lanes(owner TEXT NOT NULL, task_id TEXT NOT NULL UNIQUE, lane TEXT NOT NULL, PRIMARY KEY(owner,task_id));
                CREATE INDEX IF NOT EXISTS execution_lane_tasks ON task_execution_lanes(owner,lane);
                CREATE TABLE IF NOT EXISTS execution_lane_fairness(owner TEXT,lane TEXT,burst INTEGER NOT NULL,PRIMARY KEY(owner,lane));
                CREATE TABLE IF NOT EXISTS task_system_schedules(owner TEXT NOT NULL,task_id TEXT NOT NULL,PRIMARY KEY(owner,task_id));
                CREATE TABLE IF NOT EXISTS task_execution_bindings(owner TEXT NOT NULL,task_id TEXT PRIMARY KEY,registration TEXT NOT NULL,binding_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS run_creation_receipts(owner TEXT NOT NULL,request_key TEXT NOT NULL,task_id TEXT NOT NULL,run_id TEXT NOT NULL,PRIMARY KEY(owner,request_key));
                CREATE TABLE IF NOT EXISTS execution_plan_receipts(owner TEXT NOT NULL,request_key TEXT NOT NULL,signature TEXT NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(owner,request_key));
                CREATE TABLE IF NOT EXISTS schedule_disable_receipts(owner TEXT NOT NULL,request_key TEXT NOT NULL,task_id TEXT NOT NULL,expected_revision INTEGER NOT NULL,result_json TEXT NOT NULL,PRIMARY KEY(owner,request_key));
            """)

        from .activity import install
        with self.connect() as db:
            install(db)

    def execution_binding(self, owner, task_id):
        with self.connect() as db:
            row=db.execute('SELECT registration,binding_json FROM task_execution_bindings WHERE owner=? AND task_id=?',(owner,task_id)).fetchone()
        return {'registration':row['registration'],'binding':json.loads(row['binding_json'])} if row else None

    def launch_receipt(self, owner, request_key):
        with self.connect() as db:
            row=db.execute('SELECT run_id,task_id FROM run_creation_receipts WHERE owner=? AND request_key=?',(owner,request_key)).fetchone()
        return dict(row) if row else None

    def bind_execution_lane(self, owner, task_id, lane, *, expected_lane=None):
        """Trusted owner adapters assign a serial lane; this grants no execution rights."""
        if lane is not None and (not isinstance(lane, str) or not 1 <= len(lane) <= 160):
            raise ValueError("Invalid execution lane")
        with self.connect() as db:
            task = self.task(db.execute("SELECT * FROM tasks WHERE owner=? AND id=?", (owner, task_id)).fetchone())
            current = db.execute("SELECT lane FROM task_execution_lanes WHERE owner=? AND task_id=?", (owner, task_id)).fetchone()
            if lane is None and (not expected_lane or not current or current[0] != expected_lane):
                raise ValueError("Task assignment changed")
            if (current[0] if current else None) == lane:
                return
            if db.execute('SELECT 1 FROM task_execution_bindings WHERE owner=? AND task_id=?',(owner,task_id)).fetchone():
                raise ValueError('Task execution owner controls this assignment')
            if lane is not None and (task.get("deleted_at") or task.get("archived_at")):
                raise ValueError("Restore this project before assigning it")
            if db.execute("SELECT 1 FROM runs WHERE owner=? AND task_id=? AND status IN ('queued','running','planning','waiting_input','waiting_capability')", (owner, task_id)).fetchone():
                raise ValueError("Finish or cancel the active run before changing its assignment")
            if current and lane is not None:
                raise ValueError("Remove the existing assignment first")
            db.execute("DELETE FROM task_execution_lanes WHERE owner=? AND task_id=?", (owner, task_id))
            if lane is not None:
                db.execute("INSERT INTO task_execution_lanes VALUES(?,?,?)", (owner, task_id, lane))

    def update_execution_plan(self,owner,task_id,revision,registration,changes,binding,request_key):
        """Trusted owner CAS update. Existing Run snapshots/bindings are immutable."""
        if set(changes)-{'title','description','model','schedule','executor'} or changes.get('executor','managed')!='managed':raise ValueError('Unsupported plan change')
        signature=json.dumps([task_id,revision,registration,changes,binding],sort_keys=True,separators=(',',':'))
        with self.connect() as db:
            receipt=db.execute('SELECT * FROM execution_plan_receipts WHERE owner=? AND request_key=?',(owner,request_key)).fetchone()
            if receipt:
                if receipt['signature']!=signature:raise ValueError('Plan request belongs to different input')
                return json.loads(receipt['result_json'])
            row=db.execute('SELECT * FROM tasks WHERE owner=? AND id=?',(owner,task_id)).fetchone()
            current=db.execute('SELECT registration FROM task_execution_bindings WHERE owner=? AND task_id=?',(owner,task_id)).fetchone()
            if not row or not current or current['registration']!=registration:raise PermissionError('Managed plan owner mismatch')
            if row['revision']!=revision:raise ValueError('Plan changed; review again')
            data=json.loads(row['data'])
            if data.get('deleted_at') or data.get('archived_at'):raise ValueError('Plan unavailable')
            data.update(changes);data={**data,**TaskInput.model_validate({k:v for k,v in data.items() if k in TaskInput.model_fields}).model_dump()}
            data['updated_at']=datetime.now(UTC).isoformat()
            due=next_due(data['schedule'],datetime.now(UTC));due=due.isoformat() if due else None
            db.execute('UPDATE tasks SET data=?,revision=revision+1,next_due=? WHERE owner=? AND id=?',(json.dumps(data),due,owner,task_id))
            db.execute('UPDATE task_execution_bindings SET binding_json=? WHERE owner=? AND task_id=?',(json.dumps(binding),owner,task_id))
            result={'task_id':task_id,'title':data['title'],'revision':revision+1,'next_due':due,'active_runs_changed':False}
            db.execute('INSERT INTO execution_plan_receipts VALUES(?,?,?,?)',(owner,request_key,signature,json.dumps(result)))
            return result

    def disable_schedule(self, owner, task_id, revision, request_key):
        """Disable future slots atomically with an idempotent owner receipt.

        Already admitted Runs retain their execution owner and are not cancelled.
        Re-enabling a trusted task requires its owner's separate review.
        """
        with self.connect() as db:
            receipt=db.execute('SELECT * FROM schedule_disable_receipts WHERE owner=? AND request_key=?',(owner,request_key)).fetchone()
            if receipt:
                if receipt['task_id']!=task_id or receipt['expected_revision']!=revision:raise ValueError('Schedule request belongs to different input')
                return json.loads(receipt['result_json'])
            task=self.task(db.execute('SELECT * FROM tasks WHERE owner=? AND id=?',(owner,task_id)).fetchone())
            if task['revision']!=revision:raise ValueError('Task changed; review its schedule again')
            if task.get('deleted_at') or task.get('archived_at'):raise ValueError('Restore this project before changing its schedule')
            if task['schedule']['frequency']=='off':raise ValueError('This task has no active schedule')
            data=json.loads(db.execute('SELECT data FROM tasks WHERE id=?',(task_id,)).fetchone()[0])
            data['schedule']={**data['schedule'],'frequency':'off','once_at':''}
            data['updated_at']=datetime.now(UTC).isoformat()
            db.execute('UPDATE tasks SET data=?,revision=revision+1,next_due=NULL WHERE owner=? AND id=?',(json.dumps(data),owner,task_id))
            result={'task_id':task_id,'title':task['title'],'revision':revision+1,'schedule':data['schedule'],'next_due':None,'active_runs_cancelled':False}
            db.execute('INSERT INTO schedule_disable_receipts VALUES(?,?,?,?,?)',(owner,request_key,task_id,revision,json.dumps(result)))
            return result

    @staticmethod
    def _lane_run_receipt(run_id, status, run_data):
        if not run_id:
            return None
        data = json.loads(run_data)
        error = data.get('error')
        if isinstance(error, dict):
            error = {key: str(error[key])[:300] for key in ('code', 'message') if error.get(key)}
        elif isinstance(error, str) and error:
            error = {'message': error[:300]}
        else:
            error = None
        return {'id': run_id, 'status': status, 'queued': bool(data.get('todo_queued')),
                'started_at': data.get('started_at'), 'finished_at': data.get('finished_at'),
                'error': error, 'message': str(data.get('log') or '')[-1000:]}

    def execution_lane_tasks(self, owner, lane, limit=50):
        """Bounded projection of tasks and their actual execution receipts."""
        with self.connect() as db:
            rows = db.execute("""SELECT t.*, r.id AS run_id,r.status AS run_status,r.data AS run_data,
                f.id AS finished_id,f.status AS finished_status,f.data AS finished_data,
                EXISTS(SELECT 1 FROM task_execution_bindings b WHERE b.owner=t.owner AND b.task_id=t.id) AS managed
                FROM task_execution_lanes l JOIN tasks t ON t.id=l.task_id AND t.owner=l.owner
                LEFT JOIN runs r ON r.id=(SELECT id FROM runs WHERE task_id=t.id AND owner=t.owner ORDER BY rowid DESC LIMIT 1)
                LEFT JOIN runs f ON json_extract(t.data,'$.schedule.frequency') <> 'off'
                    AND r.status NOT IN ('completed','failed','cancelled','interrupted','timed_out')
                    AND f.id=(SELECT id FROM runs WHERE task_id=t.id AND owner=t.owner
                        AND status IN ('completed','failed','cancelled','interrupted','timed_out')
                        ORDER BY rowid DESC LIMIT 1)
                WHERE l.owner=? AND l.lane=? AND json_extract(t.data,'$.deleted_at') IS NULL
                ORDER BY CASE WHEN r.status IN ('running','planning','waiting_input','waiting_capability') THEN 0 WHEN r.status='queued' THEN 1
                    WHEN json_extract(t.data,'$.archived_at') IS NULL AND json_extract(t.data,'$.schedule.frequency') <> 'off' THEN 2 ELSE 3 END,
                    t.rowid DESC LIMIT ?""", (owner, lane, limit + 1)).fetchall()
        items = []
        for row in rows[:limit]:
            task = self.task(row)
            items.append({**{k: task[k] for k in ('id','title','status','progress','next_due','archived_at','updated_at')},
                'scheduled': (task.get('schedule') or {}).get('frequency', 'off') != 'off',
                'managed': bool(row['managed']),
                'run': self._lane_run_receipt(row['run_id'], row['run_status'], row['run_data']),
                'previous_finished_run': self._lane_run_receipt(row['finished_id'], row['finished_status'], row['finished_data'])})
        return {'items': items, 'has_more': len(rows) > limit}

    def activity(self, owner, **options):
        from .activity import query
        with self.connect() as db:
            return query(db, owner, **options)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.root / "todo.sqlite3", timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def task(row):
        if not row:
            raise KeyError("Project not found")
        data = json.loads(row["data"])
        return {
            "status": "completed" if data.get("completed") else "not_started",
            "progress": 100 if data.get("completed") else 0,
            "archived_at": None,
            "deleted_at": None,
            "codex": {},
            "codex_updates": [],
            "priority": "C",
            "highlight": "",
            "emoji": "",
            **json.loads(row["data"]),
            "id": row["id"],
            "revision": row["revision"],
            "next_due": row["next_due"],
            "created_at": row["created_at"],
            "updated_at": data.get("updated_at", row["created_at"]),
            "update_time_estimated": data.get("update_time_estimated", "updated_at" not in data),
        }

    def mobile_list(self, owner, query=""):
        # Do not materialize descriptions, execution payloads or attachment metadata.
        with self.connect() as db:
            directories = [dict(r) for r in db.execute(
                "SELECT d.id,d.title FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid", (owner,))]
            keys = ('directory_id','parent_id','title','emoji','priority','status','progress','highlight','position','updated_at','completed')
            columns = ','.join("json_extract(data, '$.%s') AS %s" % (k,k) for k in keys)
            tasks = []
            for row in db.execute("SELECT id,revision,created_at," + columns + " FROM tasks WHERE owner=? AND json_extract(data,'$.archived_at') IS NULL AND json_extract(data,'$.deleted_at') IS NULL ORDER BY rowid", (owner,)):
                t = dict(row)
                t['status'] = t['status'] or ('completed' if t['completed'] else 'not_started')
                t['progress'] = t['progress'] if t['progress'] is not None else (100 if t['completed'] else 0)
                t['updated_at'] = t['updated_at'] or t['created_at']
                for key, default in [('priority','C'),('emoji',''),('highlight',''),('position',0)]:
                    if t[key] is None: t[key] = default
                tasks.append(t)
            result = {'directories': directories, 'tasks': tasks}
            if query:
                result['search_matches'] = [r['id'] for r in db.execute(
                    "SELECT id FROM tasks WHERE owner=? AND instr(lower(coalesce(json_extract(data,'$.title'),'') || ' ' || coalesce(json_extract(data,'$.description'),'')),lower(?))>0", (owner,query))]
            return result

    def mobile_detail(self, owner, task_id):
        with self.connect() as db:
            task = self.task(db.execute('SELECT * FROM tasks WHERE owner=? AND id=?', (owner,task_id)).fetchone())
            if task.get('archived_at') or task.get('deleted_at'):
                raise KeyError('Project not found')
            attachments = [dict(r) for r in db.execute('SELECT id,task_id,name,size FROM attachments WHERE owner=? AND task_id=?', (owner,task_id))]
            runs = [{**json.loads(r['data']), 'id':r['id'], 'task_id':r['task_id'], 'status':r['status']} for r in db.execute(
                "SELECT * FROM runs WHERE owner=? AND task_id=? AND (status IN ('queued','running','planning','waiting_input','waiting_capability') OR id IN (SELECT id FROM runs WHERE owner=? AND task_id=? ORDER BY rowid DESC LIMIT 200)) ORDER BY rowid DESC", (owner,task_id,owner,task_id))]
            return {'task':task, 'attachments':attachments, 'runs':runs}

    def snapshot(self, owner):
        with self.connect() as db:
            directories = [dict(row) for row in db.execute(
                "SELECT d.id,d.title FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid",
                (owner,))]
            linked = {row["directory_id"]: row["source"] for row in db.execute(
                "SELECT directory_id,source FROM linked_directories WHERE owner=?", (owner,))}
            for directory in directories:
                if directory["id"] in linked:
                    directory["system_source"] = linked[directory["id"]]
            return {
                "directories": directories,
                "tasks": [
                    self.task(r)
                    for r in db.execute(
                        "SELECT * FROM tasks WHERE owner=? ORDER BY rowid", (owner,)
                    )
                ],
                "attachments": [
                    dict(r)
                    for r in db.execute(
                        "SELECT id,task_id,name,size FROM attachments WHERE owner=?",
                        (owner,),
                    )
                ],
                "runs": [
                    {
                        **json.loads(r["data"]),
                        "id": r["id"],
                        "task_id": r["task_id"],
                        "status": r["status"],
                    }
                    for r in db.execute(
                        "SELECT * FROM runs WHERE owner=? AND (status IN ('queued','running','planning','waiting_input','waiting_capability') OR id IN (SELECT id FROM runs WHERE owner=? ORDER BY rowid DESC LIMIT 200)) ORDER BY rowid DESC",
                        (owner, owner),
                    )
                ],
            }

    def list_directories(self, owner):
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT d.id,d.title FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid", (owner,))]

    def directory(self, owner, title):
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Directory name required (up to 200 characters)")
        id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO directories VALUES(?,?,?)", (id, owner, title))
        return {"id": id, "title": title}

    def linked_directory(self, owner, source, title, aliases):
        """Resolve a stable directory for an app, adopting an existing named directory."""
        with self.connect() as db:
            linked = db.execute("""SELECT d.id FROM linked_directories l JOIN directories d
                ON d.id=l.directory_id AND d.owner=l.owner WHERE l.owner=? AND l.source=?""",
                (owner, source)).fetchone()
            if linked:
                return linked["id"]
            names = {normalize_name(name) for name in (title, *aliases)}
            existing = next((row["id"] for row in db.execute(
                "SELECT id,title FROM directories WHERE owner=? ORDER BY rowid", (owner,))
                if normalize_name(row["title"]) in names), None)
            directory_id = existing or uuid.uuid4().hex
            if existing is None:
                db.execute("INSERT INTO directories VALUES(?,?,?)", (directory_id, owner, title))
            db.execute("INSERT OR REPLACE INTO linked_directories VALUES(?,?,?)",
                       (owner, source, directory_id))
            return directory_id

    def open_task_ids(self, owner, ids):
        if not ids:
            return set()
        with self.connect() as db:
            rows = db.execute("""SELECT * FROM tasks WHERE owner=? AND id IN
                (SELECT value FROM json_each(?))""", (owner, json.dumps(list(ids))))
            return {task["id"] for task in map(self.task, rows)
                    if not (task["completed"] or task["archived_at"] or task["deleted_at"])}

    def linked_task(self, owner, request_key, value):
        with self.connect() as db:
            receipt = db.execute("""SELECT t.* FROM task_creation_receipts r JOIN tasks t
                ON t.owner=r.owner AND t.id=r.task_id WHERE r.owner=? AND r.request_key=?""",
                (owner, request_key)).fetchone()
        if receipt:
            return self.task(receipt)
        return self.save(owner, value, creation_key=request_key)

    def complete_linked_task(self, owner, task):
        fields = {key: task[key] for key in TaskInput.model_fields}
        fields["status"] = "completed"
        return self.save(owner, fields, task["id"], task["revision"])

    def rename_directory(self, owner, id, title, expected_title):
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Directory name required (up to 200 characters)")
        with self.connect() as db:
            old = db.execute("SELECT title FROM directories WHERE id=? AND owner=?", (id, owner)).fetchone()
            if old is None:
                raise KeyError("Directory not found")
            if old["title"] != expected_title:
                raise ValueError("Directory changed; refresh before saving")
            db.execute("UPDATE directories SET title=? WHERE id=? AND owner=?", (title, id, owner))
        return {"id": id, "title": title}

    def delete_directory(self, owner, id, confirm_title):
        with self.connect() as db:
            directory = db.execute("SELECT title FROM directories WHERE id=? AND owner=?", (id, owner)).fetchone()
            if directory is None:
                raise KeyError("Directory not found")
            if directory["title"] != confirm_title:
                raise ValueError("Directory name does not match; refresh and confirm again")
            retained = list(db.execute("SELECT id,data FROM tasks WHERE owner=? AND json_extract(data, '$.directory_id')=?", (owner, id)))
            if any(not (json.loads(row["data"]).get("archived_at") or json.loads(row["data"]).get("deleted_at")) for row in retained):
                raise ValueError("Directory still contains active projects")
            if retained:
                # Keep retained trees reachable through the existing directory-scoped views.
                target = db.execute("SELECT id FROM directories WHERE owner=? AND title=? AND id<>? ORDER BY rowid LIMIT 1", (owner, "归档与回收站", id)).fetchone()
                target_id = target["id"] if target else uuid.uuid4().hex
                if target is None:
                    db.execute("INSERT INTO directories VALUES(?,?,?)", (target_id, owner, "归档与回收站"))
                for row in retained:
                    data = json.loads(row["data"])
                    data["directory_id"] = target_id
                    db.execute("UPDATE tasks SET data=?,revision=revision+1 WHERE id=? AND owner=?", (json.dumps(data), row["id"], owner))
            db.execute("DELETE FROM directory_order WHERE owner=? AND directory_id=?", (owner, id))
            db.execute("DELETE FROM directories WHERE owner=? AND id=?", (owner, id))
        return {"ok": True}

    def reorder_directories(self, owner, ids, expected):
        with self.connect() as db:
            current = [row["id"] for row in db.execute("SELECT d.id FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid", (owner,))]
            if current != expected or len(ids) != len(set(ids)) or set(ids) != set(current):
                raise ValueError("Directories changed; refresh before reordering")
            db.executemany("INSERT OR REPLACE INTO directory_order VALUES(?,?,?)", [(owner, id, position) for position, id in enumerate(ids)])

    def save(self, owner, value, id=None, revision=None, *, creation_key=None, create_inbox=False, directory_name=None, execution_binding=None, execution_lane=None):
        if execution_binding is not None:
            if id or not creation_key or not execution_lane or set(execution_binding) != {'registration','binding'}:
                raise ValueError('Trusted execution bindings require idempotent task creation and a lane')
            if not isinstance(execution_binding['registration'],str) or not isinstance(execution_binding['binding'],dict):
                raise ValueError('Invalid execution binding')
        elif execution_lane is not None:
            raise ValueError('Execution lane requires a trusted binding')
        if directory_name is not None:
            directory_name = directory_name.strip()
            if id or create_inbox or not directory_name or len(directory_name) > 200 or not normalize_name(directory_name):
                raise ValueError('New directory requires a valid name and a new task')
        if create_inbox:
            if id: raise ValueError('Inbox fallback is only for new tasks')
            value = {**value, 'directory_id': uuid.uuid5(uuid.NAMESPACE_URL, 'ai2apps.todo.inbox:' + owner).hex}
        data = TaskInput.model_validate(value).model_dump()
        if execution_binding is not None and data["executor"]!="managed":raise ValueError("Trusted execution bindings require the managed executor")
        data["title"] = data["title"].strip()
        if not data["title"]:
            raise ValueError("Title required")
        now = datetime.now(UTC)
        due = next_due(data["schedule"], now)
        with self.connect() as db:
            receipt_input = json.dumps({'task': data, 'directory_name': directory_name} if directory_name else data, sort_keys=True, separators=(',', ':'))
            if execution_binding is not None:
                receipt_input=json.dumps({'task':json.loads(receipt_input),'execution_binding':execution_binding,'lane':execution_lane},sort_keys=True,separators=(',',':'))
            if creation_key:
                if id: raise ValueError('Creation key cannot edit an existing task')
                receipt = db.execute('SELECT * FROM task_creation_receipts WHERE owner=? AND request_key=?', (owner, creation_key)).fetchone()
                if receipt:
                    if receipt['input_json'] != receipt_input: raise ValueError('Creation key belongs to different parameters')
                    return self.task(db.execute('SELECT * FROM tasks WHERE owner=? AND id=?', (owner, receipt['task_id'])).fetchone())
            if directory_name:
                matches = [dict(row) for row in db.execute("SELECT id,title FROM directories WHERE owner=?", (owner,))
                    if normalize_name(row['title']) == normalize_name(directory_name)]
                if len(matches) > 1:
                    raise ValueError('Directory name is ambiguous; select an existing directory')
                if matches:
                    data['directory_id'] = matches[0]['id']
                else:
                    data['directory_id'] = uuid.uuid4().hex
                    db.execute("INSERT INTO directories VALUES(?,?,?)", (data['directory_id'], owner, directory_name))
            if create_inbox:
                db.execute("INSERT OR IGNORE INTO directories VALUES(?,?,?)", (data['directory_id'], owner, '收件箱 / Inbox'))
            if not db.execute(
                "SELECT 1 FROM directories WHERE id=? AND owner=?",
                (data["directory_id"], owner),
            ).fetchone():
                raise KeyError("Directory not found")
            old = None
            if id:
                old = self.task(
                    db.execute(
                        "SELECT * FROM tasks WHERE id=? AND owner=?", (id, owner)
                    ).fetchone()
                )
                if old.get("archived_at") or old.get("deleted_at"):
                    raise ValueError("Restore this project before editing")
                if old["revision"] != revision:
                    raise ValueError("Project changed; refresh before saving")
                if old["schedule"] == data["schedule"]:
                    due = (
                        datetime.fromisoformat(old["next_due"])
                        if old["next_due"]
                        else None
                    )
                if old["directory_id"] != data["directory_id"] and any(
                    json.loads(r["data"]).get("parent_id") == id
                    for r in db.execute(
                        "SELECT data FROM tasks WHERE owner=?", (owner,)
                    )
                ):
                    raise ValueError(
                        "Move child projects first before changing directory"
                    )
            if old:
                for key in ("archived_at", "deleted_at", "archive_batch", "trash_batch"):
                    if key in old:
                        data[key] = old[key]
            data["updated_at"] = now.isoformat()
            normalize_task_state(data, old)
            data["completed_at"] = (
                (old.get("completed_at") if old and old["completed"] else now.isoformat())
                if data["completed"] else None
            )
            parent = data["parent_id"]
            visited = {id} if id else set()
            while parent:
                if parent in visited:
                    raise ValueError("A project cannot contain itself")
                visited.add(parent)
                p = self.task(
                    db.execute(
                        "SELECT * FROM tasks WHERE id=? AND owner=?", (parent, owner)
                    ).fetchone()
                )
                if p.get("archived_at") or p.get("deleted_at"):
                    raise ValueError("Restore the parent project first")
                if p["directory_id"] != data["directory_id"]:
                    raise ValueError("Parent must belong to the same directory")
                parent = p["parent_id"]
            if old and old["directory_id"] == data["directory_id"] and old["parent_id"] == data["parent_id"]:
                # Editing content must never change the manual sibling order.
                data["position"] = old.get("position", 0)
            else:
                siblings = [json.loads(row["data"]) for row in db.execute(
                    "SELECT data FROM tasks WHERE owner=?", (owner,))]
                data["position"] = max((t.get("position", 0) for t in siblings
                    if t.get("directory_id") == data["directory_id"]
                    and t.get("parent_id") == data["parent_id"]), default=-1) + 1
            id = id or uuid.uuid4().hex
            db.execute(
                "INSERT INTO tasks VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,revision=excluded.revision,next_due=excluded.next_due",
                (
                    id,
                    owner,
                    json.dumps(data),
                    (old["revision"] + 1) if old else 1,
                    due.isoformat() if due else None,
                    old["created_at"] if old else now.isoformat(),
                ),
            )
            if execution_binding is not None:
                db.execute('INSERT INTO task_execution_bindings VALUES(?,?,?,?)',(owner,id,execution_binding['registration'],json.dumps(execution_binding['binding'])))
                db.execute('INSERT INTO task_execution_lanes VALUES(?,?,?)',(owner,id,execution_lane))
            if creation_key:
                db.execute('INSERT INTO task_creation_receipts VALUES(?,?,?,?)', (owner, creation_key, receipt_input, id))
            return self.task(
                db.execute("SELECT * FROM tasks WHERE id=?", (id,)).fetchone()
            )

    def get(self, owner, id):
        with self.connect() as db:
            return self.task(
                db.execute(
                    "SELECT * FROM tasks WHERE id=? AND owner=?", (id, owner)
                ).fetchone()
            )

    def reorder(self, owner, directory_id, parent_id, items):
        """Atomically reorder a complete sibling set without changing its parent."""
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM directories WHERE id=? AND owner=?", (directory_id, owner)).fetchone():
                raise KeyError("Directory not found")
            siblings = {}
            for row in db.execute("SELECT * FROM tasks WHERE owner=? ORDER BY rowid", (owner,)):
                task = self.task(row)
                if task["directory_id"] == directory_id and task["parent_id"] == parent_id and not task.get("archived_at") and not task.get("deleted_at"):
                    siblings[task["id"]] = task
            ids = [item["id"] for item in items]
            if len(ids) != len(set(ids)) or set(ids) != set(siblings):
                raise ValueError("Sibling projects changed; refresh before reordering")
            if any(item["revision"] != siblings[item["id"]]["revision"] for item in items):
                raise ValueError("Project changed; refresh before reordering")
            for position, id in enumerate(ids):
                task = siblings[id]
                if task["position"] == position:
                    continue
                data = TaskInput.model_validate({key: task[key] for key in TaskInput.model_fields}).model_dump()
                data["completed_at"] = task.get("completed_at")
                data["position"] = position
                data["updated_at"] = now_text()
                db.execute("UPDATE tasks SET data=?,revision=revision+1 WHERE id=? AND owner=?", (json.dumps(data), id, owner))

    def recent_emojis(self, owner, id):
        self.get(owner, id)
        with self.connect() as db:
            row = db.execute("SELECT data FROM emoji_history WHERE owner=? AND task_id=?", (owner, id)).fetchone()
            return json.loads(row["data"]) if row else []

    def remember_emoji(self, owner, id, emoji):
        # Recheck inside the transaction: concurrent suggestions must not repeat.
        with self.connect() as db:
            task = self.task(db.execute("SELECT * FROM tasks WHERE owner=? AND id=?", (owner, id)).fetchone())
            row = db.execute("SELECT data FROM emoji_history WHERE owner=? AND task_id=?", (owner, id)).fetchone()
            history = json.loads(row["data"]) if row else []
            if emoji_key(emoji) in {emoji_key(x) for x in [task.get("emoji", ""), *history]}:
                return False
            db.execute("INSERT OR REPLACE INTO emoji_history VALUES(?,?,?)", (owner, id, json.dumps([*history, emoji][-5:])))
            return True

    def delete(self, owner, id):
        return self.lifecycle(owner, id, "trash")

    def lifecycle(self, owner, id, action):
        if action not in {"archive", "trash", "restore"}:
            raise ValueError("Unknown lifecycle action")
        with self.connect() as db:
            tasks = {row["id"]: self.task(row) for row in db.execute("SELECT * FROM tasks WHERE owner=?", (owner,))}
            if id not in tasks:
                raise KeyError("Project not found")
            root = tasks[id]
            ids = {id}
            while True:
                children = {t["id"] for t in tasks.values() if t["parent_id"] in ids}
                if children <= ids:
                    break
                ids |= children
            if action == "restore":
                if not root.get("archived_at") and not root.get("deleted_at"):
                    return
                parent = tasks.get(root["parent_id"])
                if parent and (parent.get("archived_at") or parent.get("deleted_at")):
                    raise ValueError("Restore the parent project first")
                key = "trash_batch" if root.get("deleted_at") else "archive_batch"
                batch = root.get(key)
                ids = {key_id for key_id in ids if key_id == id or batch and tasks[key_id].get(key) == batch}
            else:
                if root.get("deleted_at"):
                    raise ValueError("Restore this project first")
                ids = {key_id for key_id in ids if not tasks[key_id].get("deleted_at") and (action == "trash" or not tasks[key_id].get("archived_at"))}
            active_ids = {row["task_id"] for row in db.execute("SELECT task_id FROM runs WHERE owner=? AND status IN ('queued','running','planning','waiting_input','waiting_capability')", (owner,))}
            if ids & active_ids:
                raise ValueError("Stop active project runs before archiving or deleting")
            now = datetime.now(UTC)
            batch = uuid.uuid4().hex
            for task_id in ids:
                task = tasks[task_id]
                data = {k: v for k, v in task.items() if k not in {"id", "revision", "next_due", "created_at"}}
                if action == "archive":
                    data.update(archived_at=now.isoformat(), archive_batch=batch)
                elif action == "trash":
                    data.update(deleted_at=now.isoformat(), trash_batch=batch)
                elif root.get("deleted_at"):
                    data["deleted_at"] = None
                    data.pop("trash_batch", None)
                else:
                    data["archived_at"] = None
                    data.pop("archive_batch", None)
                data["updated_at"] = now.isoformat()
                data["update_time_estimated"] = False
                managed=db.execute('SELECT 1 FROM task_execution_bindings WHERE owner=? AND task_id=?',(owner,task_id)).fetchone()
                due = None if managed or data.get("archived_at") or data.get("deleted_at") else next_due(data["schedule"], now)
                db.execute("UPDATE tasks SET data=?,revision=revision+1,next_due=? WHERE owner=? AND id=?", (json.dumps(data), due.isoformat() if due else None, owner, task_id))

    def add_attachment(self, owner, task_id, name, content):
        id = uuid.uuid4().hex
        path = self.root / "attachments" / id
        path.parent.mkdir(exist_ok=True)
        with self.connect() as db:
            task = self.task(db.execute("SELECT * FROM tasks WHERE id=? AND owner=?", (task_id, owner)).fetchone())
            if task.get("archived_at") or task.get("deleted_at"):
                raise ValueError("Restore this project before adding attachments")
            path.write_bytes(content)
            db.execute(
                "INSERT INTO attachments VALUES(?,?,?,?,?)",
                (id, owner, task_id, Path(name).name[:255], len(content)),
            )
            self._touch(db, owner, task_id)
        return {"id": id}

    @staticmethod
    def _touch(db, owner, task_id):
        row = db.execute("SELECT data FROM tasks WHERE id=? AND owner=?", (task_id, owner)).fetchone()
        data = json.loads(row["data"])
        data.update(updated_at=now_text(), update_time_estimated=False)
        db.execute("UPDATE tasks SET data=?,revision=revision+1 WHERE id=? AND owner=?", (json.dumps(data), task_id, owner))

    def attachment(self, owner, id):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM attachments WHERE id=? AND owner=?", (id, owner)
            ).fetchone()
            if not row:
                raise KeyError("Attachment not found")
            return dict(row), self.root / "attachments" / row["id"]

    def remove_attachment(self, owner, id):
        attachment, _ = self.attachment(owner, id)
        task = self.get(owner, attachment["task_id"])
        if task.get("archived_at") or task.get("deleted_at"):
            raise ValueError("Restore this project before removing attachments")
        # Retain immutable blob for existing run snapshots.
        with self.connect() as db:
            db.execute("DELETE FROM attachments WHERE id=? AND owner=?", (id, owner))
            self._touch(db, owner, attachment["task_id"])

    def review_run(self, owner, id, decision, revision):
        if decision not in ("completed", "continue"):
            raise ValueError("Invalid review decision")
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=? AND owner=?", (id, owner)).fetchone()
            if not row:
                raise KeyError("Run not found")
            data = json.loads(row["data"])
            if data.get("review"):
                if data["review"]["decision"] != decision:
                    raise ValueError("Run was already reviewed")
                return data["review"]
            if row["status"] != "ended":
                raise ValueError("Only ended runs can be reviewed")
            latest = db.execute("SELECT id FROM runs WHERE owner=? AND task_id=? ORDER BY rowid DESC LIMIT 1", (owner, row["task_id"])).fetchone()
            if latest["id"] != id:
                raise ValueError("Review the latest execution instead")
            task = self.task(db.execute("SELECT * FROM tasks WHERE id=? AND owner=?", (row["task_id"], owner)).fetchone())
            if task["revision"] != revision:
                raise ValueError("Project changed; refresh before reviewing")
            if task.get("archived_at") or task.get("deleted_at"):
                raise ValueError("Restore the project before reviewing")
            now = now_text()
            updated = {**task}
            if decision == "completed":
                updated.update(status="completed", progress=100, completed=True,
                               completed_at=task.get("completed_at") or now)
            else:
                updated.update(status="in_progress", completed=False, completed_at=None,
                               progress=0 if task["progress"] == 100 else task["progress"])
            updated.update(updated_at=now, update_time_estimated=False)
            data["review"] = {"decision": decision, "reviewed_at": now, "reviewed_by": owner}
            db.execute("UPDATE tasks SET data=?,revision=revision+1 WHERE id=? AND owner=?", (json.dumps(updated), task["id"], owner))
            db.execute("UPDATE runs SET data=? WHERE id=? AND owner=?", (json.dumps(data), id, owner))
            return data["review"]

    def run_update(self, id, status, **values):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (id,)).fetchone()
            if row:
                data = {**json.loads(row["data"]), **values}
                db.execute(
                    "UPDATE runs SET status=?,data=? WHERE id=?",
                    (status, json.dumps(data), id),
                )
