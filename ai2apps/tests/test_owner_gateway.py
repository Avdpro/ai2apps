"""Owner requests may reach only the explicitly exported Mobile Chat surface."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import time

import pytest
from fastapi import FastAPI, APIRouter, Depends
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse
from ai2apps.identity import RequestPrincipal
from ai2apps.remote.owner_home import COOKIE
from ai2apps.remote.security import RemoteTokenError
from ai2apps.web import owner_home_gateway as gateway
from ai2apps.web.public_boundary import PublicDeviceBoundary
from ai2apps.web.space_routes import create_space_router
from omlx.admin import routes


@pytest.fixture
def env(tmp_path):
    principal = replace(RequestPrincipal.legacy_local(),authentication_type='owner_home_lease')
    device = SimpleNamespace(public_origin='https://device.example',device_id='device')
    record = SimpleNamespace(claims={'device_id':'device'},deadline=time.time()+60,absolute=time.time()+28800,idle=time.time()+1800,revoked=False)
    def valid(r):
        if r.revoked: raise RemoteTokenError('revoked')
    service = SimpleNamespace(valid=valid,principal=lambda r: (valid(r) or principal),urls={'device':'https://coder.ai2apps.com/u/00000000-0000-0000-0000-000000000001?entry=owner-home'})
    async def authorize(token):
        if token != 'owner': raise RemoteTokenError('unknown')
        valid(record)
        return record
    async def revoke(r): r.revoked=True
    service.authorize=authorize
    service.revoke=revoke
    manager=SimpleNamespace(owner_home=service,repository=SimpleNamespace(list=lambda:[device]),require_device=lambda _:device,authorize_session=AsyncMock(return_value=None))
    from ai2apps.storage import PlatformDatabase
    db=PlatformDatabase(tmp_path/'mobile.sqlite');db.initialize()
    runtime=SimpleNamespace(remote=manager,database=db)
    shell=MagicMock()
    shell.list_mobile_apps.return_value=[{'app_key':'ai2apps.general-chat'}, {'app_key':'ai2apps.todo'}, {'app_key':'ai2apps.knowledge'}, {'app_key':'ai2apps.gallery'}, {'app_key':'ai2apps.account'}]
    shell.list_mobile_mounts.return_value=[]
    shell.instance_entry.return_value={'app_key':'ai2apps.account'}
    shell.mount_entry.return_value={'app_key':'ai2apps.account'}
    models=AsyncMock(return_value={'data':[{'id':'test-model'}]})
    async def complete(payload,request,actor):
        assert actor is principal
        assert request.state.ai2apps_principal is principal
        assert 'authorization' not in request.headers
        async def stream(): yield b'data: [DONE]\n\n'
        return StreamingResponse(stream(),media_type='text/event-stream')
    app=FastAPI()
    app.include_router(routes.shell_router)
    app.include_router(create_space_router(lambda:manager))
    @app.get('/v1/platform/secrets')
    async def sensitive(): pytest.fail('Sensitive main server reached')
    app.add_middleware(PublicDeviceBoundary,manager_provider=lambda:manager)
    with patch.object(routes,'_get_platform_runtime',lambda:runtime),patch.object(gateway,'_runtime',lambda:runtime),patch.object(gateway,'_models',models),patch.object(gateway,'_completion',complete),patch.object(routes,'_remote_manager',lambda:manager),patch.object(routes,'_shell_manager',lambda:shell),patch.object(routes,'_require_system_app_access',lambda *args:None):
        with TestClient(app,base_url='https://device.example',headers={'Cookie':f'{COOKIE}=owner','Origin':device.public_origin}) as client:
            yield client,record,shell,models,principal


def test_owner_catalog_is_approved_mobile_apps_only(env):
    client,_,_,_,_=env
    assert client.get('/v1/mobile/apps').json()['items']==[{'app_key':'ai2apps.general-chat'}, {'app_key':'ai2apps.todo'}, {'app_key':'ai2apps.knowledge'}, {'app_key':'ai2apps.gallery'}]


@pytest.mark.parametrize('path', ['/admin','/v1/platform/secrets','/v1/models/admin','/v1/chat/completions','/mcp','/mobile/app-content/ai2apps.account','/v1/mobile/agents','/v1/mobile/chat/threads/x/attachments','/v1/mobile/chat/threads/x/agent-runs'])
def test_owner_cookie_does_not_open_other_surfaces(env,path):
    client,*_=env
    assert client.get(path).status_code==401


def test_method_and_csrf_checks(env):
    client,*_=env
    assert client.delete('/v1/mobile/apps').status_code==401
    assert client.post('/v1/mobile/chat/threads',headers={'Origin':'https://other.example'},json={}).status_code==401


def test_cross_app_instance_and_mount_denied(env):
    client,_,shell,_,_=env
    assert client.post('/v1/mobile/app-instances/account-instance/focus').status_code==403
    assert client.delete('/v1/mobile/mounts/account-mount').status_code==403
    shell.focus_instance.assert_not_called()
    shell.unmount.assert_not_called()


def test_models_and_completion_use_typed_callbacks(env):
    client,_,_,models,principal=env
    with patch('ai2apps.web.mobile_model_catalog.desktop_catalog_projection', AsyncMock(return_value=[{'id':'test-model'}])) as projection:
        assert client.get('/v1/mobile/models').json()=={'data':[{'id':'test-model'}]}
        projection.assert_awaited_once_with([{'id':'test-model'}])
    models.assert_awaited_once_with(principal)
    response=client.post('/v1/mobile/chat/completions',json={'model':'test-model','messages':[{'role':'user','content':'Hi'}]})
    assert response.status_code==200
    assert response.text=='data: [DONE]\n\n'


def test_chat_proxy_is_independent_of_main_app(env):
    client,_,_,_,principal=env
    def chat_router(runtime_provider,principal_provider):
        router=APIRouter(prefix='/chat')
        @router.get('')
        def state(actor=Depends(principal_provider)):
            assert actor is principal
            return {'selected_thread_id':None}
        return router
    with patch('ai2apps.api.chat.create_chat_router',chat_router):
        assert client.get('/v1/mobile/chat/state').json()=={'selected_thread_id':None}


def test_logout_clears_cookie_after_local_revocation(env):
    client,record,*_=env
    response=client.post('/v1/mobile/owner-home/logout')
    assert response.status_code==200
    assert record.revoked
    assert 'Max-Age=0' in response.headers['set-cookie']
    assert client.get('/v1/mobile/apps').status_code==401


def test_spoofed_authority_header_not_trusted(env):
    client,*_=env
    response=client.get('/v1/mobile/apps',headers={'Cookie':f'{COOKIE}=visitor',gateway.MARKER:'owner'})
    assert response.status_code==401


def test_real_chat_repository_roundtrip(env,tmp_path):
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.config import PlatformConfig
    client,_,_,_,_=env
    manager=gateway._runtime().remote
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    runtime.remote=manager
    with patch.object(gateway,'_runtime',lambda:runtime):
        state=client.get('/v1/mobile/chat/state')
        assert state.status_code==200
        thread=client.post('/v1/mobile/chat/threads',json={'title':'Owner integration test'}).json()
        assert thread['title']=='Owner integration test'
        url='/v1/mobile/chat/threads/'+thread['id']+'/content'
        content=client.get(url).json()
        saved=client.put(url,json={'expected_revision':content['thread']['revision'],
            'messages':[{'role':'user','content':'Lease-scoped chat'}]})
        assert saved.status_code==200
        assert client.get(url).json()['messages'][0]['content']=='Lease-scoped chat'
        assert client.get('/v1/mobile/chat/threads/'+str(__import__('uuid').uuid4())+'/content').status_code==404


def test_disabled_app_blocks_catalog_reopen_and_direct_content(env):
    from ai2apps.remote.mobile_apps import MobileAppPolicy
    client,_,shell,_,actor=env
    policy=MobileAppPolicy(routes._get_platform_runtime().database)
    policy.set_enabled(actor.installation_id,'ai2apps.gallery',False)
    assert 'ai2apps.gallery' not in [item['app_key'] for item in client.get('/v1/mobile/apps').json()['items']]
    assert client.post('/v1/mobile/apps/ai2apps.gallery/open').status_code==403
    shell.instance_entry.return_value={'app_key':'ai2apps.gallery'}
    assert client.post('/v1/mobile/app-instances/existing/focus').status_code==403
    assert client.get('/mobile/app-content/ai2apps.gallery').status_code==403
    assert client.get('/v1/mobile/gallery/collections').status_code==403
    policy.set_enabled(actor.installation_id,'ai2apps.gallery',True)
    assert 'ai2apps.gallery' in [item['app_key'] for item in client.get('/v1/mobile/apps').json()['items']]


def test_custom_package_resources_require_owner_mount_and_enabled_policy(env, tmp_path, monkeypatch):
    from ai2apps.remote.mobile_apps import MobileAppPolicy
    monkeypatch.setenv('AI2APPS_MOBILE_PACKAGE_GATEWAY_READY','1')
    client,record,shell,_,actor=env
    policy=MobileAppPolicy(routes._get_platform_runtime().database)
    shell.list_mobile_apps.return_value.append({'app_key':'custom.demo','mobile_renderer':'sandbox'})
    shell.mount_entry.return_value={'id':'mount','placement':'mobile','renderer':'sandbox',
        'resource':'index.html','app_instance_id':'instance','app_key':'custom.demo','source':'package'}
    path=tmp_path/'index.html';path.write_text('<!doctype html><html><body>Hello</body></html>')
    shell.resolve_app_resource.return_value=path
    url='/mobile/app-resource/mount/instance/index.html'
    assert client.get(url).status_code==403
    policy.set_enabled(actor.installation_id,'custom.demo',True)
    response=client.get(url)
    assert response.status_code==200
    assert 'allow-same-origin' not in response.headers['content-security-policy']
    assert 'sandbox allow-scripts' in response.headers['content-security-policy']
    assert client.get('/mobile/app-resource/mount/another/index.html').status_code==403
    bridge='/v1/mobile/app-mounts/mount/bridge'
    assert client.post(bridge,json={'method':'context'}).json()['capabilities']==[]
    assert client.post(bridge,json={'method':'execute'}).status_code==403
    assert client.post(bridge,json={'method':'context','instanceId':'another'}).status_code==422
    assert client.post(bridge,json={'method':'context'},headers={'Origin':'https://evil.example'}).status_code==401
    shell.mount_entry.return_value['placement']='sidebar'
    assert client.get(url).status_code==403
    shell.mount_entry.return_value['placement']='mobile'
    record.revoked=True
    assert client.get(url).status_code==401
    assert client.post(bridge,json={'method':'context'}).status_code==401


def test_anonymous_package_resource_is_denied(env):
    client,*_=env
    client.cookies.clear()
    assert client.get('/mobile/app-resource/mount/instance/index.html',headers={'Cookie':''}).status_code==403


@pytest.mark.parametrize('cookie', ['', f'{COOKIE}=expired'])
def test_expired_shell_navigation_returns_to_cloud_account(env, cookie):
    client,*_=env
    response=client.get('/mobile',headers={'Cookie':cookie,'Accept':'text/html'},follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location']=='https://coder.ai2apps.com/u/00000000-0000-0000-0000-000000000001?entry=owner-home'
    assert response.headers['cache-control']=='no-store'
    assert client.get('/v1/mobile/apps',headers={'Cookie':cookie,'Accept':'text/html'},follow_redirects=False).status_code in (401,403)


def test_recovery_never_redirects_unknown_host_or_untrusted_target(env):
    client,*_=env
    headers={'Cookie':'','Accept':'text/html'}
    assert client.get('/mobile',headers={**headers,'Host':'other.example'},follow_redirects=False).status_code==403
    routes._get_platform_runtime().remote.owner_home.urls['device']='https://evil.example/'
    response=client.get('/mobile',headers=headers,follow_redirects=False)
    assert response.status_code==303
    assert response.headers['location']=='/mobile/member/complete'
