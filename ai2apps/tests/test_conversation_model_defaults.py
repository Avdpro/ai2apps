from ai2apps.model_manager import ModelManagerStore
from ai2apps.model_capabilities import agent_model_eligible


def test_independent_chat_agent_defaults_and_legacy_migration(tmp_path):
    store = ModelManagerStore(tmp_path)
    store.put_default_models({'work_standard': 'old-default'})
    assert store.default_models()['work_chat'] == ''
    assert store.default_models()['work_agent'] == ''
    assert store.resolve_default_model('work_chat') == 'old-default'
    assert store.resolve_default_model('work_agent', 'unqualified-fallback') is None
    store.cloud_default_policy = lambda: {'apiDefault': {'modelId': 'arbitrary-provider-model'}}
    assert store.resolve_default_model('work_chat') == 'cloud/ai2apps/arbitrary-provider-model'
    assert store.resolve_default_model('work_agent') == 'cloud/ai2apps/arbitrary-provider-model'
    assert store.resolve_default_model('work_agent', profile='privacy') is None
    store.put_default_models({'work_chat': 'light', 'work_agent': 'qualified', 'work_standard': 'old-default'},
                             available_model_ids={'light', 'qualified', 'old-default'})
    restored = ModelManagerStore(tmp_path).default_models()
    assert restored['work_chat'] == 'light'
    assert restored['work_agent'] == 'qualified'
    assert restored['work_standard'] == 'old-default'


def test_agent_catalog_requires_both_declarations():
    assert not agent_model_eligible({'id': 'famous-powerful', 'capabilities': ['work_standard']})
    assert not agent_model_eligible({'capabilities': ['work_simple', 'tool_calling_reliable']})
    assert not agent_model_eligible({'capabilities': {'work_standard': True, 'tool_calling_reliable': False}})
    assert agent_model_eligible({'capabilities': ['work_complex', 'tool_calling_reliable']})


def test_settings_api_allows_manual_unknown_quality_and_keeps_profiles_independent(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from ai2apps.api.model_profiles import create_model_profiles_router
    from ai2apps.identity import RequestPrincipal
    store = ModelManagerStore(tmp_path)
    async def catalog(request):
        return {'light': {'id': 'light', 'model_type': 'llm', 'capabilities': ['work']},
                'image': {'id':'image','model_type':'image_generation'},
                'hidden': {'id':'hidden','model_type':'llm','is_hidden':True},
                'qualified': {'id': 'qualified', 'model_type': 'llm', 'capabilities': ['work_standard', 'tool_calling_reliable']}}
    monkeypatch.setattr('ai2apps.api.model_profiles.model_catalog', catalog)
    app = FastAPI()
    app.include_router(create_model_profiles_router(lambda: SimpleNamespace(model_manager=store), RequestPrincipal.legacy_local))
    with TestClient(app) as client:
        assert client.put('/model-profiles/normal', json={'routes': {'work_agent': 'light'}}).status_code == 200
        assert client.get('/model-profiles').json()['profiles']['normal']['work_agent'] == 'light'
        assert ModelManagerStore(tmp_path).default_models()['work_agent'] == 'light'
        assert client.put('/model-profiles/normal', json={'routes': {'work_chat': 'light', 'work_agent': 'qualified'}}).status_code == 200
        assert client.put('/model-profiles/privacy', json={'routes': {'work_agent': 'qualified'}}).status_code == 200
        assert client.put('/model-profiles/normal', json={'routes': {'work_agent': 'image'}}).status_code == 422
        assert client.put('/model-profiles/normal', json={'routes': {'work_agent': 'hidden'}}).status_code == 422
        assert client.put('/model-profiles/normal', json={'routes': {'work_agent': 'missing'}}).status_code == 422
        assert store.default_models()['work_chat'] == 'light'
        assert store.default_models('privacy')['work_chat'] == ''


def test_declaration_summary_preserves_unknown_false_and_ignores_model_names():
    from ai2apps.model_capabilities import agent_capability_summary, agent_model_selectable
    for name in ('famous-powerful', 'tiny', 'arbitrary-provider/model'):
        model={'id':name,'model_type':'llm','capabilities':{}}
        summary=agent_capability_summary(model)
        assert summary['status']=='undeclared' and not summary['automatic_eligible']
        assert all(value is None for value in summary['declarations'].values())
        assert agent_model_selectable(model)
    summary=agent_capability_summary({'model_type':'llm','capabilities':{'workStandard':True,'toolCallingReliable':False}})
    assert summary['status']=='declared_insufficient'
    assert summary['declarations']['tool_calling_reliable'] is False
    assert not summary['automatic_eligible']
    assert agent_capability_summary({'capabilities':{'work_standard':'yes','tool_calling_reliable':'true'}})['status']=='undeclared'
    assert agent_capability_summary({'capabilities':['work_complex','tool_calling_reliable']})['automatic_eligible']
