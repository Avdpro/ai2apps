from types import SimpleNamespace as NS
from dataclasses import replace
import httpx
import pytest
from fastapi.responses import Response
from ai2apps.chat import speech
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime,client_app
from test_owner_gateway import env


@pytest.mark.asyncio
async def test_desktop_speech_uses_owned_session_and_installed_ready_model(runtime,monkeypatch):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Speech')
    calls=[]
    async def invoke(model,operation,payload,**kwargs):calls.append((model,operation,payload,kwargs));return Response(b'fixture-wav',media_type='audio/wav')
    runtime.model_invocations=NS(invoke_foreground_json=invoke)
    monkeypatch.setattr(speech,'list_package_models',lambda _: [NS(id='desktop/tts',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={'tts':{'named_voices':{'voices':['voice-a']}}})])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as c:
        path=f'/v1/platform/chat/threads/{thread.session.id}/speech'
        r=await c.post(path,json={'text':'你好'})
        assert r.status_code==200 and r.content==b'fixture-wav'
        assert calls[0][0:3]==('desktop/tts','audio_speech',{'model':'desktop/tts','input':'你好','response_format':'wav','voice':'voice-a'})
        assert calls[0][3]['context'].session_id==thread.session.id
        assert (await c.post(path,json={'text':'hi','model':'other'})).status_code==422
        assert (await c.post(path,json={'text':' '})).status_code==422
        assert (await c.post(path,json={'text':'x'*601})).status_code==422
    principal=replace(RequestPrincipal.legacy_local(),actor_user_id='different-owner',client_scope='different-client')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime,lambda:principal)),base_url='http://test') as c:
        assert (await c.post(path,json={'text':'no'})).status_code==404
    assert len(calls)==1


@pytest.mark.asyncio
@pytest.mark.parametrize('models',[[],[NS(model_type='audio_tts',checkpoint_ready=False)]])
async def test_missing_tts_tells_user_to_configure_desktop(runtime,monkeypatch,models):
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Speech')
    monkeypatch.setattr(speech,'list_package_models',lambda _:models)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client_app(runtime)),base_url='http://test') as c:
        r=await c.post(f'/v1/platform/chat/threads/{thread.session.id}/speech',json={'text':'hello'})
    assert r.status_code==409 and 'Desktop' in r.json()['detail'] and '安装' in r.json()['detail']


def test_owner_mobile_exact_speech_gateway(env,tmp_path,monkeypatch):
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.config import PlatformConfig
    from ai2apps.web import owner_home_gateway as gateway
    from ai2apps.remote.mobile_apps import MobileAppPolicy
    client,_,_,_,principal=env
    manager=gateway._runtime().remote
    desktop=PlatformRuntime(PlatformConfig.from_base_path(tmp_path/'desktop'));desktop.start();desktop.remote=manager
    async def invoke(*args,**kwargs):return Response(b'owned-audio',media_type='audio/wav')
    desktop.model_invocations=NS(invoke_foreground_json=invoke)
    monkeypatch.setattr(speech,'list_package_models',lambda _:[NS(id='desktop/tts',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={})])
    monkeypatch.setattr(gateway,'_runtime',lambda:desktop)
    try:
        thread=client.post('/v1/mobile/chat/threads',json={'title':'Speech'}).json()
        path='/v1/mobile/chat/threads/'+thread['id']+'/speech'
        response=client.post(path,json={'text':'hello'})
        assert response.status_code==200,response.text
        assert response.content==b'owned-audio'
        assert client.post(path,json={'text':'hi','endpoint':'https://evil.test'}).status_code==422
        assert client.post('/v1/mobile/chat/threads/not-owned/speech',json={'text':'hi'}).status_code==404
        MobileAppPolicy(desktop.database).set_enabled(principal.installation_id,'ai2apps.general-chat',False)
        assert client.post(path,json={'text':'hi'}).status_code==403
    finally:desktop.stop()


@pytest.mark.asyncio
async def test_signed_speech_target_returns_binary(runtime,monkeypatch):
    from ai2apps.web.mobile_agent_gateway import dispatch,business_target
    import json
    principal=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='Speech')
    async def invoke(*args,**kwargs):return Response(b'signed-audio',media_type='audio/wav')
    runtime.model_invocations=NS(invoke_foreground_json=invoke)
    monkeypatch.setattr(speech,'list_package_models',lambda _:[NS(id='desktop/tts',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={})])
    path='/chat/threads/'+thread.session.id+'/speech'
    assert business_target('POST',path)==path and business_target('GET',path) is None
    response=await dispatch(runtime,principal,'POST',path,json.dumps({'text':'hello'}).encode(),{'content-type':'application/json'})
    assert response.status_code==200 and response.body==b'signed-audio'
