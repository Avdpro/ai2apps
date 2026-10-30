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

@pytest.mark.parametrize('method,path',[('POST','/v1/mobile/gallery/assets/import'),('DELETE','/v1/mobile/gallery/assets/x'),('GET','/v1/mobile/knowledge/items/x/source'),('GET','/v1/mobile/knowledge/items/x/content'),('POST','/v1/mobile/gallery/assets/x/resource-handles'),('GET','/v1/platform/knowledge/items')])
def test_unopened_routes_denied(method,path):assert not public_allowed(method,path)

@pytest.mark.parametrize('method,path',[('GET','/mobile/knowledge'),('GET','/mobile/gallery'),('GET','/v1/mobile/knowledge/items'),('POST','/v1/mobile/knowledge/items/kno_1/collect'),('GET','/v1/mobile/gallery/assets/asset_1/content')])
def test_intended_routes_allowed(method,path):assert public_allowed(method,path)

@pytest.mark.parametrize('path',['notes','web','files','ask'])
def test_new_capture_and_ask_routes_are_explicitly_exposed(path):
 assert public_allowed('POST','/v1/mobile/knowledge/'+path)
 assert not public_allowed('DELETE','/v1/mobile/knowledge/'+path)
 assert not public_allowed('POST','/v1/mobile/knowledge/anything-else')

def test_mobile_note_reuses_owner_store_and_auto_target(env):
 c,k,g,p=env
 r=c.post('/v1/mobile/knowledge/notes',json={'title':'Phone note','text':'Camera research','bucket_id':'auto'})
 assert r.status_code==201,r.text
 item=r.json();assert k.get_item(p,item['id']).text=='Camera research'
 with k.transaction() as conn:assert conn.execute('SELECT status FROM knowledge_bucket_routing WHERE item_id=?',(item['id'],)).fetchone()[0]=='pending'
 assert c.post('/v1/mobile/knowledge/notes',json={'title':'Forged','text':'content','scope':'installation'}).status_code==422

def test_mobile_web_uses_existing_ssrf_safe_static_import(env,monkeypatch):
 c,k,g,p=env
 import ai2apps.api.knowledge as api
 monkeypatch.setattr(api,'_fetch_webpage',lambda url:(url,'Web fixture','Readable webpage fixture'))
 r=c.post('/v1/mobile/knowledge/web',json={'url':'https://example.com/article','bucket_id':'auto'})
 assert r.status_code==201,r.text
 assert 'Readable webpage fixture' in str(r.json())
 assert c.post('/v1/mobile/knowledge/web',json={'url':'https://example.com','fetch_mode':'acefox'}).status_code==422

def test_mobile_ask_all_single_and_no_evidence(env,monkeypatch):
 c,k,g,p=env
 import ai2apps.knowledge.mobile_ask as module
 seen=[]
 async def fake(runtime,principal,question,bucket_id):
  seen.append((principal.actor_user_id,question,bucket_id));return {'answer':'Fixture answer','citations':[]}
 monkeypatch.setattr(module,'answer_mobile',fake)
 assert c.post('/v1/mobile/knowledge/ask',json={'question':'Watch'}).status_code==200
 assert c.post('/v1/mobile/knowledge/ask',json={'question':'Watch','bucket_id':'one'}).status_code==200
 assert seen==[('alice','Watch',None),('alice','Watch','one')]
 assert c.post('/v1/mobile/knowledge/ask',json={'question':'   '}).status_code==422
 assert c.post('/v1/mobile/knowledge/ask',json={'question':'Watch','model':'forged'}).status_code==422

@pytest.mark.asyncio
async def test_grounded_mobile_answer_scopes_and_canonical_sources(env):
 from ai2apps.knowledge.mobile_ask import answer_mobile
 from ai2apps.knowledge import KnowledgeScope
 c,k,g,p=env
 mine=k.create_text_item(p,title='Watch report',text='Watermelon research evidence')
 bob=replace(p,actor_user_id='bob');k.create_text_item(bob,title='Secret',text='Watermelon secret')
 bucket=k.create_bucket(p,name='Empty')
 calls=[]
 async def invoke(payload,*,context):
  calls.append(payload)
  return {'choices':[{'finish_reason':'stop','message':{'content':'Research answer [K1]'}}]}
 runtime=SimpleNamespace(knowledge=k,model_manager=SimpleNamespace(resolve_default_model=lambda purpose:'system-model'),model_invocations=SimpleNamespace(invoke_chat_json=invoke))
 result=await answer_mobile(runtime,p,'Watermelon')
 assert result['citations'][0]['item_id']==mine.id
 assert 'Watermelon secret' not in str(calls)
 empty=await answer_mobile(runtime,p,'Watermelon',bucket.id)
 assert not empty['citations'] and len(calls)==1
 with pytest.raises(ValueError):await answer_mobile(runtime,p,'Watermelon','forged')

def test_mobile_capture_rejects_cross_origin(env):
 c,k,g,p=env
 r=c.post('/v1/mobile/knowledge/notes',headers={'Origin':'https://attacker.invalid'},json={'title':'Note','text':'Content'})
 assert r.status_code==403

def test_mobile_file_upload_uses_durable_import_pipeline(env,monkeypatch):
 c,k,g,p=env
 jobs=[]
 monkeypatch.setattr(k,'process_import_job',lambda job_id:jobs.append(job_id))
 r=c.post('/v1/mobile/knowledge/files',data={'bucketId':'auto','sourceAppId':'ai2apps.knowledge'},files=[('files',('notes.md',b'Watch text fixture','text/markdown'))])
 assert r.status_code==202,r.text
 assert r.json()['accepted'] and jobs==[r.json()['job']['id']]
 with k.transaction() as conn:
  row=conn.execute('SELECT auto_bucket FROM knowledge_import_jobs WHERE id=?',(jobs[0],)).fetchone()
  assert row['auto_bucket']==1

@pytest.mark.parametrize('url',['http://127.0.0.1/private','http://169.254.169.254/metadata'])
def test_mobile_web_preserves_ssrf_boundary(env,url):
 c,k,g,p=env
 r=c.post('/v1/mobile/knowledge/web',json={'url':url})
 assert r.status_code==422

def test_mobile_grouped_upload_one_record_and_attachment_isolation(env):
 c,k,g,p=env
 r=c.post('/v1/mobile/knowledge/files',data={'bucketId':'auto','mergeRecord':'true','recordTitle':'购物单'},files=[('files',('one.txt',b'Apples 12','text/plain')),('files',('two.txt',b'Bread 8','text/plain'))])
 assert r.status_code==202,r.text
 parent=r.json()['job']['group_parent_id'];assert parent
 assert [i.id for i in k.list_items(p)]==[parent]
 files=c.get('/v1/mobile/knowledge/items/'+parent+'/attachments').json()['items'];assert len(files)==2
 path='/v1/mobile/knowledge/items/'+parent+'/attachments/'+files[0]['item_id']
 assert public_allowed('GET',path)
 assert c.get(path).content==b'Apples 12'
 other=k.create_text_item(p,title='Other',text='Different')
 assert c.get('/v1/mobile/knowledge/items/'+other.id+'/attachments/'+files[0]['item_id']).status_code==404

def test_group_original_zip_and_html_are_owner_guarded(env):
 import io,zipfile
 from ai2apps.knowledge.groups import group_content
 c,k,g,p=env
 job=k.create_import_job(p,bucket_id='auto',filenames=['one.txt'],merge_record=True,record_title='<script>unsafe</script>')
 k.stage_import_entry(p,job['id'],0,BytesIO(b'Original text'),media_type='text/plain');k.process_import_job(job['id'])
 parent=k.get_import_job(p,job['id'])['group_parent_id']
 html=group_content(k,p,parent).body.decode();assert '&lt;script&gt;' in html and '<script>' not in html
 with pytest.raises(Exception):group_content(k,replace(p,actor_user_id='bob'),parent)


def test_public_tls_origin_uses_verified_owner_gateway(env,monkeypatch):
    from ai2apps.web import owner_home_gateway
    c,k,g,p=env
    url='/v1/mobile/knowledge/files'
    # Untrusted Origin is still rejected, even with an owner-labelled principal.
    response=c.post(url,headers={'Origin':'https://phone.example'},data={'bucketId':'auto'},files=[('files',('a.txt',b'public upload','text/plain'))])
    assert response.status_code==403
    # Production authority() revalidates the scope marker against the configured
    # owner service and live lease; fixture stands in for that trusted ingress.
    monkeypatch.setattr(owner_home_gateway,'authority',lambda request:(object(),object()))
    response=c.post(url,headers={'Origin':'https://phone.example'},data={'bucketId':'auto','mergeRecord':'true'},files=[('files',('a.txt',b'public upload','text/plain')),('files',('b.txt',b'second page','text/plain'))])
    assert response.status_code==202,response.text
    assert response.json()['job']['group_parent_id']

@pytest.mark.asyncio
async def test_mobile_natural_question_expands_to_bilingual_terms(env):
 from ai2apps.knowledge.mobile_ask import answer_mobile
 c,k,g,p=env
 item=k.create_text_item(p,title='Order screenshot',text='Amazon order recipient: Test Person; Tax: 12.34')
 other=replace(p,actor_user_id='bob');k.create_text_item(other,title='Private order',text='Amazon secret recipient')
 calls=[]
 async def invoke(payload,*,context):
  calls.append(payload)
  value='{"queries":["Amazon","recipient","收件人"]}' if len(calls)==1 else 'Test Person [K1]'
  return {'choices':[{'finish_reason':'stop','message':{'content':value}}]}
 runtime=SimpleNamespace(knowledge=k,model_manager=SimpleNamespace(resolve_default_model=lambda purpose:'system-model'),model_invocations=SimpleNamespace(invoke_chat_json=invoke))
 result=await answer_mobile(runtime,p,'上次我亚马逊订单的收件人是谁')
 assert len(calls)==2
 assert result['citations'][0]['item_id']==item.id
 assert 'secret recipient' not in str(calls)
