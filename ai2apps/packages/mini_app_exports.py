"""Installed Mini-App declarations binding to explicit, trusted Host SDK protocols.

The signed Package owns its public capability/schema/presentation. Host protocols
are typed native API implementations, never publisher-selected Python callbacks.
Catalog entries alone cannot create bindings. All execution rechecks the installed
release, effective definition, placement and supported SDK version.
"""
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
import hashlib
import inspect
import threading
import json
from jsonschema import Draft202012Validator
from ai2apps.extensions import UnitKind
from ai2apps.apps.access import can_access_app
from ai2apps.services import ServiceRuntimeMode,ServiceInstanceStatus,ToolProviderError
from ai2apps.services.aaat import principal_for,validate_declaration
from ai2apps.services.capability_routing import CapabilityProvider,ProviderUnavailable

SCHEMA='ai2apps.mini-app-host-exports/v1'

def provider_key(package_id,mini,spec):
    return 'mini:'+hashlib.sha256(json.dumps([package_id,mini['id'],spec['host'],spec['name']]).encode()).hexdigest()


def declarations(mini,catalog=None):
    value=mini.get('aaat')
    if value is None:return []
    if not isinstance(value,dict) or set(value)!={'schema','exports'} or value['schema']!=SCHEMA:
        raise ValueError('Invalid Mini-App Host export declaration')
    exports=value['exports']
    if not isinstance(exports,list) or not 1<=len(exports)<=32:raise ValueError('Invalid Mini-App export count')
    signed=None if catalog is None else {(e['identity'],x['name'],x['interfaceVersion'])
        for e in catalog.get('entries',[]) if e['kind']=='mini-app' and e['agent']['mode']=='aaat'
        for x in e['agent']['exports']}
    placements={p['studio'] for p in mini.get('placements',[]) if isinstance(p,dict) and isinstance(p.get('studio'),str)}
    names=set();result=[]
    keys={'name','interfaceVersion','host','sdk','inputSchema','fields','displayName','summary','agentContext','selectionRequired','options'}
    for item in exports:
        if not isinstance(item,dict) or set(item)!=keys:raise ValueError('Incomplete Mini-App export')
        if not isinstance(item['name'],str) or not item['name'] or (item['host'],item['name']) in names:raise ValueError('Duplicate Mini-App export')
        if signed is not None and (mini['id'],item['name'],item['interfaceVersion']) not in signed:
            raise ValueError('Mini-App export differs from signed capability catalog')
        if item['host'] not in placements:raise ValueError('Export Host is not a declared Mini-App placement')
        if not isinstance(item['sdk'],str) or not isinstance(item['options'],dict) or not isinstance(item['selectionRequired'],bool):raise ValueError('Invalid Host SDK binding')
        schema=item['inputSchema']
        try:Draft202012Validator.check_schema(schema)
        except Exception as error:raise ValueError('Invalid Mini-App input schema') from error
        if schema.get('type')!='object' or not isinstance(schema.get('properties'),dict) or {'provider','parameters'}&set(schema['properties']):raise ValueError('Invalid Mini-App input schema')
        pending=[schema]
        while pending:
            node=pending.pop()
            if isinstance(node,dict):
                for key,v in node.items():
                    if key in ('$ref','$dynamicRef') and (not isinstance(v,str) or not v.startswith('#')):raise ValueError('Remote schema references are forbidden')
                    pending.append(v)
            elif isinstance(node,list):pending.extend(node)
        fields=item['fields']
        if not isinstance(fields,list) or any(not isinstance(f,dict) for f in fields) or len(fields)!=len(schema['properties']) or {f.get('key') for f in fields}!=set(schema['properties']):raise ValueError('Mini-App fields differ from input schema')
        if any(f.get('type') not in {'text','number','boolean','select','asset','model','json','records','multiselect'} for f in fields):raise ValueError('Unsupported Mini-App parameter field')
        validate_declaration(item['agentContext'])
        if len(json.dumps(item).encode())>65536:raise ValueError('Mini-App export exceeds 64 KiB')
        names.add((item['host'],item['name']));result.append(deepcopy(item))
    return result


@dataclass(frozen=True)
class HostProtocol:
    key: str
    hosts: tuple
    execute: object
    describe: object = None
    policy: object = None
    effects: tuple = ()
    capabilities: tuple = ()
    timeout_ms: int = 900000
    form_setup: object = None
    discovery: object = None
    normalize: object = None


class MiniAppExportBinder:
    def __init__(self,runtime):
        self.runtime=runtime;self.protocols={};self.owned={};self.errors={};self.syncing=False;self.lock=threading.RLock()

    def register_protocol(self,protocol):
        if protocol.key in self.protocols:raise ValueError('Duplicate Host SDK protocol')
        if not callable(protocol.execute):raise ValueError('Host SDK requires a native executor')
        self.protocols[protocol.key]=protocol

    def releases(self):
        releases=deepcopy(self.runtime.registry_packages._load_state().get('installed',{}))
        for package in self.runtime.extension_manager._development_packages.values():
            manifest=package.manifest
            development=manifest.get('development',{})
            catalog=development.get('capabilityCatalog')
            if not catalog:continue
            pid=development['packageId']
            releases[pid]={'packageType':'app','version':package.package_version,
                'sha256':hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest(),
                'manifestSha256':package.effective_digest,'runtimeKey':package.package_id,
                'capabilityCatalog':catalog,'developmentSource':str(package.source_root)}
        return releases

    def effective(self,stored):
        if stored.get('developmentSource'):
            package=self.runtime.extension_manager._development_packages.get(stored['runtimeKey'])
            if package and str(package.source_root)==stored['developmentSource']:
                return SimpleNamespace(manifest=package.manifest,upstream_digest='sha256:'+stored['sha256'])
            return None
        return self.runtime.extension_manager.repository.effective(UnitKind.APP,stored['runtimeKey'])

    def unregister_protocol(self,key):
        self.protocols.pop(key,None)
        self.sync()

    def is_placement(self,provider,host,mini_id):
        if provider.id not in self.owned or provider.mini_app_id!=mini_id:return False
        for pid,stored in self.releases().items():
            if stored.get('runtimeKey')!=provider.app_id:continue
            effective=self.effective(stored)
            if effective is None:continue
            for mini in effective.manifest.get('mini_apps',[]):
                if mini.get('id')!=mini_id:continue
                for spec in declarations(mini,stored.get('capabilityCatalog')):
                    if spec['host']==host and spec['name']==provider.capability and provider.id==provider_key(pid,mini,spec):
                        try:self.binding(pid,stored,mini,spec);return True
                        except ProviderUnavailable:return False
        return False

    def binding(self,pid,stored,mini,spec):
        r=self.runtime
        if r.extension_manager.builtin_mini_app_owner(spec['host'],mini['id']):
            raise ProviderUnavailable('Mini-App identity is owned by the built-in product')
        current=self.releases().get(pid)
        if current is None or any(current.get(k)!=stored.get(k) for k in ('version','sha256','manifestSha256','runtimeKey','capabilityCatalog','developmentSource')):raise ProviderUnavailable('Installed Mini-App release changed')
        definition=r.extension_manager._active_app_definition(stored['runtimeKey'])
        effective=self.effective(stored)
        if not definition or definition['status']!='enabled' or effective is None or effective.upstream_digest.removeprefix('sha256:')!=stored['sha256']:raise ProviderUnavailable('Mini-App Package is not active')
        active=next((m for m in effective.manifest.get('mini_apps',[]) if m.get('id')==mini['id']),None)
        if active!=mini or spec not in declarations(active,stored.get('capabilityCatalog')):raise ProviderUnavailable('Effective Mini-App declaration changed')
        protocol=self.protocols.get(spec['sdk'])
        if protocol is None or spec['host'] not in protocol.hosts:raise ProviderUnavailable('Required Host SDK protocol is unavailable')
        return effective,protocol

    def sync(self):
        with self.lock:
            if self.syncing:return
            self.syncing=True
            try:self._sync()
            finally:self.syncing=False

    def _sync(self):
        r=self.runtime;desired={};self.errors={}
        for pid,stored in self.releases().items():
            if stored.get('packageType')!='app':continue
            effective=self.effective(stored)
            if effective is None:continue
            for mini in effective.manifest.get('mini_apps',[]):
                try:specs=declarations(mini,stored.get('capabilityCatalog'))
                except (ValueError,KeyError,TypeError):
                    self.errors[pid]='invalid_mini_app_export';continue
                for spec in specs:
                    key=provider_key(pid,mini,spec)
                    try:
                        _,protocol=self.binding(pid,stored,mini,spec)
                        version=hashlib.sha256(json.dumps([stored,mini,spec],sort_keys=True).encode()).hexdigest()
                        desired[key]=(pid,deepcopy(stored),deepcopy(mini),deepcopy(spec),protocol,version)
                    except ProviderUnavailable:self.errors[key]='host_sdk_or_release_unavailable'
        for key,version in list(self.owned.items()):
            if key not in desired or desired[key][-1]!=version:
                r.app_capability_router.unregister(key);self.owned.pop(key)
        for key,args in desired.items():
            if key not in self.owned:
                r.app_capability_router.register(self.provider(key,*args));self.owned[key]=args[-1]
                if args[4].form_setup:args[4].form_setup(r,key,args[2],args[3])
        service=r.services.ensure_service(service_key='ai2apps.package-mini-app-adapters',package_id='ai2apps.core',package_version='1.0.0',display_name='Installed Mini-App Host SDK gateway',runtime_mode=ServiceRuntimeMode.IN_PROCESS,capabilities=('app.invoke',),config={})
        instance=r.services.ensure_instance(service_id=service.id,provider_key='builtin:mini-app-sdk',status=ServiceInstanceStatus.RUNNING,endpoint=None,health={'status':'ok'})
        active=set()
        for name in {x[3]['name'] for x in desired.values()}:
            entries=[x for x in desired.values() if x[3]['name']==name]
            try:old=r.services.get_tool(name)
            except Exception:old=None
            shared=bool(old and getattr(r.service_registry,'capability_gateways',{}).get(name)==old.service_id
                and all(set(x[4].effects)<=set(old.effects) and set(x[4].capabilities)<=set(old.required_capabilities) for x in entries))
            if old and old.service_id!=service.id and not shared:
                for key in [k for k,x in desired.items() if x[3]['name']==name]:
                    r.app_capability_router.unregister(key);self.owned.pop(key,None);self.errors[key]='gateway_collision'
                continue
            if shared:continue
            schema={'type':'object','properties':{'provider':{'type':'string'},'parameters':{'type':'object'}},'additionalProperties':True}
            r.services.ensure_tool(service_id=service.id,qualified_name=name,display_name=name,description='Installed Package Mini-App. Review the actual Package declaration before calling.',input_schema=schema,output_schema={'type':'object'},effects=tuple(sorted({e for x in entries for e in x[4].effects})),required_capabilities=tuple(sorted({c for x in entries for c in x[4].capabilities})),timeout_ms=max(x[4].timeout_ms for x in entries))
            async def invoke(args,context,name=name):return await r.app_capability_router.invoke(name,args,context)
            r.service_registry.bind_tool(name,provider_key=instance.provider_key,handler=invoke);active.add(name)
        r.services.disable_unseen_tools(service.id,active)

    def provider(self,key,pid,stored,mini,spec,protocol,version):
        r=self.runtime
        async def verify(principal):
            effective,current=self.binding(pid,stored,mini,spec)
            if current is not protocol:raise ProviderUnavailable('Host SDK changed')
            if not can_access_app(principal,effective.manifest):raise ToolProviderError('Mini-App access denied')
        async def describe(principal,model=None):
            await verify(principal)
            data=await protocol.describe(r,principal,model,mini,spec) if protocol.describe else {}
            if not isinstance(data,dict):raise ToolProviderError('Invalid Host SDK descriptor')
            schema=deepcopy(spec['inputSchema'])
            native=data.get('effective_schema')
            if native:
                if set(native.get('properties',{}))-set(schema['properties']):raise ValueError('Host SDK interface differs from Package')
                schema['allOf']=[*schema.get('allOf',[]),deepcopy(native)]
                for name,rule in native.get('properties',{}).items():
                    if 'default' in rule and Draft202012Validator(schema['properties'][name]).is_valid(rule['default']):
                        schema['properties'][name]['default']=deepcopy(rule['default'])
            fields=deepcopy(spec['fields'])
            # A trusted typed Host SDK may refine presentation/options for signed
            # fields, but cannot add parameter identities outside the Package.
            refinements={f['key']:f for f in data.get('fields',[]) if isinstance(f,dict) and f.get('key') in schema['properties']}
            fields=[{**f,**{k:v for k,v in refinements.get(f['key'],{}).items() if k in ('type','options')}} for f in fields]
            return {**data,'effective_schema':schema,'fields':fields,
                    'selection_required':spec['selectionRequired']}
        async def prepare(args,context):
            principal=principal_for(r,context);await verify(principal)
            data=await describe(principal)
            if data.get('configuration_required'):raise ValueError('Host SDK requires model configuration; parameters and materials are preserved')
            values=deepcopy(args)
            if protocol.normalize:values=await protocol.normalize(r,values,context,mini,spec)
            if not protocol.normalize:
                for field,rule in data['effective_schema']['properties'].items():
                    if field not in values and 'default' in rule:values[field]=deepcopy(rule['default'])
            from ai2apps.agents.artifact_outputs import bind_output_materials
            if context.session_id:
                values=bind_output_materials(r,principal,context.session_id,data['effective_schema'],values)
            Draft202012Validator(data['effective_schema']).validate(values)
            return values
        async def execute(args,context):
            from ai2apps.api.ownership import authorize_session
            if not context.session_id:raise ToolProviderError('Owned Session required')
            authorize_session(r,principal_for(r,context),context.session_id)
            args=await prepare(args,context)
            value=protocol.execute(r,args,context,mini,spec)
            result=await value if inspect.isawaitable(value) else value
            try:await verify(principal_for(r,context))
            except Exception as error:raise ToolProviderError('Package changed after submission; verify outcome without retrying') from error
            if not isinstance(result,dict):raise ToolProviderError('Host SDK returned an invalid result; verify outcome without retrying')
            return {**result,'app_id':stored['runtimeKey'],'mini_app_id':mini['id']}
        async def policy(args,context):
            await verify(principal_for(r,context))
            return await protocol.policy(r,args,context,mini,spec) if protocol.policy else False
        return CapabilityProvider(key,spec['name'],stored['runtimeKey'],execute,mini_app_id=mini['id'],version=version,
            describe=describe,prepare=prepare,invocation_policy=policy,configuration_app_id=spec['host'],display_name=deepcopy(spec['displayName']),summary=deepcopy(spec['summary']),agent_context=deepcopy(spec['agentContext']),priority=50,
            discovery_context=(lambda context:protocol.discovery(r,context,mini,spec)) if protocol.discovery else None)
