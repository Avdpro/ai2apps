"""Durable image-recognition state; no model or network dependencies."""
from __future__ import annotations
import json
import uuid
from ai2apps.core import utc_now_text
from .store import KnowledgeAccessError, KnowledgeConflictError

OCR_SCHEMA = """CREATE TABLE IF NOT EXISTS knowledge_image_ocr (
    item_id TEXT PRIMARY KEY REFERENCES knowledge_items(id) ON DELETE CASCADE,
    actor_user_id TEXT NOT NULL, installation_id TEXT NOT NULL,
    item_revision INTEGER NOT NULL, asset_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN
      ('queued','running','awaiting_consent','blocked','completed','failed','skipped','cancelled')),
    revision INTEGER NOT NULL DEFAULT 1, attempts INTEGER NOT NULL DEFAULT 0,
    model_id TEXT, model_label TEXT, route TEXT, selection_fingerprint TEXT,
    consent_token TEXT, approved_fingerprint TEXT, run_token TEXT,
    text TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', error TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
)"""


def insert_image_ocr(connection, item, asset_hash):
    now = utc_now_text()
    connection.execute("""INSERT OR IGNORE INTO knowledge_image_ocr
      (item_id,actor_user_id,installation_id,item_revision,asset_hash,created_at,updated_at)
      VALUES (?,?,?,?,?,?,?)""", (item.id,item.owner_user_id,item.installation_id,
      item.revision,asset_hash,now,now))


class KnowledgeOCRStore:
    def __init__(self, knowledge):
        self.knowledge = knowledge

    def owned(self, principal, item_id):
        item = self.knowledge.get_item(principal, item_id)
        if item.owner_user_id != principal.actor_user_id or item.kind != 'image':
            raise KnowledgeAccessError('Only the image owner can control recognition')
        return item

    def get(self, principal, item_id):
        self.owned(principal,item_id)
        with self.knowledge.transaction() as c:
            row=c.execute('SELECT * FROM knowledge_image_ocr WHERE item_id=? AND actor_user_id=? AND installation_id=?',
                (item_id,principal.actor_user_id,principal.installation_id)).fetchone()
        if row is None:raise KnowledgeConflictError('Image recognition task not found')
        return dict(row)

    def list(self, principal, limit=100):
        with self.knowledge.transaction() as c:
            rows=c.execute("""SELECT o.*,i.title FROM knowledge_image_ocr o
              JOIN knowledge_items i ON i.id=o.item_id
              WHERE o.actor_user_id=? AND o.installation_id=? AND i.deleted_at IS NULL
              ORDER BY CASE WHEN o.status IN ('queued','running','awaiting_consent') THEN 0 ELSE 1 END,
                o.updated_at DESC LIMIT ?""",(principal.actor_user_id,principal.installation_id,limit)).fetchall()
        # Recognition bodies are already in the Knowledge representation. Keep polling bounded.
        return [{k:r[k] for k in ('item_id','title','status','revision','attempts','model_id',
            'model_label','route','error','updated_at','consent_token')} for r in rows]

    def recover(self):
        # An interrupted remote call may have been billed. Never replay it implicitly.
        with self.knowledge.transaction(write=True) as c:
            c.execute("""UPDATE knowledge_image_ocr SET status='failed',run_token=NULL,
              consent_token=NULL,approved_fingerprint=NULL,error='interrupted',revision=revision+1,
              updated_at=? WHERE status='running'""",(utc_now_text(),))
            c.execute("""UPDATE knowledge_image_ocr SET approved_fingerprint=NULL,
              consent_token=NULL,revision=revision+1,updated_at=?
              WHERE status='queued' AND approved_fingerprint IS NOT NULL""",(utc_now_text(),))

    def next(self):
        with self.knowledge.transaction() as c:
            row=c.execute("SELECT * FROM knowledge_image_ocr WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
        return dict(row) if row else None

    def transition(self, row, status, **values):
        allowed={'model_id','model_label','route','selection_fingerprint','consent_token',
                 'approved_fingerprint','run_token','error','attempts','item_revision','text','description'}
        if set(values)-allowed:raise ValueError('Unsupported recognition state fields')
        fields={'status':status,**values,'updated_at':utc_now_text()}
        with self.knowledge.transaction(write=True) as c:
            result=c.execute('UPDATE knowledge_image_ocr SET '+','.join(k+'=?' for k in fields)+
                ',revision=revision+1 WHERE item_id=? AND revision=?',
                (*fields.values(),row['item_id'],row['revision']))
        return bool(result.rowcount)

    def decide(self, principal, item_id, *, revision, token, allow):
        row=self.get(principal,item_id)
        if (row['status']!='awaiting_consent' or row['revision']!=revision or
            not token or row['consent_token']!=token):
            raise KnowledgeConflictError('Recognition confirmation changed; refresh and review again')
        if not self.transition(row,'queued' if allow else 'skipped',consent_token=None,
            approved_fingerprint=row['selection_fingerprint'] if allow else None,error=None):
            raise KnowledgeConflictError('Recognition confirmation changed')

    def request(self, principal, item_id, *, item_revision):
        item=self.owned(principal,item_id)
        if item.revision!=item_revision:raise KnowledgeConflictError('Image revision changed')
        asset,_=self.knowledge.asset_path(principal,item_id)
        with self.knowledge.transaction(write=True) as c:
            insert_image_ocr(c,item,asset.content_hash)
        row=self.get(principal,item_id)
        if row['status']=='queued' and row['attempts']==0:return
        self.control(principal,item_id,revision=row['revision'],action='retry')

    def control(self, principal, item_id, *, revision, action):
        row=self.get(principal,item_id)
        if row['revision']!=revision:raise KnowledgeConflictError('Recognition task changed')
        if action=='retry':
            if row['status'] not in {'completed','failed','blocked','skipped','cancelled'}:
                raise KnowledgeConflictError('Recognition is already pending')
            item=self.owned(principal,item_id)
            values={'item_revision':item.revision}
            status='queued'
        elif action=='cancel':
            if row['status'] not in {'queued','running','awaiting_consent'}:
                raise KnowledgeConflictError('Recognition is not pending')
            values={};status='cancelled'
        else:raise ValueError('Unknown recognition action')
        if not self.transition(row,status,run_token=None,approved_fingerprint=None,
            consent_token=None,error=None,**values):raise KnowledgeConflictError('Recognition task changed')

    def complete(self, principal, row, *, text, description):
        """CAS both the item revision and run lease before publishing text/FTS changes."""
        item=self.owned(principal,row['item_id'])
        if item.revision!=row['item_revision']:raise KnowledgeConflictError('Image revision changed')
        asset,_=self.knowledge.asset_path(principal,item.id)
        if asset.content_hash!=row['asset_hash']:raise KnowledgeConflictError('Image asset changed')
        text=text.strip();description=description.strip();combined='\n\n'.join(x for x in (text,description) if x)
        now=utc_now_text()
        with self.knowledge.transaction(write=True) as c:
            changed=c.execute("""UPDATE knowledge_image_ocr SET status='completed',text=?,description=?,
              error=NULL,run_token=NULL,approved_fingerprint=NULL,consent_token=NULL,
              revision=revision+1,updated_at=? WHERE item_id=? AND status='running' AND run_token=?
              AND EXISTS(SELECT 1 FROM knowledge_items WHERE id=? AND revision=? AND deleted_at IS NULL)""",
              (text,description,now,item.id,row['run_token'],item.id,row['item_revision']))
            if not changed.rowcount:return False
            rep=c.execute('SELECT id FROM knowledge_representations WHERE item_id=? AND ordinal=0',(item.id,)).fetchone()
            if rep is None:raise KnowledgeConflictError('Image representation is missing')
            c.execute('DELETE FROM knowledge_chunks WHERE item_id=?',(item.id,))
            c.execute("UPDATE knowledge_representations SET text=?,producer='knowledge.ocr/v1',status='ready' WHERE id=?",(combined,rep['id']))
            for ordinal,(body,kind) in enumerate(((text,'ocr'),(description,'image_description'))):
                if not body:continue
                c.execute("""INSERT INTO knowledge_chunks(id,representation_id,item_id,space_id,ordinal,text,created_at,metadata_json)
                  VALUES (?,?,?,?,?,?,?,?)""",('kch_'+uuid.uuid4().hex,rep['id'],item.id,item.space_id,ordinal,body,now,
                  json.dumps({'kind':kind,'model_id':row['model_id'],'data_trust':'untrusted'})))
            c.execute('UPDATE knowledge_items SET revision=revision+1,updated_at=? WHERE id=?',(now,item.id))
            c.execute("UPDATE knowledge_assets SET parser='knowledge.ocr/v1' WHERE item_id=?",(item.id,))
            for key,value in (('source.extractor','knowledge.ocr/v1'),('source.model_id',row['model_id'])):
                c.execute('DELETE FROM knowledge_source_facets WHERE item_id=? AND facet_key=?',(item.id,key))
                c.execute("INSERT INTO knowledge_source_facets(item_id,facet_key,value,authority,created_at) VALUES (?,?,?,'runtime',?)",(item.id,key,value,now))

            c.execute("""INSERT INTO knowledge_change_log(operation,item_id,space_id,authoritative_revision,created_at)
              VALUES ('update',?,?,?,?)""",(item.id,item.space_id,item.revision+1,now))
        return True
