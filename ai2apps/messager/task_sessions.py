"""Owner-owned logical work sessions; summaries are references, never authority."""
import json
import re
from datetime import UTC,datetime


def now():return datetime.now(UTC).isoformat()

_REFERENCE = re.compile(
    r"`{1,3}[\s\S]*?`{1,3}|(?<![A-Za-z0-9_/\\])/#(?P<reference>\"(?:[^\"\\\n]|\\[\"\\])*\"|[^\s\"<>`/，。！？：；、（）【】,.!?:;()\[\]]+)"
)
_CONTINUE = re.compile(r"^\s*(?:继续|续接|continue)\s*$", re.IGNORECASE)


class TaskSessions:
    def __init__(self,dialogue):
        self.dialogue,self.db=dialogue,dialogue.db
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_task_sessions(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot_id TEXT NOT NULL,source_session TEXT NOT NULL,
                title TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',pinned INTEGER NOT NULL DEFAULT 0,
                archived INTEGER NOT NULL DEFAULT 0,halted INTEGER NOT NULL DEFAULT 0,
                last_job TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS messager_job_sessions(job_id TEXT PRIMARY KEY,session_id TEXT NOT NULL)')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_job_amendments(
                source_run TEXT PRIMARY KEY,target_job TEXT NOT NULL,text TEXT NOT NULL,files_json TEXT NOT NULL,created_at TEXT NOT NULL)''')
            # Each pre-existing job was an independent work session.
            for row in db.execute('SELECT * FROM messager_dialogue_jobs WHERE id NOT IN (SELECT job_id FROM messager_job_sessions)').fetchall():
                stamp=now();db.execute('INSERT OR IGNORE INTO messager_task_sessions(id,actor,bot_id,source_session,title,last_job,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(row['id'],row['actor'],row['bot_id'],row['source_session'],row['title'],row['id'],stamp,stamp))
                db.execute('INSERT OR IGNORE INTO messager_job_sessions VALUES(?,?)',(row['id'],row['id']))

    def get(self,actor,bot_id,ref,source_session=None):
        self.dialogue.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_task_sessions WHERE id=? AND actor=? AND bot_id=?',(ref,actor,bot_id)).fetchone()
        if not row or source_session and row['source_session']!=source_session:raise PermissionError('Task session unavailable')
        return dict(row)

    def search_references(self, actor, bot_id, sid, query):
        query = query.strip()[:200]
        with self.db.transaction() as db:
            return [dict(row) for row in db.execute(
                """SELECT id,title,archived FROM messager_task_sessions
                   WHERE actor=? AND bot_id=? AND source_session=?
                     AND (instr(lower(title), lower(?)) > 0 OR instr(id, ?) > 0 OR ? = '')
                   ORDER BY archived, pinned DESC, updated_at DESC, id LIMIT 8""",
                (actor, bot_id, sid, query, query, query),
            )]

    def references(self, actor, bot_id, sid, text, language):
        references = {}
        continuation = None
        matches = [match for match in _REFERENCE.finditer(text) if match.group("reference")]
        zh = language.startswith("zh")
        if re.match(r"^\s*(?:继续|续接|continue)\s+/#", text, re.IGNORECASE) and (
            not matches or not _CONTINUE.fullmatch(text[:matches[0].start()])
        ):
            raise ValueError("请在 /# 后输入任务名称或 ID。" if zh else "Enter a task name or ID after /#.")
        if len(matches) > 8:
            raise ValueError("每条消息最多引用 8 项任务。" if zh else "Reference up to 8 tasks per message.")
        with self.db.transaction() as db:
            for match in matches:
                token = match.group("reference")
                value = json.loads(token) if token.startswith('"') else token
                rows = db.execute(
                    """SELECT * FROM messager_task_sessions
                       WHERE actor=? AND bot_id=? AND source_session=? AND (id=? OR title=?)
                       ORDER BY (id=?) DESC LIMIT 2""",
                    (actor, bot_id, sid, value, value, value),
                ).fetchall()
                if not rows:
                    raise ValueError("找不到引用的任务，请检查名称或 ID。" if zh else "Task reference not found. Check its name or ID.")
                row = rows[0]
                if row["id"] != value and len(rows) > 1:
                    raise ValueError("有同名任务，请从候选列表选择或使用任务 ID。" if zh else "Multiple tasks have this name. Pick one from the list or use its ID.")
                ref = row["id"]
                references[ref] = self.project(dict(row))
                if _CONTINUE.fullmatch(text[:match.start()]):
                    continuation = ref
        return list(references.values()), continuation

    def for_job(self,ref):
        with self.db.transaction() as db:row=db.execute('SELECT s.* FROM messager_task_sessions s JOIN messager_job_sessions j ON j.session_id=s.id WHERE j.job_id=?',(ref,)).fetchone()
        return dict(row) if row else None

    def link(self,job,target=None):
        stamp=now();ref=target or job['id']
        with self.db.transaction(write=True) as db:
            linked=db.execute('SELECT session_id FROM messager_job_sessions WHERE job_id=?',(job['id'],)).fetchone()
            if linked:return linked[0]
            db.execute('INSERT OR IGNORE INTO messager_task_sessions(id,actor,bot_id,source_session,title,last_job,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)',(ref,job['actor'],job['bot_id'],job['source_session'],job['title'],job['id'],stamp,stamp))
            db.execute('INSERT OR IGNORE INTO messager_job_sessions VALUES(?,?)',(job['id'],ref))
            db.execute('UPDATE messager_task_sessions SET last_job=?,updated_at=?,archived=0 WHERE id=?',(job['id'],stamp,ref))
        return ref

    def recent(self,actor,bot_id,sid,*,archived=False,limit=20,offset=0,include_runs=False):
        self.dialogue.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:rows=db.execute('SELECT * FROM messager_task_sessions WHERE actor=? AND bot_id=? AND source_session=? AND archived=? ORDER BY pinned DESC,updated_at DESC,id LIMIT ? OFFSET ?',(actor,bot_id,sid,int(archived),max(1,min(100,limit)),max(0,offset))).fetchall()
        return [self.project(dict(row), include_runs=include_runs) for row in rows]

    def project(self, value, *, include_runs=False):
        job=self.dialogue.row(value['last_job']);status=job['status']
        worker=self.dialogue.runtime.agents.get_run(job['worker_run']) if job['worker_run'] else None
        if worker:status=worker.status.value
        summary=value['summary'][:600]
        if worker and (worker.error or {}).get('code')=='session_memory_unavailable':
            from .presentation import result_content
            summary=result_content('',status='failed',error_code='session_memory_unavailable')
        runs=self.runs(value['id']) if include_runs else []
        live=next((r for r in runs if r['status'] not in ('completed','failed','cancelled','interrupted','timed_out')),None)
        if live:status=live['status']
        delegation=getattr(self.dialogue.runtime,'messager_bot_delegation',None)
        if delegation and delegation.waiting(value['last_job']):status='waiting_collaboration'
        if value['halted']:
            failed=next((r for r in runs if r['status'] in ('failed','interrupted','timed_out')),None)
            status=failed['status'] if failed else (status if status in ('failed','interrupted','timed_out') else 'cancelled')
        return {**({'runs':runs,'run_count':self.count(value['id'])} if include_runs else {}),'id':value['id'],'title':value['title'],'summary':summary,'status':status,'pinned':bool(value['pinned']),'archived':bool(value['archived']),'last_job':value['last_job'],'updated_at':value['updated_at']}

    def count(self,ref):
        with self.db.transaction() as db:return db.execute('SELECT count(*) FROM messager_job_sessions WHERE session_id=?',(ref,)).fetchone()[0]

    def runs(self,ref):
        with self.db.transaction() as db:rows=db.execute('SELECT j.* FROM messager_dialogue_jobs j JOIN messager_job_sessions m ON m.job_id=j.id WHERE m.session_id=? ORDER BY j.rowid DESC LIMIT 100',(ref,)).fetchall()
        result=[]
        for row in reversed(rows):
            status=self.dialogue.runtime.agents.get_run(row['worker_run']).status.value if row['worker_run'] else row['status']
            result.append({'id':row['id'],'title':self.dialogue.label(row['id']),'status':status,'task_id':row['task_id'],'worker_run':row['worker_run']})
        return result

    def followups(self,job_id):
        with self.db.transaction() as db:return [dict(r) for r in db.execute("SELECT j.* FROM messager_dialogue_jobs j JOIN messager_job_sessions m ON m.job_id=j.id WHERE m.session_id=(SELECT session_id FROM messager_job_sessions WHERE job_id=?) AND j.rowid>(SELECT rowid FROM messager_dialogue_jobs WHERE id=?) AND j.status IN ('queued','running','waiting_input','waiting_capability') ORDER BY j.rowid",(job_id,job_id))]

    def manage(self,actor,bot_id,ref,action):
        value=self.get(actor,bot_id,ref)
        if action not in ('pin','unpin','archive','restore'):raise ValueError('Unknown task-session action')
        field='pinned' if action in ('pin','unpin') else 'archived';setting=int(action in ('pin','archive'))
        with self.db.transaction(write=True) as db:
            if action=='pin' and not value['pinned'] and db.execute('SELECT count(*) FROM messager_task_sessions WHERE actor=? AND bot_id=? AND pinned=1',(actor,bot_id)).fetchone()[0]>=20:raise ValueError('Unpin a task session first (limit 20)')
            if action=='archive':
                delegation=getattr(self.dialogue.runtime,'messager_bot_delegation',None)
                if delegation and delegation.waiting(value['last_job']):raise ValueError('Stop or finish collaboration before archiving')
                active=db.execute("SELECT 1 FROM messager_dialogue_jobs j JOIN messager_job_sessions m ON m.job_id=j.id WHERE m.session_id=? AND j.status IN ('queued','running','waiting_input','waiting_capability')",(ref,)).fetchone()
                if active:raise ValueError('Stop or finish this task before archiving')
            db.execute(f'UPDATE messager_task_sessions SET {field}=?,updated_at=? WHERE id=?',(setting,now(),ref))
        return self.get(actor,bot_id,ref)

    def amendments(self,ref):
        with self.db.transaction() as db:return [dict(r) for r in db.execute('SELECT * FROM messager_job_amendments WHERE target_job=? ORDER BY rowid',(ref,))]

    def instruction(self,ref):
        job=self.dialogue.row(ref);source=self.dialogue.runtime.agents.get_run(job['source_run'])
        text=source.input['prompt'];files=list(source.input.get('selected_materials',{}).get('files',[]))
        for amendment in self.amendments(ref):
            text+='\n\n用户补充要求 / Additional user instruction:\n'+amendment['text']
            files.extend(json.loads(amendment['files_json']))
        return text,list({f['id']:f for f in files}.values())

    def amend(self,target,source):
        with self.db.transaction() as db:existing=db.execute('SELECT target_job FROM messager_job_amendments WHERE source_run=?',(source.id,)).fetchone()
        if existing:return existing[0]==target
        job=self.dialogue.row(target)
        if job['worker_run'] or job['status']!='queued':return False
        self.dialogue.directory.permissions.validate(job['actor'],{'bot_id':job['bot_id']},self.dialogue.runtime.agents.get_run(job['source_run']).input['authorization'],None,{})
        text,files=self.instruction(target);extra=source.input.get('selected_materials',{}).get('files',[])
        if len(text)+len(source.input['prompt'])+80>16000 or len({f['id'] for f in [*files,*extra]})>8:return False
        with self.db.transaction(write=True) as db:
            db.execute('INSERT OR IGNORE INTO messager_job_amendments VALUES(?,?,?,?,?)',(source.id,target,source.input['prompt'],json.dumps(extra),now()))
            session=self.for_job(target)
            db.execute('UPDATE messager_task_sessions SET updated_at=? WHERE id=?',(now(),session['id']))
        return True

    def summarize(self,ref,text):
        with self.db.transaction(write=True) as db:db.execute('UPDATE messager_task_sessions SET summary=?,updated_at=? WHERE id=(SELECT session_id FROM messager_job_sessions WHERE job_id=?) AND last_job=?',(str(text)[:1200],now(),ref,ref))

    def halt(self,ref):
        session=self.for_job(ref)
        if session:
            with self.db.transaction(write=True) as db:db.execute('UPDATE messager_task_sessions SET halted=1,updated_at=? WHERE id=?',(now(),session['id']))
        return session
