"""Bot-owned App access grants. Owner declarations retain special confirmations."""
import hashlib
import json
import logging

from ai2apps.capabilities.effects import EXACT_EFFECT_CONFIRMATION, effect_profile
from ai2apps.core import utc_now
from ai2apps.core.errors import RepositoryError

DEFAULT_APPS=('ai2apps.gallery','ai2apps.messager','ai2apps.todo','ai2apps.ai-browser')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


class BotAppAccess:
    def __init__(self,runtime,directory):
        self.runtime,self.directory,self.db=runtime,directory,runtime.database
        from .task_tree_access import TaskTreeAccess
        self.tree = TaskTreeAccess(runtime)
        logging.getLogger(__name__).info('Bot App access grants v3 loaded; source=%s',__file__)
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_app_access(
                bot_id TEXT NOT NULL,actor TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1,
                grants_json TEXT NOT NULL DEFAULT '{}',PRIMARY KEY(bot_id,actor))''')
            db.execute('''CREATE TABLE IF NOT EXISTS messager_bot_approval_rules(
                bot_id TEXT NOT NULL,actor TEXT NOT NULL,mode TEXT NOT NULL
                    CHECK(mode IN ('manual','ai','always')),revision INTEGER NOT NULL,
                PRIMARY KEY(bot_id,actor))''')
            rows=db.execute('SELECT id,actor FROM messager_bots').fetchall()
        for row in rows:
            try:self.ensure(row['actor'],row['id'])
            except PermissionError:pass

    @staticmethod
    def target(provider):
        return 'mini:'+digest([provider.app_id,provider.mini_app_id]) if provider.mini_app_id else provider.app_id

    def ensure(self,actor,bot_id):
        self.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction(write=True) as db:
            grants={app:{'selected':True,'enabled':True} for app in DEFAULT_APPS}
            db.execute('INSERT OR IGNORE INTO messager_bot_app_access VALUES(?,?,1,?)',(bot_id,actor,json.dumps(grants)))
        return self.current(actor,bot_id)

    def current(self,actor,bot_id):
        self.directory.scope(actor,{'bot_id':bot_id})
        with self.db.transaction() as db:
            row=db.execute('SELECT revision,grants_json FROM messager_bot_app_access WHERE bot_id=? AND actor=?',(bot_id,actor)).fetchone()
        return (row['revision'],json.loads(row['grants_json'])) if row else (1,{})

    def providers(self):
        return tuple(p for p in self.runtime.app_capability_router.providers.values()
            if self.runtime.service_registry.visible_to_agent(p.capability,'builtin:app-chat') and self.runtime.services.get_tool(p.capability).enabled)

    def classification(self,provider):
        tool=self.runtime.services.get_tool(provider.capability)
        effects = [effect_profile(value) for value in tool.effects]
        declared=getattr(provider,'access_policy',None)
        mode = 'write' if declared == 'write' or any(effect.bot_mode == 'write' for effect in effects) else 'read'
        special = declared == 'confirm' or any(effect.special for effect in effects)
        return mode,special

    def exempt(self, provider):
        if provider.access_required:
            return False
        tool = self.runtime.services.get_tool(provider.capability)
        return (tool.enabled and not tool.effects and not tool.required_capabilities
                and not getattr(tool, 'capability_rules', ())
                and provider.access_policy in (None, 'read'))

    def blocked(self, actor, bot, provider):
        entry = self.current(actor, bot)[1].get(self.target(provider))
        return bool(entry and entry.get('selected') and not entry.get('enabled'))

    def identity(self,target):
        provider=next((p for p in self.runtime.app_capability_router.providers.values() if self.target(p)==target),None)
        owner=provider.app_id if provider else target
        row=self.runtime.extension_manager._active_app_definition(owner)
        if row is None:return None
        manifest=json.loads(row['manifest_json']);mini=provider.mini_app_id if provider else None
        declaration=next((d for d in manifest.get('mini_apps',[]) if d.get('id')==mini),None) if mini else None
        if mini and not declaration:
            # Native adapters can declare components which are registered in code.
            # Installed Packages still require their actual Mini-App manifest.
            identity=getattr(provider,'component_identity',None)
            if row['source']!='builtin' or not isinstance(identity,dict) or identity.get('id')!=mini or not identity.get('name'):return None
            declaration={**identity,'placements':[{'studio':owner}]}
        names=(declaration or {}).get('name') or (declaration or {}).get('title') or row['display_name']
        localized=names if isinstance(names,dict) else {}
        name=localized.get('en') or localized.get('zh') or str(names)
        icon=(declaration or {}).get('icon') or manifest.get('navigation',{}).get('icon','app-window')
        return {'app_id':target,'owner_app_id':owner,'mini_app_id':mini,'kind':'mini-app' if mini else 'app',
            'name':name,'names':localized,
            'owner_name':row['display_name'],'hosts':[r['display_name'] for placement in (declaration or {}).get('placements',[]) if (r:=self.runtime.extension_manager._active_app_definition(placement.get('studio',''))) is not None],'icon':icon if isinstance(icon,str) and all(c.isalnum() or c=='-' for c in icon) else 'app-window'}

    def catalog(self,actor,bot_id):
        revision,grants=self.current(actor,bot_id)
        return {**self.project_catalog(revision,grants),
                'approval_rule': self.approval_rule(actor,bot_id)}

    def approval_rule(self, actor, bot_id):
        with self.db.transaction() as db:
            row = db.execute('SELECT mode,revision FROM messager_bot_approval_rules WHERE actor=? AND bot_id=?',
                             (actor, bot_id)).fetchone()
        return dict(row) if row else {'mode': 'manual', 'revision': 0}

    def set_approval_rule(self, actor, bot_id, mode, revision):
        with self.runtime.app_chat.lock:
            if self.directory.definition(actor, bot_id)['execution_mode'] != 'agent':
                raise PermissionError('Approval modes require an Agent Bot')
            if self.approval_rule(actor, bot_id)['revision'] != revision:
                raise ValueError('Approval mode changed; reload and try again')
            with self.db.transaction(write=True) as db:
                db.execute('''INSERT INTO messager_bot_approval_rules VALUES(?,?,?,?)
                    ON CONFLICT(bot_id,actor) DO UPDATE SET mode=excluded.mode,revision=excluded.revision''',
                           (bot_id, actor, mode, revision + 1))
                self.runtime.events.append_in_transaction(db, event_type='bot.tool_approval_rule.changed',
                    subject_id=bot_id, payload={'actor_id': actor, 'mode': mode, 'revision': revision + 1})
        return {'mode': mode, 'revision': revision + 1}

    def invocation_approval_rule(self, binding, run_id, name, arguments):
        scope = binding['scope']
        actor, bot_id = binding['owner'], scope['bot_id']
        manual = {'mode': 'manual', 'revision': 0}
        if not run_id or scope.get('archive_id'):
            return manual
        frozen = self.runtime.app_chat.execution_authorization(run_id) or {}
        run = self.runtime.agents.get_run(run_id)
        tree = self.tree.context(actor, scope, frozen)
        if tree:
            policy = self.tree.approval_chain(actor, scope, frozen, tree)
        elif (scope.get('dialogue_job') or scope.get('todo_run_id') or frozen.get('mode') != 'foreground'
              or run.input.get('execution_origin', 'user') != 'user'):
            return manual
        else:
            policy = self.approval_rule(actor, bot_id)
        if policy['mode'] == 'manual':
            return manual
        providers, app, error = self.approval_target(name, arguments)
        if error or any(self.classification(provider)[1] for provider in providers):
            return manual
        versions = {p.id: p.version for p in providers}
        admitted = frozen.get('discovery_providers', {})
        if tree and scope.get('todo_run_id'):
            admitted = {p.id:p.version for p in providers
                        if frozen.get('discovery_pins', {}).get(p.id) == self.tree.policy.pin(p)}
        if any(binding['providers'].get(pid) != version or admitted.get(pid) != version
               for pid, version in versions.items()):
            return manual
        access_revision, grants = self.current(actor, bot_id)
        selected = grants.get(app['app_id'])
        if selected and not selected.get('enabled'):
            return manual
        tool = self.runtime.services.get_tool(name)
        rule = {**policy, 'target': app['app_id'], 'providers': versions, 'access_revision': access_revision,
                'tool_revision': tool.revision}
        if tree:
            rule['approval_scope'] = 'task_tree'
            if policy['mode'] == 'ai':
                from ai2apps.capabilities.risk import sanitize_value
                rule['root_goal'] = sanitize_value(self.tree.approval_goal(scope, frozen, run))
                context = self.tree.approval_context(actor, tree[0])
                previous = context.pop('previous_result', '')
                rule['task_context'] = sanitize_value(context)
                if isinstance(previous, str) and previous:
                    # Keep the finish of a reply, where numbered next steps usually appear.
                    tail = previous[-960:]
                    rule['task_context']['previous_result_excerpt'] = sanitize_value(
                        [tail[i:i + 240] for i in range(0, len(tail), 240)])
                effects = set(tool.effects)
                # Routine metered artifact production may use the model's
                # low-risk judgment even when the user's intent is unclear.
                if {'artifact.create', 'ai.usage'} <= effects <= {
                    'artifact.create', 'ai.usage', 'artifact.read', 'workspace.write', 'network',
                }:
                    rule['allow_unclear_intent'] = True
        return rule

    def save_auto_tool_approval(self, binding, run_id, name, arguments, rule):
        if rule.get('approval_scope') == 'task_tree':
            actor = binding['owner']
            frozen = self.runtime.app_chat.execution_authorization(run_id)
            root, bot = self.tree.context(actor, binding['scope'], frozen)
            self.tree.grant(actor, root, rule['target'], frozen)
            self.continue_tree_approvals(actor, bot, root, rule['target'])
            self.runtime.agent_runtime.wake()
            return
        if rule['mode'] != 'ai':
            return
        with self.db.transaction(write=True) as db:
            session = db.execute('SELECT app_instance_id FROM sessions WHERE id=?',
                                 (binding['session_id'],)).fetchone()
            self.grant_targets(binding['owner'], binding['scope']['bot_id'], (rule['target'],), db)
            self.runtime.events.append_in_transaction(db, event_type='bot.app_access.ai_approved',
                subject_id=binding['scope']['bot_id'], app_instance_id=session['app_instance_id'],
                session_id=binding['session_id'], trace_id=run_id,
                payload={'app_id': rule['target'], 'tool_name': name, 'rule_revision': rule['revision']})

    def creation_catalog(self):
        return self.project_catalog(1,{app:{'selected':True,'enabled':True} for app in DEFAULT_APPS})

    def project_catalog(self,revision,grants):
        items=[]
        grouped={}
        for p in self.providers():grouped.setdefault(self.target(p),[]).append(p)
        for target in sorted(set(grouped)|set(grants)):
            providers=grouped.get(target,[]);app=self.identity(target)
            if not app:
                if target not in grants:continue
                app=grants[target].get('identity') or {'app_id':target,'owner_app_id':target,'mini_app_id':None,'kind':'unavailable','name':target,'owner_name':'','icon':'app-window'}
            value=grants.get(target,{})
            items.append({**app,'selected':bool(value.get('selected') or value.get('enabled')),
                'enabled':bool(value.get('enabled')),'available':bool(providers) and self.identity(target) is not None,
                'special_count':sum(self.classification(p)[1] for p in providers)})
        order={app:index for index,app in enumerate(DEFAULT_APPS)}
        items.sort(key=lambda x:(x['kind']=='mini-app',order.get(x['app_id'],99),str(x['name']).lower()))
        review=digest([(x['app_id'],x['kind'],[(p.id,p.version,self.classification(p),self.runtime.services.get_tool(p.capability).revision) for p in grouped.get(x['app_id'],[])]) for x in items])
        return {'revision':revision,'review_hash':review,'items':items}

    def granted(self,actor,bot_id,provider,*,include_special=False):
        _,grants=self.current(actor,bot_id);value=grants.get(self.target(provider),{})
        if not value.get('enabled'):return False
        mode,special=self.classification(provider)
        return bool(self.identity(self.target(provider)) and value.get('enabled') and (include_special or not special))

    def exported(self,actor,bot_id):
        _,grants=self.current(actor,bot_id)
        if not any(v.get('enabled') for v in grants.values()):return ()
        values=[];identities={}
        for p in self.runtime.app_capability_router.providers.values():
            target=self.target(p);value=grants.get(target,{})
            if not value.get('enabled') or not self.runtime.service_registry.visible_to_agent(p.capability,'builtin:app-chat'):continue
            if target not in identities:identities[target]=self.identity(target)
            if not identities[target]:continue
            mode,special=self.classification(p)
            if not special:values.append(p)
        return tuple(values)

    def prepare_grants(self,current,choices):
        ids={x['app_id'] for x in current['items']};grants={}
        for value in choices:
            if value['app_id'] not in ids or value['app_id'] in grants:raise ValueError('Unknown or duplicate App')
            if set(value)!={'app_id','enabled'} or type(value['enabled']) is not bool:raise ValueError('Choose whether this Bot may access the App')
            entry=next(x for x in current['items'] if x['app_id']==value['app_id'])
            if not entry['available'] and value['enabled'] and not entry['enabled']:raise ValueError('App or Mini-App is unavailable')
            grants[value['app_id']]={'selected':True,'enabled':value['enabled'],'identity':{k:v for k,v in entry.items() if k in ('app_id','owner_app_id','mini_app_id','kind','name','owner_name','icon','hosts')}}
        return grants

    def save(self,actor,bot_id,revision,review_hash,choices,*,preserve_run=None,approval_app_id=None):
        current=self.catalog(actor,bot_id)
        if current['revision']!=revision or current['review_hash']!=review_hash:raise ValueError('App access changed; review again')
        grants=self.prepare_grants(current,choices)
        with self.runtime.app_chat.lock:
            old_revision,old=self.current(actor,bot_id)
            if old_revision!=revision or self.catalog(actor,bot_id)['review_hash']!=review_hash:raise ValueError('App access changed; review again')
            revoked_apps={app for app,v in old.items() if v.get('enabled') and not grants.get(app,{}).get('enabled')}
            revoked_apps.update(app for app,v in grants.items() if not v.get('enabled') and app not in old)
            permissions=self.runtime.messager_bot_permissions
            legacy=permissions.current(actor,bot_id)[1]
            for key,value in legacy.items():
                profile=permissions.profiles[key]
                if preserve_run and profile.app_id!=approval_app_id:continue
                choice=grants.get(profile.app_id,{})
                if not choice.get('enabled'):
                    revoked_apps.add(profile.app_id)
            if old==grants and not revoked_apps:return self.catalog(actor,bot_id)
            if revoked_apps:
                # Existing owner invalidation cancels admitted executions and freezes their old receipts.
                for app in revoked_apps:self.runtime.messager_bot_permissions.invalidate(actor,bot_id,app_id=app)
            with self.db.transaction(write=True) as db:
                db.execute('INSERT INTO messager_bot_app_access VALUES(?,?,?,?) ON CONFLICT(bot_id,actor) DO UPDATE SET revision=excluded.revision,grants_json=excluded.grants_json',(bot_id,actor,revision+1,json.dumps(grants)))
        return self.catalog(actor,bot_id)

    def grant_targets(self,actor,bot_id,targets,db):
        """Trusted additive approval: never disable unrelated Bot grants."""
        self.directory.scope(actor,{'bot_id':bot_id})
        row=db.execute('SELECT revision,grants_json FROM messager_bot_app_access WHERE actor=? AND bot_id=?',(actor,bot_id)).fetchone()
        if row is None:raise PermissionError('Bot App access unavailable')
        grants=json.loads(row['grants_json']);changed=False
        for target in targets:
            identity=self.identity(target)
            if identity is None:raise PermissionError('Approved App is unavailable')
            if not grants.get(target,{}).get('enabled'):
                grants[target]={'selected':True,'enabled':True,'identity':identity};changed=True
        if changed:db.execute('UPDATE messager_bot_app_access SET revision=revision+1,grants_json=? WHERE actor=? AND bot_id=?',(json.dumps(grants),actor,bot_id))

    def approval_target(self,name,arguments):
        candidates=[p for p in self.providers() if p.capability==name and (not arguments.get('provider') or p.id==arguments['provider'])]
        apps={self.target(p) for p in candidates}
        if len(apps)!=1:return candidates,None,'provider_ambiguous'
        app=self.identity(next(iter(apps)))
        return candidates,app,None if app else 'app_unavailable'

    def request(self,actor,bot_id,run_id,interaction_id):
        self.directory.scope(actor,{'bot_id':bot_id})
        run=self.runtime.agents.get_run(run_id);binding=self.runtime.app_chat.binding(run.session_id)
        if not binding or binding['owner']!=actor or binding['registration'] not in ('ai2apps.messager.bots','ai2apps.messager.task-execution'):raise PermissionError('Approval does not belong to this Bot')
        scope=binding['scope']
        frozen=self.runtime.app_chat.execution_authorization(run_id) or {}
        tree=self.tree.context(actor,scope,frozen)
        if (tree[1] if tree else scope['bot_id'])!=bot_id or (scope.get('todo_run_id') and not tree):
            raise PermissionError('Review access in the originating Bot conversation')
        if run.status.value!='waiting_capability' or run.cancel_requested:raise ValueError('Approval is no longer pending')
        item=next((i for i in self.runtime.agents.list_interactions(run_id) if i.id==interaction_id),None)
        if not item or item.kind.value!='approval' or item.status.value!='pending' or item.deadline_at<=utc_now():raise ValueError('Approval is no longer pending')
        name=item.request['tool_name'];arguments=item.request.get('arguments',{})
        self.runtime.app_chat.validate_execution(binding,self.runtime.app_chat.owner(binding),run,name,arguments)
        candidates,app,reason=self.approval_target(name,arguments)
        if reason:return {'eligible':False,'reason':reason}
        catalog=self.catalog(actor,bot_id)
        allowed=all(self.tree.access_granted(actor,scope['bot_id'],frozen,tree[0],p) if tree
                    else self.granted(actor,bot_id,p,include_special=True) for p in candidates)
        special=any(self.classification(p)[1] for p in candidates) or (
            EXACT_EFFECT_CONFIRMATION in (item.request.get('capabilities') or ()) or bool(item.ui_hints.get('unknown_tool_risk')))
        value={'eligible':True,'app':app,'access_granted':allowed,'special':special,'revision':catalog['revision'],'review_hash':catalog['review_hash']}
        if tree:
            value['task_tree']=True
        review={k:v for k,v in value.items() if not tree or k!='access_granted'}
        value['request_hash']=digest({**review,'tree':tree,'bot_id':bot_id,'run_id':run_id,'interaction_id':interaction_id,'request':item.request,'providers':[self.tree.policy.pin(p) for p in candidates]})
        return value

    def allow(self,actor,bot_id,run_id,interaction_id,request_hash,*,existing_access_only=False,ordinary_only=False):
        with self.runtime.app_chat.lock:
            value=self.request(actor,bot_id,run_id,interaction_id)
            if not value.get('eligible') or value['request_hash']!=request_hash:raise ValueError('Approval scope changed; review again')
            if ordinary_only and value['special']:raise PermissionError('Use the original operation confirmation')
            if value.get('task_tree'):
                frozen=self.runtime.app_chat.execution_authorization(run_id)
                root=frozen['task_tree_root']
                if not value['access_granted']:
                    if existing_access_only:raise PermissionError('This task has no current access to the App')
                    self.tree.grant(actor,root,value['app']['app_id'],frozen)
                if not value['special']:
                    self.respond_once(run_id,interaction_id)
                self.continue_tree_approvals(actor,bot_id,root,value['app']['app_id'])
                self.runtime.agent_runtime.wake()
                return {'continued':False,'requires_confirmation':True} if value['special'] else {'continued':True}
            if not value['access_granted']:
                if existing_access_only:raise PermissionError('This Bot has no current access to the App')
                catalog=self.catalog(actor,bot_id)
                choices=[{'app_id':x['app_id'],'enabled':x['enabled']} for x in catalog['items'] if x['selected']]
                if not any(x['app_id']==value['app']['app_id'] for x in choices):choices.append({'app_id':value['app']['app_id'],'enabled':False})
                for choice in choices:
                    if choice['app_id']==value['app']['app_id']:choice.update(enabled=True)
                self.save(actor,bot_id,catalog['revision'],catalog['review_hash'],choices,preserve_run=run_id,approval_app_id=value['app']['app_id'])
            if value['special']:return {'continued':False,'requires_confirmation':True}
            self.respond_once(run_id,interaction_id)
        self.runtime.agent_runtime.wake()
        return {'continued':True}

    def respond_once(self, run_id, interaction_id):
        self.runtime.agents.respond_interaction(run_id,interaction_id,response_id='bot-app-access:'+interaction_id,
                                                response={'decision':'approve','scope':'once'})

    def continue_tree_approvals(self, actor, bot, root, target):
        with self.db.transaction() as db:
            pending=db.execute('''SELECT i.run_id,i.id FROM agent_interactions i
                JOIN app_chat_run_authorizations a ON a.run_id=i.run_id
                WHERE i.kind='approval' AND i.status='pending'
                AND json_extract(a.authorization_json,'$.task_tree_root')=?''',(root,)).fetchall()
        for item in pending:
            try:
                value=self.request(actor,bot,item['run_id'],item['id'])
                if (value.get('task_tree') and value['app']['app_id']==target
                        and value['access_granted'] and not value['special']):
                    self.respond_once(item['run_id'],item['id'])
            except (PermissionError, ValueError, RepositoryError):
                # The other branch stopped or its original interaction already resolved.
                continue
