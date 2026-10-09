from dataclasses import replace
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from ai2apps.storage import PlatformDatabase
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.remote.mobile_apps import MobileAppPolicy, require_mobile_path
from ai2apps.api.remote import create_remote_router

@pytest.fixture
def runtime(tmp_path):
    db=PlatformDatabase(tmp_path/'policy.sqlite');db.initialize()
    items=[{'app_key':'ai2apps.general-chat','display_name':'Chat','mobile_renderer':'host'},
           {'app_key':'my.app','display_name':'My App','mobile_renderer':'sandbox'}]
    return SimpleNamespace(database=db,extension_manager=SimpleNamespace(list_mobile_apps=lambda **kw:items))

def test_policy_defaults_persistence_and_installation_isolation(runtime):
    p=MobileAppPolicy(runtime.database)
    assert p.enabled('one','ai2apps.general-chat')
    assert not p.enabled('one','my.app')
    p.set_enabled('one','ai2apps.general-chat',False)
    assert not MobileAppPolicy(runtime.database).enabled('one','ai2apps.general-chat')
    assert p.enabled('two','ai2apps.general-chat')

def client(runtime, principal):
    app=FastAPI();app.include_router(create_remote_router(lambda:runtime,lambda:principal))
    return TestClient(app)

def test_owner_can_disable_and_restore_but_not_enable_pending_transport(runtime):
    actor=RequestPrincipal.legacy_local()
    with client(runtime,actor) as c:
        assert c.get('/remote/mobile-apps').status_code==200
        assert c.put('/remote/mobile-apps/ai2apps.general-chat',json={'enabled':False}).status_code==200
        with pytest.raises(HTTPException):require_mobile_path(runtime,actor,'/v1/mobile/chat/completions')
        assert c.put('/remote/mobile-apps/ai2apps.general-chat',json={'enabled':True}).status_code==200
        require_mobile_path(runtime,actor,'/mobile/chat')
        assert c.put('/remote/mobile-apps/my.app',json={'enabled':True}).status_code==409
        assert c.put('/remote/mobile-apps/unknown',json={'enabled':True}).status_code==404

@pytest.mark.parametrize('actor',[replace(RequestPrincipal.legacy_local(),role=MemberRole.MEMBER),
                                 replace(RequestPrincipal.legacy_local(),authentication_type='owner_home_lease')])
def test_mobile_or_nonowner_cannot_change_policy(runtime,actor):
    with client(runtime,actor) as c:
        assert c.get('/remote/mobile-apps').status_code==403
        assert c.put('/remote/mobile-apps/ai2apps.general-chat',json={'enabled':False}).status_code==403


def test_ready_config_is_instance_scoped_and_fails_closed(tmp_path,monkeypatch):
    import json
    from ai2apps.remote.mobile_apps import package_gateway_ready
    monkeypatch.delenv('AI2APPS_MOBILE_PACKAGE_GATEWAY_READY',raising=False)
    monkeypatch.setenv('AI2APPS_RUN_DESCRIPTOR_PATH',str(tmp_path/'dev/run/local.json'))
    assert not package_gateway_ready()
    path=tmp_path/'dev/config/mobile-package-gateway.json';path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'enabled':True,'protocol':'mobile-app-access-gateway-v1'}))
    assert package_gateway_ready()
    monkeypatch.setenv('AI2APPS_RUN_DESCRIPTOR_PATH',str(tmp_path/'app-dev/run/local.json'))
    assert not package_gateway_ready()
    monkeypatch.setenv('AI2APPS_MOBILE_PACKAGE_GATEWAY_READY','0')
    assert not package_gateway_ready()
