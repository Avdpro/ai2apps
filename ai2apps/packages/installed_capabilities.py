"""Read installed release identity and actual owner registrations after installation.

This observer cannot register handlers from catalog JSON or grant permission.
Owner adapters remain responsible for runtime interface and invocation guards.
"""
from .capability_catalog import validate_target
from ai2apps.apps.access import can_access_app
from ai2apps.extensions import UnitKind


def inspect(runtime,principal,target):
    target=validate_target(target)
    binder=getattr(runtime,'package_app_exports',None)
    if binder:binder.sync()
    manager=runtime.registry_packages
    stored=manager._load_state().get('installed',{}).get(target['packageId'])
    unavailable={'status':'not_installed','providers':[],'callable':False}
    if not stored:return unavailable
    if stored.get('version')!=target['version'] or stored.get('sha256')!=target['artifactSha256'] or stored.get('manifestSha256')!=target['manifestSha256']:
        return {**unavailable,'status':'installed_release_differs'}
    if stored.get('packageType')!='app':return {**unavailable,'status':'not_an_app'}
    key=stored.get('runtimeKey')
    definition=runtime.extension_manager._active_app_definition(key)
    effective=runtime.extension_manager.repository.effective(UnitKind.APP,key)
    if not definition or definition['status']!='enabled' or effective is None or effective.upstream_digest.removeprefix('sha256:')!=target['artifactSha256']:
        return {**unavailable,'status':'inactive_or_replaced'}
    if not can_access_app(principal,effective.manifest):return {**unavailable,'status':'unavailable'}
    catalog=stored.get('capabilityCatalog') or {}
    exports=[(entry,export) for entry in catalog.get('entries',[]) for export in entry['agent']['exports'] if entry['agent']['mode']=='aaat']
    providers=runtime.app_capability_router.inspect(principal.actor_user_id,principal.installation_id)
    observed=[]
    for entry,export in exports:
        matches=[p for p in providers if p['app_id']==key and p['capability']==export['name']
            and (p.get('mini_app_id')==entry['identity'] if entry['kind']=='mini-app' else not p.get('mini_app_id'))]
        observed.append({'export':export['name'],'interface_version':export['interfaceVersion'],
            'registered_providers':[{'id':p['id'],'version':p['version'],'enabled':p['enabled'],'status':p['status']} for p in matches],
            'interface_verified':bool(matches) and all(p['id'] in getattr(binder,'owned',{}) for p in matches)})
    ready=[p for o in observed if o['interface_verified'] for p in o['registered_providers'] if p['enabled'] and p['status']=='registered']
    return {'status':'ready' if ready else 'registered_adapters_require_interface_verification' if any(o['registered_providers'] for o in observed) else 'adapter_required' if exports else 'no_aaat_declaration',
        'installation_target':target,'providers':observed,'callable':bool(ready),
        'note':'Rediscover actual registered capabilities and review their owner declarations before invocation. Catalog declarations alone are not executable interfaces.'}
