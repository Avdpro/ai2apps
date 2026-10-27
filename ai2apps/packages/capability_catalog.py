"""Signed catalog declarations and negotiated read-only discovery; never executable registration."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
from jsonschema import Draft202012Validator

FEATURE = {'endpoint':'/v1/registry/content','query':'discovery','value':'capabilities-v1',
    'schemaVersion':'ai2apps.capability-content.v1','declarationSchema':'ai2apps.package-capabilities.v1',
    'matching':'normalized-keyword-and-exact-filters','agentVerification':'publisher-declaration-only'}

@lru_cache(maxsize=2)
def validator(name):
    schema=json.loads((Path(__file__).parent/'schemas'/name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_declarations(manifest):
    catalog=manifest.get('capabilityCatalog')
    if catalog is None:return
    validator('package-capabilities-v1.schema.json').validate(catalog)
    if manifest['package']['type']!='app':raise ValueError('Only App Packages can declare capabilities')
    apps={v['name'] for v in manifest['entrypoints'] if v['kind']=='app'}
    minis={v['componentId'] for v in manifest.get('miniApps',[])}
    identities=set()
    for entry in catalog['entries']:
        key=(entry['kind'],entry['identity'])
        if key in identities:raise ValueError('Duplicate capability identity')
        identities.add(key)
        if entry['identity'] not in (apps if entry['kind']=='app' else minis):raise ValueError('Capability identity is not a signed App/Mini-App')
        agent=entry['agent']; names=[v['name'] for v in agent['exports']]
        if agent['mode']=='aaat':
            if not names or not agent.get('declarationVersion'):raise ValueError('AaAT exports require a declaration version')
        elif names or agent.get('declarationVersion'):raise ValueError('Non-AaAT entries cannot declare exports or a declaration version')
        if len(set(names))!=len(names):raise ValueError('Duplicate capability export')


def validate_page(page):
    if len(json.dumps(page).encode())>2*1024*1024:raise ValueError('Capability page exceeds 2 MiB')
    validator('capability-content-v1.schema.json').validate(page)
    keys=set()
    for card in page['items']:
        target=card['installationTarget'];release=card['release']
        if any(target[k]!=release[k] for k in target):raise ValueError('Capability card release binding mismatch')
        if card['cardKey'] in keys:raise ValueError('Duplicate capability card')
        keys.add(card['cardKey'])
        if card['agent_support']=='declared' and (not isinstance(card['agent'],dict) or card['agent'].get('mode')!='aaat'):
            raise ValueError('Missing signed AaAT declaration')
    return deepcopy(page)


async def content(manager, *, local_device=False, **params):
    """Negotiate every query; network/index errors never become an empty legacy page."""
    discover=getattr(manager,'discovery_capabilities',None)
    features=await discover() if discover else {}
    advertised=features.get('capabilityCatalog') if isinstance(features,dict) else None
    if advertised is None:
        filters=set(params)-{'q','task','limit','cursor','content'}
        if filters:raise ValueError('The Registry does not support capability/device filters')
        legacy={k:v for k,v in params.items() if k in ('q','limit','content','cursor')}
        if params.get('task'):legacy['q']=params['task']
        legacy['sort']='relevance'
        return await manager.content_catalog(**legacy)
    if not isinstance(advertised,dict) or any(advertised.get(k)!=v for k,v in FEATURE.items()):raise ValueError('Unsupported Registry capability catalog contract')
    if local_device:params={**device_query(),**params}
    page=await manager.content_catalog(**params,discovery=FEATURE['value'],sort='relevance')
    try:return validate_page(page)
    except Exception as error:
        from .registry import RegistryError
        raise RegistryError('capability_catalog_invalid','Registry capability page failed validation',details={'status':503}) from error


def validate_target(target, package_id=None, version=None):
    import re
    if not isinstance(target,dict) or set(target)!={'packageId','version','manifestSha256','artifactSha256'}:
        raise ValueError('Expected an exact Package/version/digest installation target')
    if not isinstance(target['packageId'],str) or not re.fullmatch(r'[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*',target['packageId']):raise ValueError('Invalid Package identity')
    if not isinstance(target['version'],str) or not target['version'] or len(target['version'])>80:raise ValueError('Invalid release version')
    if any(not isinstance(target[k],str) or not re.fullmatch('[0-9a-f]{64}',target[k]) for k in ('manifestSha256','artifactSha256')):raise ValueError('Invalid release digest')
    if package_id is not None and target['packageId']!=package_id or version is not None and target['version']!=version:raise ValueError('Installation target differs from the reviewed selection')
    return deepcopy(target)


def device_query():
    import platform
    from ai2apps import __version__
    from .platform_compatibility import normalized_architecture,local_os_version
    os={'Darwin':'darwin','Linux':'linux','Windows':'win32'}.get(platform.system())
    if not os:return {}
    return {'platform':os,'architecture':normalized_architecture(platform.machine()),
        'os_version':local_os_version(os),'ai2apps_version':__version__}
