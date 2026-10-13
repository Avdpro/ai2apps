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
