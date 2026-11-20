"""Structured memory owner core: versioned evidence, explicit merges and CAS undo.

No autonomous extraction, model calls, task dispatch or permission changes here.
"""
import json
import hashlib
from uuid import uuid4
from datetime import datetime, UTC


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def signature(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


class MemoryRecords:
    def __init__(self,memory):
        self.memory,self.directory,self.db=memory,memory.directory,memory.db
        import logging
        logging.getLogger(__name__).info('Bot structured memory loaded; source=%s',__file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_fields(
                memory_id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,
                slot TEXT NOT NULL,metadata_json TEXT NOT NULL,UNIQUE(actor,bot_id,slot))''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_changes(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,memory_id TEXT NOT NULL,
                request_key TEXT NOT NULL,signature TEXT NOT NULL,kind TEXT NOT NULL,
                before_json TEXT,after_json TEXT NOT NULL,before_metadata TEXT,after_metadata TEXT,
                source_json TEXT NOT NULL,source_session TEXT,message_id TEXT,undone_by TEXT,created_at TEXT NOT NULL,
                UNIQUE(actor,bot_id,request_key))''')
            db.execute('CREATE INDEX IF NOT EXISTS bot_memory_versions ON messager_memory_changes(actor,bot_id,memory_id,created_at)')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_memory_evidence(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,memory_id TEXT NOT NULL,
                change_id TEXT NOT NULL,source_key TEXT NOT NULL,source_json TEXT NOT NULL,
                UNIQUE(actor,bot_id,memory_id,source_key))''')

    def _scope(self,actor,bot):
        self.directory.scope(actor,{'bot_id':bot})

    def _main(self,db,actor,bot):
        row=db.execute('''SELECT session_id FROM app_chat_sessions WHERE owner=? AND registration='ai2apps.messager.bots'
            AND json_extract(scope_json,'$.bot_id')=? AND json_extract(scope_json,'$.dialogue_job') IS NULL ORDER BY rowid DESC LIMIT 1''',(actor,bot)).fetchone()
        return row[0] if row else None

    def _source(self,actor,bot,source):
        from .history import BotHistory
        if not source:return {'kind':'manual'}
        if isinstance(source,dict) and set(source)=={'delegation_memory_id'}:
            return self.directory.memory_returns.evidence(actor,bot,source['delegation_memory_id'])
        if not isinstance(source,dict) or set(source)-{'session_id','message_id','task_id'}:raise ValueError('Invalid memory evidence')
        if not all(isinstance(v,str) and 1<=len(v)<=256 for v in source.values()):raise ValueError('Evidence identities must be bounded strings')
        if 'task_id' in source:
            self.directory.history.task(actor,bot,source['task_id'])
        if 'session_id' in source:
            self.directory.history.session(actor,bot,source['session_id'])
            if 'message_id' in source:
                from ai2apps.storage.repositories import MessageRepository
                MessageRepository(self.db).get(source['message_id'],session_id=source['session_id'])
        elif 'message_id' in source:raise ValueError('Message evidence requires its Session')
        return {'kind':'user_selected',**source}

    def _old_request(self,db,actor,bot,key,sig):
        row=db.execute('SELECT * FROM messager_memory_changes WHERE actor=? AND bot_id=? AND request_key=?',(actor,bot,key)).fetchone()
        if row and row['signature']!=sig:raise ValueError('Memory request ID was reused with different input')
        return self._receipt(row) if row else None

    @staticmethod
    def _receipt(row):
        return {'change_id':row['id'],'memory_id':row['memory_id'],'kind':row['kind'],
                'revision':json.loads(row['after_json'])['revision'],'undone_by':row['undone_by'],'created_at':row['created_at']}

    def track(self,db,actor,bot,before,after,*,kind=None,request_key=None,sig=None,metadata_before=None,metadata_after=None,source=None,notify=True):
        ref=uuid4().hex;key=request_key or 'manual:'+ref
        source=source or {'kind':'manual'}
        stamp=datetime.now(UTC).isoformat()
        kind=kind or ('created' if before is None else 'removed' if after['deleted'] else 'updated')
        sid=self._main(db,actor,bot) if notify else None
        db.execute('INSERT INTO messager_memory_changes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL,?)',
            (ref,actor,bot,after['id'],key,sig or signature(after),kind,encoded(before) if before else None,encoded(after),
             encoded(metadata_before) if metadata_before else None,encoded(metadata_after) if metadata_after else None,encoded(source),sid,None,stamp))
        source_key=signature(source) if source.get('kind')!='manual' else key
        if kind!='undo':
            db.execute('INSERT OR IGNORE INTO messager_memory_evidence VALUES(?,?,?,?,?,?,?)',(uuid4().hex,actor,bot,after['id'],ref,source_key,encoded(source)))
        if sid and getattr(self.directory,'runtime',None):self.db.after_commit(db,lambda:self.project(actor,bot,ref))
        return ref

    def project(self,actor,bot,change_id):
        with self.directory.runtime.app_chat.lock:
            from ai2apps.storage.repositories import MessageRepository
            from ai2apps.core import MessageRole
            from ai2apps.storage import MessagePartInput
            with self.db.transaction() as db:
                row=db.execute('SELECT * FROM messager_memory_changes WHERE id=? AND actor=? AND bot_id=?',(change_id,actor,bot)).fetchone()
            if not row or not row['source_session'] or row['message_id'] is not None:return
            with self.db.transaction() as db:current=db.execute('SELECT revision FROM messager_bot_memories WHERE actor=? AND bot_id=? AND id=?',(actor,bot,row['memory_id'])).fetchone()
            if not current or current['revision']!=json.loads(row['after_json'])['revision']:
                with self.db.transaction(write=True) as db:db.execute("UPDATE messager_memory_changes SET message_id='' WHERE id=? AND message_id IS NULL",(row['id'],))
                return
            try:self.directory.history.session(actor,bot,row['source_session'])
            except PermissionError:
                with self.db.transaction(write=True) as db:db.execute("UPDATE messager_memory_changes SET message_id='' WHERE id=? AND message_id IS NULL",(row['id'],))
                return # Never append a delayed receipt to cleared/archived history.
            labels={'created':'已记住 / Memory saved','merged':'已合并记忆来源 / Memory evidence merged','updated':'已更新记忆 / Memory updated','removed':'已移除记忆 / Memory removed','undo':'已撤销记忆变更 / Memory change undone'}
            content=labels.get(row['kind'],'Memory updated')+'：'+json.loads(row['after_json'])['text']
            result=MessageRepository(self.db,self.directory.runtime.events).append(session_id=row['source_session'],role=MessageRole.ASSISTANT,
                parts=(MessagePartInput(kind='text',content={'text':content}),),idempotency_key='bot-memory-change:'+row['id'],
                metadata={'origin':'bot_memory_change','memory_change_id':row['id']})
            with self.db.transaction(write=True) as db:db.execute('UPDATE messager_memory_changes SET message_id=? WHERE id=?',(result.value.message.id,row['id']))

    def link_receipt(self,db,actor,bot,note,sid,key):
        """Bind a host-reviewed configuration's existing notification, not a second message."""
        message=db.execute("SELECT m.id FROM messages m JOIN app_chat_sessions s ON s.session_id=m.session_id WHERE m.session_id=? AND m.idempotency_key=? AND s.owner=? AND s.registration='ai2apps.messager.bots' AND json_extract(s.scope_json,'$.bot_id')=?",(sid,key,actor,bot)).fetchone()
        if not message:return
        db.execute("UPDATE messager_memory_changes SET source_session=?,message_id=? WHERE actor=? AND bot_id=? AND memory_id=? AND json_extract(after_json,'$.revision')=? AND source_session IS NULL",(sid,message['id'],actor,bot,note['id'],note['revision']))

    def changes(self,actor,bot,*,sid=None,limit=50,offset=0,message_ids=None):
        self._scope(actor,bot)
        if sid:
            self.directory.history.session(actor,bot,sid)
        if not 1<=limit<=100 or not 0<=offset<=10000:raise ValueError('Invalid memory history page')
        if message_ids is not None and (not sid or len(message_ids)>100 or not all(isinstance(i,str) and 1<=len(i)<=256 for i in message_ids)):
            raise ValueError('Message lookup requires a bounded owned Session page')
        # Recover only committed projections, never effects or deleted context.
        with self.db.transaction() as db:
            pending=db.execute('SELECT id FROM messager_memory_changes WHERE actor=? AND bot_id=? AND source_session IS NOT NULL AND message_id IS NULL ORDER BY rowid DESC LIMIT 20',(actor,bot)).fetchall()
        for row in pending:self.project(actor,bot,row['id'])
        filters='';params=[actor,bot]
        if sid:filters+=' AND source_session=?';params.append(sid)
        if message_ids is not None:
            if not message_ids:return {'items':[],'has_more':False,'next_offset':None}
            filters+=' AND message_id IN ('+','.join('?' for _ in message_ids)+')';params.extend(message_ids)
        with self.db.transaction() as db:
            rows=db.execute('SELECT * FROM messager_memory_changes WHERE actor=? AND bot_id=?'+filters+' ORDER BY rowid DESC LIMIT ? OFFSET ?',(*params,limit+1,offset)).fetchall()
        return {'items':[{**self._receipt(row),'message_id':row['message_id']} for row in rows[:limit]],
                'has_more':len(rows)>limit,'next_offset':offset+limit if len(rows)>limit else None}

    def detail(self,actor,bot,ref):
        self._scope(actor,bot)
        with self.db.transaction() as db:
            row=db.execute('SELECT * FROM messager_memory_changes WHERE id=? AND actor=? AND bot_id=?',(ref,actor,bot)).fetchone()
            if not row:raise PermissionError('Memory change unavailable')
            evidence=[json.loads(r[0]) for r in db.execute('SELECT source_json FROM messager_memory_evidence WHERE actor=? AND bot_id=? AND memory_id=?',(actor,bot,row['memory_id']))]
            current=db.execute('SELECT revision,deleted FROM messager_bot_memories WHERE actor=? AND bot_id=? AND id=?',(actor,bot,row['memory_id'])).fetchone()
        return {**self._receipt(row),'before':json.loads(row['before_json']) if row['before_json'] else None,'after':json.loads(row['after_json']),
                'metadata':json.loads(row['after_metadata']) if row['after_metadata'] else None,'source':json.loads(row['source_json']),'evidence':evidence,
                **({'provenance':self.directory.memory_returns.describe(actor,bot,json.loads(row['source_json'])['return_id'])} if json.loads(row['source_json']).get('kind')=='delegated_memory' else {}),
                'can_undo':bool(current and current['revision']==json.loads(row['after_json'])['revision'] and not row['undone_by'] and row['kind']!='undo')}

    def apply(self,actor,bot,*,request_id,subject,predicate,value,text,kind='fact',variant='',mode='merge',expected_revision=None,source=None,_guard=None,_committed=None,_restore=False):
        self._scope(actor,bot)
        if kind not in ('fact','preference','resource','model') or mode not in ('merge','replace'):raise ValueError('Invalid memory kind or operation')
        if kind == 'model':
            from .model_memories import model_value
            value = model_value(value)
            subject, predicate, variant = 'bot', 'model', value['purpose'] + ':' + value['profile']
        if not all(isinstance(v,str) and 1<=len(v.strip())<=120 for v in (subject,predicate)) or not isinstance(variant,str) or len(variant)>120:raise ValueError('Invalid memory field')
        if not isinstance(request_id,str) or not 8<=len(request_id)<=128:raise ValueError('A stable request ID is required')
        if not isinstance(value,(str,dict)) or len(encoded(value))>4000:raise ValueError('Memory value is too large')
        if not isinstance(text,str) or not 1<=len(text.strip())<=2000:raise ValueError('Memory text must contain 1-2000 characters')
        source=self._source(actor,bot,source)
        sig=signature([subject,predicate,value,text,kind,variant,mode,expected_revision,source])
        slot=signature([subject.strip(),predicate.strip(),variant])
        with self.db.transaction() as db:
            duplicate=self._old_request(db,actor,bot,request_id,sig)
        if duplicate and not _committed:return duplicate
        if kind=='resource':
            history=self.directory.history;resource=history.resource(actor,bot,value)
            if not resource['available']:raise ValueError('Memory resource is unavailable')
            # Explicitly saved references retain bytes instead of relying on an external picker path.
            if 'attachment_id' in value:
                item=self.directory.runtime.documents.get(value['session_id'],value['attachment_id'])
                path=self.directory.runtime.documents.source_path(value['session_id'],item.id)
                asset=self.directory.runtime.workspace.import_artifact(value['session_id'],path,name=item.filename,media_type=item.media_type,
                    metadata={'memory_source_attachment':item.id})
                value={'session_id':value['session_id'],'artifact_id':asset.id}
                resource=history.resource(actor,bot,value)
            value={**value,'content_hash':resource.get('content_hash','')}
        metadata={'subject':subject.strip(),'predicate':predicate.strip(),'variant':variant,'kind':kind,'value':value}
        with self.directory.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            if _guard:_guard(db)
            duplicate=self._old_request(db,actor,bot,request_id,sig)
            if duplicate:
                if _committed:_committed(db,duplicate)
                return duplicate
            field=db.execute('SELECT * FROM messager_memory_fields WHERE actor=? AND bot_id=? AND slot=?',(actor,bot,slot)).fetchone()
            before=dict(db.execute('SELECT * FROM messager_bot_memories WHERE id=? AND actor=? AND bot_id=?',(field['memory_id'],actor,bot)).fetchone()) if field else None
            previous=json.loads(field['metadata_json']) if field else None
            if before and before['deleted']:
                if not _restore:raise ValueError('This memory was removed; explicitly restore it before merging')
                # Fresh explicit user evidence starts a new record. Never revive an old source.
                db.execute('DELETE FROM messager_memory_fields WHERE memory_id=?',(before['id'],))
                before=previous=None
            if before and expected_revision is not None and before['revision']!=expected_revision:raise ValueError('Memory changed; review again')
            same=previous==metadata
            if kind=='resource' and previous and previous.get('kind')==kind:
                same=bool(value.get('content_hash') and previous['value'].get('content_hash')==value['content_hash'])
                if same:metadata=previous
            if before and not same and (mode!='replace' or expected_revision!=before['revision']):
                raise ValueError('Memory conflicts; explicitly replace the current version or select a different variant')
            if before and same:
                evidence=db.execute('SELECT 1 FROM messager_memory_evidence WHERE actor=? AND bot_id=? AND memory_id=? AND source_key=?',(actor,bot,before['id'],signature(source))).fetchone()
                if evidence and source.get('kind')!='manual':
                    result={'memory_id':before['id'],'kind':'unchanged','revision':before['revision'],'change_id':None}
                    if _committed:_committed(db,result)
                    return result
            after=self.memory.save(actor,bot,before['text'] if same else text,ref=before['id'] if before else None,
                revision=before['revision'] if before else None,connection=db,journal=False)
            db.execute('INSERT INTO messager_memory_fields VALUES(?,?,?,?,?) ON CONFLICT(memory_id) DO UPDATE SET metadata_json=excluded.metadata_json',
                (after['id'],actor,bot,slot,encoded(metadata)))
            ref=self.track(db,actor,bot,before,after,kind='merged' if same else 'updated' if before else 'created',
                request_key=request_id,sig=sig,metadata_before=previous,metadata_after=metadata,source=source)
            receipt=self._receipt(db.execute('SELECT * FROM messager_memory_changes WHERE id=?',(ref,)).fetchone())
            if _committed:_committed(db,receipt)
        return receipt

    def undo(self,actor,bot,ref,*,request_id):
        self._scope(actor,bot)
        if not isinstance(request_id,str) or not 8<=len(request_id)<=128:raise ValueError('A stable undo request ID is required')
        sig=signature(['undo',ref])
        with self.directory.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            old=self._old_request(db,actor,bot,request_id,sig)
            if old:return old
            row=db.execute('SELECT * FROM messager_memory_changes WHERE actor=? AND bot_id=? AND id=?',(actor,bot,ref)).fetchone()
            if not row or row['kind']=='undo':raise PermissionError('Memory change unavailable')
            if row['undone_by']:return self._receipt(db.execute('SELECT * FROM messager_memory_changes WHERE id=?',(row['undone_by'],)).fetchone())
            current=db.execute('SELECT * FROM messager_bot_memories WHERE actor=? AND bot_id=? AND id=?',(actor,bot,row['memory_id'])).fetchone()
            expected=json.loads(row['after_json'])
            if not current or current['revision']!=expected['revision']:raise ValueError('Later changes exist; review current memory before undoing')
            before=json.loads(row['before_json']) if row['before_json'] else None
            metadata=json.loads(row['before_metadata'] or row['after_metadata'] or '{}')
            if metadata:
                slot=signature([metadata['subject'],metadata['predicate'],metadata.get('variant','')])
                occupied=db.execute('SELECT memory_id FROM messager_memory_fields WHERE actor=? AND bot_id=? AND slot=?',(actor,bot,slot)).fetchone()
                if occupied and occupied[0]!=current['id']:raise ValueError('A newer memory occupies this field; review current memory')
            restored=self.memory.save(actor,bot,before['text'] if before else current['text'],ref=current['id'],revision=current['revision'],
                deleted=bool(before['deleted']) if before else True,connection=db,journal=False)
            if row['before_metadata']:
                db.execute('UPDATE messager_memory_fields SET metadata_json=? WHERE memory_id=?',(row['before_metadata'],current['id']))
            else:db.execute('DELETE FROM messager_memory_fields WHERE memory_id=?',(current['id'],))
            db.execute('DELETE FROM messager_memory_evidence WHERE change_id=?',(ref,))
            undo=self.track(db,actor,bot,dict(current),restored,kind='undo',request_key=request_id,sig=sig,
                metadata_before=json.loads(row['after_metadata']) if row['after_metadata'] else None,
                metadata_after=json.loads(row['before_metadata']) if row['before_metadata'] else None)
            maintenance=getattr(self.directory,'memory_tasks',None)
            if maintenance:maintenance.block(db,actor,bot,json.loads(row['source_json']),maintenance.slot(json.loads(row['after_metadata'])) if row['after_metadata'] else None)
            db.execute('UPDATE messager_memory_changes SET undone_by=? WHERE id=?',(undo,ref))
            return self._receipt(db.execute('SELECT * FROM messager_memory_changes WHERE id=?',(undo,)).fetchone())
