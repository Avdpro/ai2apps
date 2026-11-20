"""Cursor windows preserve the same authenticated App owner contract."""
from dataclasses import replace
import pytest
from ai2apps.core import MessageRole
from ai2apps.storage.models import MessagePartInput
from ai2apps.storage.repositories import MessageRepository
from test_app_chat_durable import runtime,bind_identity,open_chat,P

def test_recent_older_incremental_and_foreign_scope(runtime):
 sid,_,_=open_chat(runtime);repo=MessageRepository(runtime.database,runtime.events)
 for n in range(125):repo.append(session_id=sid,role=MessageRole.USER,parts=[MessagePartInput(kind='text',content={'text':str(n)})])
 service=runtime.app_chat
 recent=service.message_page(P(),sid)
 assert [int(i['content']) for i in recent['items']]==list(range(75,125)) and recent['has_more']
 older=service.message_page(P(),sid,before=recent['before'])
 assert [int(i['content']) for i in older['items']]==list(range(25,75))
 first=service.message_page(P(),sid,before=older['before'])
 assert [int(i['content']) for i in first['items']]==list(range(25)) and not first['has_more']
 reply=repo.append(session_id=sid,role=MessageRole.ASSISTANT,parts=[MessagePartInput(kind='text',content={'text':'new reply'})])
 delta=service.message_page(P(),sid,after=recent['after'])
 assert [i['content'] for i in delta['items']]==['new reply']
 assert delta['items'][0]['created_at']==reply.value.message.created_at.isoformat()
 assert service.snapshot(P(),sid,False)['messages']==[]
 with pytest.raises(Exception):service.message_page(replace(P(),actor_user_id='foreign'),sid)
 with pytest.raises(ValueError):service.message_page(P(),sid,before=10,after=5)
 with pytest.raises(ValueError):service.message_page(P(),sid,limit=51)

@pytest.mark.asyncio
async def test_http_pages_and_body_free_open_keep_principal_checks(runtime):
 from fastapi import FastAPI
 import httpx
 from ai2apps.api.app_chat import create_app_chat_router
 sid,_,_=open_chat(runtime);principal=[P()]
 app=FastAPI();app.include_router(create_app_chat_router(lambda:runtime,lambda:principal[0]))
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
  base='/app-chat/sessions/'+sid
  assert (await c.get(base+'/state')).json()['messages']==[]
  assert (await c.get(base+'/messages')).json()['items']==[]
  assert (await c.get(base+'/messages?limit=51')).status_code==422
  assert (await c.get(base+'/messages?before=10&after=2')).status_code==409
  principal[0]=replace(P(),actor_user_id='foreign')
  assert (await c.get(base+'/messages')).status_code in (403,404)
  assert (await c.get(base+'/state')).status_code in (403,404)
