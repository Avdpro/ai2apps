import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .models import TaskInput, emoji_key, next_due, normalize_task_state


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
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, owner TEXT NOT NULL, data TEXT NOT NULL, revision INTEGER NOT NULL, next_due TEXT, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS task_owner ON tasks(owner);
                CREATE TABLE IF NOT EXISTS attachments(id TEXT PRIMARY KEY, owner TEXT NOT NULL, task_id TEXT NOT NULL, name TEXT NOT NULL, size INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, owner TEXT NOT NULL, task_id TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS run_owner ON runs(owner,task_id);
            """)

        from .activity import install
        with self.connect() as db:
            install(db)

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

    def snapshot(self, owner):
        with self.connect() as db:
            return {
                "directories": [
                    dict(r)
                    for r in db.execute(
                        "SELECT d.id,d.title FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid",
                        (owner,),
                    )
                ],
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

    def directory(self, owner, title):
        title = title.strip()
        if not title or len(title) > 200:
            raise ValueError("Directory name required (up to 200 characters)")
        id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO directories VALUES(?,?,?)", (id, owner, title))
        return {"id": id, "title": title}

    def reorder_directories(self, owner, ids, expected):
        with self.connect() as db:
            current = [row["id"] for row in db.execute("SELECT d.id FROM directories d LEFT JOIN directory_order o ON o.directory_id=d.id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid", (owner,))]
            if current != expected or len(ids) != len(set(ids)) or set(ids) != set(current):
                raise ValueError("Directories changed; refresh before reordering")
            db.executemany("INSERT OR REPLACE INTO directory_order VALUES(?,?,?)", [(owner, id, position) for position, id in enumerate(ids)])

    def save(self, owner, value, id=None, revision=None):
        data = TaskInput.model_validate(value).model_dump()
        data["title"] = data["title"].strip()
        if not data["title"]:
            raise ValueError("Title required")
        now = datetime.now(UTC)
        due = next_due(data["schedule"], now)
        with self.connect() as db:
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
                due = None if data.get("archived_at") or data.get("deleted_at") else next_due(data["schedule"], now)
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
