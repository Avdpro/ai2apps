"""Cloud 1.77 integration with arbitrary Publisher identities; no production publication."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from ai2apps.packages.capability_catalog import FEATURE,content,validate_declarations,validate_page,validate_target
from ai2apps.packages.registry import RegistryPackageManager,RegistryError
from ai2apps.packages.contract_v1 import build_package,inspect_package,PackageContractError,create_signature_envelope,generate_publisher_key,verify_signed_package
from ai2apps.packages.install_continuations import RegistryInstallContinuationRepository
from ai2apps.packages.aaat import search
from test_app_interactions import runtime

TARGET={'packageId':'publisher/fixture','version':'1.0.0','manifestSha256':'a'*64,'artifactSha256':'b'*64}

def card(status='unverified',support='unverified'):
    return {'cardKey':'publisher/fixture@1.0.0:app:main','contentKind':'app','identity':'main','componentVersion':None,
        'displayName':'Fixture','description':'Untrusted <script>never execute</script>','localizations':'unknown','placements':'unknown',
        'scope':'unknown','provides':'unknown','tasks':'unknown','inputTypes':'unknown','outputTypes':'unknown',
        'requirements':{'declaration':'unknown','dependencies':[]},'agent_support':support,'agent':'unknown',
        'processing':'unknown','pricing':'unknown','license':'unknown','permissions':[],'compatibility':{},'downloadBytes':42,
        'publisher':{'id':'publisher','displayName':'Fixture publisher'},
        'release':{**TARGET,'status':'published','envelopeUrl':'/v1/registry/packages/publisher/fixture/versions/1.0.0/envelope','detailsUrl':'/v1/registry/packages/publisher/fixture/catalog'},
        'installationTarget':deepcopy(TARGET),'provenance':{'kind':'verified-release-no-capability-declaration','runtimeVerified':False},
        'match':{'status':status,'reasons':[],'exclusions':[{'code':'DECLARATION_REQUIRED'}] if status=='excluded' else [],'unknown':[{'code':'CAPABILITY_DECLARATION_MISSING'}] if status=='unverified' else []}}

def page(items=None):
    return {'schemaVersion':'ai2apps.capability-content.v1','catalogSnapshot':'c'*64,'matching':'normalized-keyword-and-exact-filters',
        'outcome':'unverified_candidates','counts':{'match':0,'unverified':1,'excluded':1},'items':items or [card()], 'nextCursor':None}

@pytest.mark.asyncio
async def test_negotiation_filters_and_no_fallback_on_bad_new_response():
    calls=[]
    async def discovery():return {'capabilityCatalog':{**FEATURE,'filters':['capability'],'maxLimit':100}}
    async def query(**args):calls.append(args);return page()
    manager=SimpleNamespace(discovery_capabilities=discovery,content_catalog=query)
    result=await content(manager,task='数字人',capability='fixture.render',limit=2,cursor='opaque')
    assert result['schemaVersion']=='ai2apps.capability-content.v1'
    assert calls==[{'task':'数字人','capability':'fixture.render','limit':2,'cursor':'opaque','discovery':'capabilities-v1','sort':'relevance'}]
    async def bad(**args):return {'items':[]}
    manager.content_catalog=bad
    with pytest.raises(RegistryError,match='validation'):await content(manager,q='x')
    async def stale(**args):raise RegistryError('CAPABILITY_INDEX_STALE','stale')
    manager.content_catalog=stale
    with pytest.raises(RegistryError,match='stale'):await content(manager,q='x')

@pytest.mark.asyncio
async def test_legacy_filters_are_never_silently_ignored():
    calls=[]
    async def legacy(**args):calls.append(args);return {'items':[]}
    manager=SimpleNamespace(content_catalog=legacy)
    await content(manager,q='fixture',limit=2)
    assert calls==[{'q':'fixture','limit':2,'sort':'relevance'}]
    with pytest.raises(ValueError,match='filters'):await content(manager,q='fixture',capability='fixture.render')

@pytest.mark.asyncio
async def test_aaat_excluded_is_not_recommended_and_declared_is_not_runtime_verification(runtime,monkeypatch):
    a=card();b=card('excluded');b['cardKey']='excluded-card'
    async def discovery():return {'capabilityCatalog':FEATURE}
    async def query(**args):return page([a,b])
    monkeypatch.setattr(runtime,'registry_packages',SimpleNamespace(discovery_capabilities=discovery,content_catalog=query))
    result=await search(runtime,{'query':'fixture'},None)
    assert len(result['candidates'])==1 and len(result['excluded'])==1
    assert result['counts']=={'match':0,'unverified':1,'excluded':1}
    assert result['candidates'][0]['runtime_verified'] is False
    assert result['candidates'][0]['installation_target']==TARGET
    changed=page();changed['items'][0]['release']['version']='9.0.0'
    with pytest.raises(ValueError,match='binding'):validate_page(changed)


def manifest():
    return {'schemaVersion':'ai2apps.package-manifest.v1','package':{'id':'publisher/fixture','type':'app','version':'1.0.0','displayName':'Fixture'},
        'compatibility':{'ai2apps':'*','platforms':['darwin','linux','win32'],'architectures':['arm64','x64']},
        'entrypoints':[{'name':'main','kind':'app','path':'main.js'}],'permissions':[],'dependencies':[],'files':[],
        'capabilityCatalog':{'schemaVersion':'ai2apps.package-capabilities.v1','entries':[{'kind':'app','identity':'main','provides':['fixture.render'],'tasks':['测试','fixture'],
            'inputTypes':['text/plain'],'outputTypes':['image/png'],'requirements':{'capabilities':[]},'agent':{'mode':'aaat','declarationVersion':'1.0.0','exports':[{'name':'fixture.render','interfaceVersion':'1.0.0','inputTypes':['text/plain'],'outputTypes':['image/png']}]},
            'processing':'local','pricing':'unknown','localizations':{'zh':{'displayName':'测试','description':'测试能力'},'en':{'displayName':'Fixture','description':'Fixture capability'}}}]}}


def test_new_signed_manifest_builds_verifies_and_rejects_false_identity(tmp_path):
    source=tmp_path/'source';source.mkdir();(source/'main.js').write_text('document.body.textContent="fixture";')
    declared=manifest();(source/'ai2apps.json').write_text(json.dumps(declared))
    built=build_package(source,tmp_path/'fixture.ai2app')
    assert inspect_package(built.archive_path).manifest['capabilityCatalog']==declared['capabilityCatalog']
    private,public,_=generate_publisher_key()
    envelope=create_signature_envelope(built,private,publisher_id='fixture-publisher',publisher_key_id='fixture-key')
    assert verify_signed_package(built.archive_path,envelope,public).manifest_sha256==built.manifest_sha256
    invalid=deepcopy(declared);invalid['capabilityCatalog']['entries'][0]['identity']='fake'
    with pytest.raises(ValueError,match='identity'):validate_declarations(invalid)
    invalid=deepcopy(declared);invalid['capabilityCatalog']['entries'][0]['agent']['mode']='ui-only'
    with pytest.raises(ValueError,match='Non-AaAT'):validate_declarations(invalid)

@pytest.mark.asyncio
async def test_install_pins_both_digests_before_any_effect(tmp_path,monkeypatch):
    manager=RegistryPackageManager.__new__(RegistryPackageManager);effects=[]
    inspected=SimpleNamespace(sha256='b'*64,manifest_sha256='a'*64)
    async def downloaded(*a,**kw):return inspected,None,None,None
    async def preflight(*a,**kw):effects.append('dependencies')
    async def execute(*a,**kw):effects.append('install');return 'installed'
    async def snapshot():return {'releases':[{'packageId':TARGET['packageId'],'version':'1.0.0','status':'published','artifact':{'sha256':'b'*64}}]}
    monkeypatch.setattr(manager,'download_verified',downloaded);monkeypatch.setattr(manager,'_preflight_restart_dependencies',preflight);monkeypatch.setattr(manager,'_install_with_dependencies',execute);monkeypatch.setattr(manager,'trusted_snapshot',snapshot)
    assert await manager.install('publisher','fixture','1.0.0',expected_target=TARGET)=='installed'
    assert effects==['dependencies','install'];effects.clear()
    inspected.manifest_sha256='d'*64
    with pytest.raises(RegistryError,match='digests'):await manager.install('publisher','fixture','1.0.0',expected_target=TARGET)
    assert effects==[]
    with pytest.raises(ValueError):validate_target(TARGET,'other/package','1.0.0')


def test_continuation_preserves_reviewed_target_across_repository_reopen(runtime):
    repo=RegistryInstallContinuationRepository(runtime.database)
    repo.save(actor_id='local',installation_id='local',package_id=TARGET['packageId'],version=TARGET['version'],approve_review=True,
        dependency={'packageId':'runtime/fixture'},installation_target=TARGET)
    restored=RegistryInstallContinuationRepository(runtime.database).get('local','local')
    assert restored['installationTarget']==TARGET and restored['dependency']=={'packageId':'runtime/fixture'}

def test_installed_observer_rechecks_removal_and_replacement_without_creating_providers(runtime,monkeypatch):
    from ai2apps.packages.installed_capabilities import inspect
    from ai2apps.identity import RequestPrincipal
    stored={'version':'1.0.0','sha256':'b'*64,'manifestSha256':'a'*64,'packageType':'app','runtimeKey':'fixture.app','capabilityCatalog':manifest()['capabilityCatalog']}
    state={'installed':{TARGET['packageId']:stored}}
    manager=SimpleNamespace(_load_state=lambda:state)
    effective=SimpleNamespace(upstream_digest='b'*64,manifest={})
    extensions=SimpleNamespace(_development_packages={},repository=SimpleNamespace(effective=lambda *a:effective),_active_app_definition=lambda key:{'status':'enabled'})
    monkeypatch.setattr(runtime,'registry_packages',manager);monkeypatch.setattr(runtime,'extension_manager',extensions)
    principal=RequestPrincipal.legacy_local();before=set(runtime.app_capability_router.providers)
    result=inspect(runtime,principal,TARGET)
    assert result['status']=='adapter_required' and result['callable'] is False
    assert set(runtime.app_capability_router.providers)==before
    stored['version']='2.0.0';assert inspect(runtime,principal,TARGET)['status']=='installed_release_differs'
    state['installed'].clear();assert inspect(runtime,principal,TARGET)['status']=='not_installed'
