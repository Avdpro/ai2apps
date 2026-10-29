"""Installed release binding tests; SDK effects are fixtures, not real inference."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from ai2apps.apps.access import RequestPrincipal
from ai2apps.chat.repository import ChatRepository
from ai2apps.services import ToolCallContext
from ai2apps.agents.parameter_forms import FORMS
from ai2apps.packages.mini_app_exports import HostProtocol,declarations
from test_app_interactions import runtime


def fixture(runtime,monkeypatch,suffix='alpha'):
    app='publisher.'+suffix;pid='publisher/'+suffix;name=suffix+'.compute';host='host.'+suffix
    spec=dict(name=name,interfaceVersion='1.0.0',host=host,sdk='fixture.echo/v1',inputSchema={'type':'object','properties':{'value':{'type':'string'}},'required':['value'],'additionalProperties':False},fields=[{'key':'value','type':'text','label':{'en':'Value','zh':'值'}}],displayName={'en':'Echo','zh':'回显'},summary={'en':'Fixture','zh':'测试'},agentContext={'schema':'ai2apps.aaat-declaration/v1','instructions':['Echo the supplied value.']},selectionRequired=False,options={})
    mini={'id':'mini.'+suffix,'placements':[{'studio':host}],'aaat':{'schema':'ai2apps.mini-app-host-exports/v1','exports':[spec]}}
    cat={'entries':[{'kind':'mini-app','identity':mini['id'],'agent':{'mode':'aaat','exports':[{'name':name,'interfaceVersion':'1.0.0'}]}}]}
    stored=dict(packageType='app',version='1.0.0',sha256='b'*64,manifestSha256='a'*64,runtimeKey=app,capabilityCatalog=cat)
    state={'installed':{pid:stored}};monkeypatch.setattr(runtime.registry_packages,'_load_state',lambda:state)
    effective=SimpleNamespace(upstream_digest='sha256:'+'b'*64,manifest={'mini_apps':[mini]})
    definition={'status':'enabled'};monkeypatch.setattr(runtime.extension_manager,'_active_app_definition',lambda key:definition)
    monkeypatch.setattr(runtime.extension_manager.repository,'effective',lambda *a:effective)
    calls=[]
    async def execute(r,args,context,m,s):calls.append((args,context));return {'echo':args['value']}
    binder=runtime.package_mini_exports;binder.register_protocol(HostProtocol('fixture.echo/v1',(host,),execute,effects=('artifact.create',)))
    binder.sync();provider=next(p for p in runtime.app_capability_router.providers.values() if p.capability==name)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Mini-App export fixture')
    context=ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='fixture',session_id=thread.session.id,trace_id=None)
    return SimpleNamespace(**locals())

@pytest.mark.parametrize('suffix',['alpha','unrelated-zeta'])
@pytest.mark.asyncio
async def test_installed_interface_and_uninstall(runtime,monkeypatch,suffix):
    f=fixture(runtime,monkeypatch,suffix)
    form=await f.provider.describe(RequestPrincipal.legacy_local())
    assert form['effective_schema']==f.spec['inputSchema']
    result=await runtime.tools.execute(f.name,{'provider':f.provider.id,'parameters':{'value':'original'}},context=f.context)
    assert result.output['echo']=='original' and len(f.calls)==1
    assert f.calls[0][1].session_id==f.context.session_id
    f.state['installed'].clear();f.binder.sync()
    assert f.provider.id not in runtime.app_capability_router.providers and f.provider.id not in FORMS
    assert not runtime.services.get_tool(f.name).enabled

@pytest.mark.parametrize('change',['disabled','digest','schema','sdk','catalog','placement','version'])
@pytest.mark.asyncio
async def test_changed_release_revokes_before_submission(runtime,monkeypatch,change):
    f=fixture(runtime,monkeypatch)
    if change=='disabled':f.definition['status']='disabled'
    elif change=='digest':f.effective.upstream_digest='sha256:'+'c'*64
    elif change=='schema':f.spec['inputSchema']['required']=[]
    elif change=='sdk':f.binder.protocols.clear()
    elif change=='catalog':f.stored['capabilityCatalog']['entries'][0]['agent']['exports']=[]
    elif change=='placement':f.mini['placements']=[]
    elif change=='version':f.stored['version']='2.0.0'
    f.binder.sync()
    with pytest.raises(Exception):await f.provider.handler({'value':'must not submit'},f.context)
    assert not f.calls

@pytest.mark.asyncio
async def test_change_after_submit_is_not_fallback_or_replay(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    async def changed(r,args,context,mini,spec):f.calls.append(args);f.state['installed'].clear();return {'ok':True}
    f.binder.unregister_protocol('fixture.echo/v1')
    f.binder.register_protocol(HostProtocol('fixture.echo/v1',(f.host,),changed))
    f.binder.sync();p=runtime.app_capability_router.providers[f.provider.id]
    with pytest.raises(Exception,match='without retrying'):await p.handler({'value':'once'},f.context)
    assert len(f.calls)==1

@pytest.mark.parametrize('change',['catalog','host','field','remote-ref'])
def test_invalid_declaration_rejected(runtime,monkeypatch,change):
    f=fixture(runtime,monkeypatch)
    if change=='catalog':f.spec['interfaceVersion']='2.0.0'
    elif change=='host':f.spec['host']='other.host'
    elif change=='field':f.spec['fields'].append(deepcopy(f.spec['fields'][0]))
    else:f.spec['inputSchema']['properties']['value']={'$ref':'https://example.org/schema'}
    with pytest.raises(ValueError):declarations(f.mini,f.cat)


def test_retirement_releases_name_preserving_history_and_other_owners(runtime):
    from ai2apps.services import ServiceRuntimeMode
    service=runtime.services.ensure_service(service_key='fixture.retirement',package_id='fixture.retirement',package_version='1',display_name='Fixture',runtime_mode=ServiceRuntimeMode.IN_PROCESS,capabilities=(),config={})
    tool=runtime.services.ensure_tool(service_id=service.id,qualified_name='fixture.old',display_name='Old',description='Fixture',input_schema={'type':'object'},output_schema={'type':'object'})
    native=runtime.services.get_tool('todo.create')
    runtime.services.retire_unseen_tools(service.id,set())
    with runtime.database.transaction() as db:
        row=db.execute('SELECT * FROM tool_descriptors WHERE id=?',(tool.id,)).fetchone()
    assert row and row['id']==tool.id and not row['enabled'] and row['qualified_name']!='fixture.old'
    assert runtime.services.get_tool('todo.create').id==native.id
    runtime.services.retire_unseen_tools(service.id,set())
    with runtime.database.transaction() as db:
        again=db.execute('SELECT revision FROM tool_descriptors WHERE id=?',(tool.id,)).fetchone()
    assert again['revision']==row['revision']


def test_live_source_packages_bind_only_declared_current_placements(tmp_path,monkeypatch):
    """Actual trusted source loader, not signed production installation evidence."""
    from pathlib import Path
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    root=Path(__file__).resolve().parents[2]
    monkeypatch.setenv('AI2APPS_ALLOW_DEVELOPMENT_RUNTIME','1')
    monkeypatch.setenv('AI2APPS_DEVELOPMENT_SOURCE_ROOT',str(root))
    r=PlatformRuntime(PlatformConfig.from_base_path(tmp_path/'source-data'));r.start()
    try:
        binder=r.package_mini_exports
        assert not binder.errors,binder.errors
        assert len(binder.owned)==24
        for provider in r.app_capability_router.providers.values():
            if provider.id not in binder.owned:continue
            assert provider.app_id not in ('ai2apps.readaloud','ai2apps.video-studio','ai2apps.imagine-studio','ai2apps.ai-browser')
            assert not binder.is_placement(provider,'arbitrary.unrelated-host',provider.mini_app_id)
            assert provider.id in FORMS
    finally:
        for key in list(r.package_mini_exports.owned):r.app_capability_router.unregister(key)
        r.stop()


def test_same_mini_app_cannot_cross_host_execution_binding(runtime,monkeypatch):
    from dataclasses import replace
    f=fixture(runtime,monkeypatch)
    other_host='host.unrelated-output'
    other_spec=deepcopy(f.spec);other_spec['host']=other_host
    f.mini['placements'].append({'studio':other_host})
    f.mini['aaat']['exports'].append(other_spec)
    protocol=f.binder.protocols['fixture.echo/v1']
    f.binder.unregister_protocol('fixture.echo/v1')
    f.binder.register_protocol(replace(protocol,hosts=(f.host,other_host)))
    f.binder.sync()
    providers=[p for p in runtime.app_capability_router.providers.values() if p.capability==f.name]
    assert len(providers)==2
    for host in (f.host,other_host):
        matching=[p for p in providers if f.binder.is_placement(p,host,f.mini['id'])]
        assert len(matching)==1
        assert not f.binder.is_placement(matching[0],other_host if host==f.host else f.host,f.mini['id'])
    assert {p.id for p in providers}=={next(p.id for p in providers if f.binder.is_placement(p,h,f.mini['id'])) for h in (f.host,other_host)}

@pytest.mark.asyncio
@pytest.mark.parametrize('suffix',['native-alpha','native-unrelated'])
async def test_product_owned_mini_identity_revokes_obsolete_package_binding(runtime,monkeypatch,suffix):
    import json
    from ai2apps.services.capability_routing import ProviderUnavailable
    f=fixture(runtime,monkeypatch,suffix)
    with runtime.database.transaction(write=True) as db:
        row=db.execute("SELECT manifest_json FROM app_definitions WHERE package_id='ai2apps.ai-browser'").fetchone()
        manifest=json.loads(row['manifest_json'])
        manifest['mini_apps'].append({'id':f.mini['id'],'placements':[{'studio':f.host}]})
        db.execute("UPDATE app_definitions SET manifest_json=? WHERE package_id='ai2apps.ai-browser'",(json.dumps(manifest),))
    f.binder.sync()
    assert f.provider.id not in runtime.app_capability_router.providers
    with pytest.raises(ProviderUnavailable):await f.provider.handler({'value':'do not execute'},f.context)
    assert not f.calls
