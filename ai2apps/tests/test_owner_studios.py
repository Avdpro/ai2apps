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
    assert 'studio_mobile.js' in response.text
    assert '/admin/static/' not in response.text
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
