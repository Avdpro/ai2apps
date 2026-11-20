"""Portable UI configuration contracts. Values never grant execution authority."""
from __future__ import annotations
import hashlib,json,logging,threading,uuid
from dataclasses import dataclass,field
from typing import Callable
from jsonschema import Draft202012Validator

LIMIT=16384


class StateError(ValueError):
    def __init__(self,code,message,path=''):
        super().__init__(message);self.code,self.path=code,path


def encoded(value):
    try:raw=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    except (ValueError,TypeError,RecursionError):raise StateError('invalid_state','State must be bounded JSON') from None
    if len(raw.encode())>LIMIT:raise StateError('state_too_large','State exceeds 16 KiB')
    def inspect(item,depth=0):
        if depth>16:raise StateError('state_too_deep','State exceeds nesting limit')
        if isinstance(item,dict):
            if any(k in ('__proto__','prototype','constructor') for k in item):raise StateError('invalid_key','Reserved state key')
            for v in item.values():inspect(v,depth+1)
        elif isinstance(item,list):
            for v in item:inspect(v,depth+1)
    inspect(value);return raw


def digest(value):return hashlib.sha256(encoded(value).encode()).hexdigest()


@dataclass(frozen=True)
class StateContract:
    app_id:str
    mini_app_id:str|None
    version:int
    name:str
    schema:dict
    clients:tuple[str,...]=('desktop','mobile')
    excluded_fields:tuple[str,...]=()
    migrations:dict[int,Callable]=field(default_factory=dict,compare=False)


class AppStateService:
    def __init__(self,runtime):
        self.runtime,self.db=runtime,runtime.database;self.contracts={};self.lock=threading.RLock()
        with self.db.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS portable_app_state_presets(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,installation TEXT NOT NULL,app_id TEXT NOT NULL,
                mini_app_id TEXT NOT NULL,name TEXT NOT NULL,packet_json TEXT NOT NULL,request_id TEXT NOT NULL,
                signature TEXT NOT NULL,UNIQUE(actor,installation,request_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS portable_app_state_applications(
                id TEXT PRIMARY KEY,actor TEXT NOT NULL,installation TEXT NOT NULL,instance_id TEXT NOT NULL,
                request_id TEXT NOT NULL,signature TEXT NOT NULL,contract_digest TEXT NOT NULL,
                status TEXT NOT NULL,result_json TEXT NOT NULL,UNIQUE(actor,installation,request_id))''')
        logging.getLogger(__name__).info('Portable App-State v1 loaded; source=%s',__file__)

    def register(self,contract):
        schema=json.loads(encoded(contract.schema))
        Draft202012Validator.check_schema(schema)
        if type(contract.version)!=int or contract.version<1 or schema.get('type')!='object' or schema.get('additionalProperties') is not False:
            raise StateError('invalid_contract','Contract requires a version and a closed object schema')
        if not schema.get('properties') or any(v.get('x-app-state')!='portable' for v in schema['properties'].values()):
            raise StateError('invalid_contract','Every exported field requires an explicit portable declaration')
        if set(schema.get('required',[]))!=set(schema['properties']):raise StateError('invalid_contract','Portable snapshots must declare all fields required')
        # Inline bounded schemas only: no network or filesystem schema resolution.
        def closed(value):
            if isinstance(value,dict):
                if '$ref' in value:raise StateError('invalid_contract','External schema references are not supported')
                if value.get('type')=='object' and value.get('additionalProperties') is not False:raise StateError('invalid_contract','Nested objects must be closed')
                for v in value.values():closed(v)
            elif isinstance(value,list):
                for v in value:closed(v)
        closed(schema)
        from dataclasses import replace
        owned=replace(contract,schema=schema,migrations=dict(contract.migrations))
        key=(contract.app_id,contract.mini_app_id)
        if key in self.contracts:raise StateError('duplicate_contract','Target already registered')
        self.contracts[key]=owned

    def describe(self,app_id,mini_app_id=None):
        c=self.contracts.get((app_id,mini_app_id))
        if not c:raise StateError('unsupported_target','App/Mini-App has not registered App-State')
        value={'app_id':c.app_id,'mini_app_id':c.mini_app_id,'contract_version':c.version,'name':c.name,
               'schema':c.schema,'clients':list(c.clients),'excluded_fields':list(c.excluded_fields)}
        return json.loads(encoded({**value,'contract_digest':digest(value)}))

    def authorize(self,principal,instance_id,app_id):
        row=self.runtime.extension_manager.require_instance_access(instance_id,principal)
        if row['package_id']!=app_id:raise PermissionError('State target does not match the owned App instance')
        if principal.authentication_type=='owner_home_lease':
            from ai2apps.remote.mobile_apps import app_enabled
            if not app_enabled(self.runtime,principal,app_id):raise PermissionError('App is disabled for Mobile')

    def validate(self,principal,instance_id,packet,*,migrate=False):
        encoded(packet)
        if not isinstance(packet,dict) or set(packet)!={'schema','target','values'} or packet['schema']!='ai2apps.app-state/v1':raise StateError('unsupported_envelope','Unsupported App-State envelope')
        target=packet['target']
        if not isinstance(target,dict) or set(target)!={'app_id','mini_app_id','contract_version'} or type(target['contract_version'])!=int or target['contract_version']<1 or not isinstance(target['app_id'],str) or not target['app_id'] or (target['mini_app_id'] is not None and not isinstance(target['mini_app_id'],str)):raise StateError('invalid_target','Invalid state target')
        self.authorize(principal,instance_id,target['app_id'])
        c=self.contracts.get((target['app_id'],target['mini_app_id']))
        if not c:raise StateError('unsupported_target','App/Mini-App has not registered App-State')
        client='mobile' if principal.authentication_type=='owner_home_lease' or principal.client_scope=='mobile' else 'desktop'
        if client not in c.clients:raise StateError('unsupported_client','State target is unavailable on this client')
        values=packet['values'];version=target['contract_version']
        if version!=c.version:
            if not migrate or version not in c.migrations:raise StateError('unsupported_version','State version requires an explicit supported migration')
            values=c.migrations[version](json.loads(encoded(values)))
        failures=sorted(Draft202012Validator(c.schema).iter_errors(values),key=lambda e:str(list(e.absolute_path)))
        if failures:
            error=failures[0];path='/'+('/'.join(str(x) for x in error.absolute_path))
            raise StateError('invalid_values',error.message,path)
        normalized={'schema':'ai2apps.app-state/v1','target':{'app_id':c.app_id,'mini_app_id':c.mini_app_id,'contract_version':c.version},'values':json.loads(encoded(values))}
        return {'packet':normalized,'fingerprint':digest(normalized),'contract_digest':self.describe(c.app_id,c.mini_app_id)['contract_digest'],'validation_scope':'portable_schema','requires_owner_validation':True}

    def save(self,p,instance,name,packet,request_id):
        name=name.strip()
        if not name or len(name)>80:raise StateError('invalid_name','State name must be 1–80 characters')
        value=self.validate(p,instance,packet);signature=digest({'name':name,'packet':value['packet']})
        with self.db.transaction(write=True) as db:
            old=db.execute('SELECT id,signature FROM portable_app_state_presets WHERE actor=? AND installation=? AND request_id=?',(p.actor_user_id,p.installation_id,request_id)).fetchone()
            if old:
                if old['signature']!=signature:raise StateError('request_conflict','Save request changed')
                return {'id':old['id'],'name':name,**value}
            ref=uuid.uuid4().hex;t=value['packet']['target']
            db.execute('INSERT INTO portable_app_state_presets VALUES(?,?,?,?,?,?,?,?,?)',(ref,p.actor_user_id,p.installation_id,t['app_id'],t['mini_app_id'] or '',name,encoded(value['packet']),request_id,signature))
        return {'id':ref,'name':name,**value}

    def list(self,p,instance,app,mini=None):
        self.authorize(p,instance,app);self.describe(app,mini)
        with self.db.transaction() as db:rows=db.execute('SELECT id,name,packet_json FROM portable_app_state_presets WHERE actor=? AND installation=? AND app_id=? AND mini_app_id=? ORDER BY rowid DESC LIMIT 100',(p.actor_user_id,p.installation_id,app,mini or '')).fetchall()
        return {'items':[{'id':r['id'],'name':r['name'],'packet':json.loads(r['packet_json'])} for r in rows]}

    def prepare(self,p,instance,packet,request_id,base_revision,contract_digest):
        value=self.validate(p,instance,packet)
        if value['contract_digest']!=contract_digest:raise StateError('contract_changed','Reload the current App-State contract')
        signature=digest({'instance':instance,'packet':value['packet'],'base_revision':base_revision,'contract_digest':contract_digest})
        with self.db.transaction(write=True) as db:
            old=db.execute('SELECT * FROM portable_app_state_applications WHERE actor=? AND installation=? AND request_id=?',(p.actor_user_id,p.installation_id,request_id)).fetchone()
            if old:
                if old['signature']!=signature:raise StateError('request_conflict','Restore request changed')
                return {'id':old['id'],'status':old['status'],**value}
            ref=uuid.uuid4().hex
            db.execute("INSERT INTO portable_app_state_applications VALUES(?,?,?,?,?,?,?,'prepared',?)",(ref,p.actor_user_id,p.installation_id,instance,request_id,signature,contract_digest,encoded({'fingerprint':value['fingerprint']})))
        return {'id':ref,'status':'prepared',**value}

    def complete(self,p,instance,ref,packet,status):
        if status not in ('ui_applied','failed'):raise StateError('invalid_status','Only a UI acknowledgement or failure is accepted')
        value=self.validate(p,instance,packet)
        with self.db.transaction(write=True) as db:
            row=db.execute('SELECT * FROM portable_app_state_applications WHERE id=? AND actor=? AND installation=? AND instance_id=?',(ref,p.actor_user_id,p.installation_id,instance)).fetchone()
            if not row:raise PermissionError('State application unavailable')
            if row['contract_digest']!=value['contract_digest']:raise StateError('contract_changed','Contract changed before acknowledgement')
            # Packet identity is included in the prepared result; the UI receipt proves
            # only a host UI acknowledgement, never a business operation or authority.
            if json.loads(row['result_json']).get('fingerprint')!=value['fingerprint']:raise StateError('packet_changed','Prepared state changed')
            receipt={'fingerprint':value['fingerprint'],'status':status}
            if row['status']!='prepared':
                if json.loads(row['result_json'])!=receipt:raise StateError('application_closed','State application already closed')
            else:db.execute('UPDATE portable_app_state_applications SET status=?,result_json=? WHERE id=?',(status,encoded(receipt),ref))
        return {'id':ref,**receipt}
