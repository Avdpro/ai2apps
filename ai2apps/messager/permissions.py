"""Trusted Messager access profiles. Grants never infer safety from a Tool name."""
from dataclasses import dataclass
import json
import hashlib
import logging



@dataclass(frozen=True)
class ReadProfile:
    id: str
    app_id: str
    title_zh: str
    title_en: str
    tools: tuple[str, ...]
    effects: tuple[str,...]=()
    access: str='read'
    scope: str='owned_collection'


PROFILES = (
    ReadProfile('intelligence.read', 'ai2apps.intelligence', '已保存情报', 'Saved intelligence',
        ('intelligence.channels','intelligence.search','intelligence.news','intelligence.read')),
    ReadProfile('todo.read', 'ai2apps.todo', 'Todo 项目', 'Todo projects',
        ('todo.search','todo.get','todo.resolve_directory','todo.resolve_project','todo.project_stats','todo.children')),
    ReadProfile('todo.inbox.create','ai2apps.todo','创建普通待办（仅收件箱）','Create ordinary Todos (Inbox only)',
        ('todo.inbox.create',),('workspace.write',),'create','owned_inbox'),
    ReadProfile('messager.notice.create','ai2apps.messager','创建站内提醒（仅自己）','Create in-app reminders (self only)',
        ('messager.notice.create',),('workspace.write',),'create','self_local_inbox'),
)


class BotPermissions:
    def __init__(self, runtime, directory):
        self.runtime, self.directory, self.db = runtime, directory, runtime.database
        self.profiles = {p.id:p for p in PROFILES}
        logging.getLogger(__name__).info('Bot access profiles loaded; source=%s', __file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_permissions(
                bot_id TEXT PRIMARY KEY,actor TEXT NOT NULL,revision INTEGER NOT NULL,grants_json TEXT NOT NULL)''')
            rows = db.execute('SELECT id,actor FROM messager_bots').fetchall()
        for row in rows:
            self.ensure(row['actor'], row['id'])

    def providers(self, profile):
        """Exact owner, capability and declared effects must match the trusted profile."""
        values = []
        for name in profile.tools:
            provider = self.runtime.app_capability_router.providers.get(profile.app_id+'.'+name)
            if not provider or provider.app_id != profile.app_id or provider.mini_app_id is not None or provider.capability != name:
                continue
            try:
                tool = self.runtime.services.get_tool(name)
            except Exception:
                continue
            if set(tool.effects)!=set(profile.effects):
                continue
            values.append(provider)
        return values

    def ensure(self, actor, bot_id):
        with self.db.transaction() as db:
            if db.execute('SELECT 1 FROM messager_bot_permissions WHERE actor=? AND bot_id=?', (actor, bot_id)).fetchone():
                return
        # New Bots receive their default App rights from the App/Mini-App grant owner.
        grants = {}
        with self.db.transaction(write=True) as db:
            db.execute('INSERT OR IGNORE INTO messager_bot_permissions VALUES(?,?,1,?)', (bot_id, actor, json.dumps(grants)))

    def current(self, actor, bot_id):
        self.directory.scope(actor, {'bot_id':bot_id})
        with self.db.transaction() as db:
            row = db.execute('SELECT revision,grants_json FROM messager_bot_permissions WHERE actor=? AND bot_id=?', (actor, bot_id)).fetchone()
        if row is None:
            raise PermissionError('Bot access settings unavailable')
        return row['revision'], json.loads(row['grants_json'])

    def review_hash(self):
        declarations = [{**p.__dict__, 'providers':{v.id:v.version for v in self.providers(p)}} for p in self.profiles.values()]
        return hashlib.sha256(json.dumps(declarations,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

    def catalog(self, actor, bot_id):
        revision, grants = self.current(actor, bot_id)
        items = []
        for profile in self.profiles.values():
            providers = self.providers(profile)
            versions = {p.id:p.version for p in providers}
            grant = grants.get(profile.id, {})
            items.append({'id':profile.id,'app_id':profile.app_id,
                'title':{'zh':profile.title_zh,'en':profile.title_en}, 'access':profile.access,
                'scope':profile.scope,'effects':list(profile.effects),'available':bool(providers), 'capabilities':[p.capability for p in providers],
                'foreground':bool(grant.get('foreground')),'background':bool(grant.get('background')),
                'needs_review':bool(grant) and grant.get('providers') != versions})
        return {'revision':revision,'items':items,'review_hash':self.review_hash()}

    def save(self, actor, bot_id, revision, choices, *, review_hash):
        self.directory.scope(actor, {'bot_id':bot_id})
        if review_hash != self.review_hash():raise ValueError('App interfaces changed; reload and review again')
        if len({c['id'] for c in choices}) != len(choices):
            raise ValueError('Duplicate access profile')
        grants = {}
        for choice in choices:
            profile = self.profiles.get(choice['id'])
            if profile is None:
                raise ValueError('Unsupported access profile')
            if not choice['foreground'] and not choice['background']:
                continue
            providers = self.providers(profile)
            if not providers:
                raise ValueError('App interfaces are unavailable')
            grants[profile.id] = {'foreground':choice['foreground'],'background':choice['background'],
                'providers':{p.id:p.version for p in providers}}
        # Share admission's lock: grants and newly admitted executions have a clear order.
        with self.runtime.app_chat.lock, self.db.transaction(write=True) as db:
            if review_hash != self.review_hash():raise ValueError('App interfaces changed; reload and review again')
            row = db.execute('SELECT revision,grants_json FROM messager_bot_permissions WHERE actor=? AND bot_id=?', (actor, bot_id)).fetchone()
            if row is None or row['revision'] != revision:
                raise ValueError('Access settings changed; reload and review again')
            if json.loads(row['grants_json']) == grants:
                return self.catalog(actor, bot_id)
            db.execute('UPDATE messager_bot_permissions SET revision=revision+1,grants_json=? WHERE actor=? AND bot_id=?',
                (json.dumps(grants), actor, bot_id))
            runs = db.execute("""SELECT r.id FROM agent_runs r JOIN app_chat_sessions s ON s.session_id=r.session_id
                WHERE s.owner=? AND s.registration IN (?,?) AND json_extract(s.scope_json,'$.bot_id')=?
                AND r.status NOT IN ('completed','failed','cancelled','timed_out','interrupted')""",
                (actor,'ai2apps.messager.bots','ai2apps.messager.task-execution',bot_id)).fetchall()
        for run in runs:
            self.runtime.agents.request_cancel(run['id'])
        if runs:
            self.runtime.agent_runtime.wake()
        task_execution=getattr(self.runtime,'messager_task_execution',None)
        if task_execution:task_execution.revoke(actor,bot_id,legacy_only=True)
        communication=getattr(self.runtime,'messager_bot_communication',None)
        if communication:communication.revoke(actor,bot_id)
        delegation=getattr(self.runtime,'messager_bot_delegation',None)
        if delegation:delegation.revoke(actor,bot_id)
        return self.catalog(actor, bot_id)

    def revoke_all_grants(self, db, actor, bot_id):
        """Commit explicit revocation within the owner's content-cleanup transaction."""
        self.directory.scope(actor,{'bot_id':bot_id})
        db.execute("UPDATE messager_bot_permissions SET revision=revision+1,grants_json='{}' WHERE actor=? AND bot_id=?",(actor,bot_id))
        access=getattr(self.runtime,'messager_bot_app_access',None)
        if access:
            db.execute("UPDATE messager_bot_app_access SET revision=revision+1,grants_json='{}' WHERE actor=? AND bot_id=?",(actor,bot_id))
            access.tree.revoke_dialogue_grants(db,actor,bot_id)

    def invalidate(self, actor, bot_id, app_id=None, *, preserve_grants=False):
        """Expire admitted work; content cleanup can retain persistent Bot grants."""
        self.directory.scope(actor,{'bot_id':bot_id})
        with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            _,old=self.current(actor,bot_id)
            if preserve_grants and app_id:raise ValueError('Cannot preserve grants during App revocation')
            retained=old if preserve_grants else {k:v for k,v in old.items() if app_id and self.profiles[k].app_id!=app_id}
            db.execute('UPDATE messager_bot_permissions SET revision=revision+1,grants_json=? WHERE actor=? AND bot_id=?',(json.dumps(retained),actor,bot_id))
            access=getattr(self.runtime,'messager_bot_app_access',None)
            if access and not preserve_grants:
                access.tree.revoke_dialogue_grants(db,actor,bot_id,app_id)
            if not app_id and getattr(self.runtime,'messager_bot_app_access',None):
                if preserve_grants:db.execute('UPDATE messager_bot_app_access SET revision=revision+1 WHERE actor=? AND bot_id=?',(actor,bot_id))
                else:db.execute("UPDATE messager_bot_app_access SET revision=revision+1,grants_json='{}' WHERE actor=? AND bot_id=?",(actor,bot_id))
            runs=db.execute("""SELECT r.id FROM agent_runs r JOIN app_chat_sessions s ON s.session_id=r.session_id
                WHERE s.owner=? AND s.registration IN (?,?) AND json_extract(s.scope_json,'$.bot_id')=?
                AND r.status NOT IN ('completed','failed','cancelled','timed_out','interrupted')""",
                (actor,'ai2apps.messager.bots','ai2apps.messager.task-execution',bot_id)).fetchall()
        for run in runs:self.runtime.agents.request_cancel(run['id'])
        if runs:self.runtime.agent_runtime.wake()
        self.runtime.messager_task_execution.revoke(actor,bot_id,legacy_only=bool(app_id))
        communication=getattr(self.runtime,'messager_bot_communication',None)
        if communication:communication.revoke(actor,bot_id)
        delegation=getattr(self.runtime,'messager_bot_delegation',None)
        if delegation:delegation.revoke(actor,bot_id)

    def exported(self, scope):
        bot_id = scope['bot_id']
        with self.db.transaction() as db:
            row = db.execute('SELECT actor FROM messager_bots WHERE id=?', (bot_id,)).fetchone()
        if row is None:
            return ()
        _, grants = self.current(row['actor'], bot_id)
        app_access=getattr(self.runtime,'messager_bot_app_access',None)
        extra=app_access.exported(row['actor'],bot_id) if app_access else ()
        return (*extra,*(p for key,grant in grants.items() for p in self.providers(self.profiles[key])
            if (grant.get('foreground') or grant.get('background')) and grant.get('providers',{}).get(p.id)==p.version))

    def capture(self, actor, scope, origin):
        if origin not in ('user','hook'):raise PermissionError('Unsupported Bot execution origin')
        revision, grants = self.current(actor, scope['bot_id'])
        mode = 'background' if origin == 'hook' else 'foreground'
        providers = {p.id:p.version for key, grant in grants.items() if grant.get(mode)
            for p in self.providers(self.profiles[key]) if grant.get('providers',{}).get(p.id)==p.version}
        app_access=getattr(self.runtime,'messager_bot_app_access',None)
        if app_access:providers.update({p.id:p.version for p in app_access.exported(actor,scope['bot_id'])})
        return {'revision':revision,'mode':mode,'providers':providers}

    def validate(self, actor, scope, frozen, name, arguments):
        revision, grants = self.current(actor, scope['bot_id'])
        if not isinstance(frozen,dict) or frozen.get('revision')!=revision or frozen.get('mode') not in ('foreground','background'):
            raise PermissionError('Bot access changed; start a new conversation turn')
        if name is None or name=='agent.ask_user':return
        # Check only the requested route, rather than rebuilding every App export
        # for every Tool in the planning catalog. No cross-call permission cache.
        admitted=frozen.get('discovery_providers',frozen.get('providers',{}))
        selected=arguments.get('provider')
        candidates=[p for key,version in admitted.items()
            if (p:=self.runtime.app_capability_router.providers.get(key)) is not None
            and p.capability==name and (not selected or p.id==selected)]
        app_access=getattr(self.runtime,'messager_bot_app_access',None)
        for provider in candidates:
            if admitted.get(provider.id)!=provider.version or frozen.get('providers',{}).get(provider.id)!=provider.version:
                break
            legacy=any(grant.get(frozen['mode']) and grant.get('providers',{}).get(provider.id)==provider.version
                and name in self.profiles[key].tools and provider in self.providers(self.profiles[key])
                for key,grant in grants.items())
            if not legacy and not (app_access and app_access.granted(actor,scope['bot_id'],provider)):
                break
        else:
            if candidates:return
        raise PermissionError('This Bot execution has no permission for the requested App capability')

    def permits_provider(self, actor, bot_id, origin, provider, *, include_special=False):
        """Point lookup equivalent to capture membership plus explicit App access.

        Read current grants each time, without rebuilding unrelated exports or
        retaining authorization across requests. Legacy profile constraints and
        the registered Provider identity remain authoritative.
        """
        return self._provider_check(actor, bot_id, origin, include_special=include_special)(provider)

    def _provider_check(self, actor, bot_id, origin, *, include_special=False):
        """One synchronous validation's view; never retain across calls/awaits."""
        if origin not in ('user', 'hook'):
            raise PermissionError('Unsupported Bot execution origin')
        _, grants = self.current(actor, bot_id)
        mode = 'background' if origin == 'hook' else 'foreground'
        legacy = {}
        for key, grant in grants.items():
            if grant.get(mode):
                legacy.update({p.id:p.version for p in self.providers(self.profiles[key])
                               if grant.get('providers', {}).get(p.id) == p.version})
        access = getattr(self.runtime, 'messager_bot_app_access', None)
        app_grants = access.current(actor, bot_id)[1] if access else {}
        identities = {}
        def check(provider):
            registered = self.runtime.app_capability_router.providers.get(provider.id)
            if registered is None or any(getattr(registered, key) != getattr(provider, key)
                                         for key in ('version', 'capability', 'app_id', 'mini_app_id')):
                return False
            if legacy.get(provider.id) == provider.version:
                return True
            if not access:
                return False
            target = access.target(registered)
            if not app_grants.get(target, {}).get('enabled'):
                return False
            if target not in identities:
                identities[target] = access.identity(target)
            return bool(identities[target] and (include_special or not access.classification(registered)[1]))
        return check
