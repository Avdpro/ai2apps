"""Mobile voice stays inside the owner mount and original Bot ingress."""
import io,json,wave
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest,httpx
from fastapi import FastAPI
from fastapi.responses import Response
from ai2apps.api.messager_mobile import create_messager_mobile_router
from ai2apps.messager.conversation_profile import settings
from test_app_interactions import runtime
from test_app_chat_durable import bind_identity
from test_bot_realtime_voice import configured
from test_messager_mobile import owner


def wav_bytes():
    out=io.BytesIO()
    with wave.open(out,'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(16000);f.writeframes(b'\0\0'*1600)
    return out.getvalue()


def prepare(runtime,monkeypatch):
    service,bot,sid,models,config=configured(runtime)
    for key,m in models.items():m.id=key;m.display_name=key
    monkeypatch.setattr('ai2apps.messager.mobile_voice.list_package_models',lambda r:list(models.values()))
    runtime.model_invocations.invoke_foreground_multipart=AsyncMock(return_value=Response(json.dumps({'text':'请整理资料'}),media_type='application/json'))
    runtime.model_invocations.invoke_foreground_json=AsyncMock(return_value=Response(wav_bytes(),media_type='audio/wav'))
    settings(runtime,'local',bot,model_id='fixture',expected_revision=0)
    principal=[owner()];app=FastAPI();app.include_router(create_messager_mobile_router(lambda:runtime,lambda:principal[0]))
    return service,bot,sid,principal,app


@pytest.mark.asyncio
async def test_mobile_voice_original_ingress_media_and_close_keep_run(runtime,monkeypatch):
    service,bot,sid,principal,app=prepare(runtime,monkeypatch);controller='a'*32
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base='/messager-mobile/bots/'+bot
        assert (await c.get(base+'/voice/catalog')).json()['stt'][0]['id']=='asr'
        start=await c.post(base+'/realtime/sessions',json={'session_id':sid,'controller':controller,'revision':1,'model':'fixture','language':'zh'})
        assert start.status_code==200,start.text;ref=start.json()['id']
        transcript=await c.post(base+'/voice/transcriptions',data={'session_id':sid,'voice_id':ref,'controller':controller},files={'file':('speech.wav',wav_bytes(),'audio/wav')})
        assert transcript.status_code==200,transcript.text
        context=runtime.model_invocations.invoke_foreground_multipart.call_args.kwargs['context']
        assert context.session_id==sid and context.authentication_type=='owner_home_lease' and context.consumer_app_id=='ai2apps.messager'
        turn=await c.post(base+'/realtime/sessions/'+ref+'/inputs',json={'controller':controller,'turn_id':'stable-voice-turn','text':transcript.json()['text'],'attachments':[]})
        assert turn.status_code==200,turn.text
        duplicate=await c.post(base+'/realtime/sessions/'+ref+'/inputs',json={'controller':controller,'turn_id':'stable-voice-turn','text':transcript.json()['text'],'attachments':[]})
        assert duplicate.json()==turn.json()
        speech=await c.post(base+'/voice/speech',json={'session_id':sid,'voice_id':ref,'controller':controller,'text':'真实Bot回复'})
        assert speech.status_code==200,speech.text;assert speech.content==wav_bytes()
        assert runtime.model_invocations.invoke_foreground_json.call_args.kwargs['context'].session_id==sid
        run_id=turn.json()['dialogue_run_id'];before=runtime.agents.get_run(run_id).status
        assert (await c.post(base+'/realtime/sessions/'+ref+'/close',json={'controller':controller})).json()['closed']
        assert runtime.agents.get_run(run_id).status==before
        assert (await c.post(base+'/voice/speech',json={'session_id':sid,'voice_id':ref,'controller':controller,'text':'late'})).status_code==409


@pytest.mark.asyncio
async def test_mobile_voice_rejects_foreign_controller_scope_session_and_oversize(runtime,monkeypatch):
    service,bot,sid,principal,app=prepare(runtime,monkeypatch);controller='b'*32
    ref=service.start(owner(),bot,sid,controller,1,'fixture','zh',None)['id']
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base='/messager-mobile/bots/'+bot
        for data in [{'session_id':sid,'voice_id':ref,'controller':'c'*32},{'session_id':'foreign','voice_id':ref,'controller':controller}]:
            assert (await c.post(base+'/voice/transcriptions',data=data,files={'file':('speech.wav',wav_bytes(),'audio/wav')})).status_code==404
        assert (await c.post(base+'/voice/transcriptions',data={'session_id':sid},files={'file':('speech.wav',b'x'*(4*1024*1024+1),'audio/wav')})).status_code==413
        assert (await c.post(base+'/voice/speech',json={'session_id':sid,'voice_id':ref,'controller':controller,'text':'hello','model':'arbitrary'})).status_code==422
        principal[0]=replace(owner(),actor_user_id='foreign')
        assert (await c.get(base+'/realtime/settings')).status_code==404
        principal[0]=replace(owner(),client_scope='desktop')
        assert (await c.post(base+'/realtime/sessions/'+ref+'/touch',json={'controller':controller})).status_code==403
    runtime.model_invocations.invoke_foreground_multipart.assert_not_awaited()


@pytest.mark.parametrize('enabled,declared,renderer,instance,expected',[(True,True,'host','instance',True),(False,True,'host','instance',False),(True,False,'host','instance',False),(True,True,'sandbox','instance',False),(True,True,'host','foreign',False)])
def test_microphone_headers_require_owner_mount_and_declaration(monkeypatch,enabled,declared,renderer,instance,expected):
    from ai2apps.web import mobile_app_gateway as gateway,owner_home_gateway
    principal=owner();mount={'placement':'mobile','renderer':renderer,'app_instance_id':instance,'app_key':'arbitrary-provider'}
    runtime=NS(extension_manager=NS(mount_entry=lambda key,principal:mount))
    monkeypatch.setattr(owner_home_gateway,'authority',lambda request:(NS(principal=lambda ref:principal),'lease'))
    monkeypatch.setattr(owner_home_gateway,'_runtime',lambda:runtime)
    monkeypatch.setattr('ai2apps.remote.mobile_apps.app_enabled',lambda *args:enabled)
    monkeypatch.setattr(gateway,'descriptor',lambda *args:{'microphone':declared})
    assert gateway.microphone_document({'type':'http','path':'/mobile/app-resource/mount/instance/entry'}) is expected
    assert not gateway.microphone_document({'type':'http','path':'/mobile/app-resource/mount/instance/assets/js/record.js'})


@pytest.mark.asyncio
@pytest.mark.parametrize('trusted',[True,False])
async def test_mobile_html_media_policy_is_opt_in(monkeypatch,trusted):
    from ai2apps.http_security import LocalBrowserSecurityHeadersMiddleware
    from fastapi.responses import HTMLResponse
    monkeypatch.setattr('ai2apps.web.mobile_app_gateway.microphone_document',lambda scope:trusted)
    app=FastAPI()
    @app.get('/entry')
    def entry():return HTMLResponse('<p>trusted fixture</p>',headers={'Content-Security-Policy':"default-src 'self'; frame-ancestors 'self'"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=LocalBrowserSecurityHeadersMiddleware(app)),base_url='http://test') as c:
        response=await c.get('/entry')
        assert ('microphone=(self)' in response.headers['permissions-policy']) is trusted
        assert ("media-src 'self' blob:" in response.headers['content-security-policy']) is trusted


@pytest.mark.asyncio
async def test_manual_read_works_without_asr_or_realtime_setup_and_respects_bot_voice(runtime,monkeypatch):
    service,bot,sid,principal,app=prepare(runtime,monkeypatch)
    with runtime.database.transaction(write=True) as db:db.execute('DELETE FROM messager_realtime_settings WHERE bot_id=?',(bot,))
    runtime.model_invocations.model('asr').checkpoint_ready=False
    from ai2apps.messager.voice import BotVoice
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base='/messager-mobile/bots/'+bot+'/voice/read';body={'session_id':sid,'text':'Read the visible reply'}
        result=await c.post(base,json=body);assert result.status_code==200,result.text;assert result.content==wav_bytes()
        assert runtime.model_invocations.invoke_foreground_json.call_args.args[2]['voice']=='one'
        BotVoice(runtime.messager_bots,runtime).save('local',bot,{'mode':'model','model_id':'tts','voice':'two','profile_id':None},0)
        assert (await c.post(base,json=body)).status_code==200
        assert runtime.model_invocations.invoke_foreground_json.call_args.args[2]['voice']=='two'
        assert runtime.model_invocations.invoke_foreground_json.call_args.kwargs['context'].session_id==sid
        assert (await c.post(base,json={**body,'model':'arbitrary'})).status_code==422
        assert (await c.post(base,json={**body,'session_id':'foreign'})).status_code==404
        principal[0]=replace(owner(),actor_user_id='foreign')
        assert (await c.post(base,json=body)).status_code==404
    runtime.model_invocations.invoke_foreground_multipart.assert_not_awaited()


@pytest.mark.asyncio
async def test_input_only_and_read_only_settings_are_independent(runtime,monkeypatch):
    service,bot,sid,principal,app=prepare(runtime,monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base='/messager-mobile/bots/'+bot
        only_input=await c.put(base+'/realtime/settings',json={'stt_model_id':'asr','tts_model_id':None,'voice':None,'profile_id':None,'revision':1})
        assert only_input.status_code==200,only_input.text
        assert only_input.json()['ready'] and not only_input.json()['speech_ready']
        start=await c.post(base+'/realtime/sessions',json={'session_id':sid,'controller':'d'*32,'revision':2,'model':'fixture','language':'zh'})
        assert start.status_code==200,start.text;ref=start.json()['id']
        assert (await c.post(base+'/voice/speech',json={'session_id':sid,'voice_id':ref,'controller':'d'*32,'text':'silent'})).status_code==409
        runtime.model_invocations.invoke_foreground_json.assert_not_awaited()
        assert (await c.post(base+'/realtime/sessions/'+ref+'/inputs',json={'controller':'d'*32,'turn_id':'input-only','text':'do work','attachments':[]})).json()['state']=='accepted'
        await c.post(base+'/realtime/sessions/'+ref+'/close',json={'controller':'d'*32})
        only_read=await c.put(base+'/realtime/settings',json={'stt_model_id':None,'tts_model_id':'tts','voice':'two','profile_id':None,'revision':2})
        assert only_read.status_code==200,only_read.text
        assert not only_read.json()['ready'] and only_read.json()['speech_ready']
        assert (await c.post(base+'/voice/read',json={'session_id':sid,'text':'Read without ASR'})).status_code==200
        assert runtime.model_invocations.invoke_foreground_json.call_args.args[2]['voice']=='two'


def test_unavailable_tts_degrades_to_input_only_without_losing_task_ingress(runtime):
    service,bot,sid,models,_=configured(runtime)
    models['tts'].checkpoint_ready=False
    value=service.get('local',bot)
    assert value['ready'] and not value['speech_ready']
    assert service.start(owner(),bot,sid,'e'*32,1,'fixture','zh',None)['settings']['speech_ready'] is False
