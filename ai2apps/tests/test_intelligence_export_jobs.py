import asyncio
import uuid
import pytest
from ai2apps.tests.test_intelligence_api import client
from ai2apps.identity import RequestPrincipal
from ai2apps.intelligence.models import ChannelInput
from ai2apps.intelligence.export_jobs import file_path
from ai2apps.tests.test_intelligence_html_export import png


def create(client,format='html',**kwargs):
    runtime=client.app.state.runtime;owner=RequestPrincipal.legacy_local().actor_user_id
    c=runtime.intelligence_collector.store.save_channel(owner,ChannelInput(name='Export',interests='Reports').model_dump())
    article={'title':'Title','summary':'Summary','body':'Paragraph [1]','sources':[{'url':'https://example.org/source','title':'Source'}],'images':[{'url':'https://example.org/image.png'}]}
    runtime.intelligence_collector.store.import_article(owner,c['id'],article,'https://example.org/source')
    payload={'channel_id':c['id'],'format':format,'request_id':uuid.uuid4().hex,**kwargs}
    r=client.post('/intelligence/exports',json=payload)
    assert r.status_code==200,r.text
    return runtime,owner,payload,r.json()['id']


@pytest.mark.asyncio
async def test_html_job_download_and_request_identity(client,monkeypatch):
    from ai2apps.intelligence import html_export
    monkeypatch.setattr(html_export,'image_bytes',lambda *args:(png(),'image/png'))
    runtime,owner,payload,id=create(client,include_toc=False)
    assert client.get('/intelligence/exports/'+id+'/file').status_code==409
    assert client.post('/intelligence/exports',json=payload).json()['id']==id
    assert client.post('/intelligence/exports',json={**payload,'quality':'original'}).status_code==409
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    status=client.get('/intelligence/exports/'+id).json()
    assert status['status']=='completed',status
    assert status['result']['images']==1
    file=client.get('/intelligence/exports/'+id+'/file')
    assert file.status_code==200 and 'src="data:image/png;base64,' in file.text
    assert '<nav>' not in file.text and '<details class="article-card ' in file.text
    assert status['result']['include_toc'] is False
    assert 'attachment' in file.headers['content-disposition']
    assert client.get('/intelligence/exports/stask_'+'0'*32).status_code==404
    assert client.post('/intelligence/exports',json=payload).json()['id']==id
    assert file_path(runtime.intelligence_collector.store,owner,id,'html').exists()


@pytest.mark.asyncio
async def test_cancel_queued_export_and_zip_job(client):
    runtime,owner,payload,id=create(client,'zip')
    r=client.post('/intelligence/exports/'+id+'/cancel');assert r.status_code==200
    await runtime.system_tasks.tick()
    assert client.get('/intelligence/exports/'+id).json()['status']=='cancelled'
    assert client.get('/intelligence/exports/'+id+'/file').status_code==409
    runtime,owner,payload,id=create(client,'zip')
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    assert client.get('/intelligence/exports/'+id+'/file').content[:2]==b'PK'


def test_export_payload_validation(client):
    assert client.post('/intelligence/exports',json={'format':'html','request_id':'x'*16}).status_code==422
    assert client.post('/intelligence/exports',json={'format':'zip','request_id':'x'*16,'since':'2026-11-01'}).status_code==422
    assert client.post('/intelligence/exports',json={'format':'zip','request_id':'x'*16,'arbitrary_url':'https://example.org'}).status_code==422


@pytest.mark.asyncio
async def test_cancel_running_export_never_publishes_file(client,monkeypatch):
    import threading
    from ai2apps.intelligence import html_export
    started=threading.Event();release=threading.Event()
    def loader(*args):
        started.set();release.wait(3);return png(),'image/png'
    monkeypatch.setattr(html_export,'image_bytes',loader)
    runtime,owner,payload,id=create(client)
    await runtime.system_tasks.tick()
    while not started.is_set():await asyncio.sleep(.01)
    assert client.get('/intelligence/exports').json()['items'][0]['id']==id
    assert client.post('/intelligence/exports/'+id+'/cancel').status_code==200
    await runtime.system_tasks.tick();release.set()
    assert client.get('/intelligence/exports/'+id).json()['status']=='cancelled'
    assert not file_path(runtime.intelligence_collector.store,owner,id,'html').exists()
    assert client.get('/intelligence/exports/'+id+'/file').status_code==409


@pytest.mark.asyncio
async def test_mobile_gateway_creates_and_downloads_export(client,monkeypatch):
    import json,base64
    from ai2apps.web import mobile_app_gateway as gateway
    from ai2apps.intelligence import html_export
    monkeypatch.setattr(html_export,'image_bytes',lambda *args:(png(),'image/png'))
    runtime,owner,payload,unused=create(client)
    spec={'api':{'module':'intelligence','factory':'create_intelligence_router','prefix':'/v1/platform/intelligence'}}
    principal=RequestPrincipal.legacy_local()
    payload['request_id']=uuid.uuid4().hex
    result=await gateway.api_response(runtime,principal,spec,{'method':'request','verb':'POST','path':'/v1/platform/intelligence/exports','headers':{'content-type':'application/json'},'body':base64.b64encode(json.dumps(payload).encode()).decode()})
    assert result.status_code==200,result.text
    id=result.json()['id']
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    response=await gateway.api_resource(runtime,principal,spec,'api/exports/'+id+'/file','')
    assert response.status_code==200
    assert response.headers['content-type'].startswith('text/html')
    assert response.headers['content-disposition'].startswith('attachment;')
    assert b'data:image/png;base64,' in response.body
    gateway._APPS.clear()


def test_retired_export_format_rejected(client):
    from ai2apps.intelligence.export_jobs import ExportRequest
    with pytest.raises(ValueError):
        ExportRequest(format='data_html',channel_id='c',request_id='x'*16)
    assert client.post('/intelligence/exports',json={'format':'data_html','channel_id':'c','request_id':'x'*16}).status_code==422
    assert client.get('/intelligence/exports/missing/data-url').status_code==404


@pytest.mark.asyncio
async def test_legacy_export_download_gone(client):
    runtime,owner,payload,id=create(client,'zip')
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    import json
    with runtime.database.transaction() as db:
        db.execute("UPDATE system_tasks SET result_json=? WHERE id=?",(json.dumps({'format':'data_html'}),id))
    assert client.get('/intelligence/exports/'+id+'/file').status_code==410


@pytest.mark.asyncio
async def test_export_uses_verified_browser_owner_name(client,monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import httpx
    from ai2apps.intelligence import html_export
    runtime=client.app.state.runtime;owner=RequestPrincipal.legacy_local().actor_user_id
    cloud=SimpleNamespace(request=AsyncMock(return_value=httpx.Response(200,json={'user':{'id':owner,'displayName':'Current User'}})))
    monkeypatch.setattr(runtime,'cloud_browser_session_from_cookies',lambda cookies:'browser',raising=False)
    monkeypatch.setattr(runtime,'cloud_for_browser',lambda key:cloud,raising=False)
    monkeypatch.setattr(html_export,'image_bytes',lambda *args:(png(),'image/png'))
    runtime,owner,payload,id=create(client)
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    assert 'Current User' in client.get('/intelligence/exports/'+id+'/file').text
    assert client.post('/intelligence/exports',json=payload).json()['id']==id
    assert client.post('/intelligence/exports',json={**payload,'_author_name':'forged'}).status_code==422


@pytest.mark.asyncio
async def test_missing_images_only_in_owned_export_result(client,monkeypatch):
    from ai2apps.intelligence import html_export
    def unavailable(*args):raise ValueError('Web request failed with HTTP 404')
    monkeypatch.setattr(html_export,'image_bytes',unavailable)
    runtime,owner,payload,id=create(client)
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    result=client.get('/intelligence/exports/'+id).json()['result']
    assert result['images_failed']==1 and '404' in result['missing_images'][0]['reason']
    text=client.get('/intelligence/exports/'+id+'/file').text
    assert 'HTTP 404' not in text and 'Missing images' not in text and 'Image not embedded' not in text


def test_upload_social_cover_owner_and_options(client):
    from ai2apps.intelligence.html_export import image_bytes
    response=client.post('/intelligence/exports/cover',files={'file':('cover.png',png(),'image/png')})
    assert response.status_code==200,response.text
    url=response.json()['url'];assert url.endswith('/share-cover.jpg')
    runtime=client.app.state.runtime;owner=RequestPrincipal.legacy_local().actor_user_id
    data,mime=image_bytes(runtime.intelligence_collector.store,owner,url,'original');assert mime=='image/jpeg'
    with pytest.raises(OSError):image_bytes(runtime.intelligence_collector.store,'different-owner',url,'original')
    assert client.post('/intelligence/exports/cover',files={'file':('bad.png',b'not image','image/png')}).status_code==422
    assert client.post('/intelligence/exports',json={'channel_id':'x','format':'html','share_cover':'https://example.org/private','request_id':'x'*16}).status_code==422


@pytest.mark.asyncio
async def test_mobile_gateway_accepts_owner_cover_upload(client):
    import base64,httpx
    from dataclasses import replace
    from ai2apps.web import mobile_app_gateway as gateway
    runtime=client.app.state.runtime;principal=replace(RequestPrincipal.legacy_local(),client_scope='mobile')
    request=httpx.Request('POST','http://fixture/',files={'file':('cover.png',png(),'image/png')});content=request.read()
    spec={'api':{'module':'intelligence','factory':'create_intelligence_router','prefix':'/v1/platform/intelligence'}}
    response=await gateway.api_response(runtime,principal,spec,{'verb':'POST','path':'/v1/platform/intelligence/exports/cover','body':base64.b64encode(content).decode(),'headers':{'content-type':request.headers['content-type']}})
    assert response.status_code==200,response.text
    assert response.json()['url'].endswith('/share-cover.jpg')


@pytest.mark.asyncio
@pytest.mark.parametrize('format',['html','zip'])
async def test_export_gallery_copy_is_owned_deduplicated_and_survives_export_cleanup(client,monkeypatch,format):
    from ai2apps.intelligence import html_export
    from ai2apps.gallery import GalleryRepository
    monkeypatch.setattr(html_export,'image_bytes',lambda *args:(png(),'image/png'))
    runtime,owner,payload,id=create(client,format)
    url='/intelligence/exports/'+id+'/gallery'
    assert client.post(url).status_code==409
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    original=client.get('/intelligence/exports/'+id+'/file').content
    first=client.post(url);assert first.status_code==200,first.text
    value=first.json();assert value['created'] and value['asset']['source_app_id']=='ai2apps.intelligence'
    second=client.post(url).json();assert not second['created'] and second['asset']['id']==value['asset']['id']
    gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery',runtime.events)
    assert len(gallery.list_assets(owner))==1
    path=file_path(runtime.intelligence_collector.store,owner,id,format);path.unlink()
    assert client.post(url).status_code==409
    asset=gallery.get_asset(owner,value['asset']['id'])
    _,saved_path=gallery.asset_path(owner,asset['id']);assert saved_path.read_bytes()==original
    from dataclasses import replace
    from ai2apps.intelligence.export_jobs import save_export_to_gallery
    with pytest.raises(KeyError):save_export_to_gallery(runtime,replace(RequestPrincipal.legacy_local(),actor_user_id='other-owner'),id)
    assert asset['content_hash']=='sha256:'+__import__('hashlib').sha256(original).hexdigest()
    with pytest.raises(Exception):gallery.get_asset('other-owner',asset['id'])


@pytest.mark.asyncio
async def test_gallery_rejects_changed_export(client,monkeypatch):
    from ai2apps.intelligence import html_export
    monkeypatch.setattr(html_export,'image_bytes',lambda *args:(png(),'image/png'))
    runtime,owner,_,id=create(client)
    await runtime.system_tasks.tick();await asyncio.gather(*runtime.system_tasks.jobs.values())
    file_path(runtime.intelligence_collector.store,owner,id,'html').write_bytes(b'changed')
    assert client.post('/intelligence/exports/'+id+'/gallery').status_code==409
