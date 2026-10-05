"""Portable owner-scoped Todo backups; path-based, transactional merge."""
import hashlib
import io
import json
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from .models import TaskInput, next_due
from .store import now_text

MAX_BYTES = 512 * 1024 * 1024
MAX_FILE = 32 * 1024 * 1024
ACTIVE = ('queued', 'running', 'planning', 'waiting_input', 'waiting_capability')


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(UTC)
    except (TypeError, ValueError):
        raise ValueError('Invalid backup timestamp') from None


def read_state(store, db, owner):
    directories = [dict(r) for r in db.execute('SELECT d.id,d.title FROM directories d LEFT JOIN directory_order o ON d.id=o.directory_id AND o.owner=d.owner WHERE d.owner=? ORDER BY COALESCE(o.position,2147483647),d.rowid', (owner,))]
    tasks = [store.task(r) for r in db.execute('SELECT * FROM tasks WHERE owner=? ORDER BY rowid', (owner,))]
    attachments = [dict(r) for r in db.execute('SELECT id,task_id,name,size FROM attachments WHERE owner=? ORDER BY id', (owner,))]
    return directories, tasks, attachments


def paths(directories, tasks):
    dirs = {}
    for d in directories:
        if not isinstance(d.get('title'), str) or not d['title'].strip() or len(d['title']) > 200 or d['id'] in dirs:
            raise ValueError('Invalid or duplicated directory')
        dirs[d['id']] = d['title']
    if len(set(dirs.values())) != len(dirs):
        raise ValueError('存在同名目录，无法按路径合并，请先重命名。')
    by_id = {t['id']: t for t in tasks}
    if len(by_id) != len(tasks):
        raise ValueError('Duplicate project IDs')
    result = {}
    for t in tasks:
        chain = []
        seen = set()
        current = t
        while current['id'] not in result:
            if current['id'] in seen or current['directory_id'] not in dirs:
                raise ValueError('Invalid project hierarchy')
            if len(seen) >= 256:
                raise ValueError('Project hierarchy exceeds 256 levels')
            seen.add(current['id'])
            chain.append(current)
            parent = current.get('parent_id')
            if not parent:
                base = (dirs[current['directory_id']],)
                break
            if parent not in by_id or by_id[parent]['directory_id'] != t['directory_id']:
                raise ValueError('Invalid project parent')
            current = by_id[parent]
        else:
            base = result[current['id']]
        for node in reversed(chain):
            base = (*base, node['title'])
            result[node['id']] = base
    if len(set(result.values())) != len(result):
        raise ValueError('存在同一路径下的同名项目，无法判断合并对象，请先重命名。')
    return result


def export_backup(store, owner, directory_id=None):
    output = io.BytesIO()
    with store.connect() as db, zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        directories, tasks, attachments = read_state(store, db, owner)
        if directory_id is not None:
            directories = [d for d in directories if d['id'] == directory_id]
            if not directories:
                raise KeyError('Directory not found')
            tasks = [t for t in tasks if t['directory_id'] == directory_id]
        task_ids = {t['id'] for t in tasks}
        attachments = [a for a in attachments if a['task_id'] in task_ids]
        total = 0
        for a in attachments:
            try:
                payload = (store.root / 'attachments' / a['id']).read_bytes()
            except OSError as error:
                raise ValueError('Attachment file missing or unreadable; backup was not created') from error
            total += len(payload)
            if total > MAX_BYTES:
                raise ValueError('Backup attachments exceed 512 MiB')
            a['file'] = 'attachments/' + a['id']
            a['sha256'] = hashlib.sha256(payload).hexdigest()
            archive.writestr(a['file'], payload)
        # History is inert text; live agents, terminal IDs and session artifacts do not migrate.
        runs = []
        for row in db.execute('SELECT * FROM runs WHERE owner=? ORDER BY rowid', (owner,)):
            if row['task_id'] not in task_ids:
                continue
            data = json.loads(row['data'])
            history = {k: data[k] for k in ('started_at', 'queued_at', 'finished_at', 'scheduled_at', 'output', 'log', 'error', 'exit_code') if k in data}
            runs.append({'source_id': data.get('import_source_id', row['id']), 'task_id': row['task_id'], 'status': row['status'], 'data': history})
        manifest = {'format': 'ai2apps.todo.backup', 'version': 1, 'exported_at': now_text(), 'directories': directories, 'tasks': tasks, 'attachments': attachments, 'runs': runs}
        raw = json.dumps(manifest, ensure_ascii=False).encode()
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError('Backup metadata exceeds 64 MiB')
        if total + len(raw) > MAX_BYTES:
            raise ValueError('Backup exceeds 512 MiB')
        archive.writestr('todo.json', raw)
    if output.tell() > MAX_BYTES:
        raise ValueError('Backup exceeds 512 MiB')
    return output.getvalue()


def parse_backup(content):
    try:
        if len(content) > MAX_BYTES:
            raise ValueError('Backup exceeds 512 MiB')
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 100001 or len({x.filename for x in entries}) != len(entries) or sum(x.file_size for x in entries) > MAX_BYTES:
                raise ValueError('Backup exceeds limits or has duplicate entries')
            if archive.getinfo('todo.json').file_size > 64 * 1024 * 1024:
                raise ValueError('Backup metadata exceeds 64 MiB')
            data = json.loads(archive.read('todo.json'))
            if data.get('format') != 'ai2apps.todo.backup' or data.get('version') != 1:
                raise ValueError('Unsupported Todo backup version')
            tasks = data['tasks']
            if len(tasks) > 100000:
                raise ValueError('Too many projects')
            paths(data['directories'], tasks)
            for task in tasks:
                clean = TaskInput.model_validate({k: task[k] for k in TaskInput.model_fields if k in task}).model_dump()
                if not clean['title'].strip() or clean['completed'] != (clean['status'] == 'completed') or (clean['completed'] and clean['progress'] != 100):
                    raise ValueError('Invalid project state')
                task.update(clean)
                timestamp(task['created_at'])
                timestamp(task['updated_at'])
                for key in ('archived_at', 'deleted_at', 'completed_at'):
                    if task.get(key):
                        timestamp(task[key])
            ids = {t['id'] for t in tasks}
            blobs = {}
            seen = set()
            for a in data['attachments']:
                if a['id'] in seen or a['task_id'] not in ids or not isinstance(a['name'], str) or not a['name'] or len(a['name']) > 255:
                    raise ValueError('Invalid attachment')
                seen.add(a['id'])
                if archive.getinfo(a['file']).file_size > MAX_FILE:
                    raise ValueError('Attachment exceeds 32 MiB')
                payload = archive.read(a['file'])  # Read by member name; never extract paths.
                if len(payload) != a['size'] or hashlib.sha256(payload).hexdigest() != a['sha256']:
                    raise ValueError('Attachment integrity check failed')
                blobs[a['id']] = payload
            for run in data.get('runs', []):
                if run['task_id'] not in ids or not isinstance(run['source_id'], str) or not isinstance(run['data'], dict) or run['status'] not in (*ACTIVE, 'completed', 'failed', 'cancelled', 'interrupted', 'skipped', 'ended'):
                    raise ValueError('Invalid run history')
            return data, blobs
    except (KeyError, TypeError, AttributeError, OverflowError, zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, RuntimeError) as error:
        raise ValueError('Invalid Todo backup') from error


def merge_backup(store, owner, content, expected=None):
    backup, blobs = parse_backup(content)
    written = []
    try:
        with store.connect() as db:
            directories, tasks, attachments = read_state(store, db, owner)
            if db.execute("SELECT 1 FROM runs WHERE owner=? AND status IN ('queued','running','planning','waiting_input','waiting_capability')", (owner,)).fetchone():
                raise ValueError('请先停止当前账号正在执行或排队的任务，再导入。')
            fingerprint = hashlib.sha256(json.dumps([directories, tasks, attachments], sort_keys=True).encode()).hexdigest()
            if expected is not None and expected != fingerprint:
                raise ValueError('预览后本地数据已变化，请重新预览。')
            local_paths = paths(directories, tasks)
            incoming_paths = paths(backup['directories'], backup['tasks'])
            local = {local_paths[t['id']]: t for t in tasks}
            mapped_dirs = {d['title']: d['id'] for d in directories}
            dir_ids = {d['id']: mapped_dirs.get(d['title'], uuid.uuid4().hex) for d in backup['directories']}
            actions = []
            mapping = {}
            winners = []
            estimated = 0
            for t in sorted(backup['tasks'], key=lambda t: len(incoming_paths[t['id']])):
                path = incoming_paths[t['id']]
                old = local.get(path)
                mapping[t['id']] = old['id'] if old else uuid.uuid4().hex
                action = 'create' if not old else 'update' if timestamp(t['updated_at']) > timestamp(old['updated_at']) else 'keep'
                estimated += bool(t.get('update_time_estimated') or old and old.get('update_time_estimated'))
                actions.append({'path': list(path), 'action': action, 'incoming_updated_at': t['updated_at'], 'local_updated_at': old['updated_at'] if old else None})
                if action != 'keep':
                    winners.append((t, old))
            result = {'expected': fingerprint, 'create': sum(a['action']=='create' for a in actions), 'update': sum(a['action']=='update' for a in actions), 'keep': sum(a['action']=='keep' for a in actions), 'estimated_times': estimated, 'new_directories': sum(d['title'] not in mapped_dirs for d in backup['directories']), 'items': actions}
            if expected is None:
                return result
            for i, d in enumerate(backup['directories']):
                if d['title'] not in mapped_dirs:
                    db.execute('INSERT INTO directories VALUES(?,?,?)', (dir_ids[d['id']], owner, d['title']))
                    db.execute('INSERT INTO directory_order VALUES(?,?,?)', (owner, dir_ids[d['id']], len(directories)+i))
            now = datetime.now(UTC)
            winner_ids = {t['id'] for t, _ in winners}
            for t, old in winners:
                task_id = mapping[t['id']]
                payload = {k: t[k] for k in TaskInput.model_fields}
                payload.update({k: t[k] for k in ('updated_at', 'update_time_estimated', 'archived_at', 'deleted_at', 'completed_at', 'archive_batch', 'trash_batch') if k in t})
                payload['directory_id'] = dir_ids[t['directory_id']]
                payload['parent_id'] = mapping.get(t['parent_id'])
                due = None if payload.get('archived_at') or payload.get('deleted_at') else next_due(payload['schedule'], now)
                db.execute('INSERT OR REPLACE INTO tasks VALUES(?,?,?,?,?,?)', (task_id, owner, json.dumps(payload), old['revision']+1 if old else 1, due.isoformat() if due else None, t['created_at']))
                db.execute('DELETE FROM attachments WHERE owner=? AND task_id=?', (owner, task_id))
            # Immutable old blobs remain available to existing execution snapshots.
            for a in backup['attachments']:
                if a['task_id'] not in winner_ids:
                    continue
                aid = uuid.uuid4().hex
                dest = store.root / 'attachments' / aid
                dest.parent.mkdir(exist_ok=True)
                written.append(dest)
                dest.write_bytes(blobs[a['id']])
                db.execute('INSERT INTO attachments VALUES(?,?,?,?,?)', (aid, owner, mapping[a['task_id']], Path(a['name']).name, a['size']))
            for run in backup.get('runs', []):
                if db.execute('SELECT 1 FROM runs WHERE owner=? AND id=?', (owner, run['source_id'])).fetchone():
                    continue
                data = {k: run['data'][k] for k in ('started_at', 'queued_at', 'finished_at', 'scheduled_at', 'output', 'log', 'error', 'exit_code') if k in run['data']}
                rid = uuid.uuid5(uuid.NAMESPACE_URL, f"todo-import:{owner}:{run['source_id']}").hex
                data.update(import_source_id=run['source_id'], imported=True)
                status = run['status']
                if status in ACTIVE:
                    status = 'interrupted'
                    data.update(error='Imported history only; live execution was not migrated.', finished_at=now.isoformat())
                db.execute('INSERT OR IGNORE INTO runs VALUES(?,?,?,?,?)', (rid, owner, mapping[run['task_id']], status, json.dumps(data)))
            return result
    except BaseException:
        for file in written:
            file.unlink(missing_ok=True)
        raise
