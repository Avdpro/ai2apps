from types import SimpleNamespace
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.client import create_client_router
from ai2apps.browser.shell_window import ShellBrowserWindowBroker, shell_browser_profile_key
from ai2apps.identity import RequestPrincipal
from ai2apps.storage import PlatformDatabase


def test_profile_status_reads_acknowledged_identity_without_native_action(tmp_path, monkeypatch):
    import ai2apps.api.client as module
    db=PlatformDatabase(tmp_path/'profiles.sqlite3'); db.initialize()
    broker=ShellBrowserWindowBroker()
    principal=RequestPrincipal.legacy_local()
    own=shell_browser_profile_key(principal.actor_user_id,'default')
    for key,context in [(own,'own-context'),(shell_browser_profile_key('other','default'),'other-context')]:
        request=broker.enqueue(action='bind',profile_key=key,profile_name='Default',is_default=True)
        broker.finish(request,status='bound',pid=42,user_context=context)
    monkeypatch.setattr(module,'shell_browser_window_broker',broker)
    app=FastAPI(); app.include_router(create_client_router(runtime_provider=lambda:SimpleNamespace(database=db,browser=object()),principal_provider=lambda:principal),prefix='/v1/platform')
    response=TestClient(app).get('/v1/platform/client/browser-profile-bindings')
    assert response.status_code==200
    assert response.json()=={'bindings':{'default':'own-context'}}
    assert broker.claim_next() is None
    request=broker.enqueue(action='delete',profile_key=own,profile_name='Default',is_default=True)
    broker.finish(request,status='deleted',pid=42)
    assert broker.known_binding(own) is None
