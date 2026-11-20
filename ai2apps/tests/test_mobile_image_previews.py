"""Preview bytes save bandwidth without changing originals, scope or model inputs."""
import base64,hashlib,io,json
from copy import deepcopy
from dataclasses import replace
import httpx,pytest
from PIL import Image
from fastapi import FastAPI,HTTPException
from fastapi.encoders import jsonable_encoder
from ai2apps.api.chat import create_chat_router,ChatContentResponse
from ai2apps.api.messager_mobile import create_messager_mobile_router
from ai2apps.chat import ChatRepository,LegacyChatMessageInput
from ai2apps.core import MessageRole
from ai2apps.chat.mobile_images import project_response,prepare_request
from ai2apps.web.mobile_image_preview import preview_file,preview_bytes,MAX_EDGE,MAX_PREVIEW
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity
from test_bot_capability_discovery import setup
from test_messager_mobile import owner


def photo(size=(2400,1800)):
    out=io.BytesIO();image=Image.effect_noise(size,60).convert('RGB');image.save(out,'PNG');return out.getvalue()


@pytest.mark.asyncio
async def test_preview_size_orientation_metadata_and_original_integrity(tmp_path):
    source=photo();path=tmp_path/'photo.png';path.write_bytes(source);before=hashlib.sha256(source).hexdigest()
    small=await preview_file(path)
    assert small==await preview_file(path)
    with Image.open(io.BytesIO(small)) as image:
        assert image.format=='JPEG' and max(image.size)<=MAX_EDGE and not image.getexif()
    assert len(small)<=MAX_PREVIEW and len(small)<len(source)//5
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before
    rgba=Image.new('RGBA',(100,100),(0,0,0,0));data=io.BytesIO();rgba.save(data,'PNG')
    with Image.open(io.BytesIO(await preview_bytes(data.getvalue()))) as image:assert min(image.getpixel((50,50)))>245
    oriented=Image.new('RGB',(1200,600),'blue');exif=Image.Exif();exif[274]=6;exif[270]='private metadata';data=io.BytesIO();oriented.save(data,'JPEG',exif=exif)
    with Image.open(io.BytesIO(await preview_bytes(data.getvalue()))) as image:assert image.height>image.width and not image.getexif()


@pytest.mark.asyncio
async def test_preview_rejects_non_image_and_pixel_bombs(monkeypatch):
    with pytest.raises(HTTPException):await preview_bytes(b'<svg>not raster</svg>')
    monkeypatch.setattr('ai2apps.web.mobile_image_preview.MAX_PIXELS',10)
    with pytest.raises(HTTPException) as error:await preview_bytes(photo((20,20)))
    assert error.value.status_code==413


@pytest.mark.asyncio
async def test_bot_preview_authorizes_before_cache_and_keeps_original(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);p=[owner()];source=photo((1200,900));path=tmp_path/'original.png';path.write_bytes(source)
    artifact=runtime.workspace.import_artifact(sid,path,name='original.png',media_type='image/png')
    app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,lambda:p[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        url=f'/messager-mobile/bots/{bot["id"]}/files/{sid}/artifacts/{artifact.id}'
        preview=await c.get(url+'?preview=true');assert preview.status_code==200,preview.text
        assert preview.headers['content-type']=='image/jpeg' and preview.headers['x-ai2apps-image-variant']=='mobile-preview'
        assert (await c.get(url)).content==source
        p[0]=replace(owner(),actor_user_id='foreign')
        assert (await c.get(url+'?preview=true')).status_code==404


def inline_thread(runtime):
    repository=ChatRepository(runtime.database,runtime.events,principal=owner())
    original=photo((1200,900));url='data:image/png;base64,'+base64.b64encode(original).decode()
    thread,_=repository.create_thread(title='Inline original',legacy_messages=(LegacyChatMessageInput(role=MessageRole.USER,content=[{'type':'image_url','image_url':{'url':url}}],metadata={'id':'legacy-image'}),))
    sid=thread.session.id;record=repository.get_content(sid)
    value=jsonable_encoder(ChatContentResponse.from_record(record));projected=json.loads(project_response('/chat/threads/'+sid+'/content',200,json.dumps(value).encode()))
    return repository,sid,original,url,projected


@pytest.mark.asyncio
async def test_chat_inline_projection_roundtrip_and_model_hydration_preserve_original(runtime):
    repository,sid,original,url,projected=inline_thread(runtime)
    image=projected['messages'][0]['content'][0]['image_url'];assert not image['url'].startswith('data:')
    assert image['url'].endswith('&preview=mobile') and 'mobile_image_ref' in image
    assert len(json.dumps(projected))<len(url)//10
    payload={'expected_revision':projected['thread']['revision'],'messages':deepcopy(projected['messages']),'session_metadata':{}}
    restored=prepare_request(runtime,owner(),'PUT','/chat/threads/'+sid+'/content',payload)
    assert restored['messages'][0]['content'][0]['image_url']=={'url':url}
    model=prepare_request(runtime,owner(),'POST','/chat/threads/'+sid+'/turns',{'request':{'messages':deepcopy(projected['messages'])}})
    assert model['request']['messages'][0]['content'][0]['image_url']=={'url':url}
    principal=[owner()];app=FastAPI();app.include_router(create_chat_router(lambda:runtime,lambda:principal[0]))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        thumb=await c.get(image['url'].replace('/v1/mobile',''))
        assert thumb.status_code==200,thumb.text;assert thumb.headers['content-type']=='image/jpeg'
        full=await c.get(image['mobile_original_url'].replace('/v1/mobile',''));assert full.content==original
        saved=await c.put('/chat/threads/'+sid+'/content',json=restored);assert saved.status_code==200,saved.text
        assert repository.get_content(sid).messages[0].content[0]['image_url']['url']==url
        principal[0]=replace(owner(),actor_user_id='foreign')
        assert (await c.get(image['url'].replace('/v1/mobile',''))).status_code==404
    tampered=deepcopy(projected['messages']);tampered[0]['content'][0]['image_url']['mobile_image_ref']['digest']='0'*64
    with pytest.raises(HTTPException):prepare_request(runtime,owner(),'PUT','/chat/threads/'+sid+'/content',{'messages':tampered})


def test_inline_rehydration_is_bounded_and_scope_bound(runtime,monkeypatch):
    _,sid,_,url,projected=inline_thread(runtime)
    message=deepcopy(projected['messages'][0])
    monkeypatch.setattr('ai2apps.chat.mobile_images.MAX_RESTORED_BYTES',len(url)+1500)
    with pytest.raises(HTTPException) as error:prepare_request(runtime,owner(),'POST','/chat/threads/'+sid+'/turns',{'request':{'messages':[deepcopy(message),deepcopy(message)]}})
    assert error.value.status_code==413
    with pytest.raises(HTTPException):prepare_request(runtime,owner(),'PUT','/chat/threads/other/content',{'messages':[message]})


@pytest.mark.asyncio
async def test_owner_mobile_proxy_projects_and_restores_real_http_snapshots(runtime,monkeypatch):
    from types import SimpleNamespace as NS
    from starlette.requests import Request
    from ai2apps.web import owner_home_gateway as gateway
    repository,sid,original,url,_=inline_thread(runtime)
    principal=owner();grant=NS(principal=lambda record:principal,valid=lambda record:None)
    monkeypatch.setattr(gateway,'authority',lambda request:(grant,'lease'))
    monkeypatch.setattr(gateway,'_runtime',lambda:runtime)
    path='/chat/threads/'+sid+'/content'
    def request(method='GET',query=b''):
        return Request({'type':'http','method':method,'path':'/v1/mobile'+path,'query_string':query,'headers':[]})
    result=await gateway.chat_proxy(request(),'GET',path);assert result.status_code==200
    projected=json.loads(result.body);image=projected['messages'][0]['content'][0]['image_url']
    assert not image['url'].startswith('data:')
    saved=await gateway.chat_proxy(request('PUT'),'PUT',path,{'expected_revision':projected['thread']['revision'],'messages':projected['messages'],'session_metadata':{}})
    assert saved.status_code==200,saved.body
    assert repository.get_content(sid).messages[0].content[0]['image_url']['url']==url
    from urllib.parse import urlsplit
    parsed=urlsplit(image['url'])
    thumb=await gateway.chat_proxy(request(query=parsed.query.encode()),'GET',parsed.path.removeprefix('/v1/mobile'))
    assert thumb.status_code==200 and thumb.media_type=='image/jpeg'
