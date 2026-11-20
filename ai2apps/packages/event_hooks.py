"""Host-mediated consent for installed Package App/Mini-App event consumers.

Signed declarations bound possible requests. Only a user decision creates a
scope-hashed grant. The handler is host-owned; Package scripts cannot register
callbacks, borrow a Bot identity or choose arbitrary background Tools.
"""
from dataclasses import replace
import json,time,uuid,logging
from packaging.version import Version,InvalidVersion
from ai2apps.extensions import UnitKind,ExtensionError
from ai2apps.core import RepositoryError
from ai2apps.events.hooks import ConsumerType,HookError,digest
from ai2apps.storage.records import canonical_json
from ai2apps.system_tasks.sessions import execution_principal
from ai2apps.services import ToolCallContext
from .hook_contract import declaration,validate_app,HANDLER

APP='package.app.event-inbox'
MINI='package.mini-app.event-inbox'
IDENTITY=('package_id','runtime_key','instance_id','mini_app_id','studio_id')


class PackageHooks:
    def __init__(self,runtime):
        self.runtime=runtime;self.db=runtime.database;self.hooks=runtime.event_hooks
        logging.getLogger(__name__).info('Package Hook consent loaded; source=%s',__file__)

    def current(self,actor,instance,mini=None,studio=None):
        r=self.runtime;m=r.extension_manager;p=execution_principal(r,actor)
        try:row=m.require_instance_access(instance,p)
        except (RepositoryError,ExtensionError):raise PermissionError('Package instance unavailable') from None
        key=row['package_id']
        active=m._active_app_definition(key)
        if not active or active['source']=='builtin':raise PermissionError('An installed Package App is required')
        effective=m.repository.effective(UnitKind.APP,key);upstream=m.repository.active_package(UnitKind.APP,key)
        if not effective or not upstream or effective.upstream_digest!=upstream.digest:raise PermissionError('Package is disabled, removed or changing')
        verification=upstream.verification.get('signature',{})
        installed=r.registry_packages._load_state().get('installed',{})
        matches=[(pid,v) for pid,v in installed.items() if v.get('packageType')=='app' and v.get('runtimeKey')==key]
        if verification.get('trust')=='ai2apps-cloud-registry-v1':
            if len(matches)!=1:raise PermissionError('Verified Package installation unavailable')
            pid,stored=matches[0]
            if stored.get('sha256')!=upstream.digest.removeprefix('sha256:') or stored.get('version')!=upstream.version:
                raise PermissionError('Package upgrade is not committed')
            envelope=verification.get('envelope',{}).get('payload',{})
            publisher=verification.get('publisher_id')
            if not publisher or envelope.get('publisherId')!=publisher or envelope.get('artifact',{}).get('sha256')!=stored['sha256']:
                raise PermissionError('Package publisher provenance changed')
            installed_at=stored['installedAt'];trust='registry'
        elif verification.get('trust')=='trusted' and verification.get('signature')=='valid':
            publisher=verification.get('publisher')
            try:record=r.package_repository.get_publisher(publisher)
            except RepositoryError:raise PermissionError('Package publisher unavailable') from None
            if record.trust_status.value!='trusted' or publisher!=upstream.publisher_key:raise PermissionError('Package publisher revoked')
            pid='local:'+key;stored={};installed_at=upstream.installed_at.isoformat();trust='local'
        else:raise PermissionError('Package Hooks require a verified installation')
        if str(active['effective_digest'])!=effective.effective_digest:raise PermissionError('Effective Package is changing')
        manifest=effective.manifest;consumer=manifest
        try:validate_app(manifest)
        except (ValueError,TypeError,KeyError):raise PermissionError('Effective Package Hook declaration is invalid') from None
        if mini is not None:
            candidates=[v for v in manifest.get('mini_apps',[]) if v.get('id')==mini and any(x.get('studio')==studio for x in v.get('placements',[]))]
            if len(candidates)!=1 or m.builtin_mini_app_owner(studio,mini):raise PermissionError('Mini-App identity unavailable')
            consumer=candidates[0]
        permissions=declaration(consumer.get('event_hooks'))
        if permissions is None:raise PermissionError('Package did not declare event Hooks')
        release={'digest':effective.effective_digest,'artifact':upstream.digest,'version':upstream.version,
            'consumer_version':consumer.get('version',upstream.version),'publisher':publisher,'installed_at':installed_at,
            'patches':effective.patch_set_digest,'trust':trust,'development':bool(stored.get('developmentSource'))}
        binding={'package_id':pid,'runtime_key':key,'instance_id':instance,'mini_app_id':mini,'studio_id':studio,
            'release':release,'declaration':permissions,'display_name':str(consumer.get('name') or active['display_name'])[:160]}
        return binding

    @staticmethod
    def compatible(old,new):
        if any(old.get(k)!=new.get(k) for k in ('publisher','trust','patches')):return False
        if old['digest']==new['digest']:
            return old['artifact']==new['artifact'] and old['installed_at']==new['installed_at'] and old['version']==new['version']
        if old.get('development') or new.get('development'):return False
        try:
            before,after=Version(old['version']),Version(new['version'])
            c_before,c_after=Version(old['consumer_version']),Version(new['consumer_version'])
            return after>before and after.major==before.major and c_after>=c_before and c_after.major==c_before.major
        except (ValueError,InvalidVersion):return False

    def validate(self,actor,binding):
        if set(binding)!={*IDENTITY,'release','declaration','display_name'}:raise ValueError('Invalid Package Hook identity')
        live=self.current(actor,binding['instance_id'],binding['mini_app_id'],binding['studio_id'])
        if any(live[k]!=binding[k] for k in IDENTITY) or live['declaration']!=binding['declaration'] or not self.compatible(binding['release'],live['release']):
            raise PermissionError('Package interface, permissions or publisher changed; request consent again')
        return dict(binding)

    def prepare(self,actor,binding,settings):
        self.validate(actor,binding)
        if not isinstance(settings,dict) or set(settings)-{'read_details','actions'} or type(settings.get('read_details',False)) is not bool:
            raise ValueError('Invalid Package handler settings')
        d=binding['declaration'];read=settings.get('read_details',False)
        if read and not d['details']:raise PermissionError('Package did not declare detail reads')
        actions=self.runtime.hook_actions.prepare(actor,settings.get('actions',[]))
        if any(a['registration'] not in d['actions'] for a in actions):raise PermissionError('Package action was not declared')
        return {'read_details':read,'actions':actions}

    def authorize(self,actor,spec):
        ref=spec.get('package_consent',{}).get('id')
        with self.db.transaction() as db:
            grant=db.execute('SELECT * FROM package_hook_grants WHERE id=? AND owner=?',(ref,actor)).fetchone()
            current=db.execute('SELECT v.spec_json,r.status FROM hook_rules r JOIN hook_rule_revisions v ON v.rule_id=r.id AND v.revision=r.revision WHERE r.id=?',(grant['rule_id'],)).fetchone() if grant else None
        p=execution_principal(self.runtime,actor)
        if (not grant or grant['state']!='active' or grant['installation_id']!=p.installation_id or grant['expires']<=self.hooks.clock()
                or grant['scope_hash']!=digest(spec) or current is None or current['status']=='deleted' or digest(json.loads(current[0]))!=grant['scope_hash']):
            raise HookError('consent_required','User consent is missing, expired or revoked')
        b=spec['consumer']['binding']
        try:live=self.current(actor,b['instance_id'],b['mini_app_id'],b['studio_id'])
        except PermissionError:
            with self.db.transaction(write=True) as db:
                changed=db.execute("UPDATE package_hook_grants SET state='needs_consent',error='package_unavailable' WHERE id=? AND state='active'",(ref,)).rowcount
                db.execute("UPDATE hook_rules SET status='paused',error='consent_required' WHERE id=? AND status!='deleted'",(grant['rule_id'],))
                if changed:self.audit(db,actor,'reconsent_required',ref,None,{'reason':'package_unavailable'})
            raise HookError('consent_required','Package provenance or access changed') from None
        accepted=json.loads(grant['accepted_release_json'])
        if b['declaration']!=live['declaration'] or not self.compatible(accepted,live['release']):
            with self.db.transaction(write=True) as db:
                changed=db.execute("UPDATE package_hook_grants SET state='needs_consent',error='package_changed' WHERE id=? AND state='active'",(ref,)).rowcount
                db.execute("UPDATE hook_rules SET status='paused',error='consent_required' WHERE id=?",(grant['rule_id'],))
                if changed:self.audit(db,actor,'reconsent_required',ref,None,{'release':live['release']})
            raise HookError('consent_required','Package update requires renewed consent')
        if accepted!=live['release']:
            with self.db.transaction(write=True) as db:
                # Compatibility updates only release provenance, never the approved scope.
                changed=db.execute("UPDATE package_hook_grants SET accepted_release_json=? WHERE id=? AND state='active' AND accepted_release_json=?",(canonical_json(live['release']),ref,grant['accepted_release_json'])).rowcount
                if changed:self.audit(db,actor,'compatible_upgrade',ref,None,{'from':accepted,'to':live['release']})

    def session(self,work):
        return self.session_for(work.actor,work.spec['consumer']['binding'])

    def session_for(self,actor,b):
        from ai2apps.storage.repositories import SessionRepository
        from ai2apps.core import SessionVisibility
        self.validate(actor,b)
        with self.db.transaction() as db:
            row=db.execute("SELECT id FROM sessions WHERE app_instance_id=? AND status='active' AND json_extract(metadata_json,'$.package_hook_consumer')=? ORDER BY created_at LIMIT 1",(b['instance_id'],b['mini_app_id'] or 'app')).fetchone()
        if row:return row[0]
        return SessionRepository(self.db,self.runtime.events).create(app_instance_id=b['instance_id'],title='Package event inbox',visibility=SessionVisibility.UNLISTED,
            metadata={'package_hook_consumer':b['mini_app_id'] or 'app'}).id

    async def execute(self,work,ctx):
        settings=work.plan['settings'];result={'event_id':work.event['id'],'handler':HANDLER}
        if settings['read_details']:result['details']=await work.details()
        evidence={'content':canonical_json(result)}
        result['actions']=await self.runtime.hook_actions.execute(work,work.plan.get('actions',[]),evidence) if work.plan.get('actions') else []
        return work.report(result)

    @staticmethod
    def audit(db,actor,action,grant,request,data):
        db.execute('INSERT INTO package_hook_audit(owner,grant_id,request_id,action,data_json,created) VALUES(?,?,?,?,?,?)',(actor,grant,request,action,canonical_json(data),time.time()))

    def request(self,p,binding,proposal):
        allowed={'event_type','scope','subjects','filters','background','read_details','actions','expires_in','request_id'}
        if not isinstance(proposal,dict) or set(proposal)-allowed:raise ValueError('Invalid Package Hook request')
        if type(proposal.get('background',False)) is not bool:raise ValueError('Invalid background request')
        duration=proposal.get('expires_in',86400)
        if type(duration) is not int or not 60<=duration<=604800:raise ValueError('Consent duration must be 60–604800 seconds')
        key=proposal.get('request_id')
        if not isinstance(key,str) or not 8<=len(key)<=128:raise ValueError('A stable request_id is required')
        self.validate(p.actor_user_id,binding);d=binding['declaration'];bg=proposal.get('background',False)
        if proposal.get('event_type') not in d['event_types'] or proposal.get('scope','subjects') not in d['scopes'] or bg and not d['background']:
            raise PermissionError('Hook request exceeds the signed declaration')
        settings=self.prepare(p.actor_user_id,binding,{'read_details':proposal.get('read_details',False),'actions':proposal.get('actions',[])})
        if settings['read_details'] and not self.runtime.business_events.types[proposal['event_type']].details:raise ValueError('Event has no details interface')
        if settings['actions'] and not bg:raise ValueError('Actions require an explicitly approved background plan')
        registration=MINI if binding['mini_app_id'] else APP
        value={'consumer':{'registration':registration,'binding':binding},'event_type':proposal['event_type'],
               'scope':proposal.get('scope','subjects'),'subjects':proposal.get('subjects',[]),'filters':proposal.get('filters',[])}
        if bg:value['execution']={'settings':settings,'expires_in':duration}
        identity=canonical_json({k:binding[k] for k in IDENTITY});signature=digest({'proposal':proposal,'binding':binding})
        with self.db.transaction() as db:
            old=db.execute('SELECT * FROM package_hook_requests WHERE owner=? AND identity_json=? AND request_key=?',(p.actor_user_id,identity,key)).fetchone()
        if old:
            if old['signature']!=signature:raise HookError('request_conflict','Request ID already bound to different permissions')
            return {'status':old['state'],'request_id':old['id'],'requires_user_consent':True}
        spec=self.hooks.normalize(p.actor_user_id,value)
        preview={'preview_ref':'hp_'+uuid.uuid4().hex,'expires_at':self.hooks.clock()+600}
        ref='phg_'+uuid.uuid4().hex;rid='phr_'+uuid.uuid4().hex
        spec['package_consent']={'id':ref,'installation_id':p.installation_id,'expires_at':self.hooks.clock()+duration,
                                 'read_details':settings['read_details'],'details_binding':list(self.runtime.business_events.types[proposal['event_type']].details or ()) if settings['read_details'] else None}
        with self.db.transaction(write=True) as db:
            existing=db.execute('SELECT * FROM package_hook_requests WHERE owner=? AND identity_json=? AND request_key=?',(p.actor_user_id,identity,key)).fetchone()
            if existing:
                if existing['signature']!=signature:raise HookError('request_conflict','Request ID already bound to different permissions')
                return {'status':existing['state'],'request_id':existing['id'],'requires_user_consent':True}
            db.execute("DELETE FROM package_hook_requests WHERE owner=? AND state='pending' AND expires<?",(p.actor_user_id,self.hooks.clock()))
            if db.execute("SELECT count(*) FROM package_hook_requests WHERE owner=? AND state='pending'",(p.actor_user_id,)).fetchone()[0]>=100:raise ValueError('Pending consent request limit reached')
            if db.execute("SELECT count(*) FROM package_hook_requests WHERE owner=? AND state='pending' AND json_extract(spec_json,'$.consumer.binding.package_id')=?",(p.actor_user_id,binding['package_id'])).fetchone()[0]>=10:raise ValueError('At most ten pending requests per Package')
            db.execute('DELETE FROM hook_previews WHERE expires<?',(self.hooks.clock(),))
            if db.execute('SELECT count(*) FROM hook_previews WHERE owner=? AND consumed=0',(p.actor_user_id,)).fetchone()[0]>=100:raise HookError('quota_exceeded','Unconsumed preview quota reached')
            db.execute('INSERT INTO hook_previews VALUES(?,?,?,?,0)',(preview['preview_ref'],p.actor_user_id,canonical_json(spec),preview['expires_at']))
            db.execute("INSERT INTO package_hook_requests VALUES(?,?,?,?,?,?,?,?, 'pending',?,?,NULL)",(rid,p.actor_user_id,p.installation_id,identity,key,signature,preview['preview_ref'],canonical_json(spec),self.hooks.clock(),preview['expires_at']))
            self.audit(db,p.actor_user_id,'requested',None,rid,{'identity':json.loads(identity)})
        return {'status':'pending','request_id':rid,'requires_user_consent':True}

    def request_app(self,p,instance,proposal):return self.request(p,self.current(p.actor_user_id,instance),proposal)

    def mini_binding(self,p,studio,mount):
        from ai2apps.studio.capability_broker import StudioCapabilityBroker
        mounted=StudioCapabilityBroker(self.runtime).mounted_mini_app(studio,mount,principal=p)
        return self.current(p.actor_user_id,mounted.mount['app_instance_id'],mounted.declaration['id'],studio)

    def request_mini(self,p,studio,mount,proposal):return self.request(p,self.mini_binding(p,studio,mount),proposal)

    def review(self,actor,rid):
        with self.db.transaction() as db:row=db.execute('SELECT * FROM package_hook_requests WHERE id=? AND owner=?',(rid,actor)).fetchone()
        if not row:raise HookError('rule_not_found','Consent request unavailable')
        spec=json.loads(row['spec_json']);b=spec['consumer']['binding'];d=self.runtime.business_events.types.get(spec['event_type'])
        return {'id':rid,'state':'expired' if row['state']=='pending' and min(row['expires'],spec['package_consent']['expires_at'])<=self.hooks.clock() else row['state'],
            'review_hash':digest(spec),'expires':row['expires'],'consumer':b['display_name'],'package_id':b['package_id'],'mini_app_id':b['mini_app_id'],
            'publisher':b['release']['publisher'],'version':b['release']['version'],'event':d.title if d else spec['event_type'],
            'scope':spec['scope'],'subjects':spec['subjects'],'filters':spec['filters'],'background':spec['mode']=='background',
            'read_details':spec['package_consent']['read_details'],'actions':[{**a,'title':self.runtime.hook_actions.types[a['registration']].title if a['registration'] in self.runtime.hook_actions.types else a['registration']} for a in spec.get('execution',{}).get('actions',[])],
            'grant_expires':spec['package_consent']['expires_at'],'grant_id':spec['package_consent']['id']}

    def decide(self,p,rid,choice,review_hash,request_id):
        if p.client_scope!='desktop':raise PermissionError('Consent must be given in the Local desktop host')
        review=self.review(p.actor_user_id,rid)
        if review['review_hash']!=review_hash:raise HookError('revision_conflict','Consent scope changed')
        if choice not in ('approve','deny'):raise ValueError('Invalid consent decision')
        with self.db.transaction() as db:row=db.execute('SELECT * FROM package_hook_requests WHERE id=? AND owner=?',(rid,p.actor_user_id)).fetchone()
        if (row['state'],choice) in (('approved','approve'),('denied','deny')):return json.loads(row['result_json'])
        if row['state']!='pending' or review['state']=='expired':raise HookError('preview_expired','Consent request expired or already decided')
        spec=json.loads(row['spec_json']);binding=spec['consumer']['binding']
        if choice=='deny':
            with self.db.transaction(write=True) as db:
                result={'status':'denied','request_id':rid}
                changed=db.execute("UPDATE package_hook_requests SET state='denied',result_json=? WHERE id=? AND state='pending'",(canonical_json(result),rid)).rowcount
                if not changed:raise HookError('revision_conflict','Request already decided')
                db.execute('UPDATE hook_previews SET consumed=1 WHERE id=?',(row['preview_ref'],))
                self.audit(db,p.actor_user_id,'denied',None,rid,{})
            return result
        live=self.current(p.actor_user_id,binding['instance_id'],binding['mini_app_id'],binding['studio_id'])
        if live['release']!=binding['release'] or live['declaration']!=binding['declaration']:raise HookError('declaration_changed','Package changed while consent was pending')
        def admission(db,frozen,rule,revision):
            current=db.execute('SELECT state,expires FROM package_hook_requests WHERE id=?',(rid,)).fetchone()
            if current['state']!='pending' or current['expires']<=self.hooks.clock() or digest(frozen)!=review_hash:raise HookError('preview_expired','Consent request was superseded')
            if p.installation_id!=row['installation_id']:raise PermissionError('Installation changed')
            ref=frozen['package_consent']['id']
            db.execute("INSERT INTO package_hook_grants VALUES(?,?,?,?,?,?,?,'active',?,?,?,NULL)",(ref,p.actor_user_id,p.installation_id,rule,digest(frozen),canonical_json(frozen),canonical_json(live['release']),frozen['package_consent']['expires_at'],p.actor_user_id,self.hooks.clock()))
            result={'status':'approved','request_id':rid,'grant_id':ref,'rule_id':rule,'revision':revision}
            db.execute("UPDATE package_hook_requests SET state='approved',result_json=? WHERE id=?",(canonical_json(result),rid))
            self.audit(db,p.actor_user_id,'approved',ref,rid,{'scope_hash':digest(frozen)})
        self.hooks.save(p.actor_user_id,row['preview_ref'],request_id,admission=admission)
        with self.db.transaction() as db:return json.loads(db.execute('SELECT result_json FROM package_hook_requests WHERE id=?',(rid,)).fetchone()[0])

    def requests(self,actor):
        with self.db.transaction() as db:ids=[r[0] for r in db.execute('SELECT id FROM package_hook_requests WHERE owner=? ORDER BY created DESC LIMIT 100',(actor,))]
        return {'items':[self.review(actor,rid) for rid in ids]}

    def control(self,actor,ref,operation,revision,request_id):
        if operation not in ('pause','resume'):raise ValueError('Invalid permission operation')
        with self.db.transaction() as db:
            row=db.execute('SELECT rule_id,state FROM package_hook_grants WHERE id=? AND owner=?',(ref,actor)).fetchone()
        if not row or row['state']!='active':raise HookError('consent_required','Permission is unavailable or requires renewed consent')
        return self.hooks.change(actor,row['rule_id'],operation,revision,request_id)

    def revoke(self,actor,ref):
        with self.db.transaction(write=True) as db:
            row=db.execute('SELECT * FROM package_hook_grants WHERE id=? AND owner=?',(ref,actor)).fetchone()
            if not row:raise HookError('rule_not_found','Consent grant unavailable')
            db.execute("UPDATE package_hook_grants SET state='revoked',error='user_revoked' WHERE id=?",(ref,))
            db.execute("UPDATE hook_rules SET status='paused',error='consent_revoked' WHERE id=? AND status!='deleted'",(row['rule_id'],))
            self.audit(db,actor,'revoked',ref,None,{})
        return {'status':'revoked','grant_id':ref}

    def revoke_runtime(self,kind,key,reason):
        if kind is not UnitKind.APP:return
        with self.db.transaction(write=True) as db:
            rows=db.execute("SELECT id,owner,rule_id FROM package_hook_grants WHERE state='active' AND json_extract(spec_json,'$.consumer.binding.runtime_key')=?",(key,)).fetchall()
            for row in rows:
                db.execute("UPDATE package_hook_grants SET state='revoked',error=? WHERE id=?",(reason,row['id']))
                db.execute("UPDATE hook_rules SET status='paused',error='package_consent_revoked' WHERE id=? AND status!='deleted'",(row['rule_id'],))
                self.audit(db,row['owner'],'package_revoked',row['id'],None,{'reason':reason})

    def grants(self,actor):
        with self.db.transaction() as db:
            rows=[dict(r) for r in db.execute('SELECT g.*,r.status AS rule_status,r.revision AS rule_revision FROM package_hook_grants g JOIN hook_rules r ON r.id=g.rule_id WHERE g.owner=? ORDER BY g.approved DESC LIMIT 100',(actor,))]
        result=[]
        for row in rows:
            spec=json.loads(row['spec_json']);b=spec['consumer']['binding'];status=row['state'];error=row['error']
            if row['rule_status']=='deleted':status='deleted'
            if status=='active':
                try:
                    self.hooks._validate(actor,spec)
                    with self.db.transaction() as db:row['accepted_release_json']=db.execute('SELECT accepted_release_json FROM package_hook_grants WHERE id=?',(row['id'],)).fetchone()[0]
                except (ValueError,PermissionError,KeyError):status='needs_consent';error='package_or_scope_changed'
            if row['expires']<=self.hooks.clock():status='expired'
            if row['rule_status']!='active' and status=='active':status=row['rule_status']
            result.append({'id':row['id'],'rule_id':row['rule_id'],'revision':row['rule_revision'],'state':status,'error':error,'consumer':b['display_name'],
                'package_id':b['package_id'],'mini_app_id':b['mini_app_id'],'expires':row['expires'],'approved':row['approved'],
                'approved_release':b['release'],'accepted_release':json.loads(row['accepted_release_json']),
                'permissions':{'event_type':spec['event_type'],'scope':spec['scope'],'subjects':spec['subjects'],'filters':spec['filters'],'background':spec['mode']=='background','read_details':spec['package_consent']['read_details'],'actions':spec.get('execution',{}).get('actions',[])}})
        return {'items':result}

    def matches(self,binding,spec):return all(binding[k]==spec['consumer']['binding'][k] for k in IDENTITY)

    async def inbox(self,p,binding,*,ack=None,detail=None):
        self.validate(p.actor_user_id,binding);items=[]
        with self.db.transaction() as db:
            rows=[dict(r) for r in db.execute('''SELECT d.*,v.spec_json,h.result_json FROM hook_deliveries d
                JOIN hook_rules r ON r.id=d.rule_id JOIN hook_rule_revisions v ON v.rule_id=r.id AND v.revision=r.revision
                LEFT JOIN hook_reports h ON h.delivery_id=d.id
                WHERE r.owner=? AND r.status='active' AND d.rule_revision=r.revision
                AND json_extract(v.spec_json,'$.consumer.binding.instance_id')=?
                AND json_extract(v.spec_json,'$.consumer.binding.mini_app_id') IS ?
                AND json_extract(v.spec_json,'$.consumer.registration') IN (?,?)
                AND (? IS NULL OR d.id=?) AND (? IS NULL OR d.id=?)
                AND (? IS NOT NULL OR ? IS NOT NULL OR NOT EXISTS(SELECT 1 FROM hook_consumer_acks a WHERE a.delivery_id=d.id))
                ORDER BY d.event_sequence LIMIT 100''',(p.actor_user_id,binding['instance_id'],binding['mini_app_id'],APP,MINI,ack,ack,detail,detail,ack,detail))]
        for row in rows:
            spec=json.loads(row['spec_json'])
            if not self.matches(binding,spec):continue
            try:self.hooks._validate(p.actor_user_id,spec);event=self.runtime.business_events.read(p.actor_user_id,row['event_id'])
            except (ValueError,PermissionError,KeyError):continue
            if detail:
                permission=spec['package_consent']
                definition=self.runtime.business_events.types[spec['event_type']]
                if not permission['read_details'] or list(definition.details or ())!=permission['details_binding']:raise PermissionError('Detail read was not approved or interface changed')
                provider=self.runtime.app_capability_router.providers.get(definition.details[1])
                if not provider or (provider.capability,provider.id,provider.version)!=tuple(definition.details):raise PermissionError('Approved detail Provider changed')
                router=self.runtime.app_capability_router
                if provider.id in router.disabled(p.actor_user_id,p.installation_id) or not self.runtime.services.get_tool(definition.details[0]).enabled:raise PermissionError('Approved detail interface disabled')
                with self.db.transaction(write=True) as db:
                    cached=db.execute('SELECT * FROM package_hook_detail_reads WHERE delivery_id=? AND owner=?',(detail,p.actor_user_id)).fetchone()
                    if cached and cached['result_json']:return json.loads(cached['result_json'])
                    if cached and cached['attempts']>=3:raise PermissionError('Detail read retry budget exhausted')
                    db.execute('INSERT INTO package_hook_detail_reads VALUES(?,?,1,NULL) ON CONFLICT(delivery_id) DO UPDATE SET attempts=attempts+1',(detail,p.actor_user_id))
                sid=self.session_for(p.actor_user_id,binding)
                context=replace(ToolCallContext.from_principal(p,caller_id='package:approved-event-detail',session_id=sid),pinned_provider=tuple(definition.details))
                output=await self.runtime.tools.execute(definition.details[0],{'event_id':event['id'],'provider':definition.details[1]},context=context)
                self.hooks._validate(p.actor_user_id,spec)
                serialized=canonical_json(output.output)
                if len(serialized.encode())>48000:raise ValueError('Event detail exceeds inbox limit')
                with self.db.transaction(write=True) as db:db.execute('UPDATE package_hook_detail_reads SET result_json=? WHERE delivery_id=? AND owner=?',(serialized,detail,p.actor_user_id))
                return output.output
            report=json.loads(row['result_json']) if row['result_json'] else None
            if spec['mode']=='background' and report is None:continue
            items.append({'delivery_id':row['id'],'rule_id':row['rule_id'],'event':event,**({'result':report} if report else {})})
        if ack:
            if ack not in {item['delivery_id'] for item in items}:raise PermissionError('Package delivery unavailable')
            with self.db.transaction(write=True) as db:db.execute('INSERT OR IGNORE INTO hook_consumer_acks VALUES(?,?)',(ack,p.actor_user_id))
            return {'acknowledged':ack}
        if detail:raise PermissionError('Approved delivery unavailable')
        return {'items':items}


def install(runtime):
    host=PackageHooks(runtime);runtime.package_hooks=host
    for registration,kind in ((APP,'app'),(MINI,'mini-app')):
        runtime.event_hooks.register_consumer(ConsumerType(registration,kind,'ai2apps.package-hooks','1',host.validate,host.prepare,host.execute,host.session,
            effects=lambda settings:settings.get('actions',[]),authorize=host.authorize,needs_details=lambda settings:settings['read_details'],background_capabilities=('app.use',)))
    runtime.extension_manager.package_access_revoked=host.revoke_runtime
