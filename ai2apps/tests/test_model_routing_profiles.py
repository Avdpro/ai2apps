from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.model_manager import ModelManagerStore
from ai2apps.api.model_profiles import create_model_profiles_router
from ai2apps.identity import RequestPrincipal
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.tests.test_web_agent_mini_apps import broker


def test_privacy_never_inherits_normal_cloud_or_fallback(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path)
    store.put_default_models({'work_standard': 'normal-cloud'})
    monkeypatch.setattr(store, 'cloud_default_policy', lambda: {'apiDefault': {'modelId': 'cloud-default'}})
    assert store.resolve_default_model('work_standard') == 'normal-cloud'
    assert store.resolve_default_model('work_simple') == 'cloud/ai2apps/cloud-default'
    assert store.resolve_default_model('work_standard', 'fallback', profile='privacy') is None
    store.put_default_models({'work_standard': 'trusted-cloud', 'image_generation': 'private-image'}, profile='privacy')
    assert store.resolve_default_model('work_standard', profile='privacy') == 'trusted-cloud'
    assert store.resolve_default_model('image_generation', profile='privacy') == 'private-image'
    store.put_default_models({'work_standard': 'new-normal'})
    assert store.resolve_default_model('work_standard', profile='privacy') == 'trusted-cloud'
    assert store.defaults_path.with_name('privacy-models.json').stat().st_mode & 0o777 == 0o600
    with pytest.raises(ValueError): store.default_models('typo')


def test_profiles_api_validates_model_and_preserves_normal(tmp_path, monkeypatch):
    store = ModelManagerStore(tmp_path)
    store.put_default_models({'work_standard': 'normal'})
    model = SimpleNamespace(model_type='llm', endpoints={'chat_completions':'url'}, capabilities=('work',))
    async def catalog(request): return {'trusted': {'id':'trusted','model_type':'llm','capabilities':['work']}}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog',catalog)
    runtime = SimpleNamespace(model_manager=store, model_invocations=SimpleNamespace(model=lambda key: model if key == 'trusted' else None))
    app=FastAPI();app.include_router(create_model_profiles_router(lambda:runtime,lambda:RequestPrincipal.legacy_local()))
    client=TestClient(app)
    assert client.put('/model-profiles/privacy',json={'routes':{'work_standard':'unknown'}}).status_code==422
    assert client.put('/model-profiles/privacy',json={'routes':{'image_generation':'trusted'}}).status_code==422
    assert client.put('/model-profiles/privacy',json={'routes':{'work_standard':'trusted'}}).status_code==200
    result=client.get('/model-profiles').json()['profiles']
    assert result['normal']['work_standard']=='normal'
    assert result['privacy']['work_standard']=='trusted'


def test_privacy_capability_uses_shared_queue_without_frontend_override(broker):
    service,mount,principal=broker
    mount.declaration['web_agent']['model_profile']='privacy'
    task=service.submit('mount',principal,capability='list',parameters={'count':3},profile='default',request_id='private')
    assert task['browser_context']['model_profile']=='privacy'
    assert task['profile_key']=='default'  # browser login Profile is independent


def test_compiler_keeps_profile_and_rejects_typo():
    source={'agent_type':'web','model_profile':'privacy','site_scope':['https://example.com/**'],
        'steps':[{'name':'read','operation':'inspect','on':{'success':'done','failed':'failed'}}]}
    assert compile_source(source).ir['model_profile']=='privacy'
    source['model_profile']='typo'
    assert not compile_source(source).valid


def test_run_routes_are_selected_and_pinned_from_privacy(tmp_path):
    from ai2apps.agent_builder.service import create_ir_run
    store=ModelManagerStore(tmp_path)
    store.put_default_models({'work_standard':'ordinary'})
    store.put_default_models({'work_standard':'cloud/private/trusted'},profile='privacy')
    captured={}
    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(id='run'),False
    runtime=SimpleNamespace(model_manager=store,agents=SimpleNamespace(create_run=create),
        agent_runtime=SimpleNamespace(wake=lambda:None))
    create_ir_run(runtime,session_id='session',ir={'model_profile':'privacy','steps':[]},invocation_input={}, browser_context={'model_profile':'normal'})
    params=captured['input']['parameters']
    assert params['model_profile']=='privacy'
    assert params['ai_model_routes']=={'simple':None,'standard':'cloud/private/trusted','complex':None}
    store.put_default_models({'work_standard':'changed'},profile='privacy')
    assert params['ai_model_routes']['standard']=='cloud/private/trusted'


@pytest.mark.asyncio
async def test_missing_privacy_planner_model_does_not_call_normal(tmp_path):
    from ai2apps.browser.background_planner import BackgroundPlanner
    store=ModelManagerStore(tmp_path)
    store.put_default_models({'work_standard':'ordinary'})
    calls=[]
    runtime=SimpleNamespace(model_manager=store,model_invocations=SimpleNamespace(model=lambda key:calls.append(key)))
    run=SimpleNamespace(input={'parameters':{'model_profile':'privacy','ai_model_routes':{}}})
    with pytest.raises(RuntimeError,match='privacy profile'):
        await BackgroundPlanner(runtime).next(run=run,step={},observation={},attempts=[],scopes=[])
    assert calls==[None]


@pytest.mark.asyncio
async def test_privacy_cloud_planning_uses_selected_authenticated_route(monkeypatch):
    import json
    from ai2apps.browser.background_planner import BackgroundPlanner
    monkeypatch.setattr('ai2apps.browser.background_planner._exploration_prompt',lambda request:'test')
    calls=[]
    async def invoke(payload,context):
        calls.append((payload['model'],context))
        return {'choices':[{'message':{'content':json.dumps({'decision':'needs_user','assistance_kind':'missing_information'})}}]}
    service=SimpleNamespace(context_for_actor=lambda *a,**k:'actor-context',invoke_agent_cloud_json=invoke)
    run=SimpleNamespace(session_id='session',input={'parameters':{'owner_user_id':'owner',
        'model_profile':'privacy','ai_model_routes':{'standard':'cloud/trusted/model'}}})
    decision=await BackgroundPlanner(SimpleNamespace(model_invocations=service)).next(run=run,step={},observation={},attempts=[],scopes=[])
    assert decision['decision']=='needs_user'
    assert calls==[('cloud/trusted/model','actor-context')]


@pytest.mark.parametrize('tier', ['simple', 'standard', 'complex'])
@pytest.mark.parametrize('system_private,requested,declared', [
    (True, 'normal', 'normal'), (False, 'privacy', 'normal'), (False, 'normal', 'privacy')])
def test_shared_task_routes_never_fall_back(tier, system_private, requested, declared):
    from ai2apps.task_llm import effective_profile, resolve_task_model
    calls = []
    def resolve(purpose, profile='normal'):
        calls.append((purpose, profile)); return None
    runtime = SimpleNamespace(privacy_mode=system_private,
        model_manager=SimpleNamespace(resolve_default_model=resolve))
    assert effective_profile(runtime, requested, declared) == 'privacy'
    assert resolve_task_model(runtime, tier, requested, declared=declared) is None
    assert calls == [('work_' + tier, 'privacy')]


def test_system_privacy_replaces_old_normal_planner_routes():
    from ai2apps.task_llm import resolve_task_model
    calls = []
    runtime = SimpleNamespace(privacy_mode=True, model_manager=SimpleNamespace(
        resolve_default_model=lambda purpose, **kwargs: calls.append((purpose, kwargs)) or 'private'))
    assert resolve_task_model(runtime, 'standard', 'normal', pinned_routes={'standard': 'ordinary'}) == 'private'
    assert calls == [('work_standard', {'profile': 'privacy'})]


def test_system_privacy_applies_to_background_run_at_creation():
    from ai2apps.agent_builder.service import create_ir_run
    captured = {}; routes = []
    def create(**kwargs): captured.update(kwargs); return SimpleNamespace(id='run'), False
    runtime = SimpleNamespace(privacy_mode=True, model_manager=SimpleNamespace(
        resolve_default_model=lambda purpose, **kwargs: routes.append((purpose, kwargs)) or 'private'),
        agents=SimpleNamespace(create_run=create), agent_runtime=SimpleNamespace(wake=lambda: None))
    create_ir_run(runtime, session_id='session', ir={'steps': []}, invocation_input={},
                  browser_context={'model_profile': 'normal'})
    assert captured['input']['parameters']['model_profile'] == 'privacy'
    assert all(kwargs == {'profile': 'privacy'} for _, kwargs in routes)


def test_system_privacy_applies_to_shared_mobile_desktop_task_submission(broker):
    service, mount, principal = broker
    service.runtime.privacy_mode = True
    task = service.submit('mount', principal, capability='list', parameters={'count': 3},
                          profile='default', request_id='system-private')
    assert task['browser_context']['model_profile'] == 'privacy'


def test_durable_request_rechecks_system_privacy_and_strips_internal_routing():
    from ai2apps.task_llm import prepare_task_request
    runtime = SimpleNamespace(privacy_mode=True, model_manager=SimpleNamespace(
        resolve_default_model=lambda purpose, **kwargs: 'private' if kwargs.get('profile') == 'privacy' else 'normal'))
    request = {'model': 'normal', 'messages': [], '_ai2apps_task_route': {'complexity': 'standard', 'profile': 'normal'}}
    assert prepare_task_request(runtime, request) == {'model': 'private', 'messages': []}
    assert request['model'] == 'normal'  # persisted replay input remains intact
    runtime.model_manager.resolve_default_model = lambda *a, **kw: None
    with pytest.raises(RuntimeError, match='privacy profile'):
        prepare_task_request(runtime, request)


def test_shared_simple_payload_omits_unsupported_temperature():
    from ai2apps.task_llm import task_payload
    assert 'temperature' not in task_payload('model', [], 'simple')
    assert task_payload('model', [], 'standard')['temperature'] == 0


@pytest.mark.asyncio
async def test_durable_dispatch_uses_private_route_without_leaking_metadata():
    from ai2apps.agents.runtime import AgentRuntime
    seen = []
    runtime = SimpleNamespace(privacy_mode=True, model_manager=SimpleNamespace(
        resolve_default_model=lambda *args, **kwargs: 'private-model'))
    async def provider(request, progress, context):
        seen.append(request); return {'choices': []}
    executor = SimpleNamespace(_model_invocations=SimpleNamespace(runtime=runtime),
        repository=SimpleNamespace(update_status_line=lambda *a, **kw: None), _call_model_provider=provider)
    await AgentRuntime._run_model_call(executor, 'run', {'model': 'normal', 'messages': [],
        '_ai2apps_task_route': {'complexity': 'standard', 'profile': 'normal'}},
        model_name='normal', step_sequence=1, context=None)
    assert seen == [{'model': 'private-model', 'messages': []}]
