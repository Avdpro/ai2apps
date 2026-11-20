"""Persistent subscriptions with explicit, pinned consumer delegations."""
from __future__ import annotations

import hashlib
import json
import math
import logging
import time
from dataclasses import dataclass
from typing import Callable
from uuid import uuid4

from jsonschema import Draft202012Validator
from ai2apps.storage.records import canonical_json
from ai2apps.apps.access import has_app_capability


class HookError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ConsumerType:
    id: str
    kind: str
    app_id: str
    version: str
    validate: Callable  # trusted (actor, binding) -> canonical binding or exception
    prepare: Callable | None = None  # trusted (actor, binding, settings) -> frozen owner plan
    execute: Callable | None = None  # trusted async (HookWork, TaskContext) -> report
    session: Callable | None = None  # trusted (HookWork) -> owned execution Session
    effects: Callable | None = None  # trusted (settings) -> frozen registered action plans
    authorize: Callable | None = None  # host consent check (actor, frozen spec)
    needs_details: Callable | None = None  # host (settings) -> bool
    background_capabilities: tuple[str,...] = ('app.use','app.coder.use')


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class HookSubscriptions:
    MAX_RULES = 100
    MAX_MATCHES = 1000

    def __init__(self, business, *, clock=time.time):
        self.business, self.db, self.clock = business, business.database, clock
        self.consumers = {}
        logging.getLogger(__name__).info("Persistent Hook subscriptions loaded; source=%s", __file__)

    def register_consumer(self, consumer):
        if consumer.id in self.consumers or consumer.kind not in ('bot', 'app', 'mini-app'):
            raise ValueError('Invalid or duplicate Hook consumer')
        self.consumers[consumer.id] = consumer
        if getattr(self,'execution',None):self.execution.register(consumer)

    def catalog(self):
        return [dict(registration=c.id, kind=c.kind, app_id=c.app_id, version=c.version,
                     mode='observe_only',modes=['observe_only', 'background'] if c.execute and c.prepare else ['observe_only']) for c in self.consumers.values()]

    def normalize(self, actor, value):
        if set(value)-{'consumer','event_type','subjects','filters','scope','execution'} or not {'consumer','event_type','subjects','filters'}<=set(value):
            raise HookError('invalid_rule', 'A rule requires consumer, event_type, subjects and filters')
        target = value['consumer']
        if (not isinstance(target, dict) or set(target) != {'registration', 'binding'}
                or not isinstance(target['registration'],str) or not isinstance(target['binding'],dict)
                or not isinstance(value['event_type'],str)):
            raise HookError('invalid_consumer', 'Select a registered consumer and binding')
        consumer = self.consumers.get(target['registration'])
        definition = self.business.types.get(value['event_type'])
        if consumer is None or definition is None:
            raise HookError('registration_unavailable', 'Event type or consumer is unavailable')
        binding = consumer.validate(actor, target['binding'])
        if not isinstance(binding,dict):raise HookError('invalid_consumer','Consumer binding must be structured data')
        scope=value.get('scope','subjects')
        if scope not in ('subjects','owned_collection'):raise HookError('invalid_scope','Unknown subscription scope')
        subjects = value['subjects']
        if (not isinstance(subjects, list) or not (0 if scope=='owned_collection' else 1) <= len(subjects) <= 20
                or any(not isinstance(x,str) or not 1 <= len(x) <= 300 for x in subjects)):
            raise HookError('invalid_subjects', 'Select between one and twenty explicit resource IDs')
        subjects = sorted(set(subjects))
        if scope=='owned_collection' and (subjects or definition.authorize_collection is None or not definition.authorize_collection(actor)):
            raise HookError('subscription_denied','Owned collection scope is not declared or authorized')
        if not all(definition.authorize(actor, subject) for subject in subjects):
            raise HookError('subscription_denied', 'Resource scope is unavailable')
        filters = value['filters']
        if not isinstance(filters, list) or len(filters) > 12:
            raise HookError('invalid_filter', 'At most twelve AND conditions are allowed')
        normalized = []
        for item in filters:
            if not isinstance(item, dict) or set(item) != {'field','op','value'}:
                raise HookError('invalid_filter','A condition requires field, op and value')
            field, op, val = item['field'], item['op'], item['value']
            if field not in definition.filters or op not in ('eq','in','gt','gte','lt','lte'):
                raise HookError('invalid_filter','Filter field or operation is not declared')
            schema = definition.schema['properties'][field]
            if op in ('gt','gte','lt','lte'):
                if schema.get('type') not in ('integer','number') or type(val) not in (int,float) or not math.isfinite(val):
                    raise HookError('invalid_filter','Range conditions require finite numbers')
            candidates = val if op == 'in' else [val]
            if not isinstance(candidates,list) or not 1 <= len(candidates) <= 20:
                raise HookError('invalid_filter','Set conditions require one to twenty values')
            for candidate in candidates:
                if type(candidate) in (int,float) and not math.isfinite(candidate):
                    raise HookError('invalid_filter','Filter numbers must be finite')
                if isinstance(candidate,(dict,list)):
                    raise HookError('invalid_filter','Filter values must be scalar')
                try:
                    Draft202012Validator(schema).validate(candidate)
                    # JSON Schema's boolean/integer separation must also apply to comparisons.
                    canonical_json(candidate)
                except Exception as exc:
                    raise HookError('invalid_filter','Filter value does not match the declared schema') from exc
            normalized.append({'field':field,'op':op,'value':val})
        spec = dict(event_type=definition.name,event_version=definition.version,
                    declaration_revision=self.business.revision(definition),
                    consumer={'registration':consumer.id,'version':consumer.version,'binding':binding},
                    scope=scope,subjects=subjects,filters=normalized,mode='observe_only')
        if value.get('execution') is not None:
            request=value['execution']
            if (not isinstance(request,dict) or set(request)-{'settings','expires_in'}
                    or not isinstance(request.get('settings',{}),dict)
                    or type(request.get('expires_in',86400)) is not int
                    or not 60<=request.get('expires_in',86400)<=604800):
                raise HookError('invalid_execution','Select settings and a delegation duration of 60–604800 seconds')
            if not consumer.prepare or not consumer.execute:
                raise HookError('invalid_execution','This event/consumer has no trusted execution entry')
            from ai2apps.system_tasks.sessions import execution_principal
            principal=execution_principal(self.execution.runtime,actor)
            if not all(has_app_capability(principal,c) for c in consumer.background_capabilities):
                raise PermissionError('Background delegation requires desktop development access')
            settings=consumer.prepare(actor,binding,request.get('settings',{}))
            read_details=consumer.needs_details(settings) if consumer.needs_details else True
            if read_details and not definition.details:raise HookError('invalid_execution','Event has no details interface')
            spec['mode']='background'
            spec['execution']={'installation_id':principal.installation_id,
                'expires_at':self.clock()+request.get('expires_in',86400),
                'details_binding':list(definition.details) if read_details else None,
                'settings':settings,
                'policy':{'read_only':True,'max_depth':8,'max_activations':20,'max_seconds':900,'max_tool_calls':12}}
            if consumer.effects:
                actions=consumer.effects(spec['execution']['settings'])
                spec['execution']['actions']=actions
                spec['execution']['policy']['read_only']=not bool(actions)
        if len(canonical_json(spec).encode()) > 16000:
            raise HookError('invalid_rule','Rule is too large')
        return spec

    def _validate(self, actor, spec, *, consent=True):
        definition = self.business.types.get(spec['event_type'])
        consumer = self.consumers.get(spec['consumer']['registration'])
        if (definition is None or consumer is None or definition.version != spec['event_version']
                or self.business.revision(definition) != spec['declaration_revision']
                or consumer.version != spec['consumer']['version']):
            raise HookError('declaration_changed','Event or consumer declaration changed; preview the rule again')
        if consent and consumer.authorize:consumer.authorize(actor,spec)
        if consumer.validate(actor,spec['consumer']['binding']) != spec['consumer']['binding']:
            raise HookError('consumer_changed','Consumer binding changed')
        if spec.get('scope')=='owned_collection' and (definition.authorize_collection is None or not definition.authorize_collection(actor)):
            raise HookError('subscription_denied','Collection authorization was revoked')
        if not all(definition.authorize(actor,s) for s in spec['subjects']):
            raise HookError('subscription_denied','Resource authorization was revoked')
        if spec.get('mode')=='background':
            plan=spec['execution']
            from ai2apps.system_tasks.sessions import execution_principal
            principal=execution_principal(self.execution.runtime,actor)
            if principal.installation_id!=plan['installation_id'] or not all(has_app_capability(principal,c) for c in consumer.background_capabilities):
                raise HookError('subscription_denied','Background authority revoked')
            if not consumer.prepare or not consumer.execute or (list(definition.details or ()) if (consumer.needs_details(plan['settings']) if consumer.needs_details else True) else None)!=plan['details_binding']:
                raise HookError('declaration_changed','Background execution entry changed')
            if (consumer.effects(plan['settings']) if consumer.effects else [])!=plan.get('actions',[]):
                raise HookError('declaration_changed','Frozen action scope changed')
            if consumer.prepare(actor,spec['consumer']['binding'],plan['settings'])!=plan['settings'] or plan['expires_at']<=self.clock():
                raise HookError('subscription_denied','Background delegation expired or owner settings changed')
        return definition

    def preview(self, actor, value):
        spec = self.normalize(actor,value)
        preview_id = 'hp_' + uuid4().hex
        expires = self.clock()+600
        with self.db.transaction(write=True) as db:
            db.execute('DELETE FROM hook_previews WHERE expires<?',(self.clock(),))
            if db.execute('SELECT count(*) FROM hook_previews WHERE owner=? AND consumed=0',(actor,)).fetchone()[0]>=100:
                raise HookError('quota_exceeded','Unconsumed preview quota reached')
            db.execute('INSERT INTO hook_previews VALUES(?,?,?,?,0)',(preview_id,actor,canonical_json(spec),expires))
        return dict(preview_ref=preview_id,expires_at=expires,rule=spec,mode=spec['mode'])

    @staticmethod
    def _high(db):
        return db.execute("SELECT COALESCE((SELECT seq FROM sqlite_sequence WHERE name='events'),0)").fetchone()[0]

    def _request(self, db, actor, key, signature):
        if not isinstance(key,str) or not 8 <= len(key) <= 128:
            raise HookError('invalid_request','A stable request_id of 8–128 characters is required')
        row = db.execute('SELECT * FROM hook_requests WHERE owner=? AND request_id=?',(actor,key)).fetchone()
        if row:
            if row['signature'] != signature:
                raise HookError('request_conflict','Request ID is already bound to a different operation')
            return json.loads(row['result_json'])

    @staticmethod
    def _record(db, actor, key, signature, result):
        db.execute('INSERT INTO hook_requests VALUES(?,?,?,?)',(actor,key,signature,canonical_json(result)))
        return result

    @staticmethod
    def _owned(db, actor, rule_id, *, include_deleted=False):
        query="SELECT * FROM hook_rules WHERE id=? AND owner=?"
        if not include_deleted:query+=" AND status!='deleted'"
        row = db.execute(query,(rule_id,actor)).fetchone()
        if row is None:
            raise HookError('rule_not_found','Hook rule unavailable')
        return dict(row)

    def save(self, actor, preview_ref, request_id, *, rule_id=None, expected_revision=None, admission=None):
        signature = digest(dict(action='save',preview=preview_ref,rule_id=rule_id,revision=expected_revision))
        with self.db.transaction() as db:
            old = self._request(db,actor,request_id,signature)
            if old is not None:
                return old
            preview = db.execute('SELECT * FROM hook_previews WHERE id=? AND owner=?',(preview_ref,actor)).fetchone()
        if preview is None or preview['expires'] <= self.clock():
            raise HookError('preview_expired','Preview unavailable or expired')
        spec = json.loads(preview['spec_json'])
        self._validate(actor,spec,consent=admission is None)
        with self.db.transaction(write=True) as db:
            old = self._request(db,actor,request_id,signature)
            if old is not None:
                return old
            live_preview=db.execute('SELECT * FROM hook_previews WHERE id=? AND owner=?',(preview_ref,actor)).fetchone()
            if live_preview is None or live_preview['consumed']:
                raise HookError('preview_consumed','Preview was already used')
            if preview['expires'] <= self.clock():
                raise HookError('preview_expired','Preview expired')
            high = self._high(db)
            if rule_id:
                row = self._owned(db,actor,rule_id)
                if row['revision'] != expected_revision:
                    raise HookError('revision_conflict','Hook rule changed')
                if row['status'] == 'paused':
                    # Reapproval replaces a paused rule from now; stale backlog cannot gain new authority.
                    db.execute("UPDATE hook_rule_revisions SET scan_state='skipped',end_sequence=COALESCE(end_sequence,?) WHERE rule_id=? AND scan_state='active'",(high,rule_id))
                    db.execute("UPDATE hook_rule_revisions SET end_sequence=? WHERE rule_id=? AND revision=? AND scan_state='skipped'",(high,rule_id,row['revision']))
                # Editing a delegation revokes its pending execution authority;
                # old observation-only revisions retain E2 filter boundaries.
                db.execute("UPDATE hook_rule_revisions SET scan_state='skipped',end_sequence=COALESCE(end_sequence,?) WHERE rule_id=? AND scan_state='active' AND json_extract(spec_json,'$.mode')='background'",(high,rule_id))
                revision = row['revision']+1
                db.execute('UPDATE hook_rule_revisions SET end_sequence=? WHERE rule_id=? AND end_sequence IS NULL',(high,rule_id))
                db.execute("UPDATE hook_rules SET status='active',revision=?,error=NULL WHERE id=?",(revision,rule_id))
            else:
                count = db.execute("SELECT count(*) FROM hook_rules WHERE owner=? AND status!='deleted'",(actor,)).fetchone()[0]
                if count >= self.MAX_RULES:
                    raise HookError('quota_exceeded','Hook rule quota reached')
                rule_id, revision = 'hook_'+uuid4().hex, 1
                db.execute("INSERT INTO hook_rules VALUES(?,?,'active',?,NULL,?)",(rule_id,actor,revision,self.clock()))
            db.execute('INSERT INTO hook_rule_revisions VALUES(?,?,?,?,?,NULL,?,?)',
                       (rule_id,revision,canonical_json(spec),high,high,self.clock(),'active'))
            if admission:admission(db,spec,rule_id,revision)
            db.execute('UPDATE hook_previews SET consumed=1 WHERE id=?',(preview_ref,))
            result=dict(id=rule_id,revision=revision,status='active',starts_after=high,mode=spec['mode'])
            return self._record(db,actor,request_id,signature,result)

    def change(self, actor, rule_id, action, expected_revision, request_id):
        if action not in ('pause','resume','delete'):
            raise HookError('invalid_action','Unknown Hook action')
        signature=digest(dict(action=action,rule_id=rule_id,revision=expected_revision))
        # Check current owner resources before resuming, outside SQLite's write lock.
        if action == 'resume':
            with self.db.transaction() as db:
                old=self._request(db,actor,request_id,signature)
                if old is not None:return old
                row=self._owned(db,actor,rule_id)
                spec=json.loads(db.execute('SELECT spec_json FROM hook_rule_revisions WHERE rule_id=? AND revision=?',(rule_id,row['revision'])).fetchone()[0])
            self._validate(actor,spec)
        with self.db.transaction(write=True) as db:
            old=self._request(db,actor,request_id,signature)
            if old is not None:return old
            row=self._owned(db,actor,rule_id)
            if row['revision']!=expected_revision:
                raise HookError('revision_conflict','Hook rule changed')
            if action=='resume' and row['status']=='active':
                raise HookError('invalid_state','Hook rule is already active')
            high=self._high(db)
            # Pause/delete explicitly skip all still-unscanned ranges; these are audit records.
            if action in ('pause','delete'):
                db.execute("UPDATE hook_rule_revisions SET scan_state='skipped',end_sequence=COALESCE(end_sequence,?) WHERE rule_id=? AND scan_state='active'",(high,rule_id))
                previous=db.execute('SELECT spec_json FROM hook_rule_revisions WHERE rule_id=? AND revision=?',(rule_id,row['revision'])).fetchone()[0]
                db.execute('INSERT INTO hook_rule_revisions VALUES(?,?,?,?,?,?,?,?)',
                           (rule_id,row['revision']+1,previous,high,high,high,self.clock(),'skipped'))
                status='deleted' if action=='delete' else 'paused'
                db.execute('UPDATE hook_rules SET status=?,revision=revision+1,error=NULL WHERE id=?',(status,rule_id))
            else:
                revision=row['revision']+1
                db.execute("UPDATE hook_rule_revisions SET end_sequence=? WHERE rule_id=? AND revision=? AND scan_state='skipped'",(high,rule_id,row['revision']))
                db.execute('INSERT INTO hook_rule_revisions VALUES(?,?,?,?,?,NULL,?,?)',
                           (rule_id,revision,canonical_json(spec),high,high,self.clock(),'active'))
                db.execute("UPDATE hook_rules SET status='active',revision=?,error=NULL WHERE id=?",(revision,rule_id))
            return self._record(db,actor,request_id,signature,
                                dict(id=rule_id,revision=row['revision']+1,status='active' if action=='resume' else status,mode=json.loads(db.execute('SELECT spec_json FROM hook_rule_revisions WHERE rule_id=? AND revision=?',(rule_id,row['revision'])).fetchone()[0])['mode']))

    def rules(self, actor):
        with self.db.transaction() as db:
            rows=db.execute("SELECT * FROM hook_rules WHERE owner=? AND status!='deleted' ORDER BY created,id",(actor,)).fetchall()
            return [dict(r) for r in rows]

    def get(self, actor, rule_id):
        with self.db.transaction() as db:
            row=self._owned(db,actor,rule_id,include_deleted=True)
            revisions=db.execute('SELECT * FROM hook_rule_revisions WHERE rule_id=? ORDER BY revision',(rule_id,)).fetchall()
        return {**row,'revisions':[{k:v for k,v in dict(r).items() if k!='spec_json'} | {'spec':json.loads(r['spec_json'])} for r in revisions]}

    @staticmethod
    def _match(spec, data):
        for f in spec['filters']:
            val=data.get(f['field']);expected=f['value'];op=f['op']
            if f['field'] not in data:return False
            same=lambda a,b: a==b and (type(a) is bool)==(type(b) is bool)
            if op=='eq' and not same(val,expected):return False
            if op=='in' and not any(same(val,x) for x in expected):return False
            if op=='gt' and not val>expected:return False
            if op=='gte' and not val>=expected:return False
            if op=='lt' and not val<expected:return False
            if op=='lte' and not val<=expected:return False
        return True

    def scan(self, limit=100):
        if not 1<=limit<=500:raise ValueError('Invalid scan batch')
        with self.db.transaction() as db:
            revisions=[dict(r) for r in db.execute('''SELECT v.*,r.owner FROM hook_rule_revisions v JOIN hook_rules r ON r.id=v.rule_id
                WHERE r.status='active' AND v.scan_state='active' ORDER BY v.created,v.revision''')]
        for rev in revisions:
            spec=json.loads(rev['spec_json'])
            try:
                self._validate(rev['owner'],spec)
            except (HookError,PermissionError,KeyError,ValueError) as exc:
                self._pause_error(rev['rule_id'],getattr(exc,'code','consumer_unavailable'))
                continue
            with self.db.transaction(write=True) as db:
                current=db.execute('''SELECT v.*,r.status FROM hook_rule_revisions v JOIN hook_rules r ON r.id=v.rule_id
                    WHERE v.rule_id=? AND v.revision=?''',(rev['rule_id'],rev['revision'])).fetchone()
                if current['status']!='active' or current['scan_state']!='active':continue
                floor=db.execute('SELECT floor_sequence FROM business_event_retention WHERE id=1').fetchone()[0]
                if current['cursor']<floor:
                    db.execute("UPDATE hook_rules SET status='paused',error='cursor_gap' WHERE id=?",(rev['rule_id'],))
                    continue
                high=current['end_sequence'] if current['end_sequence'] is not None else self._high(db)
                rows=db.execute('''SELECT * FROM business_event_facts WHERE owner=? AND sequence>? AND sequence<=?
                    ORDER BY sequence LIMIT ?''',(rev['owner'],current['cursor'],high,limit)).fetchall()
                matches=db.execute('SELECT count(*) FROM hook_deliveries WHERE rule_id=?',(rev['rule_id'],)).fetchone()[0]
                cursor=current['cursor']
                for event in rows:
                    if event['type']==spec['event_type'] and (spec.get('scope')=='owned_collection' or event['subject_id'] in spec['subjects']):
                        if event['declaration_revision']!=spec['declaration_revision']:
                            db.execute("UPDATE hook_rules SET status='paused',error='declaration_changed' WHERE id=?",(rev['rule_id'],));break
                        if self._match(spec,json.loads(event['data_json'])):
                            if matches>=self.MAX_MATCHES:
                                db.execute("UPDATE hook_rules SET status='paused',error='quota_exceeded' WHERE id=?",(rev['rule_id'],));break
                            inserted=db.execute('''INSERT OR IGNORE INTO hook_deliveries
                                VALUES(?,?,?,?,?,'matched',?)''',('hd_'+uuid4().hex,rev['rule_id'],event['event_id'],event['sequence'],rev['revision'],self.clock())).rowcount
                            matches+=inserted
                    cursor=event['sequence']
                else:
                    if len(rows)<limit:cursor=high
                db.execute('UPDATE hook_rule_revisions SET cursor=? WHERE rule_id=? AND revision=?',(cursor,rev['rule_id'],rev['revision']))
                if current['end_sequence'] is not None and cursor>=high:
                    db.execute("UPDATE hook_rule_revisions SET scan_state='complete' WHERE rule_id=? AND revision=?",(rev['rule_id'],rev['revision']))
        return len(revisions)

    def _pause_error(self, rule_id, code):
        with self.db.transaction(write=True) as db:
            db.execute("UPDATE hook_rules SET status='paused',error=? WHERE id=? AND status='active'",(code,rule_id))

    def deliveries(self, actor, rule_id, *, after=0, limit=50):
        if after<0 or not 1<=limit<=100:raise HookError('invalid_cursor','Invalid delivery cursor')
        with self.db.transaction() as db:
            self._owned(db,actor,rule_id,include_deleted=True)
            rows=[dict(r) for r in db.execute('SELECT * FROM hook_deliveries WHERE rule_id=? AND event_sequence>? ORDER BY event_sequence LIMIT ?',(rule_id,after,limit))]
        items=[]
        for row in rows:
            # Revalidate both consumer and source rights at the read boundary.
            with self.db.transaction() as db:
                spec=json.loads(db.execute('SELECT spec_json FROM hook_rule_revisions WHERE rule_id=? AND revision=?',(rule_id,row['rule_revision'])).fetchone()[0])
            try:
                self._validate(actor,spec)
                event=self.business.read(actor,row['event_id'])
                with self.db.transaction() as db:
                    execution=db.execute('SELECT * FROM hook_executions WHERE delivery_id=?',(row['id'],)).fetchone()
                execution=dict(execution) if execution else None
                if execution:
                    execution['result']=json.loads(execution.pop('result_json') or 'null')
                items.append({**row,'event':event,'executed':bool(execution and execution['task_id']), 'execution':execution})
            except (PermissionError,KeyError,HookError,ValueError):
                items.append({'id':row['id'],'state':'unavailable','executed':False})
        return {'items':items,'next_cursor':rows[-1]['event_sequence'] if rows else after}
