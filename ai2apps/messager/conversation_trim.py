"""Explicit, reviewed conversation trimming. Tasks and Bot policy are independent."""
import hashlib
import json
import re

from ai2apps.core import utc_now_text
from ai2apps.storage.repositories.messages import MessageRepository

IDS = re.compile(r'\b(?:art_[0-9a-f]{32}|attc_[0-9a-f]{32})\b')


class ConversationTrim:
    def __init__(self, history):
        self.history = history
        self.runtime, self.db = history.runtime, history.db
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_conversation_trims(
                review_hash TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,
                session_id TEXT NOT NULL,result_json TEXT NOT NULL,pending_json TEXT NOT NULL)''')

    def _review(self, actor, bot, sid, message_id, db):
        binding = self.history.session(actor, bot, sid)
        if json.loads(binding['scope_json']) != {'bot_id': bot}:
            raise PermissionError('Open the main Bot conversation')
        anchor = db.execute("SELECT * FROM messages WHERE id=? AND session_id=? AND role='assistant'",
                            (message_id, sid)).fetchone()
        if not anchor:
            raise ValueError('Bot message is no longer available')
        rows = db.execute('''SELECT m.id,m.sequence,m.metadata_json,m.role,
            COALESCE((SELECT json_group_array(content_json) FROM message_parts WHERE message_id=m.id),'[]') AS parts
            FROM messages m WHERE m.session_id=? AND m.sequence>? AND COALESCE(json_extract(m.metadata_json,'$.retired'),0)=0
            ORDER BY m.sequence''', (sid, anchor['sequence'])).fetchall()
        removed, kept = set(), set()
        def refs(row):
            value = row['metadata_json'] + row['parts']
            run_id = json.loads(row['metadata_json']).get('agent_run_id')
            if run_id:
                run = db.execute('SELECT input_json FROM agent_runs WHERE id=? AND session_id=?', (run_id, sid)).fetchone()
                if run:
                    value += json.dumps(json.loads(run[0]).get('selected_materials', {}))
            return set(IDS.findall(value))
        for row in rows:
            removed.update(refs(row))
        retained = db.execute('''SELECT m.metadata_json,
            COALESCE((SELECT json_group_array(content_json) FROM message_parts WHERE message_id=m.id),'[]') AS parts
            FROM messages m WHERE session_id=? AND sequence<=?''', (sid, anchor['sequence'])).fetchall()
        for row in retained:
            kept.update(refs(row))
        # Resource memories must continue working; Task execution may still need
        # selected inputs. These references never confer additional authority.
        for row in db.execute('SELECT f.metadata_json FROM messager_memory_fields f JOIN messager_bot_memories m ON m.id=f.memory_id WHERE m.actor=? AND m.bot_id=? AND m.deleted=0', (actor, bot)):
            kept.update(IDS.findall(row[0]))
        for row in db.execute("SELECT input_json FROM agent_runs WHERE session_id=? AND status NOT IN ('completed','failed','cancelled','interrupted','timed_out')", (sid,)):
            active_input=json.loads(row[0])
            kept.update(IDS.findall(json.dumps({k:active_input.get(k) for k in ('prompt','selected_materials')})))
        for row in db.execute('SELECT text FROM messager_bot_memories WHERE actor=? AND bot_id=? AND deleted=0',(actor,bot)):
            kept.update(IDS.findall(row[0]))
        materials = []
        for ref in sorted(removed - kept):
            table = 'artifacts' if ref.startswith('art_') else 'attachments'
            if db.execute('SELECT 1 FROM '+table+' WHERE id=? AND session_id=?', (ref, sid)).fetchone():
                materials.append({'kind':table, 'id':ref})
        value = {'session_id':sid,'message_id':message_id,'through_sequence':anchor['sequence'],
                 'deleted_messages':sum(r['role'] in ('user','assistant') for r in rows),
                 'deleted_materials':len(materials),'shared_materials':len(removed & kept)}
        signature = json.dumps([actor,bot,value,[dict(r) for r in rows],materials], sort_keys=True)
        value['review_hash'] = hashlib.sha256(signature.encode()).hexdigest()
        return value, rows, materials

    def review(self, actor, bot, sid, message_id):
        with self.runtime.app_chat.lock, self.db.transaction() as db:
            return self._review(actor, bot, sid, message_id, db)[0]

    def apply(self, actor, bot, sid, message_id, review_hash):
        with self.runtime.app_chat.lock:
            return self._apply_locked(actor, bot, sid, message_id, review_hash)

    def _in_use(self, actor, bot, sid, ref):
        # Cleanup retries may follow new messages or new work using this file.
        with self.db.transaction() as db:
            return bool(db.execute("""SELECT 1 FROM messages m WHERE m.session_id=?
                AND COALESCE(json_extract(m.metadata_json,'$.retired'),0)=0
                AND (instr(m.metadata_json,?)>0 OR EXISTS(SELECT 1 FROM message_parts p
                    WHERE p.message_id=m.id AND instr(p.content_json,?)>0)
                    OR EXISTS(SELECT 1 FROM agent_runs r WHERE r.id=json_extract(m.metadata_json,'$.agent_run_id')
                        AND instr(COALESCE(json_extract(r.input_json,'$.selected_materials'),''),?)>0)) LIMIT 1""",
                (sid,ref,ref,ref)).fetchone() or db.execute("""SELECT 1 FROM agent_runs WHERE session_id=?
                AND status NOT IN ('completed','failed','cancelled','interrupted','timed_out')
                AND (instr(COALESCE(json_extract(input_json,'$.selected_materials'),''),?)>0
                     OR instr(COALESCE(json_extract(input_json,'$.prompt'),''),?)>0) LIMIT 1""",(sid,ref,ref)).fetchone()
                or db.execute("""SELECT 1 FROM messager_bot_memories m LEFT JOIN messager_memory_fields f ON f.memory_id=m.id
                    WHERE m.actor=? AND m.bot_id=? AND m.deleted=0
                    AND (instr(m.text,?)>0 OR instr(COALESCE(f.metadata_json,''),?)>0) LIMIT 1""",(actor,bot,ref,ref)).fetchone())

    def _apply_locked(self, actor, bot, sid, message_id, review_hash):
        self.history.session(actor, bot, sid)
        with self.runtime.app_chat.lock, self.db.transaction(write=True) as db:
            receipt = db.execute('SELECT * FROM messager_conversation_trims WHERE review_hash=? AND actor=? AND bot_id=? AND session_id=?',
                                 (review_hash,actor,bot,sid)).fetchone()
            if receipt:
                result, pending = json.loads(receipt['result_json']), json.loads(receipt['pending_json'])
                if result['message_id'] != message_id:
                    raise ValueError('Confirmation belongs to another Bot message')
            else:
                result, rows, pending = self._review(actor, bot, sid, message_id, db)
                if result['review_hash'] != review_hash:
                    raise ValueError('Conversation changed; review the trim again')
                result['retired_request_ids'] = [value for row in rows
                    if isinstance(value := json.loads(row['metadata_json']).get('client_request_id'), str)]
                # Keep content-free tombstones for sequence and idempotency keys.
                # No Task, Run, grant or memory records are deleted or cancelled.
                for row in rows:
                    original=MessageRepository._load(db,row['id'])
                    metadata=original.message.metadata
                    tombstone={'retired':True,'retired_request_digest':MessageRepository._request_digest(
                        role=original.message.role,status=original.message.status,metadata=metadata,parts=original.parts)}
                    if 'client_request_id' in metadata:
                        tombstone['client_request_id']=metadata['client_request_id']
                    db.execute('DELETE FROM message_parts WHERE message_id=?', (row['id'],))
                    db.execute("UPDATE messages SET role='system',metadata_json=?,updated_at=? WHERE id=?",
                               (json.dumps(tombstone),utc_now_text(),row['id']))
                meta = json.loads(db.execute('SELECT metadata_json FROM sessions WHERE id=?', (sid,)).fetchone()[0])
                meta['conversation_revision'] = int(meta.get('conversation_revision', 0)) + 1
                db.execute('UPDATE sessions SET metadata_json=? WHERE id=?', (json.dumps(meta),sid))
                result['conversation_revision'] = meta['conversation_revision']
                db.execute('INSERT INTO messager_conversation_trims VALUES(?,?,?,?,?,?)',
                           (review_hash,actor,bot,sid,json.dumps(result),json.dumps(pending)))
        # File cleanup is resumable using the exact reviewed receipt, never a
        # broader history deletion. Workspace retirement protects shared blobs.
        remaining = []
        for item in pending:
            if self._in_use(actor,bot,sid,item['id']):
                result['deleted_materials']-=1
                result['shared_materials']+=1
                continue
            try:
                if item['kind'] == 'artifacts':
                    self.runtime.workspace.retire_artifact(sid, item['id'])
                else:
                    self.runtime.documents.retire(sid, item['id'])
            except OSError:
                remaining.append(item)
        with self.db.transaction(write=True) as db:
            db.execute('UPDATE messager_conversation_trims SET pending_json=?,result_json=? WHERE review_hash=?',
                       (json.dumps(remaining), json.dumps(result), review_hash))
        return {**result,'cleanup_pending':len(remaining)}
