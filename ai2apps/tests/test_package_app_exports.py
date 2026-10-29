"""Actual Router/Gateway lifecycle with arbitrary Package identities; Service execution is a fixture."""
from copy import deepcopy
from types import SimpleNamespace
import json
import pytest
from ai2apps.services import ServiceRuntimeMode,ServiceInstanceStatus,ToolCallContext
from ai2apps.services.capability_routing import ProviderUnavailable
from ai2apps.packages.app_exports import declarations
from ai2apps.packages.install_handoff import begin,complete,SCHEMA
from ai2apps.identity import RequestPrincipal
from ai2apps.chat import ChatRepository
from ai2apps.agents.parameter_forms import FORMS
from test_app_interactions import runtime


def test_fresh_runtime_does_not_predeclare_package_mini_apps(runtime):
    """Actual production startup, without the legacy backend unit fixture."""
    forbidden={'video.avatar','image.frozen_time','voice.generate_music',
        'voice.generate_song','voice.generate_sound_effects','voice.detailed_transcription',
        'voice.separate','voice.replace_speaker','video.dub','video.replace_speaker',
        'shopping.history','shopping.prepare_cart','travel.flights','travel.hotels'}
    providers=runtime.app_capability_router.providers.values()
    assert not forbidden & {p.capability for p in providers}
    assert not forbidden & {f.capability or f.key for f in FORMS.values()}
    assert {p.mini_app_id for p in providers if p.app_id=='ai2apps.ai-browser'} >= {'ai2apps.search-all','ai2apps.web-reader'}
    assert any(p.capability=='todo.create' for p in providers)
    assert any(p.capability=='voice.quick_read' for p in providers)


def test_catalog_only_installed_package_does_not_create_execution_interface(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    f.state['installed'][f.pid]['aaatRuntime']=[]
    f.effective.manifest['aaat']['exports']=[]
    runtime.package_app_exports.sync()
    assert f.provider.id not in runtime.app_capability_router.providers
    assert f.provider.id not in FORMS
    from ai2apps.packages.installed_capabilities import inspect
    observed=inspect(runtime,RequestPrincipal.legacy_local(),f.target)
    assert observed['status']=='adapter_required' and not observed['callable']


def fixture(runtime,monkeypatch,suffix='alpha'):
    app='publisher.'+suffix;pid='publisher/'+suffix;cap=suffix+'.compute';toolname='isolated.'+suffix+'.compute'
    schema={'x-ai2apps-interface-version':'1.0.0','type':'object','properties':{'value':{'type':'string'}},'required':['value'],'additionalProperties':False}
    declaration={'schema':'ai2apps.aaat-declaration/v1','instructions':['Fixture owner: echo the supplied value.']}
    spec={'kind':'app','identity':'main','name':cap,'interfaceVersion':'1.0.0','servicePackage':'publisher/service-'+suffix,'serviceTool':toolname,'inputSchema':schema,'agentContext':declaration}
    catalog={'entries':[{'kind':'app','identity':'main','agent':{'mode':'aaat','exports':[{'name':cap,'interfaceVersion':'1.0.0'}]}}]}
    state={'installed':{pid:{'packageType':'app','version':'1.0.0','sha256':'b'*64,'manifestSha256':'a'*64,'runtimeKey':app,'capabilityCatalog':catalog,'aaatRuntime':[spec],'aaatDependencies':[{'packageId':spec['servicePackage'],'optional':False,'version':'==1.0.0'}]},spec['servicePackage']:{'packageType':'service','version':'1.0.0','runtimeKey':'isolated.'+suffix,'sha256':'c'*64}}}
    manager=SimpleNamespace(_load_state=lambda:state)
    monkeypatch.setattr(runtime,'registry_packages',manager)
    definition={'status':'enabled'};effective=SimpleNamespace(upstream_digest='sha256:'+'b'*64,manifest={'aaat':{'exports':[spec]}})
    monkeypatch.setattr(runtime.extension_manager,'_active_app_definition',lambda key:definition)
    monkeypatch.setattr(runtime.extension_manager.repository,'effective',lambda *a:effective)
    package=SimpleNamespace(service_key='isolated.'+suffix,package_version='1.0.0',runtime_mode=ServiceRuntimeMode.MANAGED_PROCESS,verification={'signature':{'envelope':{'payload':{'artifact':{'sha256':'c'*64}}}}})
    monkeypatch.setattr(runtime.package_manager.packages,'active',lambda key:package)
    service=runtime.services.ensure_service(service_key=package.service_key,package_id='publisher/service-'+suffix,package_version='1.0.0',display_name='Fixture isolated service',runtime_mode=ServiceRuntimeMode.MANAGED_PROCESS,capabilities=(),config={})
    instance=runtime.services.ensure_instance(service_id=service.id,provider_key='fixture:'+suffix,status=ServiceInstanceStatus.RUNNING,endpoint='http://127.0.0.1:1',health={'status':'ok'})
    runtime.services.ensure_tool(service_id=service.id,qualified_name=toolname,display_name=cap,description='Fixture',input_schema=schema,output_schema={'type':'object'},effects=('external_read',),required_capabilities=())
    calls=[]
    async def execute(args,context):calls.append((args,context));return {'value':args['value']}
    runtime.service_registry.bind_tool(toolname,provider_key=instance.provider_key,handler=execute)
    runtime.package_app_exports.sync()
    provider=next(p for p in runtime.app_capability_router.providers.values() if p.capability==cap)
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Package fixture')
    context=ToolCallContext.from_principal(RequestPrincipal.legacy_local(),caller_id='fixture',session_id=thread.session.id,trace_id=None)
    return SimpleNamespace(state=state,pid=pid,cap=cap,spec=spec,provider=provider,definition=definition,effective=effective,context=context,calls=calls,service=service,
        target={'packageId':pid,'version':'1.0.0','manifestSha256':'a'*64,'artifactSha256':'b'*64})

@pytest.mark.parametrize('suffix',['alpha','arbitrary-zen'])
@pytest.mark.asyncio
async def test_signed_export_routes_with_same_scope_and_revokes_forms(runtime,monkeypatch,suffix):
    f=fixture(runtime,monkeypatch,suffix)
    result=await runtime.tools.execute(f.cap,{'provider':f.provider.id,'parameters':{'value':'original input'}},context=f.context)
    assert result.output['value']=='original input' and len(f.calls)==1
    assert f.calls[0][1].session_id==f.context.session_id and f.calls[0][1].actor_user_id=='local'
    assert f.provider.id in FORMS
    f.definition['status']='disabled';runtime.package_app_exports.sync()
    assert f.provider.id not in runtime.app_capability_router.providers and f.provider.id not in FORMS
    with pytest.raises(ProviderUnavailable):await f.provider.handler({'value':'stale'},f.context)
    assert len(f.calls)==1
    f.definition['status']='enabled';runtime.package_app_exports.sync()
    assert f.provider.id in runtime.app_capability_router.providers
    f.state['installed'].pop(f.pid);runtime.package_app_exports.sync()
    assert f.provider.id not in runtime.app_capability_router.providers

@pytest.mark.asyncio
async def test_dependency_upgrade_and_schema_change_replace_or_revoke_version(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    old=f.provider
    f.state['installed'][f.spec['servicePackage']]['sha256']='d'*64
    runtime.package_manager.packages.active('fixture').verification['signature']['envelope']['payload']['artifact']['sha256']='d'*64
    runtime.package_app_exports.sync()
    new=runtime.app_capability_router.providers[old.id]
    assert new.version!=old.version
    with pytest.raises(ProviderUnavailable):await old.handler({'value':'stale'},f.context)
    assert not f.calls
    f.effective.manifest['aaat']['exports']=[];runtime.package_app_exports.sync()
    assert old.id not in runtime.app_capability_router.providers

@pytest.mark.asyncio
async def test_service_disable_revokes_and_reenable_rebinds(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    await runtime.service_registry.set_enabled(f.service.service_key,expected_revision=f.service.revision,enabled=False)
    assert f.provider.id not in runtime.app_capability_router.providers
    svc=runtime.services.get_service(f.service.service_key)
    await runtime.service_registry.set_enabled(svc.service_key,expected_revision=svc.revision,enabled=True)
    assert f.provider.id in runtime.app_capability_router.providers
    result=await runtime.tools.execute(f.cap,{'provider':f.provider.id,'value':'flat form'},context=f.context)
    assert result.output['value']=='flat form'


def test_signed_runtime_descriptor_not_catalog_inference(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    app={'aaat':{'schema':'ai2apps.app-service-exports/v1','exports':[f.spec]}}
    deps=[{'packageId':f.spec['servicePackage'],'optional':False}]
    catalog=f.state['installed'][f.pid]['capabilityCatalog']
    assert declarations(app,catalog,deps)==[f.spec]
    assert declarations({},catalog,deps)==[]
    for mutate in ('url','dependency','version','unknown'):
        changed=deepcopy(app);spec=changed['aaat']['exports'][0]
        if mutate=='url':spec['serviceTool']={"url":"https://bad.invalid"}
        if mutate=='dependency':spec['servicePackage']='other/package'
        if mutate=='version':spec['interfaceVersion']='2.0.0'
        if mutate=='unknown':spec['handler']='arbitrary.py:run'
        with pytest.raises((ValueError,TypeError)):declarations(changed,catalog,deps)


def test_chat_handoff_pins_observed_target_preserves_run_and_verifies_actual_provider(runtime,monkeypatch):
    f=fixture(runtime,monkeypatch)
    step=SimpleNamespace(kind='tool',tool_name='discover.packages',status=SimpleNamespace(value='completed'),output={'candidates':[{'installation_target':f.target}]})
    monkeypatch.setattr(runtime.agents,'list_steps',lambda rid:(step,))
    run=SimpleNamespace(id='run-fixture',session_id=f.context.session_id)
    values={'installation_target':f.target,'requested_capability':f.cap}
    payload=begin(runtime,RequestPrincipal.legacy_local(),run,None,None,values)
    # Serialized handoff survives a new process; no mutable callback or client state.
    record={'payload_json':json.dumps(payload)}
    result=complete(runtime,RequestPrincipal.legacy_local(),run,None,None,record)
    assert result['original_task_ready'] and result['business_executed'] is False and not f.calls
    assert result['ready_providers'][0]['id']==f.provider.id
    from fastapi import HTTPException
    with pytest.raises(HTTPException):complete(runtime,RequestPrincipal.legacy_local(),SimpleNamespace(session_id='other'),None,None,record)
    bad={**values,'installation_target':{**f.target,'version':'9.0.0'}}
    with pytest.raises(HTTPException):begin(runtime,RequestPrincipal.legacy_local(),run,None,None,bad)
    f.state['installed'][f.pid]['sha256']='e'*64
    with pytest.raises(HTTPException):complete(runtime,RequestPrincipal.legacy_local(),run,None,None,record)

@pytest.mark.asyncio
@pytest.mark.parametrize('cancelled',[False,True])
async def test_durable_chat_install_handoff_http_restart_and_cancel(runtime,monkeypatch,cancelled):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.agents import CompleteAction,ToolCallAction
    from ai2apps.agents.parameter_forms import form_action
    from test_app_interactions import wait
    f=fixture(runtime,monkeypatch)
    bound=runtime.service_registry.bound_tool('discover.packages')
    async def catalog(args,context):return {'candidates':[{'installation_target':f.target}]}
    runtime.service_registry.bind_tool('discover.packages',provider_key=bound.provider_key,handler=catalog)
    arguments={'request_id':'install-task','capability':'discover.install','values':{'installation_target':f.target,'requested_capability':f.cap}}
    runtime.agents.ensure_definition(agent_key='test.package-handoff',package_version='1',display_name='Fixture',executor_key='test.package-handoff',max_steps=12,timeout_seconds=120)
    def execute(context):
        if not context.step('observed'):return ToolCallAction('observed','discover.packages',{'query':'fixture'})
        action=form_action(context,arguments)
        if action:return action
        return CompleteAction(context.interaction('form:install-task').response)
    runtime.agent_runtime.bind_executor('test.package-handoff',execute)
    run,_=runtime.agents.create_run(session_id=f.context.session_id,agent_key='test.package-handoff',input={'prompt':'Original objective retained','material_id':'original-owned-reference'})
    app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=RequestPrincipal.legacy_local))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        await wait(runtime,run.id,'waiting_input');item=runtime.agents.list_interactions(run.id)[0]
        url=f'/v1/platform/agent-runs/{run.id}/interactions/{item.id}'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            state=(await client.get(url+'/parameters')).json()
            assert state['handoff_only'] and state['configuration_required']
            assert state['continue_label']['en']=='Review installation in Discover'
            assert state['handoff_message']['zh']
            assert state['can_continue_in_app'] and state['values']==arguments['values']
            start=await client.post(url+'/parameters/handoff',json={'revision':state['revision'],'values':state['values']})
            assert start.status_code==200,start.text
            await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
            restored=await client.get(url+'/handoff')
            assert restored.json()['parameters']['installation_target']==f.target
            assert runtime.agents.get_run(run.id).input['material_id']=='original-owned-reference'
            if cancelled:
                response=await client.post(url+'/respond',json={'response_id':'cancel-fixture','response':{'status':'cancelled','result':{}}})
                assert response.status_code==200,response.text
                assert (await client.post(url+'/parameters/handoff/complete')).json()=={'status':'cancelled','result':{}}
            else:
                response=await client.post(url+'/parameters/handoff/complete')
                assert response.status_code==200,response.text
                assert response.json()['result']['original_task_ready']
                # Repeated completion reads the same receipt; it never executes business.
                assert (await client.post(url+'/parameters/handoff/complete')).json()==response.json()
        await wait(runtime,run.id,'completed')
        assert not f.calls
    finally:await runtime.stop_background_tasks()


def test_package_contract_validates_signed_runtime_exports(tmp_path):
    import yaml
    from ai2apps.packages.contract_v1 import build_package,inspect_package,PackageContractError
    from test_capability_catalog_client import manifest
    m=manifest();m['dependencies']=[{'packageId':'publisher/isolated','version':'==1.0.0','optional':False}]
    spec={'kind':'app','identity':'main','name':'fixture.render','interfaceVersion':'1.0.0','servicePackage':'publisher/isolated','serviceTool':'isolated.fixture.render',
        'inputSchema':{'type':'object','properties':{},'x-ai2apps-interface-version':'1.0.0'},'agentContext':{'schema':'ai2apps.aaat-declaration/v1','instructions':['Fixture only.']}}
    source=tmp_path/'source';source.mkdir();(source/'main.js').write_text('fixture')
    (source/'ai2apps.json').write_text(json.dumps(m))
    (source/'app.yaml').write_text(yaml.safe_dump({'schema':'ai2apps.app/v1','aaat':{'schema':'ai2apps.app-service-exports/v1','exports':[spec]}}))
    inspected=inspect_package(build_package(source,tmp_path/'fixture.ai2app').archive_path)
    assert any(f.path=='app.yaml' for f in inspected.files)
    spec['servicePackage']='undeclared/authority'
    (source/'app.yaml').write_text(yaml.safe_dump({'aaat':{'schema':'ai2apps.app-service-exports/v1','exports':[spec]}}))
    with pytest.raises((PackageContractError,ValueError)):build_package(source,tmp_path/'bad.ai2app')

@pytest.mark.asyncio
async def test_stale_dependency_permission_and_identity_guards(runtime,monkeypatch):
    from dataclasses import replace
    from ai2apps.services import ToolGatewayError
    f=fixture(runtime,monkeypatch)
    with pytest.raises(Exception,match='Installation mismatch'):
        await f.provider.prepare({'value':'wrong scope'},replace(f.context,installation_id='other-installation'))
    service_tool=runtime.services.get_tool(f.spec['serviceTool'])
    runtime.services.ensure_tool(service_id=service_tool.service_id,qualified_name=service_tool.qualified_name,display_name=service_tool.display_name,description=service_tool.description,
        input_schema=service_tool.input_schema,output_schema=service_tool.output_schema,effects=service_tool.effects,required_capabilities=('fixture.execute',))
    runtime.package_app_exports.sync()
    current=runtime.app_capability_router.providers[f.provider.id]
    assert current.version!=f.provider.version
    with pytest.raises(ToolGatewayError,match='Missing capabilities'):
        await runtime.tools.execute(f.cap,{'provider':current.id,'parameters':{'value':'unauthorized'}},context=f.context)
    assert not f.calls
    f.state['installed'][f.spec['servicePackage']]['version']='2.0.0'
    runtime.package_manager.packages.active('fixture').package_version='2.0.0'
    runtime.package_app_exports.sync()
    assert current.id not in runtime.app_capability_router.providers


def test_isolated_transport_uses_host_identity_not_argument_json(monkeypatch):
    from ai2apps.packages.runtime import PackageRuntimeBinder
    import urllib.request
    seen=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,limit):return b'{"ok":true}'
    def open_(request,timeout):seen.append(request);return Response()
    monkeypatch.setattr(urllib.request,'urlopen',open_)
    context=ToolCallContext(caller_id='host',actor_user_id='actor',installation_id='install',session_id='session',invocation_id='invocation')
    PackageRuntimeBinder._http_json('http://127.0.0.1:1/tools/fixture','POST',{'actor_user_id':'forged'},'run',context)
    headers={key.lower():value for key,value in seen[0].headers.items()}
    assert headers['x-ai2apps-actor-id']=='actor' and headers['x-ai2apps-installation-id']=='install'
    assert headers['x-ai2apps-session-id']=='session' and headers['x-ai2apps-invocation-id']=='invocation'

@pytest.mark.asyncio
async def test_revocation_after_submission_never_falls_back_or_claims_preflight_failure(runtime,monkeypatch):
    from ai2apps.services.capability_routing import CapabilityProvider,CapabilityInvocationError
    f=fixture(runtime,monkeypatch);calls=[]
    async def changed_after_submit(args,context):
        calls.append('submitted');f.definition['status']='disabled';return {'value':'actually executed'}
    async def fallback(args,context):calls.append('fallback');return {'value':'duplicate'}
    bound=runtime.service_registry.bound_tool(f.spec['serviceTool'])
    runtime.service_registry.bind_tool(f.spec['serviceTool'],provider_key=bound.provider_key,handler=changed_after_submit)
    runtime.app_capability_router.register(CapabilityProvider('arbitrary.fallback',f.cap,'arbitrary.owner',fallback,priority=-1))
    with pytest.raises(CapabilityInvocationError) as error:
        await runtime.app_capability_router.invoke(f.cap,{'value':'once'},f.context)
    assert error.value.code=='provider_error' and error.value.details['phase']=='execute'
    assert calls==['submitted']

@pytest.mark.asyncio
async def test_real_signed_app_activation_and_state_commit_registers_and_uninstalls(runtime,monkeypatch,tmp_path):
    import yaml
    from ai2apps.packages.registry import RegistryPackageManager
    from ai2apps.packages.contract_v1 import build_package,create_signature_envelope,generate_publisher_key,verify_signed_package
    from ai2apps.extensions.manager import InteractivePackageManager
    from ai2apps.extensions.repository import ExtensionRepository
    from test_capability_catalog_client import manifest
    f=fixture(runtime,monkeypatch)
    # Restore actual App repository/activation methods; only isolated Service code is a fixture.
    monkeypatch.setattr(runtime.extension_manager,'_active_app_definition',InteractivePackageManager._active_app_definition.__get__(runtime.extension_manager))
    monkeypatch.setattr(runtime.extension_manager.repository,'effective',ExtensionRepository.effective.__get__(runtime.extension_manager.repository))
    manager=RegistryPackageManager(cloud=None,root=tmp_path/'registry',secrets=runtime.secrets,extension_manager=runtime.extension_manager,service_manager=runtime.package_manager)
    monkeypatch.setattr(runtime,'registry_packages',manager)
    state=deepcopy(f.state);state['installed'].pop(f.pid);manager._save_state(state)
    m=manifest();m['package']['id']=f.pid;m['dependencies']=[{'packageId':f.spec['servicePackage'],'optional':False,'version':'==1.0.0'}]
    entry=m['capabilityCatalog']['entries'][0];entry['provides']=[f.cap];entry['agent']['exports'][0]['name']=f.cap
    source=tmp_path/'real-app';source.mkdir();(source/'ai2apps.json').write_text(json.dumps(m));(source/'main.js').write_text('fixture')
    (source/'app.yaml').write_text(yaml.safe_dump({'schema':'ai2apps.app/v1','entry':{'kind':'sandbox','resource':'main.js'},'aaat':{'schema':'ai2apps.app-service-exports/v1','exports':[f.spec]}}))
    built=build_package(source,tmp_path/'real.ai2app');private,public,_=generate_publisher_key()
    envelope=create_signature_envelope(built,private,publisher_id='fixture',publisher_key_id='fixture-key')
    verified=verify_signed_package(built.archive_path,envelope,public)
    release={'publisher':{'id':'fixture','key':{'id':'fixture-key','fingerprintSha256':'a'*64}}}
    async def downloaded(*args,**kwargs):return verified,envelope,release,1
    monkeypatch.setattr(manager,'download_verified',downloaded)
    await manager._install_with_dependencies('publisher','alpha','1.0.0',approve_review=True,stack=(),progress=None)
    stored=manager._load_state()['installed'][f.pid]
    assert stored['aaatRuntime']==[f.spec] and stored['aaatDependencies']==m['dependencies']
    from ai2apps.packages.installed_capabilities import inspect
    target={'packageId':f.pid,'version':'1.0.0','manifestSha256':verified.manifest_sha256,'artifactSha256':verified.sha256}
    ready=inspect(runtime,RequestPrincipal.legacy_local(),target)
    assert ready['status']=='ready' and ready['callable'],ready
    provider=ready['providers'][0]['registered_providers'][0]
    output=await runtime.tools.execute(f.cap,{'provider':provider['id'],'value':'real signed App'},context=f.context)
    assert output.output['value']=='real signed App'
    await manager.uninstall(f.pid,force=True)
    assert provider['id'] not in runtime.app_capability_router.providers and provider['id'] not in FORMS
