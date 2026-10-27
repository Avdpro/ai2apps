"""Signed App-to-isolated-Service AaAT binding; no executable catalog callbacks."""
from copy import deepcopy
import hashlib
import json
import threading
import logging
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from jsonschema import Draft202012Validator
from ai2apps.extensions import UnitKind
from ai2apps.apps.access import can_access_app
from ai2apps.services import ServiceRuntimeMode, ServiceInstanceStatus, ToolProviderError, ServiceStatus
from ai2apps.services.aaat import principal_for, validate_declaration
from ai2apps.services.capability_routing import CapabilityProvider, ProviderUnavailable


def declarations(app, catalog, dependencies):
    if not isinstance(app,dict):raise ValueError('App definition must be an object')
    value=app.get('aaat')
    if value is None:return []
    if not isinstance(value,dict) or set(value)!={'schema','exports'} or value['schema']!='ai2apps.app-service-exports/v1':
        raise ValueError('Invalid App AaAT runtime protocol')
    exports=value['exports']
    if not isinstance(exports,list) or not 1<=len(exports)<=64:raise ValueError('Invalid App AaAT exports')
    signed={(e['kind'],e['identity'],x['name']):x for e in (catalog or {}).get('entries',[]) if e['agent']['mode']=='aaat' for x in e['agent']['exports']}
    required={d['packageId'] for d in dependencies if not d['optional']}
    seen=set();result=[]
    for item in exports:
        if not isinstance(item,dict) or set(item)!={'kind','identity','name','interfaceVersion','servicePackage','serviceTool','inputSchema','agentContext'}:
            raise ValueError('Incomplete or unknown App AaAT binding fields')
        key=tuple(item[k] for k in ('kind','identity','name'))
        if key in seen or key not in signed or item['interfaceVersion']!=signed[key]['interfaceVersion']:
            raise ValueError('Runtime export differs from signed capability catalog')
        seen.add(key)
        if item['servicePackage'] not in required or not isinstance(item['serviceTool'],str):
            raise ValueError('AaAT requires an explicit non-optional Service dependency')
        schema=item['inputSchema']
        pending=[schema]
        while pending:
            node=pending.pop()
            if isinstance(node,dict):
                for key,value in node.items():
                    if key in ('$ref','$dynamicRef') and (not isinstance(value,str) or not value.startswith('#')):
                        raise ValueError('Remote schema references are not supported')
                    pending.append(value)
            elif isinstance(node,list):pending.extend(node)
        Draft202012Validator.check_schema(schema)
        if schema.get('x-ai2apps-interface-version')!=item['interfaceVersion']:raise ValueError('Service schema must declare the exact AaAT interface version')
        if schema.get('type')!='object' or not isinstance(schema.get('properties'),dict) or {'provider','parameters'} & set(schema['properties']):
            raise ValueError('AaAT input must be an object without reserved routing fields')
        validate_declaration(item['agentContext'])
        if len(json.dumps(item).encode())>32768:raise ValueError('App AaAT binding exceeds 32 KiB')
        result.append(deepcopy(item))
    return result


class AppExportBinder:
    def __init__(self,runtime):
        self.runtime=runtime;self.owned={};self.errors={};self.syncing=False;self.lock=threading.RLock()
        logging.getLogger(__name__).info("Package AaAT lifecycle loaded from %s",__file__)

    def binding(self,package_id,stored,spec):
        r=self.runtime;state=r.registry_packages._load_state().get('installed',{})
        current=state.get(package_id)
        if current is None or any(current.get(k)!=stored.get(k) for k in ('version','sha256','manifestSha256','runtimeKey','aaatRuntime','aaatDependencies','capabilityCatalog')):
            raise ProviderUnavailable('Installed App release changed')
        definition=r.extension_manager._active_app_definition(stored['runtimeKey'])
        effective=r.extension_manager.repository.effective(UnitKind.APP,stored['runtimeKey'])
        if not definition or definition['status']!='enabled' or effective is None or effective.upstream_digest.removeprefix('sha256:')!=stored['sha256']:
            raise ProviderUnavailable('App is disabled, removed or replaced')
        # Patches can change execution policy: require an unpatched exact definition.
        if effective.manifest.get('aaat',{}).get('exports')!=stored['aaatRuntime']:
            raise ProviderUnavailable('Effective App export interface changed')
        dependency=state.get(spec['servicePackage']) or {}
        constraint=next((d['version'] for d in stored.get('aaatDependencies',[]) if d['packageId']==spec['servicePackage'] and not d['optional']),None)
        if constraint is None or Version(str(dependency.get('version','0'))) not in SpecifierSet('' if constraint=='*' else constraint.replace(' ',',')):
            raise ProviderUnavailable('Service dependency no longer satisfies signed requirements')
        if dependency.get('packageType')!='service':raise ProviderUnavailable('Service dependency is not installed')
        package=r.package_manager.packages.active(dependency.get('runtimeKey',''))
        if package is None or package.runtime_mode is ServiceRuntimeMode.IN_PROCESS or package.package_version!=dependency['version']:
            raise ProviderUnavailable('Isolated Service dependency changed')
        provenance=package.verification.get('signature',{}).get('envelope',{}).get('payload',{}).get('artifact',{})
        if provenance.get('sha256')!=dependency.get('sha256'):raise ProviderUnavailable('Service artifact identity changed')
        if not spec['serviceTool'].startswith(package.service_key+'.'):raise ProviderUnavailable('Service does not own export Tool')
        tool=r.services.get_tool(spec['serviceTool'])
        service=r.services.get_service(package.service_key)
        instance=r.services.get_instance_for_service(service.id)
        bound=r.service_registry.bound_tool(tool.qualified_name)
        if service.status is not ServiceStatus.ENABLED or instance.status not in (ServiceInstanceStatus.RUNNING,ServiceInstanceStatus.DEGRADED) or tool.service_id!=service.id or not tool.enabled or not bound or bound.provider_key!=instance.provider_key or tool.input_schema!=spec['inputSchema']:
            raise ProviderUnavailable('Service Tool interface changed')
        return effective,tool,dependency

    def sync(self):
        with self.lock:
            if self.syncing:return
            self.syncing=True
            try:self._sync()
            finally:self.syncing=False

    def _sync(self):
        r=self.runtime;desired={};self.errors={}
        for pid,stored in r.registry_packages._load_state().get('installed',{}).items():
            if stored.get('packageType')!='app':continue
            for spec in stored.get('aaatRuntime',[]):
                identifier='pkg:'+hashlib.sha256(json.dumps([pid,spec['kind'],spec['identity'],spec['name']],ensure_ascii=False).encode()).hexdigest()
                try:
                    effective,tool,dependency=self.binding(pid,stored,spec)
                    version=hashlib.sha256(json.dumps([stored['version'],stored['sha256'],stored['manifestSha256'],spec,dependency.get('version'),dependency.get('sha256'),tool.revision,tool.effects,tool.required_capabilities,tool.capability_rules],sort_keys=True).encode()).hexdigest()
                    desired[identifier]=(pid,deepcopy(stored),deepcopy(spec),tool,version)
                except Exception:
                    self.errors[identifier]='runtime_interface_unavailable'
        for identifier,version in list(self.owned.items()):
            if identifier not in desired or desired[identifier][-1]!=version:
                r.app_capability_router.unregister(identifier);self.owned.pop(identifier)
        for identifier,(pid,stored,spec,tool,version) in desired.items():
            if identifier in self.owned:continue
            try:
                r.app_capability_router.register(self.provider(identifier,pid,stored,spec,version))
                self.owned[identifier]=version
            except Exception:self.errors[identifier]='registration_rejected'
        # Routed gateways aggregate real downstream guards, never publisher claims.
        from ai2apps.services import ServiceRuntimeMode
        service=r.services.ensure_service(service_key='ai2apps.package-app-adapters',package_id='ai2apps.package-app-adapters',package_version='0.1.0',display_name='Package App AaAT bridge',runtime_mode=ServiceRuntimeMode.IN_PROCESS,capabilities=('app.invoke',),config={})
        instance=r.services.ensure_instance(service_id=service.id,provider_key='builtin:package-app-adapters',status=ServiceInstanceStatus.RUNNING,endpoint=None,health={'status':'ok'})
        active=set()
        for name in {v[2]['name'] for key,v in desired.items() if key in self.owned}:
            entries=[v for key,v in desired.items() if key in self.owned and v[2]['name']==name]
            try:existing=r.services.get_tool(name)
            except Exception:existing=None
            # Never replace an unrelated gateway or built-in capability.
            if existing is not None and existing.service_id!=service.id:
                for key in [key for key,v in desired.items() if v[2]['name']==name and key in self.owned]:
                    r.app_capability_router.unregister(key);self.owned.pop(key);self.errors[key]='capability_gateway_collision'
                continue
            effects=tuple(sorted({x for v in entries for x in v[3].effects}))
            caps=tuple(sorted({x for v in entries for x in v[3].required_capabilities}))
            if any(v[3].capability_rules for v in entries):
                # Dynamic rules must remain in the authoritative downstream gateway;
                # outer generic admission requires the full bounded capability union.
                caps=tuple(sorted(set(caps)|{x for v in entries for rule in v[3].capability_rules for x in rule.get('capabilities',[])}))
            schema={'type':'object','properties':{'provider':{'type':'string'},'parameters':{'type':'object'}},'required':['provider'],'additionalProperties':True}
            r.services.ensure_tool(service_id=service.id,qualified_name=name,display_name=name,description='Installed signed App capability. Review its Provider declaration and collect parameters before invocation.',input_schema=schema,output_schema={'type':'object'},effects=effects,required_capabilities=caps,timeout_ms=300000)
            async def invoke(args,context,capability=name):return await r.app_capability_router.invoke(capability,args,context)
            r.service_registry.bind_tool(name,provider_key=instance.provider_key,handler=invoke);active.add(name)
        r.services.disable_unseen_tools(service.id,active)

    def provider(self,identifier,pid,stored,spec,version):
        r=self.runtime
        async def describe(principal,model=None):
            effective,_,_=self.binding(pid,stored,spec)
            if not can_access_app(principal,effective.manifest):raise ToolProviderError('App access denied')
            return {'effective_schema':deepcopy(spec['inputSchema'])}
        async def prepare(args,context):
            self.sync()
            if self.owned.get(identifier)!=version:raise ProviderUnavailable('Provider version changed')
            principal=principal_for(r,context)
            await describe(principal)
            if not context.session_id:raise ToolProviderError('Owned Session is required')
            from ai2apps.api.ownership import authorize_session
            authorize_session(r,principal,context.session_id)
            Draft202012Validator(spec['inputSchema']).validate(args)
            return args
        async def handler(args,context):
            # Recheck after preparation and preserve actor/Session/grants/idempotency.
            await prepare(args,context)
            result=await r.tools.execute(spec['serviceTool'],args,context=context)
            try:self.binding(pid,stored,spec)
            except ProviderUnavailable as error:
                raise ToolProviderError('Export changed after submission; outcome requires verification, do not retry') from error
            return {**result.output,'app_id':stored['runtimeKey'],'mini_app_id':spec['identity'] if spec['kind']=='mini-app' else None}
        return CapabilityProvider(identifier,spec['name'],stored['runtimeKey'],handler,mini_app_id=spec['identity'] if spec['kind']=='mini-app' else None,
            version=version,describe=describe,prepare=prepare,agent_context=spec['agentContext'])
