"""Review additive Bot grants and bind current access to each task Run."""
import json
import logging
from datetime import UTC,datetime
from pydantic import BaseModel,ConfigDict,Field
from .app_access import digest


class AccessNeed(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    capability:str=Field(min_length=1,max_length=256)
    provider:str|None=Field(default=None,max_length=256)
    reason:str=Field(min_length=1,max_length=500)
    conditional:bool=False


class TaskAccess:
    def __init__(self,tasks):
        self.tasks,self.runtime,self.db=tasks,tasks.runtime,tasks.db
        with self.db.transaction(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS messager_task_access_policies(id TEXT PRIMARY KEY,actor TEXT,bot_id TEXT,value_json TEXT,status TEXT,created_at TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS messager_task_access_leases(policy_id TEXT,todo_run_id TEXT,target TEXT,created_at TEXT,PRIMARY KEY(policy_id,todo_run_id,target))')
        logging.getLogger(__name__).info('Bot inherited task access loaded; source=%s',__file__)

    def pin(self,p):
        tool=self.runtime.services.get_tool(p.capability)
        return {'version':p.version,'tool_revision':tool.revision,'target':self.runtime.messager_bot_app_access.target(p),
            'capability':p.capability,'declaration':digest({'context':p.agent_context,'related':p.related_capabilities,'policy':p.access_policy,'effects':tool.effects,**({'access_required':False} if not p.access_required else {})})}

    def controls(self):
        return {p.id for p in (self.tasks.provider,*self.runtime.messager_bot_communication.providers,
            self.runtime.messager_bot_delegation.provider,self.runtime.messager_bot_collaboration.provider,
            self.runtime.messager_bot_configuration.provider,self.tasks.directory.memory_returns.provider)}

    def pool(self):
        access=self.runtime.messager_bot_app_access;controls=self.controls();identities={};result={}
        for p in access.providers():
            if p.id in controls:continue
            target=access.target(p)
            if target not in identities:identities[target]=access.identity(target)
            if identities[target]:result[p.id]=p
        return result

    def task_controls(self):
        from .communication import DIRECTORY
        directory=next(p for p in self.runtime.messager_bot_communication.providers if p.capability==DIRECTORY)
        return (directory,self.runtime.messager_bot_delegation.provider)

    @staticmethod
    def changed_choice(policy,mode,apps,bots):
        return ((mode is not None and mode!=policy.get('mode'))
            or (apps is not None and sorted(apps)!=policy.get('apps',[]))
            or (bots is not None and sorted(bots)!=policy.get('bots',[])))

    def current_pins(self,actor,bot):
        access=self.runtime.messager_bot_app_access
        ordinary=self.tasks.permissions.capture(actor,{'bot_id':bot},'user')['providers']
        return {pid:self.pin(p) for pid,p in self.pool().items()
                if ordinary.get(pid)==p.version or access.exempt(p) or access.granted(actor,bot,p,include_special=True)}

    def capture(self,actor,bot,frozen):
        if frozen['task_access']['mode']!='inherit':return frozen
        base=self.tasks.permissions.capture(actor,{'bot_id':bot},'hook')
        pins=self.current_pins(actor,bot)
        controls={p.id:self.pin(p) for p in self.task_controls()}
        bot_access=self.runtime.messager_bot_access
        links={entry['id']:link['revision'] for entry in self.tasks.directory.list(actor)
               if (link:=bot_access.link(actor,bot,entry['id']))['enabled']}
        return {**base,'task_access':frozen['task_access'],'run_pins':{**pins,**controls},'bot_links':links,
                'providers':{pid:pin['version'] for pid,pin in (pins|controls).items()},
                'task_tree_providers':{pid:pin['version'] for pid,pin in pins.items()},
                'discovery_pins':{pid:self.pin(p) for pid,p in self.pool().items()}}

    def preflight(self,actor,bot,needs,base):
        if not isinstance(needs,list) or len(needs)>16:raise ValueError('At most sixteen access requirements')
        needs=[AccessNeed.model_validate(v).model_dump() for v in needs]
        pool=self.pool();access=self.runtime.messager_bot_app_access;targets={};visited=set();work=[(v,0) for v in needs]
        while work:
            need,depth=work.pop(0)
            found=[p for p in pool.values() if p.capability==need['capability'] and (not need['provider'] or p.id==need['provider'])]
            if not found:raise ValueError('Resolve an installed business capability with app.describe first: '+need['capability'])
            if len({access.target(p) for p in found})>1:raise ValueError('Choose an exact Provider for ambiguous capability: '+need['capability'])
            for p in found:
                target=access.target(p);entry=targets.setdefault(target,{'reasons':[],'required':False,'capabilities':[],'required_providers':[]})
                if need['reason'] not in entry['reasons']:entry['reasons'].append(need['reason'])
                entry['required']|=not need['conditional'];entry['capabilities']=sorted(set(entry['capabilities'])|{p.capability})
                if not need['conditional'] and p.id not in entry['required_providers']:entry['required_providers'].append(p.id)
                if p.id in visited:continue
                visited.add(p.id)
                if len(visited)>48:raise ValueError('Preflight dependency graph exceeds its bound')
                # Related declarations are possibilities, not mandatory business steps.
                if depth<3:
                    for name in p.related_capabilities:
                        if any(q.capability==name for q in pool.values()):work.append(({'capability':name,'provider':None,'reason':'Related owner declaration: '+p.capability,'conditional':True},depth+1))
        for pid,version in base['providers'].items():
            p=pool.get(pid)
            if p and p.version==version:targets.setdefault(access.target(p),{'reasons':['Existing background access'],'required':False,'capabilities':[]})
        grouped={}
        for pid,p in pool.items():grouped.setdefault(access.target(p),{})[pid]=self.pin(p)
        apps=[]
        for target,pins in grouped.items():
            info=access.identity(target);usage=targets.get(target,{})
            apps.append({**info,'predicted':target in targets,'required':usage.get('required',False),'reasons':usage.get('reasons',[]),
                'capabilities':usage.get('capabilities',[]),'required_providers':sorted(usage.get('required_providers',[])),
                'special_count':sum(access.classification(pool[pid])[1] for pid in pins),'pins':pins})
        apps.sort(key=lambda a:(not a['predicted'],a['kind'],a['name']))
        inherited=self.current_pins(actor,bot)
        for app in apps:
            app['current_access']=all(pid in inherited for pid in (app['required_providers'] or app['pins']))
        bot_access=self.runtime.messager_bot_access
        bots=[{'id':entry['id'],'name':entry['name'],**bot_access.link(actor,bot,entry['id'])}
              for entry in self.tasks.directory.list(actor) if entry['id']!=bot and bot_access.visible(actor,bot,entry['id'])]
        return {'schema':'ai2apps.bot-task-preflight/v2','requirements':needs,'apps':apps,'base':base,'bots':bots,
            'limitations':['Declaration-only preflight; no business calls. Existing Bot access is inherited at Run start.'],
            'requirements_declared':bool(needs)}

    def seal(self,actor,bot,ref,preflight,base,mode=None,apps=None,bots=None):
        mode=mode or ('inherit' if preflight['schema']=='ai2apps.bot-task-preflight/v2' else 'fixed')
        if mode=='inherit':
            if preflight['schema']!='ai2apps.bot-task-preflight/v2':raise ValueError('Prepare a fresh plan access review')
            return self.seal_inherited(actor,bot,ref,preflight,base,apps,bots)
        if bots:raise ValueError('Additional Bot access requires inherited access')
        if mode not in ('fixed','auto'):raise ValueError('Choose fixed or automatic task access')
        entries={a['app_id']:a for a in preflight['apps']}
        if apps is None:
            # Programmatic approval without a selection never adds authority.
            selected={self.runtime.messager_bot_app_access.target(p) for pid,p in self.pool().items() if base['providers'].get(pid)==p.version}
            pins={pid:self.pin(p) for pid,p in self.pool().items() if base['providers'].get(pid)==p.version}
        else:
            if not isinstance(apps,list) or len(apps)>32 or len(set(apps))!=len(apps) or any(a not in entries for a in apps):raise ValueError('Choose installed targets from this preflight')
            selected=set(apps);pins={pid:pin for target in selected for pid,pin in entries[target]['pins'].items()}
        missing={a['app_id'] for a in preflight['apps'] if a['required']}-selected
        if missing:raise ValueError('Required targets were not approved: '+', '.join(sorted(missing)))
        if len(pins)>512:raise ValueError('Split this plan into smaller access scopes')
        for pid,pin in pins.items():self.check_pin(pid,pin)
        policy={'id':ref,'mode':mode,'apps':sorted(selected),'pins':pins,'base_revision':base['revision']}
        encoded=json.dumps(policy,sort_keys=True)
        frozen={**base,'providers':{pid:p['version'] for pid,p in pins.items()},'task_access':policy}
        if len(json.dumps(frozen,ensure_ascii=False).encode())>45000:raise ValueError('Plan access snapshot is too large; choose fewer Apps or split the task')
        with self.db.transaction(write=True) as db:
            old=db.execute('SELECT * FROM messager_task_access_policies WHERE id=?',(ref,)).fetchone()
            if old and (old['actor']!=actor or old['bot_id']!=bot or old['value_json']!=encoded or old['status']!='approved'):raise ValueError('Plan access choice changed; prepare a new review')
            if mode=='fixed':self.runtime.messager_bot_app_access.grant_targets(actor,bot,selected,db)
            db.execute("INSERT OR IGNORE INTO messager_task_access_policies VALUES(?,?,?,?,'approved',?)",(ref,actor,bot,encoded,datetime.now(UTC).isoformat()))
        return frozen

    def seal_inherited(self,actor,bot,ref,preflight,base,apps,bots):
        entries={a['app_id']:a for a in preflight['apps']}
        recipients={b['id']:b for b in preflight['bots']}
        apps=[] if apps is None else apps
        bots=[] if bots is None else bots
        for selected,available in ((apps,entries),(bots,recipients)):
            if not isinstance(selected,list) or len(selected)>32 or len(set(selected))!=len(selected) or any(key not in available for key in selected):
                raise ValueError('Choose exact additional targets from this review')
        inherited=self.current_pins(actor,bot)
        for key,entry in entries.items():
            if entry['required'] and key not in apps and not all(pid in inherited for pid in entry.get('required_providers',entry['pins'])):
                raise ValueError('Required App access was not granted: '+entry['name'])
        for key in apps:
            for pid,pin in entries[key]['pins'].items():self.check_pin(pid,pin)
        policy={'id':ref,'mode':'inherit','apps':sorted(apps),'bots':sorted(bots)}
        encoded=json.dumps(policy,sort_keys=True)
        access=self.runtime.messager_bot_access
        with self.db.transaction(write=True) as db:
            old=db.execute('SELECT * FROM messager_task_access_policies WHERE id=?',(ref,)).fetchone()
            if old:
                if (old['actor'],old['bot_id'],old['value_json'],old['status'])!=(actor,bot,encoded,'approved'):
                    raise ValueError('Plan access choice changed; prepare a new review')
            else:
                self.runtime.messager_bot_app_access.grant_targets(actor,bot,apps,db)
                for target in bots:
                    access.admit('task-plan',ref,actor,bot,target,approve=True,expected=recipients[target]['revision'],connection=db)
                db.execute("INSERT INTO messager_task_access_policies VALUES(?,?,?,?,'approved',?)",(ref,actor,bot,encoded,datetime.now(UTC).isoformat()))
        return {**base,'providers':{},'task_access':policy}

    def check_pin(self,pid,pin):
        p=self.runtime.app_capability_router.providers.get(pid)
        if not p or p.id in self.controls() or not self.runtime.services.get_tool(p.capability).enabled or not self.runtime.service_registry.visible_to_agent(p.capability,'builtin:app-chat') or not self.runtime.messager_bot_app_access.identity(self.runtime.messager_bot_app_access.target(p)) or self.pin(p)!=pin:raise PermissionError('Task access declaration changed; review a new plan')
        return p

    def validate(self,actor,bot,frozen,name=None,args=None,scope=None):
        policy=frozen['task_access'];args=args or {}
        with self.db.transaction() as db:row=db.execute('SELECT * FROM messager_task_access_policies WHERE id=?',(policy['id'],)).fetchone()
        if not row or row['actor']!=actor or row['bot_id']!=bot or row['status']!='approved' or json.loads(row['value_json'])!=policy:raise PermissionError('Task execution authorization was revoked or changed')
        if policy['mode']=='inherit':
            if 'run_pins' not in frozen:
                if name is not None:raise PermissionError('Task Run access has not been captured')
                return True
            self.tasks.permissions.validate(actor,{'bot_id':bot},frozen,None,{})
            return self.validate_run(actor,bot,frozen,name,args)
        self.tasks.permissions.validate(actor,{'bot_id':bot},frozen,None,{})
        if frozen['mode']!='background' or frozen['providers']!={k:v['version'] for k,v in policy['pins'].items()}:raise PermissionError('Task access snapshot mismatch')
        if name is None:return True
        if name=='agent.ask_user':return True
        if name in ('app.describe','capability.describe','app.collect_parameters','app.interact','agent.read_tool_result','agent.read_context_checkpoint','agent.read_session_memory'):
            target=args.get('capability') or args.get('provider')
            matches=[(pid,p) for pid,p in policy['pins'].items() if target in (pid,p['capability']) and (not args.get('provider') or args['provider']==pid)]
            if target and not matches:raise PermissionError('Descriptor or interaction target is outside this plan')
            for pid,pin in matches:self.check_pin(pid,pin)
            return True
        pins={pid:pin for pid,pin in policy['pins'].items() if pin['capability']==name and (not args.get('provider') or args['provider']==pid)}
        if not pins:raise PermissionError('Task cannot expand Access while running; edit and review its plan')
        special=False
        for pid,pin in pins.items():
            p=self.check_pin(pid,pin)
            if policy['mode']=='fixed' and not self.runtime.messager_bot_app_access.granted(actor,bot,p,include_special=True):raise PermissionError('Bot App access was revoked')
            special|=self.runtime.messager_bot_app_access.classification(p)[1]
        return not special

    def validate_run(self,actor,bot,frozen,name,args):
        if name in (None,'agent.ask_user'):return True
        descriptor=name in ('app.describe','capability.describe','app.collect_parameters','app.interact','agent.read_tool_result','agent.read_context_checkpoint','agent.read_session_memory')
        target=(args.get('capability') or args.get('provider')) if descriptor else name
        if not target:return True
        pins=frozen['run_pins']
        catalog={**frozen.get('discovery_pins',{}), **pins} if frozen.get('task_tree_root') else pins
        matches=[(pid,pin) for pid,pin in catalog.items()
                 if target in (pid,pin['capability']) and (not args.get('provider') or args['provider']==pid)]
        access=self.runtime.messager_bot_app_access
        if frozen.get('task_tree_root'):
            if not matches:raise PermissionError('Capability is outside the admitted task catalog')
            providers=[self.run_provider(actor,bot,pid,pin,frozen['revision']) if pid in pins
                       else self.check_pin(pid,pin) for pid,pin in matches]
            if descriptor:return True
            ordinary=[p for p in providers if p not in self.task_controls()]
            if any(access.blocked(actor,bot,p) and not access.exempt(p) for p in ordinary):
                raise PermissionError('This Bot explicitly disabled the requested App access')
            return all(not access.classification(p)[1] and access.tree.access_granted(
                actor,bot,frozen,frozen['task_tree_root'],p) for p in ordinary)
        providers=[self.run_provider(actor,bot,pid,pin,frozen['revision']) for pid,pin in matches]
        if not providers:raise PermissionError('This capability was outside the Bot access captured at task start')
        return descriptor or not any(self.runtime.messager_bot_app_access.classification(p)[1] for p in providers if p not in self.task_controls())

    def run_provider(self,actor,bot,pid,pin,revision):
        for p in self.task_controls():
            if p.id==pid and self.pin(p)==pin:return p
        p=self.check_pin(pid,pin)
        if self.runtime.messager_bot_app_access.exempt(p):
            return p
        try:self.tasks.permissions.validate(actor,{'bot_id':bot},
                {'revision':revision,'mode':'foreground','providers':{pid:p.version}},
                p.capability,{'provider':pid})
        except PermissionError:
            if not self.runtime.messager_bot_app_access.granted(actor,bot,p,include_special=True):raise
        return p

    def admit_call(self,actor,bot,frozen,scope,name,args):
        policy=frozen.get('task_access')
        if not policy or policy['mode']!='auto':return
        pins=[pin for pid,pin in policy['pins'].items() if pin['capability']==name and (not args.get('provider') or args['provider']==pid)]
        if not pins:return  # Discovery/forms do not acquire business access.
        # Admission for a selected call, never catalog visibility or business success.
        with self.runtime.app_chat.lock:
            self.validate(actor,bot,frozen,name,args,scope)
            with self.db.transaction(write=True) as db:
                actual=db.execute('SELECT actor,bot_id,proposal_id,authorization_json FROM messager_task_runs WHERE todo_run_id=?',(scope['todo_run_id'],)).fetchone()
                if not actual or actual['actor']!=actor or actual['bot_id']!=bot or actual['proposal_id']!=policy['id'] or json.loads(actual['authorization_json'])!=frozen:raise PermissionError('Automatic access requires the original plan Run')
                self.runtime.messager_bot_app_access.grant_targets(actor,bot,{pin['target'] for pin in pins},db)
                for pin in pins:db.execute('INSERT OR IGNORE INTO messager_task_access_leases VALUES(?,?,?,?)',(policy['id'],scope['todo_run_id'],pin['target'],datetime.now(UTC).isoformat()))

    def exports(self,actor,bot,frozen):
        self.validate(actor,bot,frozen)
        if frozen['task_access']['mode']=='inherit':
            result=[]
            for pid,pin in frozen['run_pins'].items():
                try:result.append(self.run_provider(actor,bot,pid,pin,frozen['revision']))
                except PermissionError:continue
            if frozen.get('task_tree_root'):
                for pid,pin in frozen.get('discovery_pins',{}).items():
                    if pid in frozen['run_pins']:continue
                    try:result.append(self.check_pin(pid,pin))
                    except PermissionError:continue
            return tuple(result)
        result=[]
        for pid,pin in frozen['task_access']['pins'].items():result.append(self.check_pin(pid,pin))
        return tuple(result)

    def revoke(self,actor,bot,ref):
        self.tasks.proposal(actor,bot,ref)
        with self.runtime.app_chat.lock,self.db.transaction(write=True) as db:
            db.execute("UPDATE messager_task_access_policies SET status='revoked' WHERE id=? AND actor=? AND bot_id=?",(ref,actor,bot))
            runs=db.execute('SELECT agent_run_id FROM messager_task_runs WHERE proposal_id=? AND actor=? AND bot_id=?',(ref,actor,bot)).fetchall()
        for r in runs:
            if r[0]:self.runtime.agents.request_cancel(r[0])
        self.tasks.revoke(actor,bot,proposal_id=ref)
        return {'status':'revoked'}

    def audit(self,actor,bot):
        self.tasks.directory.scope(actor,{'bot_id':bot})
        with self.db.transaction() as db:
            rows=db.execute('SELECT p.id,p.status,p.value_json,(SELECT proposal_json FROM messager_task_proposals t WHERE t.id=p.id) AS proposal,(SELECT count(*) FROM messager_task_access_leases l WHERE l.policy_id=p.id) AS admissions FROM messager_task_access_policies p WHERE actor=? AND bot_id=? ORDER BY rowid DESC LIMIT 30',(actor,bot)).fetchall()
        return [{'targets':[self.runtime.messager_bot_app_access.identity(a) or {'name':'Unavailable App / Mini-App'} for a in json.loads(r['value_json'])['apps']], 'id':r['id'],'title':json.loads(r['proposal'])['title'] if r['proposal'] else '', 'status':r['status'],'mode':json.loads(r['value_json'])['mode'],'apps':json.loads(r['value_json'])['apps'],'access_admissions':r['admissions']} for r in rows]
