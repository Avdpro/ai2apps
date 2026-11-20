"""Bot-owned task/step/resource history. Search results never grant execution."""
import json
import re
from ai2apps.core import RepositoryError

CHAT = 'ai2apps.messager.bots'


class BotHistory:
    def __init__(self, directory):
        self.directory, self.db = directory, directory.db
        import logging
        logging.getLogger(__name__).info('Bot history index loaded; source=%s',__file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_history_index(
                task_id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,text TEXT NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS bot_history_owner ON messager_history_index(actor,bot_id)')
            db.execute('CREATE VIRTUAL TABLE IF NOT EXISTS messager_history_fts USING fts5(task_id UNINDEXED,text)')

    def conversation_trim(self):
        from .conversation_trim import ConversationTrim
        return ConversationTrim(self)

    @property
    def runtime(self):
        return self.directory.runtime

    def session(self, actor, bot, sid, *, retained=False):
        self.directory.scope(actor, {'bot_id': bot})
        with self.db.transaction() as db:
            row = db.execute('SELECT * FROM app_chat_sessions WHERE session_id=? AND owner=? AND json_extract(scope_json,\'$.bot_id\')=?', (sid,actor,bot)).fetchone()
        allowed = (CHAT, CHAT+'.archived') if retained else (CHAT,)
        if not row or row['registration'] not in allowed:
            raise PermissionError('Bot source unavailable')
        return dict(row)

    def task(self, actor, bot, ref, *, archived=False):
        self.directory.scope(actor, {'bot_id': bot})
        value = self.runtime.messager_dialogue.sessions.get(actor,bot,ref)
        self.session(actor,bot,value['source_session'])
        if value['archived'] and not archived:
            raise PermissionError('Task is archived')
        return value

    def resource(self, actor, bot, ref, *, retained=False):
        if not isinstance(ref,dict) or set(ref) not in ({'session_id','artifact_id'},{'session_id','attachment_id'}) or not all(isinstance(v,str) and 0<len(v)<=256 for v in ref.values()):
            raise ValueError('A stable Session artifact reference is required')
        self.session(actor,bot,ref['session_id'],retained=retained)
        try:
            if 'attachment_id' in ref:
                item=self.runtime.documents.get(ref['session_id'],ref['attachment_id'])
                self.runtime.documents.source_path(ref['session_id'],item.id)
                return {**ref,'available':True,'name':item.filename,'media_type':item.media_type,'content_hash':item.sha256,'size_bytes':item.size_bytes}
            asset=self.runtime.workspace.get_artifact(ref['session_id'],ref['artifact_id'])
            self.runtime.workspace.artifact_path(asset)
        except (RepositoryError,OSError,KeyError,ValueError):
            return {**ref,'available':False}
        return {**ref,'available':True,'name':asset.name,'media_type':asset.media_type,
                'content_hash':asset.content_hash,'size_bytes':asset.size_bytes}

    def _steps(self, ref):
        with self.db.transaction() as db:
            return [dict(r) for r in db.execute('''SELECT j.id,j.source_run,j.worker_run,j.source_session,j.worker_session,j.status,j.task_id,
                j.title,COALESCE(l.label,j.title) AS step_label,COALESCE(p.summary,'') AS result,
                COALESCE(p.metadata_json,'{}') AS result_metadata,
                COALESCE(json_extract(r.input_json,'$.prompt'),'') AS instruction,
                COALESCE(json_extract(r.input_json,'$.selected_materials.files'),'[]') AS input_files,
                COALESCE(w.status,j.status) AS actual_status
                FROM messager_job_sessions m JOIN messager_dialogue_jobs j ON j.id=m.job_id
                LEFT JOIN agent_runs r ON r.id=j.source_run LEFT JOIN agent_runs w ON w.id=j.worker_run
                LEFT JOIN messager_job_labels l ON l.job_id=j.id LEFT JOIN messager_job_presentations p ON p.job_id=j.id
                WHERE m.session_id=? ORDER BY j.rowid LIMIT 101''',(ref,))]

    def detail(self, actor, bot, ref, *, archived=False):
        value=self.task(actor,bot,ref,archived=archived)
        rows=self._steps(ref);steps=[]
        for row in rows[:100]:
            outputs=[]
            for artifact in json.loads(row['result_metadata']).get('artifacts',[])[:32]:
                if artifact.get('session_id')!=row['source_session'] or not isinstance(artifact.get('artifact_id'),str):continue
                try:outputs.append(self.resource(actor,bot,{'session_id':row['source_session'],'artifact_id':artifact['artifact_id']}))
                except PermissionError:continue
            inputs=[]
            for item in json.loads(row['input_files'])[:8]:
                try:
                    file=self.runtime.documents.get(row['source_session'],item['id'])
                    inputs.append({'session_id':row['source_session'],'attachment_id':file.id,'name':file.filename,'media_type':file.media_type})
                except (RepositoryError,KeyError):continue
            steps.append({'id':row['id'],'label':row['step_label'],'instruction':row['instruction'][:4000],
                          'status':row['actual_status'],'summary':row['result'][:4000],
                          'run_id':row['worker_run'],'todo_task_id':row['task_id'],'inputs':inputs,'outputs':outputs})
        # Execution order is evidence of sequence, not proof that one image edits another.
        return {'task':{k:value[k] for k in ('id','title','summary','source_session','archived','created_at','updated_at')},
                'steps':steps,'has_more_steps':len(rows)>100,'data_trust':'untrusted','coverage':'Recorded owned task steps; no inferred image ancestry'}

    def sync(self, actor, bot, *, after='', limit=1000):
        self.directory.scope(actor,{'bot_id':bot})
        with self.db.transaction() as db:
            rows=db.execute('''SELECT t.id,t.title,t.summary FROM messager_task_sessions t
                JOIN app_chat_sessions s ON s.session_id=t.source_session AND s.owner=t.actor
                WHERE t.actor=? AND t.bot_id=? AND s.registration=? AND json_extract(s.scope_json,'$.bot_id')=t.bot_id
                AND t.id>? ORDER BY t.id LIMIT ?''',(actor,bot,CHAT,after,limit+1)).fetchall()
        documents=[]
        for row in rows[:limit]:
            steps=self._steps(row['id'])[:100]
            text='\n'.join([row['title'],row['summary'][:4000],*[
                '\n'.join((r['step_label'],r['instruction'][:1000],r['result'][:2000],
                    ' '.join(str(a.get('filename','')) for a in json.loads(r['result_metadata']).get('artifacts',[])[:32]))) for r in steps]])[:64000]
            documents.append((row['id'],text))
        with self.db.transaction(write=True) as db:
            for ref,text in documents:
                old=db.execute('SELECT text FROM messager_history_index WHERE task_id=?',(ref,)).fetchone()
                if old and old[0]==text:continue
                db.execute('INSERT INTO messager_history_index VALUES(?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET text=excluded.text',(ref,actor,bot,text))
                db.execute('DELETE FROM messager_history_fts WHERE task_id=?',(ref,))
                db.execute('INSERT INTO messager_history_fts VALUES(?,?)',(ref,text))
        return {'processed':len(documents),'has_more':len(rows)>limit,'next':documents[-1][0] if len(rows)>limit else None}

    def search(self, actor, bot, query='', *, limit=20,offset=0,archived=False,index_after=''):
        if not isinstance(query,str) or len(query)>300 or not 1<=limit<=50 or not 0<=offset<=10000:
            raise ValueError('Invalid history query or page')
        coverage=self.sync(actor,bot,after=index_after)
        tokens=re.findall(r'\S+',query.strip().lower())[:12]
        params=[actor,bot,CHAT,int(archived)]
        condition=''
        if tokens:
            # Literal substrings support CJK and arbitrary punctuation without FTS query injection.
            condition=' AND '+' AND '.join('instr(lower(i.text),?)>0' for _ in tokens)
            params.extend(tokens)
        ordering='t.updated_at DESC,t.id'
        if tokens:
            ordering='CASE WHEN t.id IN (SELECT task_id FROM messager_history_fts WHERE messager_history_fts MATCH ?) THEN 0 ELSE 1 END,'+ordering
            params.append(' AND '.join(chr(34)+t.replace(chr(34),chr(34)*2)+chr(34) for t in tokens))
        with self.db.transaction() as db:
            rows=db.execute('''SELECT t.id,t.title,t.summary,t.updated_at,t.archived,
                COALESCE(r.status,j.status) AS status FROM messager_task_sessions t
                JOIN messager_history_index i ON i.task_id=t.id AND i.actor=t.actor AND i.bot_id=t.bot_id
                JOIN app_chat_sessions s ON s.session_id=t.source_session AND s.owner=t.actor
                JOIN messager_dialogue_jobs j ON j.id=t.last_job LEFT JOIN agent_runs r ON r.id=j.worker_run
                WHERE t.actor=? AND t.bot_id=? AND s.registration=? AND json_extract(s.scope_json,'$.bot_id')=t.bot_id
                AND t.archived=?'''+condition+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',(*params,limit+1,offset)).fetchall()
        return {'items':[{**dict(r),'summary':r['summary'][:600],'match_terms':tokens} for r in rows[:limit]],
                'has_more':len(rows)>limit,'next_offset':offset+limit if len(rows)>limit else None,
                'index':coverage,'data_trust':'untrusted','coverage':'Owned active conversations; explicit archived-task filter; index may require continuation'}
