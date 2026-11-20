"""Owner-scoped project snapshots, immutable versions and durable outputs."""
import json

from ai2apps.core import utc_now_text
from ai2apps.storage.records import canonical_json
from ai2apps.system_tasks.service import TERMINAL

from .models import APP_ID


def _one(db, sql, params):
    row = db.execute(sql, params).fetchone()
    if row is None:
        raise KeyError('Doc Studio record unavailable')
    return row


def _may_publish(db, owner, task_id):
    if task_id is None:
        return True
    return db.execute(
        "SELECT 1 FROM system_tasks WHERE owner=? AND id=? AND app_id=? AND status='running'",
        (owner, task_id, APP_ID),
    ).fetchone() is not None


class Repository:
    def __init__(self, database):
        self.database = database

    def save_pack(self, owner, manifest):
        pack_id = manifest['pack_key'][:32] + manifest['version'][:32]
        with self.database.transaction(write=True) as db:
            db.execute('INSERT OR IGNORE INTO doc_studio_packs VALUES (?,?,?)',
                       (owner, pack_id, canonical_json(manifest)))
        return self.pack(owner, pack_id)

    def pack(self, owner, pack_id):
        with self.database.transaction() as db:
            row = _one(db, 'SELECT manifest FROM doc_studio_packs WHERE owner=? AND id=?', (owner, pack_id))
        return {'id': pack_id, **json.loads(row['manifest'])}

    def projects(self, owner):
        with self.database.transaction() as db:
            return [dict(row) for row in db.execute(
                'SELECT id,title,created_at FROM doc_studio_projects WHERE owner=? AND deleted_at IS NULL ORDER BY created_at DESC,id',
                (owner,))]

    @staticmethod
    def _project(db, owner, project_id):
        return _one(db, 'SELECT id,title,created_at FROM doc_studio_projects WHERE owner=? AND id=? AND deleted_at IS NULL',
                    (owner, project_id))

    def project(self, owner, project_id):
        with self.database.transaction() as db:
            return dict(self._project(db, owner, project_id))

    def create_project(self, owner, project_id, title):
        with self.database.transaction(write=True) as db:
            if not db.execute(
                'INSERT OR IGNORE INTO doc_studio_projects(owner,id,title,created_at) VALUES (?,?,?,?)',
                (owner, project_id, title, utc_now_text()),
            ).rowcount:
                project = self._project(db, owner, project_id)
                if project['title'] != title:
                    raise ValueError('Project request ID already used with a different title')
            return dict(self._project(db, owner, project_id))

    def rename_project(self, owner, project_id, title):
        with self.database.transaction(write=True) as db:
            self._project(db, owner, project_id)
            db.execute('UPDATE doc_studio_projects SET title=? WHERE owner=? AND id=?',
                       (title, owner, project_id))
            return dict(self._project(db, owner, project_id))

    def delete_project(self, owner, project_id):
        with self.database.transaction(write=True) as db:
            project = _one(db, 'SELECT deleted_at FROM doc_studio_projects WHERE owner=? AND id=?',
                           (owner, project_id))
            if project['deleted_at'] is not None:
                return
            terminal = ','.join('?' for _ in TERMINAL)
            if db.execute(f"""SELECT 1 FROM system_tasks
                WHERE owner=? AND app_id=? AND json_extract(payload_json,'$.project_id')=?
                AND status NOT IN ({terminal}) LIMIT 1""", (owner, APP_ID, project_id, *TERMINAL)).fetchone():
                raise ValueError('工程仍有进行中的任务，请先等待完成或取消。 / Wait for or cancel the active project tasks.')
            for table in ('imports', 'import_items', 'materials', 'images', 'versions', 'outputs'):
                db.execute(f'DELETE FROM doc_studio_{table} WHERE owner=? AND project_id=?', (owner, project_id))
            # Retain only the empty identifier so retrying an old create cannot revive it.
            db.execute("UPDATE doc_studio_projects SET deleted_at=?,title='' WHERE owner=? AND id=?",
                       (utc_now_text(), owner, project_id))

    def imported(self, owner, project_id, pack_id):
        with self.database.transaction() as db:
            return db.execute('SELECT 1 FROM doc_studio_imports WHERE owner=? AND project_id=? AND pack_id=?',
                              (owner, project_id, pack_id)).fetchone() is not None

    def import_pack(self, owner, project_id, title, pack_id, materials, images, *, task_id):
        with self.database.transaction(write=True) as db:
            if not _may_publish(db, owner, task_id):
                return
            if title is not None:
                db.execute('INSERT OR IGNORE INTO doc_studio_projects(owner,id,title,created_at) VALUES (?,?,?,?)',
                           (owner, project_id, title, utc_now_text()))
            self._project(db, owner, project_id)
            if not db.execute('INSERT OR IGNORE INTO doc_studio_imports VALUES (?,?,?,?)',
                              (owner, project_id, pack_id, utc_now_text())).rowcount:
                return
            for material in materials:
                db.execute('INSERT OR IGNORE INTO doc_studio_materials VALUES (?,?,?,?,?)',
                           (owner, project_id, material['id'], material['source_id'], canonical_json(material)))
                db.execute('INSERT INTO doc_studio_import_items VALUES (?,?,?,?)',
                           (owner, project_id, pack_id, material['id']))
            for asset_id, (data, mime) in images.items():
                db.execute('INSERT OR IGNORE INTO doc_studio_images VALUES (?,?,?,?,?)',
                           (owner, project_id, asset_id, mime, data))

    def materials(self, owner, project_id):
        with self.database.transaction() as db:
            self._project(db, owner, project_id)
            rows = db.execute('''SELECT m.data,i.pack_id FROM doc_studio_imports AS p
                JOIN doc_studio_import_items AS i USING(owner,project_id,pack_id)
                JOIN doc_studio_materials AS m ON m.owner=i.owner AND m.project_id=i.project_id AND m.id=i.material_id
                WHERE p.owner=? AND p.project_id=? ORDER BY p.rowid DESC,i.rowid''', (owner, project_id))
            materials, active = {}, set()
            for row in rows:
                item = json.loads(row['data'])
                if item['id'] not in materials:
                    item['pack_ids'] = []
                    item['active'] = item['source_id'] not in active
                    active.add(item['source_id'])
                    materials[item['id']] = item
                materials[item['id']]['pack_ids'].append(row['pack_id'])
            return list(materials.values())

    def image(self, owner, project_id, asset_id):
        with self.database.transaction() as db:
            row = _one(db, '''SELECT data,mime FROM doc_studio_images
                WHERE owner=? AND project_id=? AND id=?''', (owner, project_id, asset_id))
        return row['data'], row['mime']

    def image_sizes(self, owner, project_id, asset_ids):
        if not asset_ids:
            return {}
        with self.database.transaction() as db:
            placeholders = ','.join('?' for _ in asset_ids)
            return dict(db.execute(
                f'SELECT id,length(data) FROM doc_studio_images WHERE owner=? AND project_id=? AND id IN ({placeholders})',
                (owner, project_id, *asset_ids),
            ).fetchall())

    def store_image(self, owner, project_id, asset_id, data, mime):
        with self.database.transaction(write=True) as db:
            self._project(db, owner, project_id)
            db.execute('INSERT OR IGNORE INTO doc_studio_images VALUES (?,?,?,?,?)',
                       (owner, project_id, asset_id, mime, data))

    def versions(self, owner, project_id):
        with self.database.transaction() as db:
            rows = db.execute('''SELECT id,created_at,json_extract(data,'$.title') AS title,
                json_extract(data,'$.target') AS target FROM doc_studio_versions
                WHERE owner=? AND project_id=? ORDER BY rowid DESC''', (owner, project_id))
            return [dict(row) for row in rows]

    def version(self, owner, project_id, version_id):
        with self.database.transaction() as db:
            row = _one(db, 'SELECT * FROM doc_studio_versions WHERE owner=? AND project_id=? AND id=?',
                       (owner, project_id, version_id))
        return {'id': row['id'], 'created_at': row['created_at'], **json.loads(row['data'])}

    def save_version(self, owner, project_id, version_id, data, *, request=None, task_id=None):
        with self.database.transaction(write=True) as db:
            if not _may_publish(db, owner, task_id):
                return None
            self._project(db, owner, project_id)
            row = db.execute('SELECT data FROM doc_studio_versions WHERE owner=? AND project_id=? AND id=?',
                             (owner, project_id, version_id)).fetchone()
            if row is None:
                db.execute('INSERT INTO doc_studio_versions VALUES (?,?,?,?,?)',
                           (owner, project_id, version_id, utc_now_text(), canonical_json(data)))
            elif request is not None and json.loads(row['data']).get('request') != request:
                raise ValueError('Edit request ID already used with different content')
        return self.version(owner, project_id, version_id)

    def tasks(self, owner, project_id):
        with self.database.transaction() as db:
            rows = db.execute('''SELECT id,kind,status,message,result_json,progress_json FROM system_tasks
                WHERE owner=? AND app_id=? AND json_extract(payload_json,'$.project_id')=?
                ORDER BY created_at DESC LIMIT 25''', (owner, APP_ID, project_id))
            items = [dict(row) for row in rows]
            for item in items:
                item['result'] = json.loads(item.pop('result_json'))
                item['progress'] = json.loads(item.pop('progress_json'))
            return items

    def save_output(self, owner, project_id, output_id, metadata, data):
        with self.database.transaction(write=True) as db:
            if not _may_publish(db, owner, output_id):
                return
            self._project(db, owner, project_id)
            db.execute('INSERT OR IGNORE INTO doc_studio_outputs VALUES (?,?,?,?,?,?)',
                       (owner, project_id, output_id, utc_now_text(), canonical_json(metadata), data))

    def outputs(self, owner, project_id):
        with self.database.transaction() as db:
            rows = db.execute('''SELECT id,created_at,metadata FROM doc_studio_outputs
                WHERE owner=? AND project_id=? ORDER BY rowid DESC''', (owner, project_id))
            return [{'id': row['id'], 'created_at': row['created_at'], **json.loads(row['metadata'])} for row in rows]

    def output(self, owner, project_id, output_id):
        with self.database.transaction() as db:
            row = _one(db, 'SELECT metadata,data FROM doc_studio_outputs WHERE owner=? AND project_id=? AND id=?',
                       (owner, project_id, output_id))
        return json.loads(row['metadata']), row['data']

