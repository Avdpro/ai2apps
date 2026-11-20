import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            for table in ('social_drafts', 'social_posts'):
                db.execute(f'CREATE TABLE IF NOT EXISTS {table}(owner TEXT,id TEXT,data TEXT,PRIMARY KEY(owner,id))')
            db.execute('CREATE TABLE IF NOT EXISTS preferences(owner TEXT,id TEXT,data TEXT,PRIMARY KEY(owner,id))')
            db.execute('CREATE TABLE IF NOT EXISTS snapshots(owner TEXT,id TEXT,data TEXT,PRIMARY KEY(owner,id))')
            db.execute('CREATE TABLE IF NOT EXISTS publications(owner TEXT,request_id TEXT,data TEXT,PRIMARY KEY(owner,request_id))')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.root/'share.sqlite3',timeout=10)
        try:
            db.execute('BEGIN IMMEDIATE');yield db;db.commit()
        except BaseException:db.rollback();raise
        finally:db.close()
    def path(self,owner,id):
        if len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise ValueError('Invalid snapshot')
        return self.root/'files'/hashlib.sha256(owner.encode()).hexdigest()/id
    def get(self,table,owner,id):
        assert table in ('snapshots','publications','preferences','social_drafts','social_posts')
        key='request_id' if table=='publications' else 'id'
        with self.connect() as db:row=db.execute(f'SELECT data FROM {table} WHERE owner=? AND {key}=?',(owner,id)).fetchone()
        if row is None:raise KeyError('Share record not found')
        return json.loads(row[0])
    def save(self,table,owner,id,value):
        assert table in ('snapshots','publications','preferences','social_drafts','social_posts')
        with self.connect() as db:db.execute(f'INSERT INTO {table} VALUES (?,?,?) ON CONFLICT DO UPDATE SET data=excluded.data',(owner,id,json.dumps(value)))
    def recent(self,owner):
        with self.connect() as db:rows=db.execute('SELECT data FROM publications WHERE owner=? ORDER BY rowid DESC LIMIT 30',(owner,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def latest_target(self,owner,provider):
        with self.connect() as db:
            rows=db.execute('SELECT data FROM snapshots WHERE owner=? ORDER BY rowid DESC',(owner,)).fetchall()
        return next((x for row in rows if (x:=json.loads(row[0])).get('provider')==provider),{})

    def recent_social(self, owner):
        with self.connect() as db:
            rows = db.execute('SELECT data FROM social_drafts WHERE owner=? ORDER BY rowid DESC LIMIT 30',
                              (owner,)).fetchall()
        return [json.loads(row[0]) for row in rows]
