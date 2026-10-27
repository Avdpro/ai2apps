from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.api.cloud import create_cloud_router
from ai2apps.identity import RequestPrincipal
from ai2apps.remote.visitor_avatar import VisitorAvatar, avatar_projection


def fixture(status=200):
    cloud=SimpleNamespace(request=AsyncMock(return_value=httpx.Response(status,json={'avatarRevision':2,'avatarUrl':None},headers={'etag':'"avatar-2"','retry-after':'5'})))
    app=FastAPI();app.include_router(create_cloud_router(lambda:SimpleNamespace(cloud=cloud),RequestPrincipal.legacy_local))
    return TestClient(app),cloud


@pytest.mark.parametrize('status',[200,401,409,428,429,503])
def test_upload_cas_and_error_passthrough(status):
    client,cloud=fixture(status)
    response=client.put('/cloud/profile/avatar',headers={'If-Match':'"avatar-1"'},files={'file':('private-name.png',b'png','image/png')})
    assert response.status_code==status
    assert response.headers['etag']=='"avatar-2"'
    assert response.headers['retry-after']=='5'
    args=cloud.request.call_args
    assert args.args==('PUT','/v1/profile/avatar')
    assert args.kwargs['headers']=={'If-Match':'"avatar-1"'}
    assert args.kwargs['files']=={'file':('avatar.png',b'png','image/png')}


def test_missing_revision_extra_field_and_oversize_never_reach_cloud():
    client,cloud=fixture()
    assert client.delete('/cloud/profile/avatar').status_code==428
    h={'If-Match':'"avatar-0"'}
    assert client.put('/cloud/profile/avatar?ownerId=other',headers=h,files={'file':('x',b'x')}).status_code==400
    assert client.put('/cloud/profile/avatar',headers=h,data={'ownerId':'other'},files={'file':('x',b'x')}).status_code==400
    assert client.put('/cloud/profile/avatar',headers=h,files={'file':('x',b'x'*(5*1024*1024+1))}).status_code==413
    assert cloud.request.await_count==0


def test_delete_has_only_cas_and_no_body():
    client,cloud=fixture()
    assert client.delete('/cloud/profile/avatar',headers={'If-Match':'"avatar-2"'}).status_code==200
    assert cloud.request.call_args.args==('DELETE','/v1/profile/avatar')
    assert cloud.request.call_args.kwargs['files'] is None


@pytest.mark.parametrize('url',['https://evil.example/a.png','https://coder.ai2apps.com@evil.example/a.png','https://coder.ai2apps.com/v1/public/avatars/00000000-0000-0000-0000-000000000000.png?token=x',None])
def test_projection_rejects_untrusted_url(url):
    assert avatar_projection({'ownerAvatarRevision':1,'ownerAvatarUrl':url})['ownerAvatarUrl'] is None


@pytest.mark.asyncio
async def test_projection_refresh_is_independent_of_space_revision():
    url='https://coder.ai2apps.com/v1/public/avatars/00000000-0000-0000-0000-000000000000.png'
    manager=SimpleNamespace(_request=AsyncMock(return_value={'ownerAvatarRevision':1,'ownerAvatarUrl':url}))
    avatar=VisitorAvatar(manager)
    assert (await avatar.get('owner'))['ownerAvatarUrl']==url
    await avatar.get('owner');assert manager._request.await_count==1
    avatar.cache['owner']=(0,avatar.cache['owner'][1])
    manager._request.return_value={'ownerAvatarRevision':2,'ownerAvatarUrl':None}
    assert (await avatar.get('owner'))=={'ownerAvatarRevision':2,'ownerAvatarUrl':None}


def test_avatar_csp_only_on_account_and_space_editor():
    from fastapi.responses import HTMLResponse
    from ai2apps.http_security import LocalBrowserSecurityHeadersMiddleware
    from ai2apps.web.space_routes import HEADERS
    app=FastAPI()
    @app.get('/{path:path}')
    def page(path):
        return HTMLResponse('ok')
    app.add_middleware(LocalBrowserSecurityHeadersMiddleware)
    with TestClient(app) as client:
        for path in ['/admin/app-content/ai2apps.account','/admin/app-content/ai2apps.visitor-space']:
            policy=client.get(path).headers['content-security-policy']
            assert 'img-src \'self\' data: blob: https://coder.ai2apps.com;' in policy
        assert 'https://coder.ai2apps.com' not in client.get('/admin/app-content/ai2apps.terminal').headers['content-security-policy']
    assert "img-src 'self' https://coder.ai2apps.com;" in HEADERS['Content-Security-Policy']
