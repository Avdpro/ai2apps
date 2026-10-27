"""Owner Studio route and principal boundary regression tests."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from ai2apps.identity import RequestPrincipal, MemberRole
from ai2apps.web import owner_studio_gateway as studio
from ai2apps.web import owner_home_gateway as owner
from ai2apps.tests.test_owner_gateway import env

@pytest.mark.parametrize('key', sorted(studio.STUDIO_APPS))
def test_studio_entry_exported(key):
    from ai2apps.apps.system import SYSTEM_APP_MANIFESTS
    manifest = next(m for m in SYSTEM_APP_MANIFESTS if m['id'] == key)
    assert manifest['mobile']['ready'] is True
    assert key in owner.OWNER_APPS
    assert owner.public_allowed('POST', '/v1/mobile/apps/' + key + '/open')
    assert owner.public_allowed('GET', '/mobile/app-content/' + key)

@pytest.mark.parametrize('method,path', [
    ('GET','/v1/platform/secrets'), ('POST','/v1/platform/cloud/auth/login'),
    ('GET','/v1/platform/sessions/x/workspace'),
    ('POST','/v1/platform/video-studio/composer/projects/open'),
    ('POST','/v1/platform/video-studio/composer/projects/save'),
    ('POST','/v1/platform/gallery/assets/x/browser-transfer'),
    ('GET','/v1/platform/studios/ai2apps.account/mini-apps'),
    ('POST','/v1/platform/imagine-studio/models'),
    ('GET','/v1/platform/readaloud/new-admin-api'),
])
def test_unexported_routes_stay_denied(method,path):
    assert not studio.allowed(method,path)


@pytest.mark.parametrize('method,path',[
    ('GET','/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_test/draft'),
    ('PUT','/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_test/draft'),
    ('DELETE','/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_test/draft'),
    ('GET','/v1/platform/imagine-studio/frozen-time/models'),
    ('POST','/v1/platform/imagine-studio/frozen-time/mounts/mnt_test/previews'),
    ('GET','/v1/platform/imagine-studio/frozen-time/previews/key/video'),
    ('POST','/v1/platform/imagine-studio/frozen-time/mounts/mnt_test/runs'),
    ('POST','/v1/platform/imagine-studio/runs/run/frozen-time'),
    ('POST','/v1/platform/imagine-studio/runs/recover-session-results'),
    ('GET','/v1/platform/imagine-studio/runs/run/frozen-content/output.mp4'),
    ('POST','/v1/platform/imagine-studio/frozen-time/mounts/mnt_test/runs/run/convert'),
])
def test_frozen_mobile_startup_and_workflow_exact_exports(method,path):
    assert studio.allowed(method,path)
    with TestClient(studio.create_app(lambda:None)) as client:
        assert client.request(method,path).status_code==401


@pytest.mark.parametrize('method,path',[
    ('POST','/v1/platform/imagine-studio/runs/run/save-live-photo'),
    ('POST','/v1/platform/imagine-studio/frozen-time/mounts/mnt_test/runs/run/save-live-photo'),
    ('POST','/v1/platform/client/native-export/id/complete'),
    ('GET','/v1/platform/client/native-export/next'),
    ('POST','/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_test/draft'),
    ('GET','/v1/platform/studios/ai2apps.account/mini-app-mounts/mnt_test/draft'),
])
def test_mobile_draft_and_frozen_exports_do_not_expose_native_save(method,path):
    assert not studio.allowed(method,path)

@pytest.mark.parametrize('path', ['/v1/platform/imagine-studio/mini-apps',
    '/v1/platform/readaloud/mini-apps', '/v1/platform/video-studio/mini-apps'])
def test_direct_isolated_app_requires_authority(path):
    with TestClient(studio.create_app(lambda:None)) as client:
        assert client.get(path).status_code == 401


def test_models_isolated_and_lease_guarded(env):
    client,record,_,models,_=env
    assert client.get('/v1/models').status_code == 200
    models.assert_awaited_once()
    record.revoked=True
    assert client.get('/v1/models').status_code == 401


def test_owner_studio_csrf_and_no_cookie(env):
    client,*_=env
    assert client.post('/v1/images/generations',json={},headers={'Origin':'https://other.example'}).status_code==401
    assert client.get('/v1/models',headers={'Cookie':''}).status_code==403


def test_frozen_inventory_matches_real_router():
    app=studio.create_app(lambda:None)
    paths=app.openapi()['paths']
    for row in studio.ROUTES:
        # OpenAPI erases path converter syntax.
        path=row['path'].replace(':path','')
        assert row['method'].lower() in paths[path], row
    assert '/v1/platform/sessions/{session_id}/workspace' not in paths


def test_migrated_llm_mobile_routes_and_asset_are_explicit():
    from omlx.admin import routes
    assert 'js/audiobook_source.js' in routes.MOBILE_STATIC_FILES
    for suffix in ('mini-app-mounts/mnt_test/llm', 'mini-apps/ai2apps.audio.audiobook/llm'):
        path = '/v1/platform/studios/ai2apps.readaloud/' + suffix
        assert studio.allowed('POST', path)
        assert not studio.allowed('GET', path)
        assert not studio.allowed('POST', path.replace('ai2apps.readaloud', 'untrusted.app'))
    assert not studio.allowed('POST', '/v1/platform/readaloud/projects/p/source/analyze')
    assert not studio.allowed('POST', '/v1/platform/studios/ai2apps.readaloud/mini-app-mounts/mnt_test/subtitle-refinement')


def test_owner_package_draft_through_public_boundary(env, monkeypatch):
    from ai2apps.api import studio_mini_apps as api
    client, _, manager, _, _ = env
    runtime = owner._runtime()
    runtime.extension_manager = manager
    manager.instance_entry.return_value = {'app_key': 'ai2apps.imagine-studio'}
    mounted = SimpleNamespace(mount={'context': {'studioInstanceId': 'studio'}}, declaration={'id': 'ai2apps.imagine.frozen-time'})
    monkeypatch.setattr(api, 'StudioCapabilityBroker', lambda _: SimpleNamespace(mounted_mini_app=lambda *a, **k: mounted))
    monkeypatch.setattr(api, 'authorize_app_instance', lambda *a: None)
    response = client.get('/v1/platform/studios/ai2apps.imagine-studio/mini-app-mounts/mnt_test/draft')
    assert response.status_code == 200, response.text
    assert response.json() == {'value': None}


def test_member_is_not_promoted_to_owner():
    actor=replace(RequestPrincipal.legacy_local(),role=MemberRole.MEMBER,authentication_type='owner_home_lease')
    service=SimpleNamespace(principal=lambda _:actor)
    with patch.object(owner,'authority',lambda request:(service,None)):
        with TestClient(studio.create_app(lambda:None)) as client:
            assert client.get('/v1/models').status_code==403

@pytest.mark.parametrize('key', sorted(studio.STUDIO_APPS))
def test_real_mobile_templates_and_static_dependencies(env,key):
    import re
    from omlx.admin import routes
    client,*_=env
    response=client.get('/mobile/app-content/'+key)
    assert response.status_code==200
    assert ('data-mobile-open-app' if key=='ai2apps.ai-browser' else 'studio_mobile.js') in response.text
    assert '/admin/static/' not in response.text
    assert '/mobile/static/js/app_chat.js' not in response.text
    assert '/mobile/static/js/studio_app_chat.js' not in response.text
    for asset in re.findall(r'(?:src|href)="/mobile/static/([^"?]+)',response.text):
        assert asset in routes.MOBILE_STATIC_FILES, asset
    assert 'frame-ancestors' in response.headers['content-security-policy']


def test_gallery_owner_isolation_and_range(tmp_path):
    from io import BytesIO
    from ai2apps.storage import PlatformDatabase
    from ai2apps.gallery import GalleryRepository
    db=PlatformDatabase(tmp_path/'db.sqlite');db.initialize()
    gallery=GalleryRepository(db,tmp_path/'gallery')
    mine,_=gallery.import_stream('alice',BytesIO(b'12345678'),name='clip.mp4',media_type='video/mp4')
    other,_=gallery.import_stream('bob',BytesIO(b'private'),name='secret.png',media_type='image/png')
    html,_=gallery.import_stream('alice',BytesIO(b'<script>alert(1)</script>'),name='example.html',media_type='text/html')
    runtime=SimpleNamespace(database=db,events=None,config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    actor=replace(RequestPrincipal.legacy_local(),actor_user_id='alice',authentication_type='owner_home_lease')
    with patch.object(owner,'authority',lambda request:(SimpleNamespace(principal=lambda _:actor),None)):
        with TestClient(studio.create_app(lambda:runtime)) as client:
            prefix='/v1/platform/gallery/assets/'
            assert client.get(prefix+other['id']).status_code==404
            response=client.get(prefix+mine['id']+'/content',headers={'Range':'bytes=2-4'})
            assert response.status_code==206
            assert response.content==b'345'
            assert response.headers['cache-control']=='no-store'
            response=client.get(prefix+html['id']+'/content')
            assert response.headers['content-disposition']=='attachment'
            assert 'sandbox' in response.headers['content-security-policy']

@pytest.mark.parametrize('path,payload',[
    ('/v1/platform/video-studio/composer/sources',{'sourcePath':'/private/file.mp4'}),
    ('/v1/platform/video-studio/runs/run/extract-audio',{'source_path':'/private/file.mp4'}),
    ('/v1/platform/imagine-studio/batch-output/chunks',{'target':{'kind':'local'}}),
    ('/v1/platform/imagine-studio/batch-output/chunks',{'target':{'outputRoot':'/private'}}),
])
def test_native_filesystem_paths_never_exported(path,payload):
    actor=replace(RequestPrincipal.legacy_local(),authentication_type='owner_home_lease')
    with patch.object(owner,'authority',lambda request:(SimpleNamespace(principal=lambda _:actor),None)):
        with TestClient(studio.create_app(lambda:None)) as client:
            assert client.post(path,json=payload).status_code==403


def test_image_and_audio_invocation_keep_owner_identity(monkeypatch, tmp_path):
    from unittest.mock import AsyncMock
    from starlette.responses import JSONResponse
    import ai2apps.model_providers as providers
    import ai2apps.audio_codecs as codecs
    actor=replace(RequestPrincipal.legacy_local(),actor_user_id='alice',authentication_type='owner_home_lease')
    invocations=SimpleNamespace(invoke_foreground_json=AsyncMock(return_value=JSONResponse({'image':{}})),
        invoke_foreground_multipart=AsyncMock(return_value=JSONResponse({'text':'test'})))
    from ai2apps.storage import PlatformDatabase
    db=PlatformDatabase(tmp_path/'invoke.sqlite');db.initialize()
    runtime=SimpleNamespace(model_invocations=invocations,database=db)
    monkeypatch.setattr(providers,'resolve_package_model',lambda runtime, model:SimpleNamespace(id=model,model_type='audio_stt' if model=='speech' else 'image_generation'))
    monkeypatch.setattr(codecs,'decode_audio_to_wav',lambda *args,**kwargs:b'wav')
    with patch.object(owner,'authority',lambda request:(SimpleNamespace(principal=lambda _:actor),None)):
        with TestClient(studio.create_app(lambda:runtime)) as client:
            assert client.post('/v1/images/generations',json={'model':'image','prompt':'test'}).status_code==200
            assert invocations.invoke_foreground_json.call_args.kwargs['context'].actor_user_id=='alice'
            assert client.post('/v1/audio/transcriptions',data={'model':'speech'},files={'file':('test.wav',b'wav','audio/wav')}).status_code==200
            context=invocations.invoke_foreground_multipart.call_args.kwargs['context']
            assert context.actor_user_id=='alice' and context.authentication_type=='owner_home_lease'


def test_capability_install_is_not_exposed():
    assert studio.allowed('POST','/v1/platform/capabilities/probe')
    assert not studio.allowed('POST','/v1/platform/capabilities/ensure')
    assert not studio.allowed('POST','/v1/platform/provisioning/sessions/x/confirm')


def test_gallery_mini_mobile_uses_mobile_bootstrap(env):
    import re
    from omlx.admin import routes
    client, *_ = env
    response = client.get('/mobile/app-content/ai2apps.gallery?surface=mini')
    assert response.status_code == 200
    assert '/admin/static/' not in response.text
    assert 'mobile_app.js' in response.text
    assert 'js/alpine.min.js' in response.text
    assert 'js/gallery.js' in response.text
    assert 'data-gallery-surface="mini-entry"' in response.text
    for asset in re.findall(r'(?:src|href)="/mobile/static/([^"?]+)', response.text):
        assert asset in routes.MOBILE_STATIC_FILES, asset


def test_disabled_studio_rejects_direct_api(env):
    from ai2apps.remote.mobile_apps import MobileAppPolicy
    from omlx.admin import routes
    client,_,_,_,actor=env
    policy=MobileAppPolicy(routes._get_platform_runtime().database)
    policy.set_enabled(actor.installation_id,'ai2apps.imagine-studio',False)
    assert client.get('/v1/platform/imagine-studio/mini-apps').status_code==403


def test_nested_router_exports_only_exact_methods_and_paths():
    from fastapi import APIRouter, FastAPI, Depends
    calls = []
    def guard():
        calls.append('guard')
    child = APIRouter(dependencies=[Depends(guard)])
    child.add_api_route('/ok', lambda: {'ok': True}, methods=['GET', 'POST'])
    child.add_api_route('/private', lambda: {'secret': True}, methods=['GET'])
    middle = APIRouter()
    middle.include_router(child, prefix='/inner')
    root = APIRouter()
    root.include_router(middle, prefix='/outer')
    studio.restrict_router(root, {('GET', '/v1/platform/outer/inner/ok')})
    app = FastAPI()
    app.include_router(root, prefix='/v1/platform')
    with TestClient(app) as client:
        assert client.get('/v1/platform/outer/inner/ok').json() == {'ok': True}
        assert calls == ['guard']
        assert client.post('/v1/platform/outer/inner/ok').status_code == 405
        assert client.get('/v1/platform/outer/inner/private').status_code == 404

def test_ai_browser_mobile_gateway_entry_assets_and_authoring_boundary(env,monkeypatch):
    from ai2apps.apps.system import SYSTEM_APP_MANIFESTS
    from ai2apps.web import mobile_app_gateway as host
    client,record,shell,_,actor=env
    spec=next(m for m in SYSTEM_APP_MANIFESTS if m['id']=='ai2apps.ai-browser')['mobile']['gateway']
    shell.mount_entry.return_value={'id':'mount','app_key':'ai2apps.ai-browser','app_instance_id':'instance','renderer':'host','placement':'mobile','source':'builtin'}
    monkeypatch.setattr(host,'descriptor',lambda manager,mount:spec)
    response=client.get('/mobile/app-resource/mount/instance/entry')
    assert response.status_code==200,response.text[:300]
    assert 'aib-mobile' in response.text and 'mobile-app-gateway' in response.text
    for asset in spec['assets']:
        assert client.get('/mobile/app-resource/mount/instance/assets/'+asset).status_code==200,asset
    assert client.get('/mobile/app-resource/mount/instance/assets/js/agent_mini.js').status_code==404
    for path in ['/v1/platform/agent-drafts','/v1/platform/client/browser-bidi-ticket','/v1/platform/client/browser-profiles/default/launch']:
        result=client.post('/v1/mobile/app-mounts/mount/bridge',json={'method':'request','verb':'POST','path':path,'body':''})
        assert result.status_code==200
        assert result.json()['status'] in (404,405)
    assert not studio.allowed('POST','/v1/platform/browser-workspace/tasks')
    assert not studio.allowed('POST','/v1/platform/client/browser-bidi-ticket')
    assert studio.allowed('GET','/v1/platform/studios/ai2apps.ai-browser/mini-apps')
    assert studio.allowed('POST','/v1/platform/studios/ai2apps.ai-browser/mini-app-mounts/mount/web-agent/tasks')
    profiles=client.post('/v1/mobile/app-mounts/mount/bridge',json={'method':'request','verb':'GET','path':'/v1/platform/client/browser-profiles','body':''})
    assert profiles.status_code==200 and profiles.json()['status']==200
    from ai2apps.api.ai_browser_mobile import create_ai_browser_mobile_router
    from fastapi import FastAPI
    app=FastAPI()
    app.include_router(create_ai_browser_mobile_router(lambda: None,lambda: actor),prefix='/v1/platform')
    assert 'get' in app.openapi()['paths']['/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/capabilities']


@pytest.mark.parametrize('method,path', [
    ('POST','/v1/platform/studio-jobs'), ('GET','/v1/platform/studio-jobs'),
    ('GET','/v1/platform/studio-jobs/by-run/run'), ('GET','/v1/platform/studio-jobs/job'),
    ('POST','/v1/platform/studio-jobs/job/retry'), ('POST','/v1/platform/studio-jobs/job/cancel'),
])
def test_background_job_exact_mobile_exports_still_require_owner(method,path):
    assert studio.allowed(method,path)
    with TestClient(studio.create_app(lambda:None)) as client:
        assert client.request(method,path).status_code == 401
    assert not studio.allowed('DELETE','/v1/platform/studio-jobs/job')
    assert not studio.allowed('POST','/v1/platform/studio-jobs/job/publish')


def test_notification_routes_are_explicit_owner_exports():
    for path in ['/v1/platform/notifications/resolve-target',
                 '/v1/platform/studios/ai2apps.ai-browser/mini-app-mounts/mount/notifications']:
        assert studio.allowed('POST',path)
        assert owner.public_allowed('POST',path)
        with TestClient(studio.create_app(lambda:None)) as client:
            assert client.post(path,json={'target':{'app_id':'ai2apps.intelligence'}}).status_code==401
    assert not studio.allowed('POST','/v1/platform/notifications/send')
    assert not studio.allowed('POST','/v1/platform/studios/unknown.app/mini-app-mounts/mount/notifications')
