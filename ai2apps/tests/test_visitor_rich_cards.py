import io
from types import SimpleNamespace
import pytest
from PIL import Image
from ai2apps.remote.visitor_space import validate_document,build_snapshot,walk_cards
from ai2apps.remote.visitor_assets import VisitorAssets,LIMITS,HTML_CSP,published_asset_ids

def doc(cards): return {'title':'Space','cards':cards}
@pytest.fixture
def assets(tmp_path):return VisitorAssets(SimpleNamespace(path=tmp_path/'db.sqlite'),'owner')

def test_html_limit_and_scope(assets):
    data=b' '*LIMITS['html'];asset=assets.put('html',data)
    assert assets.get(asset['id'])[1].read_bytes()==data
    with pytest.raises(ValueError):assets.put('html',data+b'x')
    with pytest.raises(ValueError):VisitorAssets(SimpleNamespace(path=assets.root.parents[1]/'db.sqlite'),'other').get(asset['id'])
    with pytest.raises(ValueError):assets.get('../db.sqlite')
    assert 'allow-same-origin' not in HTML_CSP
    assert "connect-src 'none'" in HTML_CSP

def test_image_normalization_and_publish(assets):
    out=io.BytesIO();Image.new('RGB',(3000,100),'red').save(out,'JPEG')
    asset=assets.put('image',out.getvalue());assert asset['width']==2560 and asset['mime']=='image/png'
    snapshot=build_snapshot(doc([{'kind':'image','assetId':asset['id']},{'kind':'carousel','cards':[{'kind':'article','body':'# hello'},{'kind':'html','hidden':True}]}]),[],assets)
    assert published_asset_ids(snapshot)=={asset['id']}
    assert len(list(walk_cards(snapshot['cards'])))==3
    with pytest.raises(ValueError):build_snapshot(doc([{'kind':'html','assetId':asset['id']}]),[],assets)
    with pytest.raises(ValueError):build_snapshot(doc([{'kind':'image'}]),[],assets)

@pytest.mark.parametrize('card',[
    {'kind':'carousel','cards':[{'kind':'carousel','cards':[]}]},
    {'kind':'carousel','cards':[{'kind':'text'}]*9},
    {'kind':'carousel','autoplay':'true'}, {'kind':'carousel','interval':0},
    {'kind':'image','assetId':'../../secrets'}, {'kind':'html','height':99999},
    {'kind':'video','url':'https://private/file'}, {'kind':'article','body':'x'*(1024*1024+1)},
])
def test_limits(card):
    with pytest.raises(ValueError):validate_document(doc([card]))

def test_media_route_requires_lease_publication_revision_and_gate(assets,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.web.space_routes import create_space_router
    from ai2apps.remote.security import RemoteTokenError
    asset=assets.put('html',b'<h1>Hello</h1>')
    device=SimpleNamespace(public_origin='https://device.example')
    state={'revision':2,'published':doc([{'kind':'carousel','cards':[{'kind':'html','assetId':asset['id']}]}])}
    async def authorize(device,token,**kw):
        if token!='ok':raise RemoteTokenError('no')
    manager=SimpleNamespace(repository=SimpleNamespace(list=lambda:[device],database=SimpleNamespace(path=assets.root.parent.parent/'db.sqlite')),
        space=SimpleNamespace(visitor_sessions=SimpleNamespace(authorize=authorize),visitor_settings=lambda _:state,installation=lambda _:SimpleNamespace(id='owner')))
    app=FastAPI();app.include_router(create_space_router(lambda:manager));monkeypatch.setenv('AI2APPS_VISITOR_CONTENT_GATEWAY_READY','1')
    with TestClient(app,base_url=device.public_origin) as c:
        url='/mobile/space/media/2/'+asset['id'];headers={'Cookie':'__Secure-ai2apps_space=ok'}
        assert c.get(url).status_code==403
        response=c.get(url,headers=headers);assert response.status_code==200
        assert response.headers['content-security-policy']==HTML_CSP
        assert c.head(url,headers=headers).status_code==200
        assert c.get(url,headers={**headers,'Range':'bytes=0-2'}).status_code==206
        assert c.get(url.replace('/2/','/1/'),headers=headers).status_code==403
        state['published']=doc([]);assert c.get(url,headers=headers).status_code==403
        monkeypatch.setenv('AI2APPS_VISITOR_CONTENT_GATEWAY_READY','0');assert c.get(url,headers=headers).status_code==403

def test_owner_upload_draft_and_cloud_gate(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from unittest.mock import Mock,AsyncMock
    from ai2apps.storage import PlatformDatabase
    from ai2apps.api.remote import create_remote_router
    from ai2apps.identity import RequestPrincipal
    db=PlatformDatabase(tmp_path/'db.sqlite');db.initialize()
    runtime=SimpleNamespace(database=db,extension_manager=SimpleNamespace(list_apps=lambda **kw:[]),remote=SimpleNamespace(space=SimpleNamespace(revoke=Mock()),refresh_space_capability=AsyncMock()))
    app=FastAPI();app.include_router(create_remote_router(lambda:runtime,lambda:RequestPrincipal.legacy_local()))
    monkeypatch.setenv('AI2APPS_VISITOR_CONTENT_GATEWAY_READY','0')
    with TestClient(app) as c:
        r=c.post('/remote/visitor-space/assets/html',content=b'<h1>safe</h1>');assert r.status_code==200
        asset=r.json()['id'];assert c.get('/remote/visitor-space/assets/'+asset).status_code==200
        assert c.put('/remote/visitor-space/draft',json={'version':0,'draft':doc([{'kind':'html','assetId':asset}])}).status_code==200
        assert c.post('/remote/visitor-space/publish',json={'version':1}).status_code==409
        monkeypatch.setenv('AI2APPS_VISITOR_CONTENT_GATEWAY_READY','1')
        assert c.post('/remote/visitor-space/publish',json={'version':1}).status_code==200

def test_video_probe_accepts_real_mp4_and_rejects_nonvideo(assets,tmp_path):
    import shutil,subprocess
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg or not shutil.which('ffprobe'):pytest.skip('ffmpeg unavailable')
    path=tmp_path/'sample.mp4'
    subprocess.run([ffmpeg,'-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=0.2','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    meta=assets.put('video',path.read_bytes());assert meta['width']==64 and meta['mime']=='video/mp4'
    with pytest.raises(ValueError):assets.put('video',b'<html>not video</html>')


def test_html_autoload_cover_validation_and_publication(assets):
    html=assets.put('html',b'<html>Hi</html>')
    out=io.BytesIO();Image.new('RGB',(32,32),'blue').save(out,'PNG')
    image=assets.put('image',out.getvalue())
    card={'kind':'html','assetId':html['id'],'coverId':image['id'],'autoload':True}
    snapshot=build_snapshot(doc([card]),[],assets)
    assert snapshot['cards'][0]['autoload'] is True
    assert published_asset_ids(snapshot)=={html['id'],image['id']}
    assert validate_document(doc([{'kind':'html'}]))['cards'][0]['autoload'] is False
    with pytest.raises(ValueError):validate_document(doc([{**card,'autoload':'yes'}]))
    with pytest.raises(ValueError):build_snapshot(doc([{**card,'coverId':html['id']}]),[],assets)
