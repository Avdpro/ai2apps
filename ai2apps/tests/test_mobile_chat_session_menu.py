import json
import pytest
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.web.mobile_agent_gateway import business_target,dispatch
from test_app_interactions import runtime
from test_owner_gateway import env

@pytest.mark.asyncio
async def test_signed_manage_uses_existing_thread_acl_and_revision(runtime):
    owner=RequestPrincipal.legacy_local()
    record,_=ChatRepository(runtime.database,runtime.events,principal=owner).create_thread(title='Before')
    path='/chat/threads/'+record.session.id
    assert business_target('PATCH',path)==path and business_target('DELETE',path)==path
    assert business_target('PATCH',path+'/anything') is None
    assert business_target('POST',path+'/manage')==path+'/manage'
    assert business_target('POST',path+'/manage/other') is None
    response=await dispatch(runtime,owner,'POST',path+'/manage',json.dumps({'action':'rename','title':'After','expected_revision':record.session.revision}).encode(),{'content-type':'application/json'})
    assert response.status_code==200
    updated=json.loads(response.body)
    response=await dispatch(runtime,owner,'DELETE',path,b'',{},query='expected_revision=0')
    assert response.status_code==422
    response=await dispatch(runtime,owner,'POST',path+'/manage',json.dumps({'action':'delete','expected_revision':updated['revision']}).encode(),{'content-type':'application/json'})
    assert response.status_code==200 and json.loads(response.body)['status']=='deleted'

def test_owner_manage_exact_routes_and_revision(env,tmp_path,monkeypatch):
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.config import PlatformConfig
    from ai2apps.web import owner_home_gateway as gateway
    client,_,_,_,_=env
    desktop=PlatformRuntime(PlatformConfig.from_base_path(tmp_path/'desktop'));desktop.start();desktop.remote=gateway._runtime().remote
    monkeypatch.setattr(gateway,'_runtime',lambda:desktop)
    try:
        thread=client.post('/v1/mobile/chat/threads',json={'title':'Before'}).json();path='/v1/mobile/chat/threads/'+thread['id']
        changed=client.post(path+'/manage',json={'action':'rename','title':'After','expected_revision':thread['revision']})
        assert changed.status_code==200,changed.text
        assert client.delete(path+'?expected_revision='+str(thread['revision'])).status_code==409
        assert client.patch('/v1/mobile/chat/threads/not-owned',json={'title':'No','expected_revision':1}).status_code==404
        assert client.post('/v1/mobile/chat/threads/not-owned/manage',json={'action':'delete','expected_revision':1}).status_code==404
        assert client.post(path+'/manage',json={'action':'delete','expected_revision':thread['revision']}).status_code==409
        assert client.post(path+'/manage',json={'action':'delete','expected_revision':changed.json()['revision'],'title':'ignored'}).status_code==422
        assert client.post(path+'/manage',json={'action':'rename','expected_revision':changed.json()['revision'],'title':' '}).status_code==422
        deleted=client.post(path+'/manage',json={'action':'delete','expected_revision':changed.json()['revision']})
        assert deleted.status_code==200 and deleted.json()['status']=='deleted'
    finally:desktop.stop()
