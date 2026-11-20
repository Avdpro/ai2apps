"""User-owned sidebar groups; grouping never changes Bot authority."""
import logging
import json
from uuid import uuid4
from contextlib import nullcontext

QUICK='quick'


class BotGroups:
    def __init__(self,directory):
        logging.getLogger(__name__).info("Messager Bot grouping loaded; source=%s",__file__)
        self.directory,self.db=directory,directory.db
        with self.db.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_groups(actor TEXT NOT NULL,id TEXT NOT NULL,name TEXT NOT NULL,collapsed INTEGER NOT NULL DEFAULT 0,revision INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(actor,id))')
            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_group_members(actor TEXT NOT NULL,bot_id TEXT NOT NULL,group_id TEXT,PRIMARY KEY(actor,bot_id))')

            db.execute('CREATE TABLE IF NOT EXISTS messager_bot_group_order(actor TEXT PRIMARY KEY,ids TEXT NOT NULL)')

    def ensure(self,db,actor):
        db.execute('INSERT OR IGNORE INTO messager_bot_groups(actor,id,name) VALUES(?,?,?)',(actor,QUICK,'Quick Bots'))

    def list(self,actor):
        with self.db.transaction() as db:
            rows=db.execute('SELECT id,name,collapsed,revision FROM messager_bot_groups WHERE actor=? ORDER BY CASE WHEN id=? THEN 0 ELSE 1 END,rowid',(actor,QUICK)).fetchall()
        if not any(r['id']==QUICK for r in rows):
            with self.db.transaction(write=True) as db:self.ensure(db,actor)
            return self.list(actor)
        with self.db.transaction() as db:
            saved=db.execute('SELECT ids FROM messager_bot_group_order WHERE actor=?',(actor,)).fetchone()
        order=json.loads(saved['ids']) if saved else []
        rank={ref:index for index,ref in enumerate(order)}
        rows=sorted(rows,key=lambda r:rank.get(r['id'],len(rank)))
        return [{**dict(r),'collapsed':bool(r['collapsed']),'permanent':r['id']==QUICK} for r in rows]

    def reorder(self,actor,ids):
        if len(ids)!=len(set(ids)):raise ValueError('Duplicate group')
        with self.db.transaction(write=True) as db:
            self.ensure(db,actor)
            actual={r['id'] for r in db.execute('SELECT id FROM messager_bot_groups WHERE actor=?',(actor,))}
            if set(ids)!=actual:raise ValueError('Groups changed; refresh and try again')
            db.execute('INSERT INTO messager_bot_group_order VALUES(?,?) ON CONFLICT(actor) DO UPDATE SET ids=excluded.ids',(actor,json.dumps(ids)))

    def create(self,actor,name):
        name=name.strip()
        if not 1<=len(name)<=64:raise ValueError('Choose a group name (1–64 characters)')
        ref=uuid4().hex
        with self.db.transaction(write=True) as db:
            self.ensure(db,actor)
            db.execute('INSERT INTO messager_bot_groups(actor,id,name) VALUES(?,?,?)',(actor,ref,name))
        return ref

    def update(self,actor,ref,revision,*,collapsed=None,delete=False,name=None):
        with self.db.transaction(write=True) as db:
            self.ensure(db,actor)
            row=db.execute('SELECT * FROM messager_bot_groups WHERE actor=? AND id=?',(actor,ref)).fetchone()
            if not row:raise PermissionError('Group unavailable')
            if row['revision']!=revision:raise ValueError('Group changed; review it again')
            if delete:
                if ref==QUICK:raise ValueError('Quick Bots cannot be deleted')
                db.execute('UPDATE messager_bot_group_members SET group_id=NULL WHERE actor=? AND group_id=?',(actor,ref))
                db.execute('DELETE FROM messager_bot_groups WHERE actor=? AND id=?',(actor,ref))
            elif name is not None:
                if ref == QUICK:
                    raise ValueError('Quick Bots cannot be renamed')
                name = name.strip()
                if not 1 <= len(name) <= 64:
                    raise ValueError('Choose a group name (1–64 characters)')
                db.execute(
                    'UPDATE messager_bot_groups SET name=?,revision=revision+1 WHERE actor=? AND id=?',
                    (name, actor, ref),
                )
            elif collapsed is not None:
                db.execute('UPDATE messager_bot_groups SET collapsed=?,revision=revision+1 WHERE actor=? AND id=?',(int(collapsed),actor,ref))

    def move(self,actor,bot,group_id,*,connection=None):
        with (nullcontext(connection) if connection is not None else self.db.transaction(write=True)) as db:
            if not db.execute('SELECT 1 FROM messager_bots WHERE actor=? AND id=?',(actor,bot)).fetchone():raise PermissionError('Bot unavailable')
            self.ensure(db,actor)
            if group_id is not None and not db.execute('SELECT 1 FROM messager_bot_groups WHERE actor=? AND id=?',(actor,group_id)).fetchone():raise PermissionError('Group unavailable')
            db.execute('INSERT INTO messager_bot_group_members VALUES(?,?,?) ON CONFLICT(actor,bot_id) DO UPDATE SET group_id=excluded.group_id',(actor,bot,group_id))

    def project(self,actor,bots):
        with self.db.transaction() as db:
            members={r['bot_id']:r['group_id'] for r in db.execute('SELECT bot_id,group_id FROM messager_bot_group_members WHERE actor=?',(actor,))}
        for bot in bots:
            bot['group_id']=members.get(bot['id'],QUICK if bot.get('definition',{}).get('execution_mode') in ('flash','app_shortcut') else None)
        return bots
