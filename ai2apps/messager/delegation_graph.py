"""Messager-owned dependency graph and reviewed model allowances."""
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from ai2apps.agents.artifact_outputs import output_artifacts
from ai2apps.agents.models import CompleteAction
from ai2apps.agents.token_budget import budget_decision, token_allowance, total_model_tokens
from .tasks import CHAT
from .task_tree_access import MODEL

ACTIVE=('pending','admitting','running')
BASE_MODEL_TOKENS = 64_000
# Keep the original capacity of eight base reservations for child/resume rounds.
POLICY={'max_depth':3,'max_edges':8,'max_model_tokens':8*BASE_MODEL_TOKENS,'round_model_tokens':BASE_MODEL_TOKENS,'max_tool_calls':36,'timeout_seconds':600,'round_steps':24}

class DelegationGraph:
    def __init__(self,service):
        self.service,self.runtime,self.db=service,service.runtime,service.db
        with self.db.transaction(write=True) as db:
            # Deadline checks run for each visible Tool. Limit the join to this
            # graph's authorizations and budget waits, not all historical cards.
            db.execute("""CREATE INDEX IF NOT EXISTS ix_delegation_authorization_root
                ON app_chat_run_authorizations(json_extract(authorization_json,'$.delegation_graph.root_id'))""")
            db.execute("""CREATE INDEX IF NOT EXISTS ix_delegation_budget_waits
                ON agent_interactions(run_id,created_at)
                WHERE json_extract(request_json,'$.collaboration_budget')=1""")
            db.execute('''CREATE TABLE IF NOT EXISTS messager_delegation_roots(id TEXT PRIMARY KEY,actor TEXT NOT NULL,bot TEXT NOT NULL,session TEXT NOT NULL,parent_job TEXT NOT NULL,policy_json TEXT NOT NULL,status TEXT NOT NULL,deadline REAL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_delegation_edges(id TEXT PRIMARY KEY,root TEXT NOT NULL,parent_edge TEXT,parent_session TEXT NOT NULL,source_bot TEXT NOT NULL,target_bot TEXT NOT NULL,depth INTEGER NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS messager_delegation_work(edge TEXT PRIMARY KEY,source_task TEXT NOT NULL,target_task TEXT NOT NULL,work_key TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_delegation_leases(root TEXT NOT NULL,lease TEXT PRIMARY KEY,tokens INTEGER NOT NULL,edge TEXT,phase TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_delegation_stops(root TEXT PRIMARY KEY,reason TEXT NOT NULL,initiator TEXT,status TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_delegation_calls(root TEXT NOT NULL,invocation TEXT NOT NULL,PRIMARY KEY(root,invocation))')
        self.runtime.tools.execution_guards.append(self);self.runtime.app_capability_router.execution_guards.append(self)
        logging.getLogger(__name__).info('Bot task dependency and reentry C4.1.1 loaded; source=%s',__file__)
        logging.getLogger(__name__).info('Bot bounded multilevel delegation C4.1 loaded; source=%s',__file__)

    def edge(self,ref):
        with self.db.transaction() as db:r=db.execute('SELECT * FROM messager_delegation_edges WHERE id=?',(ref,)).fetchone()
        return dict(r) if r else None

    def root(self,ref):
        with self.db.transaction() as db:r=db.execute('SELECT * FROM messager_delegation_roots WHERE id=?',(ref,)).fetchone()
        if r is None:raise PermissionError('Collaboration root unavailable')
        return dict(r)

    def chain(self,edge):
        result=[];seen=set()
        while edge:
            if edge['id'] in seen or len(seen)>=POLICY['max_depth']:raise PermissionError('Invalid collaboration dependency graph')
            seen.add(edge['id']);result.append(edge);edge=self.edge(edge['parent_edge']) if edge['parent_edge'] else None
        return list(reversed(result))

    def check(self,root,*,started=False):
        r=self.root(root)
        if r['status']!='active':raise PermissionError('Collaboration stopped or its shared deadline expired')
        if r['deadline'] is not None and self.execution_deadline(r)<=time.time():
            raise PermissionError('Collaboration stopped or its shared deadline expired')
        if started and r['deadline'] is None:raise PermissionError('Collaboration has not been approved')
        self.runtime.messager_bots.scope(r['actor'],{'bot_id':r['bot']})
        b=self.runtime.app_chat.binding(r['session'])
        if not b or b['owner']!=r['actor'] or b['registration']!=CHAT or b['scope']!={'bot_id':r['bot']}:raise PermissionError('Original collaboration conversation unavailable')
        parent=self.runtime.messager_dialogue.sessions.for_job(r['parent_job'])
        if parent:
            if parent['halted']:raise PermissionError('Original collaboration task stopped')
        else:
            with self.db.transaction() as db:
                todo=db.execute('SELECT 1 FROM messager_task_runs WHERE todo_run_id=? AND actor=? AND bot_id=? AND agent_run_id=?',
                                (r['parent_job'],r['actor'],r['bot'],r['id'])).fetchone()
            if not todo:raise PermissionError('Original collaboration task unavailable')
            run=self.runtime.agents.get_run(r['id'])
            if run.cancel_requested or run.status.value in ('completed','failed','cancelled','interrupted','timed_out'):
                raise PermissionError('Original collaboration task stopped')
        return r

    def execution_deadline(self, root):
        """Exclude time spent awaiting an owner budget decision from the shared clock."""
        with self.db.transaction() as db:
            waits=db.execute("""SELECT i.created_at, i.deadline_at, i.resolved_at, i.status
                FROM app_chat_run_authorizations a JOIN agent_interactions i ON i.run_id=a.run_id
                WHERE json_extract(a.authorization_json,'$.delegation_graph.root_id')=?
                  AND json_extract(i.request_json,'$.collaboration_budget')=1
                ORDER BY i.created_at""",(root['id'],)).fetchall()
        deadline=root['deadline']
        now=time.time()
        previous_end=0
        for wait in waits:
            start=datetime.fromisoformat(wait['created_at']).timestamp()
            if start>=deadline:
                break
            expiry=datetime.fromisoformat(wait['deadline_at']).timestamp()
            resolved=(datetime.fromisoformat(wait['resolved_at']).timestamp()
                      if wait['resolved_at'] else now if wait['status']=='pending' else expiry)
            end=min(resolved,expiry,now)
            deadline+=max(0,end-max(start,previous_end))
            previous_end=max(previous_end,end)
        return deadline

    def can_delegate(self,row):
        edge=self.edge(row['id'])
        if not edge or row['status'] not in ('admitting','running') or not json.loads(row['value_json']).get('allow_subdelegation'):return False
        root=self.check(edge['root'],started=True)
        return edge['depth']<json.loads(root['policy_json'])['max_depth']

    def insert(self,db,row,parent,logical):
        """Called in the proposal's transaction under the host admission lock."""
        v=json.loads(row['value_json'])
        edge=self.edge(parent['id']) if parent else None
        if parent and not self.can_delegate(parent):raise PermissionError('This delegation does not permit further work assignment')
        if parent and json.loads(parent['value_json']).get('batch_id'):raise PermissionError('Fixed background plans cannot expand their participant scope')
        if edge:
            root=self.check(edge['root'],started=True);depth=edge['depth']+1
        else:
            root={'id':v['root_run'],'actor':row['actor'],'bot':row['source_bot'],'session':row['source_session'],'parent_job':row['parent_job'],'policy_json':json.dumps(POLICY),'status':'active','deadline':None};depth=1
            old=db.execute('SELECT * FROM messager_delegation_roots WHERE id=?',(root['id'],)).fetchone()
            if old:
                root=dict(old)
                if root['actor']!=row['actor'] or root['status']!='active':raise PermissionError('Original collaboration root is closed')
                depth=1
        policy=json.loads(root['policy_json'])
        if db.execute('SELECT count(*) FROM messager_delegation_edges WHERE root=?',(root['id'],)).fetchone()[0]>=policy['max_edges']:raise ValueError('Collaboration edge budget exhausted')
        if depth>policy['max_depth']:raise ValueError('Collaboration depth limit reached')
        source_task=self.node_for_job(row['parent_job'],logical)
        target_task='work:'+row['id']
        self.check_wait(db,row['actor'],source_task,target_task,exclude=row['id'])
        if edge:
            for ancestor in self.chain(edge):
                prior=self.work(ancestor['id'])
                if prior and prior['work_key']==v['work_fingerprint']:
                    raise ValueError('Repeated unchanged work on this dependency branch; refine the subtask, inputs or deliverable instead of delegating the same work again')
        db.execute('INSERT OR IGNORE INTO messager_delegation_roots VALUES(?,?,?,?,?,?,?,?)',tuple(root[k] for k in ('id','actor','bot','session','parent_job','policy_json','status','deadline')))
        db.execute('INSERT INTO messager_delegation_edges VALUES(?,?,?,?,?,?,?)',(row['id'],root['id'],edge['id'] if edge else None,logical,row['source_bot'],row['target_bot'],depth))
        db.execute('INSERT INTO messager_delegation_work VALUES(?,?,?,?)',(row['id'],source_task,target_task,v.get('work_fingerprint','legacy:'+row['id'])))
        return root,depth

    def work(self,ref):
        with self.db.transaction() as db:r=db.execute('SELECT * FROM messager_delegation_work WHERE edge=?',(ref,)).fetchone()
        if r:return dict(r)
        edge=self.edge(ref)
        if not edge:return None
        return {'edge':ref,'source_task':'work:'+edge['parent_edge'] if edge['parent_edge'] else 'task:'+edge['parent_session'],'target_task':'work:'+ref,'work_key':'legacy:'+ref}

    def node_for_job(self,job,logical=None):
        incoming=self.service.child(job)
        if incoming:return 'work:'+incoming['id']
        session=self.runtime.messager_dialogue.sessions.for_job(job)
        return 'task:'+(session['id'] if session else logical or job)

    def check_wait(self,db,actor,source,target,*,exclude=None):
        # Nodes identify independent work, never a Bot, Tool or model identity.
        graph={}
        rows=db.execute("SELECT * FROM messager_bot_delegations WHERE actor=? AND id!=? AND status IN ('pending','admitting','running')",(actor,exclude or '')).fetchall()
        for row in rows:
            work=self.work(row['id'])
            if work:parent,child=work['source_task'],work['target_task']
            else:
                parent=self.node_for_job(row['parent_job'])
                child=self.node_for_job(row['child_job']) if row['child_job'] else 'work:'+row['id']
            graph.setdefault(parent,set()).add(child)
        todo=[target];seen=set()
        while todo:
            current=todo.pop()
            if current==source:raise ValueError('Task wait cycle: '+source+' -> '+target+' reaches the waiting task '+source)
            if current not in seen:seen.add(current);todo.extend(graph.get(current,()))


    def validate_edge(self,row):
        edge=self.edge(row['id'])
        if not edge:return None
        root=self.check(edge['root'])
        for ancestor in self.chain(edge)[:-1]:
            parent=self.service.row(ancestor['id'])
            if parent['status']!='running':raise PermissionError('Upstream collaboration is no longer active')
            self.service.validate(parent)
            value=json.loads(row['value_json'])
            if value.get('access_model')!=MODEL:
                allowed=json.loads(parent['value_json'])['allowed']
                if any(allowed.get(k)!=v for k,v in value['allowed'].items()):
                    raise PermissionError('A child cannot widen legacy upstream access')
        return root

    def reserve(self,row,key,*,resume=False):
        edge=self.edge(row['id'])
        if not edge:return None
        if row['status'] not in ('admitting','running'):raise PermissionError('Only an approved collaboration round can reserve budget')
        with self.runtime.app_chat.lock:
            root=self.check(edge['root']);policy=json.loads(root['policy_json'])
            deadline=self.execution_deadline(root) if root['deadline'] is not None else None
            with self.db.transaction(write=True) as db:
                if root['deadline'] is None:
                    deadline=time.time()+policy['timeout_seconds'];db.execute('UPDATE messager_delegation_roots SET deadline=? WHERE id=? AND deadline IS NULL',(deadline,root['id']))
                old=db.execute('SELECT * FROM messager_delegation_leases WHERE lease=?',(key,)).fetchone()
                if not old:
                    # Each lease has one base reservation. Confirmed top-ups
                    # belong to that lease and add to the shared allowance.
                    used=db.execute('SELECT count(*) FROM messager_delegation_leases WHERE root=?',(root['id'],)).fetchone()[0]*policy['round_model_tokens']
                    if used+policy['round_model_tokens']>policy['max_model_tokens']:raise PermissionError('Shared collaboration model allowance exhausted')
                    db.execute('INSERT INTO messager_delegation_leases VALUES(?,?,?,?,?)',(root['id'],key,policy['round_model_tokens'],edge['parent_edge'] if resume else edge['id'],'resume' if resume else 'child'))
                elif old['root']!=root['id']:raise PermissionError('Budget receipt belongs to another collaboration')
            remaining=int(deadline-time.time())
            if remaining<1:raise PermissionError('Shared collaboration deadline expired')
            return {'root_id':root['id'],'lease':key}, {'max_steps':policy['round_steps'],'timeout_seconds':remaining,'max_model_tokens':policy['round_model_tokens']}

    def frozen(self,run):return (self.runtime.app_chat.execution_authorization(run.id) or {}).get('delegation_graph')

    def checkpoint(self,binding,ctx,*,finishing=False):
        grant=self.frozen(ctx.run)
        if not grant:return
        with self.runtime.app_chat.lock:
            root=self.check(grant['root_id'],started=True)
            policy=json.loads(root['policy_json'])
            # Only this owner's durable token prompts can extend a graph lease.
            scoped=replace(ctx,interactions=tuple(item for item in ctx.interactions
                if item.request.get('collaboration_budget') is True))
            base,limit=token_allowance(scoped)
            with self.db.transaction() as db:
                lease=db.execute('SELECT tokens FROM messager_delegation_leases WHERE root=? AND lease=?',
                                 (root['id'],grant['lease'])).fetchone()
            if not lease:
                raise PermissionError('Collaboration round has no budget receipt')
            if limit>lease['tokens']:
                with self.db.transaction(write=True) as db:
                    db.execute('UPDATE messager_delegation_leases SET tokens=? WHERE lease=?',
                               (limit,grant['lease']))
            if len(ctx.steps)>=policy['round_steps']:
                self.stop(root['id'],'Shared collaboration round step allowance exhausted')
                raise PermissionError('Collaboration step limit reached')
            if finishing:
                return None
            used=total_model_tokens(ctx.steps)
            action=budget_decision(scoped,used)
            if isinstance(action,CompleteAction):
                return CompleteAction({**action.output,'collaboration_budget_stopped':True,'artifacts':
                    output_artifacts(ctx.steps,self.runtime.workspace,ctx.run.session_id)})
            if action is not None:
                return replace(action,
                    prompt=f'本轮协作已使用 {used:,} tokens。继续会追加 {base:,} tokens，从当前步骤接着执行。也可以结束并保留已有结果。',
                    request={**action.request,'collaboration_budget':True})

    def binding(self,context):
        if not context.trace_id:return None
        b=self.runtime.app_chat.binding(context.session_id)
        if not b or b['registration']!=CHAT:return None
        run=self.runtime.agents.get_run(context.trace_id)
        if run.session_id!=context.session_id:raise PermissionError('Collaboration Run identity mismatch')
        grant=self.frozen(run)
        if grant:
            if run.cancel_requested or run.status.value in ('completed','failed','cancelled','interrupted','timed_out'):raise PermissionError('Collaboration Run is no longer active')
            root=self.check(grant['root_id'],started=True)
            if context.actor_user_id!=root['actor']:raise PermissionError('Collaboration actor mismatch')
            return root
        return None

    def visible(self,context,name):return True
    def authorize(self,context,name,args):self.binding(context)
    @contextmanager
    def scope(self,context):
        root=self.binding(context)
        if root:
            if not context.invocation_id:raise PermissionError('Collaboration needs an invocation receipt')
            with self.db.transaction(write=True) as db:
                if not db.execute('SELECT 1 FROM messager_delegation_calls WHERE root=? AND invocation=?',(root['id'],context.invocation_id)).fetchone():
                    if db.execute('SELECT count(*) FROM messager_delegation_calls WHERE root=?',(root['id'],)).fetchone()[0]>=json.loads(root['policy_json'])['max_tool_calls']:raise PermissionError('Shared collaboration Tool budget exhausted')
                    db.execute('INSERT INTO messager_delegation_calls VALUES(?,?)',(root['id'],context.invocation_id))
        yield

    def stop(self,root,reason,*,initiator=None,status='cancelled'):
        with self.runtime.app_chat.lock:
            r=self.root(root)
            if r['status']=='completed':return
            with self.db.transaction(write=True) as db:
                db.execute('INSERT OR IGNORE INTO messager_delegation_stops VALUES(?,?,?,?)',(root,reason,initiator,status))
                receipt=db.execute('SELECT * FROM messager_delegation_stops WHERE root=?',(root,)).fetchone()
                reason,initiator,status=receipt['reason'],receipt['initiator'],receipt['status']
                db.execute("UPDATE messager_delegation_roots SET status='stopped' WHERE id=?",(root,))
                rows=[dict(x) for x in db.execute("SELECT d.* FROM messager_bot_delegations d JOIN messager_delegation_edges e ON e.id=d.id WHERE e.root=? AND d.status IN ('pending','admitting','running')",(root,))]
                jobs=[dict(x) for x in db.execute("SELECT j.* FROM messager_dialogue_jobs j JOIN agent_runs a ON a.id=j.source_run WHERE json_extract(a.input_json,'$.authorization.delegation_graph.root_id')=?",(root,))]
                db.execute("UPDATE messager_dialogue_jobs SET status='cancelled' WHERE status='queued' AND id IN (SELECT j.id FROM messager_dialogue_jobs j JOIN agent_runs a ON a.id=j.source_run WHERE json_extract(a.input_json,'$.authorization.delegation_graph.root_id')=?)",(root,))
            for row in rows:self.service.stop(row,status if row['id']==initiator else 'cancelled',reason,propagate=False)
            d=self.runtime.messager_dialogue;d.sessions.halt(r['parent_job'])
            for job in jobs:
                d.sessions.halt(job['id'])
                if job['worker_run']:self.runtime.agents.request_cancel(job['worker_run'])
            self.runtime.agent_runtime.wake()

    def observe(self,job):
        d=self.runtime.messager_dialogue;source=self.runtime.agents.get_run(job['source_run']);grant=source.input.get('authorization',{}).get('delegation_graph')
        if not grant or not job['worker_run']:return
        run=self.runtime.agents.get_run(job['worker_run'])
        if run.status.value in ('failed','cancelled','interrupted','timed_out'):self.stop(grant['root_id'],'A collaboration execution stopped');return
        with self.db.transaction() as db:lease=db.execute('SELECT * FROM messager_delegation_leases WHERE lease=?',(grant['lease'],)).fetchone()
        if run.status.value=='completed' and lease and lease['phase']=='resume' and lease['edge'] is None:
            if (run.output or {}).get('collaboration_budget_stopped'):
                self.stop(grant['root_id'],'已选择结束协作并保留已有结果。')
                return
            with self.db.transaction(write=True) as db:
                pending=db.execute("SELECT 1 FROM messager_delegation_edges e JOIN messager_bot_delegations d ON d.id=e.id WHERE e.root=? AND d.status IN ('pending','admitting','running')",(grant['root_id'],)).fetchone()
                if not pending:db.execute("UPDATE messager_delegation_roots SET status='completed' WHERE id=? AND status='active'",(grant['root_id'],))

    def recover(self):
        # Replay cleanup receipts even when every remaining edge is only pending.
        with self.db.transaction() as db:
            stopped=db.execute('''SELECT s.* FROM messager_delegation_stops s JOIN messager_delegation_roots r ON r.id=s.root
                WHERE EXISTS (SELECT 1 FROM messager_delegation_edges e JOIN messager_bot_delegations d ON d.id=e.id WHERE e.root=s.root AND d.status IN ('pending','admitting','running'))
                OR EXISTS (SELECT 1 FROM messager_job_sessions m JOIN messager_task_sessions t ON t.id=m.session_id WHERE m.job_id=r.parent_job AND t.halted=0)
                OR EXISTS (SELECT 1 FROM messager_dialogue_jobs j JOIN agent_runs a ON a.id=j.source_run LEFT JOIN messager_job_sessions m ON m.job_id=j.id LEFT JOIN messager_task_sessions t ON t.id=m.session_id
                    WHERE json_extract(a.input_json,'$.authorization.delegation_graph.root_id')=s.root AND (j.status IN ('queued','running') OR t.halted=0)) LIMIT 100''').fetchall()
        for receipt in stopped:self.stop(receipt['root'],receipt['reason'],initiator=receipt['initiator'],status=receipt['status'])
