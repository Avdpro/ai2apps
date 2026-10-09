from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ai2apps.storage import PlatformDatabase
from ai2apps.identity import RequestPrincipal
from ai2apps.knowledge import KnowledgeStore, KnowledgeScope
from ai2apps.gallery import GalleryRepository
from ai2apps.web.mobile_library import create_mobile_library_router
from ai2apps.web.owner_home_gateway import public_allowed

@pytest.fixture
def env(tmp_path):
    db=PlatformDatabase(tmp_path/'platform.sqlite3');db.initialize()
    knowledge=KnowledgeStore(db,blob_root=tmp_path/'knowledge');knowledge.initialize()
    gallery=GalleryRepository(db,tmp_path/'gallery')
    p=replace(RequestPrincipal.legacy_local(),actor_user_id='alice',authentication_type='owner_home_lease')
    runtime=SimpleNamespace(database=db,knowledge=knowledge,config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    app=FastAPI();app.include_router(create_mobile_library_router(lambda:runtime,lambda:p,lambda *args:'Library'))
    with TestClient(app) as client:yield client,knowledge,gallery,p

def test_knowledge_search_read_collect_and_private_isolation(env):
    c,k,g,p=env;bob=replace(p,actor_user_id='bob')
    mine=k.create_text_item(p,title='Mobile note',text='Watermelon discovery')
    chinese=k.create_text_item(p,title='手机知识库验收',text='中文短词检索')
    assert c.get('/v1/mobile/knowledge/items?q=手机').json()['items'][0]['id']==chinese.id
    secret=k.create_text_item(bob,title='Private',text='Watermelon secret')
    shared=k.create_text_item(bob,title='Shared',text='Watermelon shared',scope=KnowledgeScope.INSTALLATION)
    result=c.get('/v1/mobile/knowledge/items?q=Watermelon').json()['items']
    assert {i['id'] for i in result}=={mine.id,shared.id}
    assert c.get('/v1/mobile/knowledge/items/'+mine.id).json()['text']=='Watermelon discovery'
    assert c.get('/v1/mobile/knowledge/items/'+secret.id).status_code in (403,404)
    assert c.post('/v1/mobile/knowledge/items/'+secret.id+'/collect').status_code in (403,404)
    r=c.post('/v1/mobile/knowledge/items/'+mine.id+'/collect');assert r.status_code==200
    bucket=r.json()['bucket_id']
    assert c.post('/v1/mobile/knowledge/items/'+mine.id+'/collect').json()['bucket_id']==bucket
    assert c.get('/v1/mobile/knowledge/items',params={'bucket_id':bucket}).json()['items'][0]['id']==mine.id
    assert all(b.owner_user_id==p.actor_user_id for b in k.list_buckets(p) if b.id==bucket)

def test_gallery_read_range_download_and_isolation(env):
    c,k,g,p=env
    mine,_=g.import_stream('alice',BytesIO(b'0123456789'),name='sample.mp4',media_type='video/mp4')
    other,_=g.import_stream('bob',BytesIO(b'private'),name='private.png',media_type='image/png')
    unsafe,_=g.import_stream('alice',BytesIO(b'<svg/>'),name='unsafe.svg',media_type='image/svg+xml')
    items=c.get('/v1/mobile/gallery/assets').json()['items']
    assert [i['id'] for i in items]==[mine['id']]
    assert 'storage_key' not in items[0]
    url='/v1/mobile/gallery/assets/'+mine['id']+'/content'
    r=c.get(url,headers={'Range':'bytes=2-5'});assert r.status_code==206 and r.content==b'2345'
    assert r.headers['cache-control']=='no-store'
    assert 'attachment' in c.get(url+'?download=true').headers['content-disposition']
    for a in (other,unsafe):assert c.get('/v1/mobile/gallery/assets/'+a['id']+'/content').status_code==404
    assert c.get('/v1/mobile/gallery/assets?kind=file').status_code==422

@pytest.mark.parametrize('method,path',[('POST','/v1/mobile/gallery/assets/import'),('DELETE','/v1/mobile/gallery/assets/x'),('GET','/v1/mobile/knowledge/items/x/source'),('GET','/v1/mobile/knowledge/items/x/content'),('POST','/v1/mobile/knowledge/ask'),('POST','/v1/mobile/gallery/assets/x/resource-handles'),('GET','/v1/platform/knowledge/items')])
def test_unopened_routes_denied(method,path):assert not public_allowed(method,path)

@pytest.mark.parametrize('method,path',[('GET','/mobile/knowledge'),('GET','/mobile/gallery'),('GET','/v1/mobile/knowledge/items'),('POST','/v1/mobile/knowledge/items/kno_1/collect'),('GET','/v1/mobile/gallery/assets/asset_1/content')])
def test_intended_routes_allowed(method,path):assert public_allowed(method,path)
