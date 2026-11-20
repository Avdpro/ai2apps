"""Authorization for one Bot task execution and its descendants."""
import json

from ai2apps.core import utc_now


MODEL = 'task-tree/v1'
APPROVAL_PRIORITY = {'manual': 0, 'ai': 1, 'always': 2}

# Resolve continuations through owner records, never through a model-supplied
# task ID or the conversation's most recent task.
_TASK_HISTORY = '''FROM messager_dialogue_jobs current
    JOIN messager_job_sessions link ON link.job_id=current.id
    JOIN messager_task_sessions task ON task.id=link.session_id
    JOIN messager_job_sessions history ON history.session_id=task.id
    JOIN messager_dialogue_jobs prior ON prior.id=history.job_id AND prior.rowid<current.rowid
         AND prior.actor=task.actor AND prior.bot_id=task.bot_id AND prior.source_session=task.source_session'''
_TASK_OWNER = '''current.source_run=? AND current.actor=? AND task.actor=current.actor
    AND task.bot_id=current.bot_id AND task.source_session=current.source_session AND task.halted=0'''


class TaskTreeAccess:
    def __init__(self, runtime):
        self.runtime = runtime
        self.db = runtime.database
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_task_tree_grants(
                actor TEXT NOT NULL, root TEXT NOT NULL, target TEXT NOT NULL,
                pins_json TEXT NOT NULL, approved_at TEXT NOT NULL,
                PRIMARY KEY(actor,root,target))''')

    @property
    def access(self):
        return self.runtime.messager_bot_app_access

    @property
    def policy(self):
        return self.runtime.messager_task_execution.access

    def snapshot(self, actor, bot, authorization):
        return {
            pid: provider.version for pid, provider in self.policy.pool().items()
            if not self.access.blocked(actor, bot, provider)
            and (authorization['providers'].get(pid) == provider.version
                 or self.access.granted(actor, bot, provider, include_special=True))
        }

    def path(self, actor, bot, parent, receiver):
        members = {**parent, **receiver}
        return {
            pid: provider.version for pid, provider in self.policy.pool().items()
            if members.get(pid) == provider.version and not self.access.blocked(actor, bot, provider)
        }

    def context(self, actor, scope, frozen):
        root_id = frozen.get('task_tree_root')
        if not root_id:
            return None
        if scope.get('todo_run_id')==root_id:
            self.runtime.messager_task_execution.task_scope(actor,scope)
            return root_id, scope['bot_id']
        if not scope.get('dialogue_job'):
            raise PermissionError('Task tree requires a task execution scope')
        graph_id=frozen.get('delegation_graph',{}).get('root_id',root_id)
        graph = self.runtime.messager_bot_delegation.graph
        with self.db.transaction() as db:
            graph_exists = db.execute('SELECT 1 FROM messager_delegation_roots WHERE id=?', (graph_id,)).fetchone()
        if graph_exists:
            root = graph.check(graph_id)
            if root['actor'] != actor:
                raise PermissionError('Task tree belongs to another user')
            return root_id, root['bot']
        with self.db.transaction() as db:
            job = db.execute('''SELECT j.bot_id FROM messager_dialogue_jobs j
                JOIN messager_job_sessions candidate ON candidate.job_id=j.id
                JOIN messager_job_sessions current ON current.session_id=candidate.session_id
                JOIN messager_task_sessions task ON task.id=current.session_id
                WHERE j.source_run=? AND j.actor=? AND j.bot_id=? AND task.halted=0
                      AND current.job_id=?''',
                             (root_id, actor, scope['bot_id'], scope['dialogue_job'])).fetchone()
        if not job:
            raise PermissionError('Task tree authorization no longer matches the execution')
        return root_id, job['bot_id']

    def approval_chain(self, actor, scope, frozen, root):
        bot = scope['bot_id']
        delegation = self.runtime.messager_bot_delegation
        child = delegation.child(scope.get('dialogue_job')) if scope.get('dialogue_job') else None
        if child:
            edge = delegation.graph.edge(child['id'])
            graph_id = frozen.get('delegation_graph', {}).get('root_id')
            if not edge or edge['root'] != graph_id or child['target_bot'] != bot or child['actor'] != actor:
                raise PermissionError('Task approval does not match its delegation path')
            chain = [root[1], *(item['target_bot'] for item in delegation.graph.chain(edge))]
        else:
            if root[1] != bot:
                raise PermissionError('Task approval does not match its root Bot')
            chain = [bot]
        rules = {item: self.access.approval_rule(actor, item) for item in dict.fromkeys(chain)}
        strongest = max(rules.values(), key=lambda rule: APPROVAL_PRIORITY[rule['mode']])
        return {**strongest, 'chain_revisions': {item: rule['revision'] for item, rule in rules.items()}}

    def approval_goal(self, scope, frozen, run):
        graph_id = frozen.get('delegation_graph', {}).get('root_id')
        if graph_id:
            return self.runtime.agents.get_run(graph_id).input.get('prompt', '')
        if scope.get('dialogue_job'):
            return self.runtime.agents.get_run(frozen['task_tree_root']).input.get('prompt', '')
        return run.input.get('prompt', '')

    def approval_context(self, actor, root):
        with self.db.transaction() as db:
            current = db.execute('''SELECT task.title, label.label FROM messager_dialogue_jobs current
                JOIN messager_job_sessions link ON link.job_id=current.id
                JOIN messager_task_sessions task ON task.id=link.session_id
                LEFT JOIN messager_job_labels label ON label.job_id=current.id
                WHERE ''' + _TASK_OWNER, (root, actor)).fetchone()
            if not current:
                return {}
            first = db.execute('SELECT source.input_json ' + _TASK_HISTORY
                               + ' LEFT JOIN agent_runs source ON source.id=prior.source_run WHERE '
                               + _TASK_OWNER + ' ORDER BY prior.rowid LIMIT 1', (root, actor)).fetchone()
            last = db.execute('SELECT worker.output_json ' + _TASK_HISTORY
                              + ' LEFT JOIN agent_runs worker ON worker.id=prior.worker_run WHERE '
                              + _TASK_OWNER + ' ORDER BY prior.rowid DESC LIMIT 1', (root, actor)).fetchone()
        context = {'task_title': current['title'], 'requested_step': current['label']}
        if first and first['input_json']:
            context['original_request'] = json.loads(first['input_json']).get('prompt', '')
        if last and last['output_json']:
            context['previous_result'] = json.loads(last['output_json']).get('content', '')
        return context

    def granted(self, actor, root, provider):
        target = self.access.target(provider)
        with self.db.transaction() as db:
            rows = db.execute('SELECT pins_json FROM messager_task_tree_grants WHERE actor=? AND root=? AND target=?',
                              (actor, root, target)).fetchall()
            pin = self.policy.pin(provider)
            if any(json.loads(row['pins_json']).get(provider.id) == pin for row in rows):
                return True
            rows = db.execute('SELECT grant_row.pins_json ' + _TASK_HISTORY + '''
                JOIN messager_task_tree_grants grant_row ON grant_row.root=prior.source_run
                    AND grant_row.actor=prior.actor
                WHERE ''' + _TASK_OWNER + ' AND grant_row.target=?', (root, actor, target)).fetchall()
        return any(json.loads(row['pins_json']).get(provider.id) == pin for row in rows)

    def revoke_dialogue_grants(self, db, actor, bot, target=None):
        db.execute('''DELETE FROM messager_task_tree_grants WHERE actor=?
            AND root IN (SELECT source_run FROM messager_dialogue_jobs WHERE actor=? AND bot_id=?)
            AND (? IS NULL OR target=?)''', (actor, actor, bot, target, target))

    def grant(self, actor, root, target, frozen):
        # An App approval covers the ordinary, currently declared AaATs of that
        # App/Mini-App that were in the requesting Run's discovery snapshot.
        pins = {}
        for provider in self.policy.pool().values():
            if self.access.target(provider) != target:
                continue
            pin = self.policy.pin(provider)
            admitted_pin = frozen.get('discovery_pins', {}).get(provider.id)
            admitted_version = frozen.get('discovery_providers', {}).get(provider.id)
            admitted_tool = frozen.get('discovery_tools', {}).get(provider.capability)
            if admitted_pin == pin or (admitted_version == provider.version and
                                      admitted_tool == pin['tool_revision']):
                pins[provider.id] = pin
        if not pins:
            raise PermissionError('The requested App is outside the admitted task catalog')
        with self.db.transaction(write=True) as db:
            row = db.execute('SELECT pins_json FROM messager_task_tree_grants WHERE actor=? AND root=? AND target=?',
                             (actor, root, target)).fetchone()
            if row:
                pins = {**json.loads(row['pins_json']), **pins}
            db.execute('''INSERT INTO messager_task_tree_grants VALUES(?,?,?,?,?)
                ON CONFLICT(actor,root,target) DO UPDATE SET pins_json=excluded.pins_json''',
                       (actor, root, target, json.dumps(pins), utc_now()))

    def access_granted(self, actor, bot, frozen, root, provider):
        return (self.access.exempt(provider) or
                (not self.access.blocked(actor, bot, provider) and
                 (frozen.get('task_tree_providers', {}).get(provider.id) == provider.version
                  or self.granted(actor, root, provider))))
