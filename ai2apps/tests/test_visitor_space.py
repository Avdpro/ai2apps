from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.remote.visitor_space import VisitorSpaceStore, validate_document, build_snapshot, resolve_resource

@pytest.fixture
def store(tmp_path):
    db=PlatformDatabase(tmp_path/'visitor.sqlite');db.initialize()
    return VisitorSpaceStore(db)

def document(title='Published'):
    return {'title':title,'description':'Hello','theme':'ocean','cards':[{'kind':'text','title':'Welcome','text':'Hi'}]}

def test_draft_publish_and_close_reopen_epoch(store):
    assert store.get('owner')['enabled'] is False
    a=store.update('owner',0,draft=document())
    assert a['published'] is None
    a=store.update('owner',a['version'],published=build_snapshot(a['draft'],[]))
    a=store.update('owner',a['version'],enabled=True)
    first_epoch=a['epoch']
    a=store.update('owner',a['version'],draft=document('Private draft'))
    assert a['published']['title']=='Published'
    assert store.get('other')['published'] is None
    a=store.update('owner',a['version'],enabled=False)
    a=store.update('owner',a['version'],enabled=True)
    assert a['epoch']>first_epoch
    assert a['revision']==1

def test_conflict_does_not_overwrite_and_enable_requires_publish(store):
    with pytest.raises(ValueError):store.update('owner',0,enabled=True)
    store.update('owner',0,draft=document())
    with pytest.raises(ValueError):store.update('owner',0,draft=document('stale'))
    assert store.get('owner')['draft']['title']=='Published'

@pytest.mark.parametrize('url',['javascript:alert(1)','http://example.com','https://name:secret@example.com','data:text/html,hi'])
def test_unsafe_links_rejected(url):
    d=document();d['cards']=[{'kind':'link','title':'Link','url':url}]
    with pytest.raises(ValueError):validate_document(d)

def test_app_requires_explicit_entry_and_cloud_readiness(monkeypatch):
    d=document();d['cards']=[{'kind':'app','appKey':'snake'}]
    app={'appKey':'snake','digest':'v1','entry':'ui/entry.html','root':'ui'}
    with pytest.raises(ValueError):build_snapshot(d,[])
    monkeypatch.delenv('AI2APPS_VISITOR_APP_GATEWAY_READY',raising=False)
    with pytest.raises(ValueError):build_snapshot(d,[app])
    monkeypatch.setenv('AI2APPS_VISITOR_APP_GATEWAY_READY','1')
    assert build_snapshot(d,[app])['cards'][0]['binding']['digest']=='v1'

def test_resource_is_published_indexed_and_digest_bound():
    card={'appKey':'snake','binding':{'digest':'v1','root':'ui','entry':'ui/entry.html'}}
    effective=SimpleNamespace(effective_digest='v1',resources={},upstream_digest='p')
    package=SimpleNamespace(file_index=[{'path':'ui/entry.html','sha256':'x'}],store_path='/safe')
    manager=SimpleNamespace(database=MagicMock(),repository=SimpleNamespace(effective=lambda *a:effective,package=lambda *a:package),_verified_stored_resource=Mock(return_value='verified'))
    assert resolve_resource(manager,card,'ui/entry.html')=='verified'
    for path in ['../secret','ui/../secret','/ui/entry.html','app.yaml','ui/missing','ui\\entry.html']:
        with pytest.raises(ValueError):resolve_resource(manager,card,path)
    effective.effective_digest='v2'
    with pytest.raises(ValueError):resolve_resource(manager,card,'ui/entry.html')
    assert manager._verified_stored_resource.call_count==1
    effective.effective_digest='v1'
    manager.database.transaction.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=None
    with pytest.raises(ValueError):resolve_resource(manager,card,'ui/entry.html')

@pytest.mark.parametrize('remote_actor',[False,True])
def test_owner_management_and_remote_denial(store,remote_actor):
    from dataclasses import replace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.remote import create_remote_router
    from ai2apps.identity import RequestPrincipal
    actor=RequestPrincipal.legacy_local()
    if remote_actor:actor=replace(actor,authentication_type='owner_home_lease')
    runtime=SimpleNamespace(database=store.database,extension_manager=SimpleNamespace(list_apps=lambda **kw:[]),
        remote=SimpleNamespace(space=SimpleNamespace(revoke=Mock()), refresh_space_capability=AsyncMock()))
    app=FastAPI();app.include_router(create_remote_router(lambda:runtime,lambda:actor))
    with TestClient(app) as c:
        if remote_actor:
            for method,path,body in [('GET','',None),('PUT','/draft',{'version':0,'draft':document()}),('POST','/publish',{'version':0}),('PUT','/enabled',{'version':0,'enabled':True})]:
                assert c.request(method,'/remote/visitor-space'+path,json=body).status_code==403
            return
        initial=c.get('/remote/visitor-space');assert initial.status_code==200
        assert initial.json()['enabled'] is False
        assert c.put('/remote/visitor-space/draft',json={'version':0,'draft':document()}).status_code==200
        assert c.post('/remote/visitor-space/publish',json={'version':1}).status_code==200
        assert c.put('/remote/visitor-space/enabled',json={'version':2,'enabled':True}).status_code==200
        assert runtime.remote.space.revoke.call_count == 2
        assert runtime.remote.refresh_space_capability.await_count == 2


def test_archive_rejects_privileged_or_unscoped_open_entry():
    from ai2apps.extensions.archive import InteractiveArchive
    from ai2apps.extensions.models import UnitKind, ExtensionError
    manifest={'schema':'ai2apps.app/v1','id':'example.game','version':'1.0.0','name':'Game',
              'publisher':{'id':'example'},'entry':{'kind':'sandbox','resource':'ui/index.html'},
              'instances':{'mode':'singleton','scope':'user'},'state':{'version':1,'defaults':{}}}
    for entry in [{'kind':'host','resource':'ui/index.html'}, {'kind':'sandbox','resource':'ui/index.html','capabilities':['files']}, {'kind':'sandbox','resource':'index.html'}]:
        with pytest.raises(ExtensionError):InteractiveArchive._validate_manifest(UnitKind.APP,{**manifest,'open_entry':entry},{'ui/index.html','index.html'})
    InteractiveArchive._validate_manifest(UnitKind.APP,{**manifest,'open_entry':{'kind':'sandbox','resource':'ui/index.html'}},{'ui/index.html'})


def test_real_visit_cookie_is_revoked_across_close_and_reopen(store):
    import hashlib,time
    from ai2apps.remote.space import PersonalSpace
    from ai2apps.remote.security import RemoteTokenError
    installation=SimpleNamespace(id='owner',status='active',cloud_device_id='device',access_epoch=1,core_user_id='u')
    device=SimpleNamespace(device_id='device',enabled=True,status='active',access_epoch=1)
    manager=SimpleNamespace(repository=SimpleNamespace(database=store.database),
        identity_repository=SimpleNamespace(get_installation=lambda:installation),
        frpc=SimpleNamespace(status=lambda:{'running':True,'deviceId':'device'}))
    space=PersonalSpace(manager)
    state=store.update('owner',0,published=build_snapshot(document(),[]))
    state=store.update('owner',state['version'],enabled=True)
    claims={'exp':int(time.time())+120,'device_id':'device','access_epoch':1,'owner_user_id':'u','_space_epoch':state['epoch'],'_published_revision':state['revision']}
    space.sessions[hashlib.sha256(b'visit').hexdigest()]=claims
    assert space.authorize(device,'visit') is claims
    state=store.update('owner',state['version'],enabled=False)
    with pytest.raises(RemoteTokenError):space.authorize(device,'visit')
    store.update('owner',state['version'],enabled=True)
    with pytest.raises(RemoteTokenError):space.authorize(device,'visit')


def test_public_bootstrap_excludes_draft_and_management_fields(store):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.web.space_routes import create_space_router
    state=store.update('owner',0,published=build_snapshot(document(),[]))
    state=store.update('owner',state['version'],draft=document('SECRET DRAFT'))
    device=SimpleNamespace(device_id='d',public_origin='https://device.example')
    service=SimpleNamespace(visitor_sessions=SimpleNamespace(authorize=AsyncMock(return_value={'access_mode':'visitor','exp':9999999999,'owner_user_id':'u'})),visitor_settings=lambda d:state)
    manager=SimpleNamespace(repository=SimpleNamespace(list=lambda:[device]),space=service)
    app=FastAPI();app.include_router(create_space_router(lambda:manager))
    with TestClient(app,base_url=device.public_origin) as c:
        response=c.get('/v1/mobile/space/bootstrap')
        assert response.status_code==200
        assert 'SECRET DRAFT' not in response.text
        assert 'epoch' not in response.text
        assert response.json()['space']['title']=='Published'


def test_hidden_cards_stay_in_draft_only():
    d=document();d['cards'].append({'kind':'app','title':'Unfinished','appKey':'private.app','hidden':True})
    assert len(validate_document(d)['cards'])==2
    assert len(build_snapshot(d,[])['cards'])==1


def test_visitor_resource_route_cookie_revision_and_csp(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.web.space_routes import create_space_router
    from ai2apps.remote.security import RemoteTokenError
    from ai2apps.web.public_boundary import PublicDeviceBoundary
    from unittest.mock import AsyncMock
    path=tmp_path/'index.html';path.write_text('<html>public game</html>')
    monkeypatch.setenv('AI2APPS_VISITOR_APP_GATEWAY_READY','1')
    monkeypatch.setattr('ai2apps.remote.visitor_space.resolve_resource',lambda *args:path)
    device=SimpleNamespace(device_id='device',public_origin='https://device.example')
    def authorize(device,token,**kwargs):
        if token!='visitor':raise RemoteTokenError('denied')
        return {'sub':'visitor'}
    state={'revision':1,'published':{'cards':[{'kind':'app','appKey':'snake','binding':{}}]}}
    manager=SimpleNamespace(repository=SimpleNamespace(list=lambda:[device]),
        authorize_session=AsyncMock(return_value=None),space=SimpleNamespace(visitor_sessions=SimpleNamespace(authorize=AsyncMock(side_effect=authorize)),visitor_settings=lambda d:state))
    # Non-None mock models an extension manager; no Owner principal is supplied.
    app=FastAPI();app.include_router(create_space_router(lambda:manager,extension_provider=lambda:object()))
    app.add_middleware(PublicDeviceBoundary,manager_provider=lambda:manager)
    with TestClient(app,base_url=device.public_origin) as c:
        url='/mobile/space/app/1/snake/ui/index.html'
        assert c.get(url).status_code==403
        response=c.get(url,headers={'Cookie':'__Secure-ai2apps_space=visitor'})
        assert response.status_code==200
        assert "sandbox allow-scripts;" in response.headers['content-security-policy']
        assert 'allow-same-origin' not in response.headers['content-security-policy']
        assert "connect-src 'none'" in response.headers['content-security-policy']
        assert response.headers['cache-control']=='no-store'
        assert c.get(url.replace('/app/1/','/app/2/'),headers={'Cookie':'__Secure-ai2apps_space=visitor'}).status_code==403
        monkeypatch.setenv('AI2APPS_VISITOR_APP_GATEWAY_READY','0')
        assert c.get(url,headers={'Cookie':'__Secure-ai2apps_space=visitor'}).status_code==403


def test_visitor_readiness_instance_config(tmp_path,monkeypatch):
    from ai2apps.remote.visitor_space import app_gateway_ready
    monkeypatch.delenv('AI2APPS_VISITOR_APP_GATEWAY_READY',raising=False)
    monkeypatch.setenv('AI2APPS_RUN_DESCRIPTOR_PATH',str(tmp_path/'run/local.json'))
    assert not app_gateway_ready()
    (tmp_path/'config').mkdir()
    config=tmp_path/'config/visitor-space-gateway.json'
    config.write_text('{"enabled":true,"protocol":"personal-space-anonymous-v1"}')
    assert app_gateway_ready()
    monkeypatch.setenv('AI2APPS_VISITOR_APP_GATEWAY_READY','0')
    assert not app_gateway_ready()
