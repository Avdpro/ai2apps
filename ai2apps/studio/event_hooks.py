"""Package Mini-App event inbox. Signed declaration + digest survive UI unmounting.

The background entry is a host-owned read/project handler. No Package callback,
URL, Python source or frame-supplied authority is executed by the scheduler.
"""
import json
from ai2apps.events.hooks import ConsumerType
from ai2apps.system_tasks.sessions import execution_principal
from ai2apps.storage.repositories import SessionRepository
from .capability_broker import StudioCapabilityBroker, _declared_capabilities

REGISTRATION='studio.mini-app.event-inbox'
KEYS={'studio_id','mini_app_id','app_id','digest','app_instance_id'}


class MiniAppHooks:
    def __init__(self,runtime):self.runtime=runtime

    def declaration(self,actor,binding):
        if set(binding)!=KEYS or any(not isinstance(v,str) or not v for v in binding.values()):raise ValueError('Invalid Mini-App event binding')
        p=execution_principal(self.runtime,actor);m=self.runtime.extension_manager
        instance=m.require_instance_access(binding['app_instance_id'],p)
        with self.runtime.database.transaction() as db:
            row=db.execute('SELECT d.package_id,d.source FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id WHERE i.id=? AND d.status=\'enabled\'',(binding['app_instance_id'],)).fetchone()
        if row is not None and row['source']!='builtin':raise PermissionError('Installed Packages require host user consent')
        if not row or row[0]!=binding['app_id']:raise PermissionError('Mini-App instance changed')
        matches=[d for d in m.list_studio_mini_apps(binding['studio_id'],principal=p)
            if d.get('id')==binding['mini_app_id'] and d.get('provider',{}).get('appId')==binding['app_id']
            and d.get('provider',{}).get('digest')==binding['digest']]
        if len(matches)!=1 or 'events.subscribe' not in _declared_capabilities(matches[0]):raise PermissionError('Mini-App event subscription not declared or Package changed')
        return matches[0]

    def validate(self,actor,binding):
        self.declaration(actor,binding);return dict(binding)

    def prepare(self,actor,binding,settings):
        if settings:raise ValueError('The Mini-App inbox handler accepts no executable settings')
        if 'events.background' not in _declared_capabilities(self.declaration(actor,binding)):
            raise PermissionError('Mini-App background events not declared')
        return {}

    def session(self,work):
        binding=work.spec['consumer']['binding'];self.validate(work.actor,binding)
        with self.runtime.database.transaction() as db:
            old=db.execute("SELECT id FROM sessions WHERE app_instance_id=? AND status='active' AND json_extract(metadata_json,'$.mini_event_owner')=? ORDER BY created_at LIMIT 1",(binding['app_instance_id'],binding['mini_app_id'])).fetchone()
        if old:return old[0]
        from ai2apps.core import SessionVisibility
        return SessionRepository(self.runtime.database,self.runtime.events).create(app_instance_id=binding['app_instance_id'],
            title='Mini-App event inbox',visibility=SessionVisibility.UNLISTED,metadata={'mini_event_owner':binding['mini_app_id']}).id

    async def execute(self,work,ctx):
        details=await work.details()
        ctx.report(message='Mini-App 事件详情已就绪')
        return work.report({'handler':'event-inbox/v1','event_id':work.event['id'],'details':details})

    def mounted(self,p,studio,mount):
        mounted=StudioCapabilityBroker(self.runtime).mounted_mini_app(studio,mount,principal=p)
        b={'studio_id':studio,'mini_app_id':mounted.declaration['id'],'app_id':mounted.mount['app_key'],
           'digest':mounted.mount['effective_digest'],'app_instance_id':mounted.mount['app_instance_id']}
        self.validate(p.actor_user_id,b);return b

    def preview(self,p,studio,mount,proposal):
        mounted=StudioCapabilityBroker(self.runtime).mounted_mini_app(studio,mount,principal=p)
        if mounted.declaration.get('source')=='package' or mounted.mount.get('source') not in ('builtin',None):
            # The caller receives no preview token or active authorization.
            proposal=dict(proposal)
            execution=proposal.pop('execution',None)
            if execution is not None:
                proposal['background']=True
                proposal['expires_in']=execution.get('expires_in',86400)
                proposal.update(execution.get('settings',{}))
            proposal.setdefault('request_id',__import__('uuid').uuid4().hex)
            return self.runtime.package_hooks.request_mini(p,studio,mount,proposal)
        binding=self.mounted(p,studio,mount)
        if set(proposal)-{'event_type','scope','subjects','filters','execution'}:raise ValueError('Invalid event proposal')
        return self.runtime.event_hooks.preview(p.actor_user_id,{**proposal,
            'consumer':{'registration':REGISTRATION,'binding':binding},'subjects':proposal.get('subjects',[]),'filters':proposal.get('filters',[])})

    def inbox(self,p,studio,mount,*,ack=None):
        binding=self.mounted(p,studio,mount);items=[]
        with self.runtime.database.transaction() as db:
            rows=db.execute('''SELECT h.delivery_id,h.result_json,d.rule_id,d.event_sequence,v.spec_json
                FROM hook_reports h JOIN hook_deliveries d ON d.id=h.delivery_id
                JOIN hook_rule_revisions v ON v.rule_id=d.rule_id AND v.revision=d.rule_revision
                WHERE h.owner=? AND json_extract(h.consumer_json,'$.registration')=?
                AND json_extract(h.consumer_json,'$.binding.app_instance_id')=?
                AND json_extract(h.consumer_json,'$.binding.mini_app_id')=?
                AND json_extract(h.consumer_json,'$.binding.digest')=?
                AND json_extract(h.consumer_json,'$.binding.studio_id')=?
                AND (? IS NULL OR h.delivery_id=?)
                AND (? IS NOT NULL OR NOT EXISTS(SELECT 1 FROM hook_consumer_acks a WHERE a.delivery_id=h.delivery_id))
                ORDER BY h.rowid LIMIT 100''',(p.actor_user_id,REGISTRATION,binding['app_instance_id'],binding['mini_app_id'],binding['digest'],binding['studio_id'],ack,ack,ack)).fetchall()
        for row in rows:
            spec=json.loads(row['spec_json'])
            if spec['consumer']['binding']!=binding:continue
            try:
                self.runtime.event_hooks._validate(p.actor_user_id,spec)
                # Deletion/ownership loss invalidates even a cached report. A
                # metadata-only tombstone can be acknowledged without hiding later deliveries.
                event=self.runtime.business_events.read(p.actor_user_id,json.loads(row['result_json'])['event_id'])
                items.append({'delivery_id':row['delivery_id'],'rule_id':row['rule_id'],'event':event,'result':json.loads(row['result_json'])})
            except (ValueError,PermissionError,KeyError):
                items.append({'delivery_id':row['delivery_id'],'rule_id':row['rule_id'],'state':'unavailable'})
        if ack is not None:
            if ack not in {i['delivery_id'] for i in items}:raise PermissionError('Mini-App delivery unavailable')
            with self.runtime.database.transaction(write=True) as db:
                db.execute('INSERT OR IGNORE INTO hook_consumer_acks VALUES(?,?)',(ack,p.actor_user_id))
            return {'acknowledged':ack}
        return {'items':items}


def install(runtime):
    import logging
    logging.getLogger(__name__).info('Mini-App event host loaded; source=%s broker_source=%s',__file__,StudioCapabilityBroker.probe_declaration.__code__.co_filename)
    host=MiniAppHooks(runtime);runtime.mini_app_hooks=host
    runtime.event_hooks.register_consumer(ConsumerType(REGISTRATION,'mini-app','ai2apps.studio-hooks','1',host.validate,host.prepare,host.execute,host.session))
