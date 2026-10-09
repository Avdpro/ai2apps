from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch
from ai2apps.api.client import create_client_router
from ai2apps.browser.shell_window import ShellBrowserWindowBroker
from ai2apps.identity import MemberRole, RequestPrincipal


def test_focus_requires_shell_session_and_uses_native_broker():
    principal = RequestPrincipal(actor_user_id='user-123', installation_id='installation-1',
        organization_id='organization-1', billing_account_id='billing-1',
        role=MemberRole.OWNER, membership_epoch=1)
    app = FastAPI()
    app.include_router(create_client_router(runtime_provider=lambda: None,
        principal_provider=lambda: principal), prefix='/v1/platform')
    client = TestClient(app)
    with patch('ai2apps.api.client.is_desktop_shell_request', return_value=False), patch('ai2apps.api.client.shell_browser_window_broker.enqueue') as enqueue:
        assert client.post('/v1/platform/client/shell/focus').status_code == 403
        enqueue.assert_not_called()
    with patch('ai2apps.api.client.is_desktop_shell_request', return_value=True), patch('ai2apps.api.client.shell_browser_window_broker.enqueue', return_value='focus') as enqueue, patch('ai2apps.api.client.shell_browser_window_broker.wait', return_value={'status':'focused','pid':42}):
        assert client.post('/v1/platform/client/shell/focus').json()['status'] == 'focused'
        assert enqueue.call_args.kwargs['action'] == 'focus_shell'


def test_native_focus_completion():
    broker = ShellBrowserWindowBroker()
    request_id = broker.enqueue(action='focus_shell',profile_key='a'*64,profile_name='Shell',is_default=True)
    assert broker.claim_next()['action'] == 'focus_shell'
    broker.finish(request_id,status='focused',pid=42)
    assert broker.wait(request_id) == {'status':'focused','pid':42}
