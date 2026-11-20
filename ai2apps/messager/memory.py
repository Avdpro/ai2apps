"""User-owned, bounded Bot notes. Notes are context data, never authority."""
from datetime import datetime, UTC
from uuid import uuid4
import logging


class BotMemory:
    def __init__(self, directory):
        logging.getLogger(__name__).info('Bot memory loaded; source=%s',__file__)
        self.directory, self.db = directory, directory.db
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_memories(
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, bot_id TEXT NOT NULL,
                text TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, revision INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0)''')
            db.execute('CREATE INDEX IF NOT EXISTS bot_memories_owner ON messager_bot_memories(actor,bot_id)')
        from .history import BotHistory
        directory.history=BotHistory(directory)
        from .memory_records import MemoryRecords
        self.records=MemoryRecords(self)

    def list(self, actor, bot_id):
        self.directory.scope(actor, {'bot_id': bot_id})
        with self.db.transaction() as db:
            rows=db.execute('SELECT m.*,f.metadata_json FROM messager_bot_memories m LEFT JOIN messager_memory_fields f ON f.memory_id=m.id WHERE m.actor=? AND m.bot_id=? ORDER BY m.updated_at DESC,m.id LIMIT 201', (actor,bot_id)).fetchall()
        import json
        return {'items': [{**{k:r[k] for k in r.keys() if k!='metadata_json'},'metadata':json.loads(r['metadata_json']) if r['metadata_json'] else None} for r in rows], 'limit': 50, 'character_limit': 8000}

    def context(self, actor, bot_id):
        return [{'id': r['id'], 'text': r['text'], 'source': r['source'], 'updated_at': r['updated_at']}
                for r in self.list(actor, bot_id)['items'] if not r['deleted'] and (r.get('metadata') or {}).get('kind')!='model' and (not getattr(self.directory,'memory_returns',None) or self.directory.memory_returns.usable(actor,bot_id,r['id']))]

    def save(self, actor, bot_id, text, *, ref=None, revision=None, deleted=False, connection=None, journal=True):
        self.directory.scope(actor, {'bot_id': bot_id})
        text=text.strip()
        if not 1 <= len(text) <= 2000:
            raise ValueError('Memory must contain 1–2000 characters')
        now=datetime.now(UTC).isoformat()
        from contextlib import nullcontext
        with (nullcontext(connection) if connection is not None else self.db.transaction(write=True)) as db:
            old=db.execute('SELECT * FROM messager_bot_memories WHERE actor=? AND bot_id=? AND id=?', (actor,bot_id,ref)).fetchone() if ref else None
            if ref and (not old or old['revision'] != revision):
                raise ValueError('Memory changed; reload before editing')
            field=db.execute('SELECT metadata_json FROM messager_memory_fields WHERE memory_id=?',(ref,)).fetchone() if ref else None
            if old and old['deleted'] and not deleted and not field:
                import json
                from .memory_records import signature
                historical=db.execute('SELECT after_metadata FROM messager_memory_changes WHERE memory_id=? AND after_metadata IS NOT NULL ORDER BY rowid DESC LIMIT 1',(ref,)).fetchone()
                if historical:
                    metadata=json.loads(historical[0]);slot=signature([metadata['subject'],metadata['predicate'],metadata.get('variant','')])
                    occupied=db.execute('SELECT memory_id FROM messager_memory_fields WHERE actor=? AND bot_id=? AND slot=?',(actor,bot_id,slot)).fetchone()
                    if occupied and occupied[0]!=ref:raise ValueError('A newer memory occupies this field; review current memory')
            if journal and field and old and old['text']!=text and not deleted:
                raise ValueError('Use the structured memory replacement flow to change this value')
            active=db.execute('SELECT COUNT(*),COALESCE(SUM(length(text)),0) FROM messager_bot_memories WHERE actor=? AND bot_id=? AND deleted=0 AND id!=?', (actor,bot_id,ref or '')).fetchone()
            if not deleted and (active[0]>=50 or active[1]+len(text)>8000):
                raise ValueError('Keep at most 50 memories and 8000 characters per Bot')
            # Deleted notes remain recoverable, with a finite retention budget.
            if not ref and db.execute('SELECT COUNT(*) FROM messager_bot_memories WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()[0]>=200:
                raise ValueError('Memory archive is full; reuse an existing note')
            if old:
                db.execute('UPDATE messager_bot_memories SET text=?,updated_at=?,revision=revision+1,deleted=? WHERE id=?', (text,now,int(deleted),ref))
            else:
                ref=uuid4().hex
                db.execute('INSERT INTO messager_bot_memories VALUES(?,?,?,?,?,?,?,1,0)', (ref,actor,bot_id,text,'user',now,now))
            after=dict(db.execute('SELECT * FROM messager_bot_memories WHERE id=?',(ref,)).fetchone())
            returns=getattr(self.directory,'memory_returns',None)
            if old and returns:returns.invalidate(db,actor,bot_id,ref,after['revision'])
            if deleted and old:
                maintenance=getattr(self.directory,'memory_tasks',None)
                if maintenance:
                    for evidence in db.execute('SELECT source_json FROM messager_memory_evidence WHERE memory_id=?',(ref,)):
                        import json
                        maintenance.block(db,actor,bot_id,json.loads(evidence[0]),maintenance.slot(json.loads(field[0])) if field else None)
            if journal:
                import json
                metadata=json.loads(field[0]) if field else None
                self.records.track(db,actor,bot_id,dict(old) if old else None,after,metadata_before=metadata,metadata_after=metadata,notify=connection is None)
            return after

    def clear(self, actor, bot_id):
        self.directory.scope(actor, {'bot_id':bot_id})
        with self.db.transaction(write=True) as db:
            maintenance=getattr(self.directory,'memory_tasks',None)
            if maintenance:maintenance.invalidate(db,actor,bot_id)
            db.execute('UPDATE messager_bot_memories SET deleted=1,revision=revision+1,updated_at=? WHERE actor=? AND bot_id=? AND deleted=0', (datetime.now(UTC).isoformat(),actor,bot_id))
