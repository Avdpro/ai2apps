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
    endpoints = {route.name: route.endpoint for route in router.routes}
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
