from types import SimpleNamespace as NS
from dataclasses import replace
import json,time
import pytest
from fastapi import FastAPI,Request
from fastapi.testclient import TestClient
from ai2apps.web.mobile_agent_gateway import application,public_path,business_target
from ai2apps.api.mobile_agent_desktop import create_desktop_agent_router
from ai2apps.identity import RequestPrincipal
from test_mobile_agent_protocol import env,approved,sign
from ai2apps.remote.mobile_agent_crypto import local_input


def test_exact_public_routes_do_not_include_admin_owner_or_arbitrary_proxy():
    assert public_path('GET','/mobile/home')
    assert public_path('POST','/v1/mobile/agent/agent-runs/r/cancel')
    for method,path in [('GET','/v1/platform/remote/mobile-agent/confirmation'),('POST','/v1/mobile/agent/http'),('POST','/v1/mobile/agent/agent-runs/r/retry'),('PUT','/v1/mobile/agent/chat/threads/s/content'),('GET','/v1/mobile/agent/../admin')]:
        assert not public_path(method,path)
    assert business_target('POST','/chat/threads/s/agent-runs')=='/sessions/s/agent-runs'

@pytest.mark.asyncio
async def test_signed_gateway_verifies_exact_raw_target_before_dispatch(env,monkeypatch):
    import httpx
    from ai2apps.web import mobile_agent_gateway as gateway
    e=env;cid=await approved(e);e.manager.require_device(e.device).public_origin='https://device.example'
    runtime=NS(remote=e.manager);e.manager.mobile_agent=e.service;called=[]
    async def dispatch(runtime,principal,method,path,body,headers,query=''):
        from starlette.responses import JSONResponse
        called.append((principal,method,path,body));return JSONResponse({'done':True})
    monkeypatch.setattr(gateway,'dispatch',dispatch)
    async def app(scope,receive,send):await application(scope,receive,send,runtime,e.device)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://device.example') as client:
        path='/v1/mobile/agent/chat/threads';body=b'{"title":"new"}';n=e.service.nonce(cid)
        signature=sign(e.key,local_input(cid,n['jti'],'POST',path,body,n['nonce']))
        headers={'Origin':'https://device.example','X-AI2Apps-Agent-Connection':cid,'X-AI2Apps-Agent-Nonce':n['nonce'],'X-AI2Apps-Agent-Signature':signature,'Content-Type':'application/json'}
        result=await client.post(path,content=body,headers=headers);assert result.status_code==200,result.text
        assert called[0][0].authentication_type=='desktop_approved_agent'
        assert (await client.post(path,content=body,headers=headers)).status_code==403
        assert len(called)==1
        assert (await client.post(path,content=body,headers={'Origin':'https://device.example','Cookie':'owner=valid'})).status_code==403
        assert len(called)==1
        # Percent encoding changes the raw path even if the router would normalize it.
        n=e.service.nonce(cid);encoded='/v1/mobile/agent/chat/%74hreads'
        headers.update({'X-AI2Apps-Agent-Nonce':n['nonce'],'X-AI2Apps-Agent-Signature':sign(e.key,local_input(cid,n['jti'],'POST',encoded,body,n['nonce']))})
        assert (await client.post(encoded,content=body,headers=headers)).status_code==403


def test_desktop_decision_requires_local_cookie_core_and_csrf():
    actor=replace(RequestPrincipal.legacy_local(),authentication_type='local_session')
    runtime=NS(local_session_token_from_cookies=lambda cookies:cookies.get('ai2apps_local_session'),authorize_local_session=lambda token:actor if token=='fixture' else None)
    app=FastAPI();app.include_router(create_desktop_agent_router(lambda:runtime,lambda:actor))
    with TestClient(app,base_url='http://127.0.0.1',client=('127.0.0.1',1000)) as client:
        assert client.get('/mobile-agent/confirmation').status_code==403
        assert client.get('/mobile-agent/confirmation',headers={'Cookie':'ai2apps_local_session=forged'}).status_code==403
        cookie={'Cookie':'ai2apps_local_session=fixture'}
        r=client.get('/mobile-agent/confirmation',headers=cookie);assert r.status_code==200,r.text
        token=r.json()['token']
        assert client.post('/mobile-agent/device/configure',headers={**cookie,'X-AI2Apps-Desktop-Confirm':token,'Origin':'https://evil.example'},json={'enabled':True}).status_code==403
        assert client.post('/mobile-agent/device/configure',headers={**cookie,'Origin':'http://127.0.0.1'},json={'enabled':True}).status_code==403
    with TestClient(app,base_url='https://device.example',client=('127.0.0.1',1000)) as client:
        assert client.get('/mobile-agent/confirmation',headers=cookie).status_code==403

from test_aaat_declaration_context import runtime

@pytest.mark.asyncio
async def test_signed_mobile_end_to_end_real_general_form_restart_and_history(runtime,env):
    import httpx
    from test_aaat_execution_flow import register,response
    from test_aaat_declaration_context import wait
    from ai2apps.identity import IdentityRepository,OrganizationType
    e=env;cid=await approved(e);claims=e.service.leases[cid]['claims'];installation=e.manager.space.installation(e.manager.require_device(e.device))
    IdentityRepository(runtime.database).bind_installation(installation_id=installation.id,cloud_device_id=e.device,organization_id=installation.organization_id,organization_type=OrganizationType.HOUSEHOLD,core_user_id=installation.core_user_id,billing_account_id=installation.billing_account_id,access_epoch=1)
    e.manager.require_device(e.device).public_origin='https://device.example';e.manager.mobile_agent=e.service;runtime.remote=e.manager
    calls=[]
    async def describe(principal,model=None):return {'selection_required':True,'effective_schema':{'type':'object','properties':{'query':{'type':'string'}},'required':['query']}}
    async def execute(args,context):
        calls.append(args);await context.report_progress('Reading evidence',progress=.5)
        from PIL import Image
        image=runtime.config.paths.base_path/'signed-output.png';Image.new('RGB',(4,4),'green').save(image)
        artifact=runtime.workspace.import_artifact(context.session_id,image,run_id=context.trace_id,media_type='image/png',metadata={'generator':'ai2apps.images','model':'fixture'})
        return {'artifact':{'id':artifact.id,'media_type':artifact.media_type,'download_url':f'/v1/platform/sessions/{context.session_id}/artifacts/{artifact.id}/download'},'aaat_view':{'schema':'ai2apps.aaat-view/v1','id':'read','layout':'cards','title':'Read evidence','items':[{'id':'one','title':args['query'],'url':'https://source.example/original'}]}}
    register(runtime,'test.signed_mobile',execute,describe=describe)
    async def model(request):return response(text='Read evidence') if calls else response('test.signed_mobile',{'query':'draft'})
    runtime.agent_runtime.bind_model_provider(model)
    actual_remote=runtime.remote
    # Only the isolated HTTP application uses the fixture control plane. Runtime
    # background lifecycle retains its own managers and starts no external tunnel.
    original_remote=None
    async def app(scope,receive,send):await application(scope,receive,send,runtime,e.device)
    await runtime.agent_runtime.start()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://device.example') as client:
            async def signed(method,path,payload=None):
                body=b'' if payload is None else json.dumps(payload,ensure_ascii=False).encode()
                n=(await client.post('/v1/mobile/agent/connections/'+cid+'/nonce',json={},headers={'Origin':'https://device.example'})).json()
                sig=sign(e.key,local_input(cid,n['jti'],method,path,body,n['nonce']))
                return await client.request(method,path,content=body,headers={'Origin':'https://device.example','Content-Type':'application/json','X-AI2Apps-Agent-Connection':cid,'X-AI2Apps-Agent-Nonce':n['nonce'],'X-AI2Apps-Agent-Signature':sig})
            thread=await signed('POST','/v1/mobile/agent/chat/threads',{'title':'Signed mobile fixture'});assert thread.status_code==201,thread.text
            sid=thread.json()['id']
            created=await signed('POST',f'/v1/mobile/agent/chat/threads/{sid}/agent-runs',{'agent':'ai2apps.general-agent','input':{'model':'fixture','prompt':'Read evidence','tools':['test.signed_mobile']}});assert created.status_code==202,created.text
            rid=created.json()['id'];runtime.agent_runtime.wake();await wait(runtime,rid,'waiting_input')
            state=(await signed('GET','/v1/mobile/agent/agent-runs/'+rid)).json();item=state['interactions'][0]
            path=f'/v1/mobile/agent/agent-runs/{rid}/interactions/{item["id"]}/parameters'
            assert (await signed('PUT',path,{'revision':0,'values':{'query':'用户修改'}})).status_code==200
            await runtime.agent_runtime.stop();await runtime.agent_runtime.start()
            draft=(await signed('GET',path)).json();assert draft['values']['query']=='用户修改';assert not calls
            submitted=await signed('POST',path+'/submit',{'revision':draft['revision'],'values':draft['values']});assert submitted.status_code==200,submitted.text
            done=await wait(runtime,rid,'completed');assert calls==[{'query':'用户修改'}]
            assert done.output['aaat_views'][0]['view']['items'][0]['url']=='https://source.example/original'
            recovered=(await signed('GET',f'/v1/mobile/agent/chat/threads/{sid}/content')).json();assert recovered['messages'][-1]['metadata']['aaat_views']==done.output['aaat_views']
            assert len(calls)==1
            aid=done.output['content'][-1]['image_url']['artifact_id']
            image=await signed('GET',f'/v1/mobile/agent/artifacts/{rid}/{aid}')
            assert image.status_code==200,image.text
            assert image.headers['content-type']=='image/png'
            assert image.content==runtime.workspace.artifact_path(runtime.workspace.get_artifact(sid,aid)).read_bytes()
            assert (await signed('GET',f'/v1/mobile/agent/artifacts/{rid}/art_unrecorded')).status_code==404
            # Owner recovery archives the existing image without model invocation or Chat deletion.
            from ai2apps.images.agent_recovery import recover_session_results,STUDIO
            from ai2apps.studio.repository import StudioRepository
            principal=e.service.current(e.service.leases[cid]['claims'])
            instance,_,_=runtime.extension_manager.launch_app(STUDIO,principal=principal)
            assert recover_session_results(runtime,principal,instance.id)=={'recovered':1}
            assert recover_session_results(runtime,principal,instance.id)=={'recovered':0}
            scope=dict(actor_id=principal.actor_user_id,installation_id=principal.installation_id,app_instance_id=instance.id,studio_id=STUDIO)
            repo=StudioRepository(runtime.database);archived=repo.list_runs(**scope)
            assert len(archived)==1 and archived[0]['status']=='succeeded'
            assert archived[0]['artifacts'][0]['metadata']['workspaceArtifactId']!=aid
            repo.delete_run(archived[0]['id'],runtime.workspace,**scope)
            assert runtime.workspace.get_artifact(sid,aid).status=='active'
            assert recover_session_results(runtime,principal,instance.id)=={'recovered':0}
            assert len(calls)==1
    finally:
        await runtime.agent_runtime.stop()
        runtime.remote=None
