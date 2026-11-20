"""Owned material transfer uses real Session access and Gallery persistence."""
from dataclasses import replace
import httpx
import pytest
from ai2apps.api.router import create_ai2apps_router
from fastapi import FastAPI
from test_app_chat_durable import bind_identity,open_chat,P
from test_app_interactions import runtime

@pytest.mark.asyncio
async def test_gallery_import_selected_attachment_deduplicates_and_checks_ownership(runtime,tmp_path):
 sid,_,_=open_chat(runtime)
 source=tmp_path/'note.html';source.write_text('<html><body>synthetic gallery material</body></html>')
 material=runtime.documents.create_reference(sid,source,filename='note.html',media_type='text/html')
 app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=P))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  collections=(await c.get('/v1/platform/gallery/collections')).json()['items'];personal=next(x for x in collections if x['system_key']=='personal')
  endpoint=f'/v1/platform/gallery/assets/import-attachment/{sid}/{material.id}'
  first=await c.post(endpoint,json={'collectionId':personal['id'],'sourceAppId':'ai2apps.messager'});assert first.status_code==201,first.text
  second=await c.post(endpoint,json={'collectionId':personal['id'],'sourceAppId':'ai2apps.messager'});assert second.json()['asset']['id']==first.json()['asset']['id'];assert second.json()['created'] is False
  asset=first.json()['asset'];assert asset['kind']=='web';assert asset['name']=='note.html'
  changed=await c.patch('/v1/platform/gallery/assets/'+asset['id'],json={'description':'API description'})
  assert changed.status_code==200 and changed.json()['description']=='API description'
  assert changed.json()['name']=='note.html'
  fetched=await c.get('/v1/platform/gallery/assets/'+asset['id'])
  assert fetched.json()['description']=='API description'
  cleared=await c.patch('/v1/platform/gallery/assets/'+asset['id'],json={'description':''})
  assert cleared.json()['description']==''
  content=await c.get('/v1/platform/gallery/assets/'+asset['id']+'/content');assert content.content==source.read_bytes()
  other_sid,_,_=open_chat(runtime)
  assert other_sid!=sid
  wrong=await c.post(f'/v1/platform/gallery/assets/import-attachment/{other_sid}/{material.id}',json={});assert wrong.status_code in (403,404)
 foreign=replace(P(),actor_user_id='other')
 app=FastAPI();app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,principal_provider=lambda:foreign))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  denied=await c.post(endpoint,json={});assert denied.status_code in (403,404)

@pytest.mark.parametrize('name,mime',[('clip.mp4','video/mp4'),('speech.wav','audio/wav'),('bundle.bin','application/octet-stream')])
def test_non_text_material_is_attached_without_fabricated_analysis(runtime,tmp_path,name,mime):
 sid,_,_=open_chat(runtime);source=tmp_path/name;source.write_bytes(b'synthetic opaque bytes')
 item=runtime.documents.create_reference(sid,source,filename=name,media_type=mime)
 content=runtime.app_chat.attachment_content(sid,[item.id],'Inspect only if supported')
 assert 'Content has NOT been read or transcribed' in content[1]['text']
 assert item.id in content[1]['text'] and mime in content[1]['text']
 assert len(content)==2
