from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.account_browser import recharge_url, open_recharge_page
from ai2apps.api.cloud import create_cloud_router
from ai2apps.identity import RequestPrincipal


def test_login_return_target_preserves_purchase_panel():
    url = urlsplit(recharge_url())
    assert (url.scheme, url.netloc, url.path) == ('https', 'home.ai2apps.com', '/signin')
    assert parse_qs(url.query) == {'returnTo': ['/account?panel=credit-purchase#credit']}


@pytest.mark.asyncio
async def test_os_default_browser_no_shell_or_credentials(monkeypatch):
    import ai2apps.account_browser as module
    monkeypatch.setattr(module.sys, 'platform', 'darwin')
    spawn = AsyncMock(return_value=SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0))
    monkeypatch.setattr(module.asyncio, 'create_subprocess_exec', spawn)
    await open_recharge_page()
    assert spawn.call_args.args == ('/usr/bin/open', recharge_url())


@pytest.mark.parametrize('host,status,opened', [('127.0.0.1',200,True), ('::1',200,True), ('192.0.2.1',403,False)])
def test_open_recharge_requires_local_desktop(monkeypatch, host, status, opened):
    opener = AsyncMock()
    monkeypatch.setattr('ai2apps.account_browser.open_recharge_page', opener)
    app = FastAPI()
    app.include_router(create_cloud_router(lambda: SimpleNamespace(), RequestPrincipal.legacy_local))
    with TestClient(app, client=(host, 1200)) as client:
        response = client.post('/cloud/account/open-recharge')
    assert response.status_code == status
    assert opener.await_count == int(opened)


def test_launcher_failure_is_reported(monkeypatch):
    monkeypatch.setattr('ai2apps.account_browser.open_recharge_page', AsyncMock(side_effect=OSError()))
    app = FastAPI()
    app.include_router(create_cloud_router(lambda: SimpleNamespace(), RequestPrincipal.legacy_local))
    with TestClient(app, client=('127.0.0.1', 1200)) as client:
        response = client.post('/cloud/account/open-recharge')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'ACCOUNT_BROWSER_OPEN_FAILED'
