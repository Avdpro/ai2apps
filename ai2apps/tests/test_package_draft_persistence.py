import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from ai2apps.api import studio_mini_apps as api
from ai2apps.storage import PlatformDatabase


def test_package_drafts_survive_remount_and_enforce_scope(tmp_path, monkeypatch):
    database = PlatformDatabase(tmp_path / 'platform.sqlite3')
    database.initialize()
    mounted = SimpleNamespace(mount={'context': {'studioInstanceId': 'studio-one'}}, declaration={'id': 'frozen'})
    manager = SimpleNamespace(instance_entry=lambda *a, **k: {'app_key': 'imagine'})
    runtime = SimpleNamespace(database=database, extension_manager=manager)
    monkeypatch.setattr(api, 'StudioCapabilityBroker', lambda runtime: SimpleNamespace(mounted_mini_app=lambda *a, **k: mounted))
    monkeypatch.setattr(api, 'authorize_app_instance', lambda *a: None)
    router = api.create_studio_mini_app_router(lambda: runtime)
    endpoints = {route.name: route.endpoint for route in router.routes if hasattr(route,"endpoint")}
    principal = SimpleNamespace(actor_user_id='alice', installation_id='installation')
    get, put = endpoints['get_package_draft'], endpoints['put_package_draft']
    value = json.dumps({'schema': 'ai2apps.mini-app-draft/v1', 'miniApp': 'frozen', 'motionPresets': [{'name': '震撼登场'}]})
    assert get('imagine', 'old-mount', principal)['value'] is None
    put('imagine', 'old-mount', api.MiniAppDraftRequest(value=value), principal)
    assert json.loads(get('imagine', 'new-mount', principal)['value'])['motionPresets'][0]['name'] == '震撼登场'
    assert get('imagine', 'new-mount', SimpleNamespace(actor_user_id='bob', installation_id='installation'))['value'] is None
    assert get('imagine', 'new-mount', SimpleNamespace(actor_user_id='alice', installation_id='other'))['value'] is None
    mounted.mount['context']['studioInstanceId'] = 'studio-two'
    assert get('imagine', 'new-mount', principal)['value'] is None
    mounted.mount['context']['studioInstanceId'] = 'studio-one'
    with pytest.raises(HTTPException) as error:
        put('imagine', 'new-mount', api.MiniAppDraftRequest(value=value.replace('frozen', 'other')), principal)
    assert error.value.status_code == 422
    with pytest.raises(HTTPException):
        put('imagine', 'new-mount', api.MiniAppDraftRequest(value='[]'), principal)
    manager.instance_entry = lambda *a, **k: {'app_key': 'wrong-studio'}
    with pytest.raises(HTTPException) as error:
        get('imagine', 'new-mount', principal)
    assert error.value.status_code == 404


def test_client_migrates_legacy_only_when_durable_draft_absent():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / 'web/static/js/studio_mini_apps.js').read_text()
    assert 'if (value == null && legacy)' in source
    assert 'draft.miniApp === binding.miniAppId' in source
    assert 'localStorage.setItem(storageKey, request.value)' not in source
    assert 'method:\'PUT\'' in source


def test_versioned_write_rejects_stale_editor_without_overwriting_bot(tmp_path, monkeypatch):
    database=PlatformDatabase(tmp_path/'cas.sqlite3');database.initialize()
    mounted=SimpleNamespace(mount={'context':{'studioInstanceId':'host'}},declaration={'id':'example.project'})
    runtime=SimpleNamespace(database=database,extension_manager=SimpleNamespace(instance_entry=lambda *a,**k:{'app_key':'studio'}))
    monkeypatch.setattr(api,'StudioCapabilityBroker',lambda r:SimpleNamespace(mounted_mini_app=lambda *a,**k:mounted))
    monkeypatch.setattr(api,'authorize_app_instance',lambda *a:None)
    endpoints={r.name:r.endpoint for r in api.create_studio_mini_app_router(lambda:runtime).routes if hasattr(r,"endpoint")}
    p=SimpleNamespace(actor_user_id='alice',installation_id='local')
    get,put=endpoints['get_package_draft'],endpoints['put_package_draft']
    def body(value,version):return api.MiniAppDraftRequest(value=json.dumps({'schema':'ai2apps.mini-app-draft/v1','miniApp':'example.project','text':value}),expected_updated_at=version)
    first=put('studio','mount',body('original',''),p)
    second=put('studio','mount',body('bot result',first['updatedAt']),p)
    with pytest.raises(HTTPException) as error:put('studio','mount',body('stale editor',first['updatedAt']),p)
    assert error.value.status_code==409
    final=get('studio','mount',p)
    assert final['updatedAt']==second['updatedAt'] and json.loads(final['value'])['text']=='bot result'
