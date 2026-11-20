"""Core App owners share the system state API without carrying business content."""
from dataclasses import replace
from types import SimpleNamespace
import pytest,httpx
from fastapi import FastAPI,HTTPException
from starlette.requests import Request
from test_app_state import runtime,P
from ai2apps.api.app_state import create_app_state_router

CASES=[('ai2apps.intelligence',{'channel_id':None,'tab':'articles','article_filter':'unread','article_type':'all'}),
       ('ai2apps.todo',{'directory_id':None}),
       ('ai2apps.gallery',{'collection_id':'recent','kind':'image','view':'grid'}),
       ('ai2apps.knowledge',{'bucket_id':'','kind':'note','view':'library'})]

@pytest.mark.asyncio
@pytest.mark.parametrize('app_id,values',CASES)
async def test_core_owner_contracts_and_same_local_mobile_presets(runtime,monkeypatch,app_id,values):
 instance,_,_=runtime.extension_manager.launch_app(app_id,principal=P())
 principal=[P()];app=FastAPI();app.include_router(create_app_state_router(lambda:runtime,lambda:principal[0]))
 base='/app-state/instances/'+instance.id
 packet={'schema':'ai2apps.app-state/v1','target':{'app_id':app_id,'mini_app_id':None,'contract_version':1},'values':values}
 async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as c:
  saved=await c.post(base+'/presets',json={'name':'View preset','packet':packet,'request_id':'core-view-save'});assert saved.status_code==201,saved.text
  for key in ('body','search','permissions','task_id'):
   bad={**packet,'values':{**values,key:'PRIVATE'}}
   assert (await c.post(base+'/validate',json={'packet':bad})).status_code==409
  principal[0]=replace(P(),client_scope='owner-home',authentication_type='owner_home_lease')
  monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda r,p,k:k==app_id)
  items=await c.get(base+'/presets',params={'app_id':app_id});assert items.status_code==200,items.text
  assert items.json()['items'][0]['packet']==packet
  foreign={**packet,'target':{**packet['target'],'app_id':'foreign.app'}}
  assert (await c.post(base+'/validate',json={'packet':foreign})).status_code==404
  monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *a:False)
  assert (await c.get(base+'/contract',params={'app_id':app_id})).status_code==404

@pytest.mark.asyncio
@pytest.mark.parametrize('app_id,values',CASES)
async def test_mobile_gateway_state_checks_target_app_without_requiring_media_apps(runtime,monkeypatch,app_id,values):
 from ai2apps.web import owner_studio_gateway as gateway
 instance,_,_=runtime.extension_manager.launch_app(app_id,principal=P())
 actor=replace(P(),client_scope='owner-home',authentication_type='owner_home_lease')
 authority=SimpleNamespace(principal=lambda grant:actor)
 monkeypatch.setattr(gateway.owner,'authority',lambda request:(authority,object()))
 monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda r,p,k:k==app_id)
 scope={'type':'http','method':'GET','path':'/v1/platform/app-state/instances/'+instance.id+'/contract','headers':[],
        'path_params':{'instance':instance.id},'app':SimpleNamespace(state=SimpleNamespace(runtime_provider=lambda:runtime))}
 assert await gateway.principal(Request(scope))==actor
 monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *args:False)
 with pytest.raises(HTTPException) as error:await gateway.principal(Request(scope))
 assert error.value.status_code==403
