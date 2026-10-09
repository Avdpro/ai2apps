"""Accountless desktop sessions cannot register devices or spend Cloud credits."""
import asyncio
from unittest.mock import patch, AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.auth import create_auth_router
from ai2apps.cloud_client import AI2AppsCloudClient, CloudSessionStore
from ai2apps.config import PlatformConfig
from ai2apps.identity import IdentityBindingError, IdentityRepository, OrganizationType
from ai2apps.offline import OfflineAccess
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.secrets import MemorySecretBackend
from ai2apps.storage.database import PlatformDatabase


@pytest.fixture
def offline(tmp_path):
    db = PlatformDatabase(tmp_path / 'platform.db')
    db.initialize()
    return OfflineAccess(db, 'instance-1')


def bind(repository):
    repository.bind_installation(
        installation_id='installation-1', cloud_device_id='device-1',
        organization_id='organization-1', organization_type=OrganizationType.HOUSEHOLD,
        core_user_id='core-1', billing_account_id='billing-1', access_epoch=1,
    )


def test_offline_session_persists_without_cloud_identity_and_revokes(offline):
    token, principal = offline.activate()
    assert principal.authentication_type == 'offline_session'
    assert principal.actor_user_id == 'offline.instance-1'
    assert offline.identities.get_installation() is None
    restored = OfflineAccess(offline.identities.database, 'instance-1')
    assert restored.authorize(token) == principal
    assert restored.authorize('forged') is None
    assert token not in offline.path.read_text()
    restored.revoke(token)
    assert restored.authorize(token) is None
    assert restored.enabled


def test_bound_installation_cannot_activate_or_restore_offline(offline):
    bind(offline.identities)
    with pytest.raises(IdentityBindingError):
        offline.activate()
    assert not offline.enabled


def test_session_cannot_cross_instances(offline):
    token, _ = offline.activate()
    other = OfflineAccess(offline.identities.database, 'instance-2')
    other.activate()
    assert other.authorize(token) is None


def test_expired_sessions_fail_closed(offline):
    token, _ = offline.activate()
    with patch('ai2apps.offline.time.time', return_value=10**12):
        assert offline.authorize(token) is None


def test_cloud_gate_blocks_network_but_preserves_anonymous_registry(offline):
    calls = []
    def transport(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={'ok': True})
    cloud = AI2AppsCloudClient(
        session_store=CloudSessionStore(MemorySecretBackend(), 'https://cloud.example'),
        base_url='https://cloud.example', transport=httpx.MockTransport(transport),
        offline_mode=lambda: offline.enabled,
    )
    async def run():
        assert (await cloud.request('GET', '/v1/auth/me')).status_code == 200
        calls.clear()
        offline.activate()
        for path in ['/v1/auth/me', '/v1/devices', '/v1/ai/responses', '/v1/auth/login']:
            response = await cloud.request('POST', path, stream=True)
            assert response.status_code == 403
            assert response.json()['error']['code'] == 'offline_mode'
        assert calls == []
        with pytest.raises(RuntimeError, match='offline mode'):
            cloud._get_client()
        assert (await cloud.request_public('GET', '/v1/registry/index')).status_code == 200
        assert calls == ['/v1/registry/index']
        await cloud.close()
    asyncio.run(run())


@pytest.fixture
def runtime(tmp_path):
    value = PlatformRuntime(PlatformConfig.from_base_path(tmp_path, secret_backend='encrypted-file'))
    value.start()
    yield value
    value.stop()


def test_runtime_routes_identity_and_cloud_clients_consistently(runtime):
    async def run():
        runtime.remote.shutdown = AsyncMock()
        token, principal = await runtime.activate_offline()
        assert runtime.authorize_local_session(token) == principal
        assert runtime.legacy_api_key_principal() == principal
        assert runtime.refresh_local_session(token) == (token, principal, False)
        assert runtime.cloud.offline_mode()
        assert runtime.cloud_for_browser('a' * 40).offline_mode()
        assert runtime.cloud_ai_authorization_headers(principal) == {}
        assert IdentityRepository(runtime.database).local_principal_for(principal.actor_user_id) == principal
        context = runtime.model_invocations.context_for_actor(principal.actor_user_id, session_id='offline-test')
        assert context.actor_user_id == principal.actor_user_id
        assert context.installation_id == principal.installation_id
        with pytest.raises(IdentityBindingError):
            IdentityRepository(runtime.database).principal_for(principal.actor_user_id)
        with pytest.raises(IdentityBindingError, match='offline mode'):
            await runtime.bootstrap_core_account(display_name='x', owner_password='unused', cloud=runtime.cloud)
        runtime.revoke_local_session(token)
        assert runtime.authorize_local_session(token) is None
    asyncio.run(run())


def test_activation_requires_native_shell_origin_and_local_peer(runtime):
    app = FastAPI()
    app.include_router(create_auth_router(lambda: runtime), prefix='/v1/platform')
    path = '/v1/platform/auth/offline/activate'
    with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 54321)) as client:
        assert client.post(path).status_code == 403
        with patch('ai2apps.api.client.is_desktop_shell_request', return_value=True):
            assert client.post(path, headers={'Origin': 'https://evil.example'}).status_code == 403
            result = client.post(path, headers={'Origin': 'http://127.0.0.1'})
            assert result.status_code == 201
            assert 'httponly' in result.headers['set-cookie'].lower()
            assert result.json()['actorUserId'].startswith('offline.')
            assert runtime.authorize_local_session(client.cookies.get(runtime.local_session_cookie_name()))
    with TestClient(app, base_url='http://127.0.0.1', client=('192.0.2.1', 54321)) as client:
        with patch('ai2apps.api.client.is_desktop_shell_request', return_value=True):
            assert client.post(path).status_code == 403


def test_native_bootstrap_through_real_platform_auth(runtime, monkeypatch):
    from fastapi import Depends
    from ai2apps.api.client import create_client_router
    from omlx import server
    monkeypatch.setenv('AI2APPS_HELPER_TOKEN', 'a' * 64)
    monkeypatch.setenv('AI2APPS_INSTANCE_ID', 'offline-unit-test')
    monkeypatch.setattr(server, 'get_ai2apps_platform_runtime', lambda: runtime)
    app = FastAPI()
    gate = [Depends(server.verify_ai2apps_platform_access)]
    app.include_router(create_client_router(lambda: runtime), prefix='/v1/platform', dependencies=gate)
    app.include_router(create_auth_router(lambda: runtime), prefix='/v1/platform', dependencies=gate)
    with TestClient(app, base_url='http://127.0.0.1', client=('127.0.0.1', 54321)) as client:
        assert client.get('/v1/platform/auth/me').status_code == 401
        assert client.post('/v1/platform/auth/offline/activate').status_code == 403
        # Helper credentials only bootstrap the native shell, never appear in UI.
        established = client.post('/v1/platform/client/shell-session', headers={'Authorization': 'Bearer ' + 'a' * 64})
        assert established.status_code == 200
        assert client.get('/v1/platform/client/bootstrap').json()['offline_available']
        assert client.post('/v1/platform/auth/offline/activate').status_code == 201
        me = client.get('/v1/platform/auth/me')
        assert me.status_code == 200
        assert me.json()['actorUserId'].startswith('offline.')
        assert client.get('/v1/platform/client/bootstrap').json()['offline_mode']
        assert client.post('/v1/platform/auth/logout').status_code == 204
        assert client.get('/v1/platform/auth/me').status_code == 401


def test_runtime_restart_keeps_offline_mode_and_actor(tmp_path):
    config = PlatformConfig.from_base_path(tmp_path, secret_backend='encrypted-file')
    first = PlatformRuntime(config)
    first.start()
    token, principal = asyncio.run(first.activate_offline())
    first.stop()
    second = PlatformRuntime(config)
    second.start()
    try:
        assert second.offline_mode
        assert second.authorize_local_session(token) == principal
        assert IdentityRepository(second.database).get_installation() is None
    finally:
        second.stop()


@pytest.mark.parametrize('value', ['null', '', '{', '{"version":1,"sessions":{"token":NaN}}'])
def test_corrupt_mode_never_silently_reenables_cloud(offline, value):
    offline.path.write_text(value)
    with pytest.raises(IdentityBindingError):
        OfflineAccess(offline.identities.database, offline.instance_id)


def test_offline_byok_still_reaches_only_configured_provider(runtime):
    from ai2apps.cloud_gateway import proxy_cloud_chat_completion
    from omlx.api.openai_models import ChatCompletionRequest
    async def run():
        _, principal = await runtime.activate_offline()
        runtime.model_manager.put_cloud('deepseek', {'api_key': 'unit-test-only', 'models': ['test-model']})
        runtime.model_manager.set_cloud_model_enabled('deepseek', 'test-model', True)
        calls = []
        def provider(request):
            calls.append(str(request.url))
            return httpx.Response(200, json={'id': 'response', 'choices': []})
        response = await proxy_cloud_chat_completion(
            ChatCompletionRequest(model='cloud/deepseek/test-model', messages=[{'role': 'user', 'content': 'hello'}]),
            base_path=runtime.config.paths.base_path,
            model_manager=runtime.model_manager,
            cloud_client=runtime.cloud,
            authorization_headers=runtime.cloud_ai_authorization_headers(principal),
            transport=httpx.MockTransport(provider),
        )
        assert response.status_code == 200
        assert calls == ['https://api.deepseek.com/chat/completions']
        with pytest.raises(IdentityBindingError):
            IdentityRepository(runtime.database).local_principal_for('offline.another-instance')
    asyncio.run(run())


def test_registry_install_reads_are_anonymous_and_writes_still_blocked(tmp_path):
    import hashlib
    from ai2apps.packages.registry import RegistryPackageManager, RegistryError
    calls = []
    def handler(request):
        assert 'cookie' not in request.headers
        assert 'authorization' not in request.headers
        calls.append(request.url.path)
        if request.headers.get('range'):
            return httpx.Response(206, content=b'x', headers={'Content-Range':'bytes 0-0/1','Content-Length':'1'})
        return httpx.Response(200, json={'ok':True}, headers={'Set-Cookie':'ai2apps_session=must-not-be-replayed; Path=/'})
    backend=MemorySecretBackend()
    cloud=AI2AppsCloudClient(base_url='https://cloud.example', session_store=CloudSessionStore(backend,'https://cloud.example'), transport=httpx.MockTransport(handler), offline_mode=lambda:True)
    cloud.session_store.save('must-not-be-loaded')
    registry=RegistryPackageManager(cloud=cloud,root=tmp_path,secrets=None,extension_manager=None,service_manager=None)
    async def run():
        for path in ['/v1/registry/repository-key','/v1/registry/metadata/latest','/v1/registry/packages/ai2apps/model/versions/1/envelope']:
            assert (await registry._json('GET',path))['ok']
        response=await cloud.request_public('GET','/v1/registry/packages/ai2apps/model/versions/1/artifact',stream=True,headers={'Range':'bytes=0-0'})
        assert await response.aread()==b'x'
        await response.aclose()
        chunk=await registry._request_artifact_piece({'id':'cloud','kind':'cloud','url':'https://cloud.example/v1/registry/artifact'},start=0,end=0,artifact_size=1,media_type='application/octet-stream',expected_hash=hashlib.sha256(b'x').hexdigest(),observed=lambda *_:None)
        assert chunk==b'x'
        count=len(calls)
        with pytest.raises(RegistryError): await registry._json('POST','/v1/registry/packages')
        with pytest.raises(RegistryError): await registry._json('GET','/v1/auth/me')
        assert len(calls)==count
        await cloud.close()
    asyncio.run(run())


def test_offline_ignores_cached_cloud_defaults_preserves_explicit_byok(tmp_path, offline):
    import time
    from ai2apps.model_manager import ModelManagerStore
    store = ModelManagerStore(tmp_path / 'models', secret_backend=MemorySecretBackend(),
                              cloud_defaults_enabled=lambda: not offline.enabled)
    store.put_cloud_default_policy({
        'schema': 'ai2apps.ai-defaults/v1', 'revision': '1',
        'apiDefault': {'modelId': 'deepseek/deepseek-v4-flash', 'displayName': 'DeepSeek'},
    }, fetched_at=time.time())
    store.put_default_models({'work_complex': 'cloud/personal/my-model'})
    assert store.resolve_default_model('work_standard')
    offline.activate()
    assert store.cloud_default_policy() == {}
    assert store.resolve_default_model('work_standard') is None
    assert store.resolve_default_model('work_complex') == 'cloud/personal/my-model'
