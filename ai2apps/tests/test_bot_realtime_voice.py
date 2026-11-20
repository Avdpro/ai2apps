"""SQLite and original Bot admission, with model/ASR/TTS availability fixtures."""
from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from ai2apps.api.messager import create_messager_router
from test_app_interactions import runtime
from test_bot_capability_discovery import setup, P
from test_app_chat_durable import response, bind_identity
from test_bot_dialogue import job_wait


def configured(r):
    bot, sid, calls, _ = setup(r)
    models = {'asr': NS(model_type='audio_stt', checkpoint_ready=True),
              'tts': NS(model_type='audio_tts', checkpoint_ready=True,
                        audio_capabilities={'tts': {'named_voices': {'voices': ['one', 'two']}}})}
    r.model_invocations = NS(model=models.get)
    service = r.messager_dialogue.realtime
    service._test_calls = calls
    settings = service.save('local', bot['id'], {'stt_model_id': 'asr', 'tts_model_id': 'tts',
                                               'voice': 'one', 'profile_id': None}, 0)
    return service, bot['id'], sid, models, settings


def start(service, bot, sid, controller='a' * 32):
    return service.start(P(), bot, sid, controller, 1, 'fixture', 'zh', 'Asia/Shanghai')


def test_settings_are_bot_owned_revision_guarded_and_separate_from_read_aloud(runtime):
    s, bot, sid, models, settings = configured(runtime)
    assert settings['ready'] and settings['revision'] == 1
    assert s.get('local', bot)['tts_model_id'] == 'tts'
    from ai2apps.messager.voice import BotVoice
    assert BotVoice(runtime.messager_bots, runtime).get('local', bot)['mode'] == 'default'
    with pytest.raises(PermissionError): s.get('stranger', bot)
    with pytest.raises(ValueError): s.save('local', bot, settings, 0)
    models['asr'].checkpoint_ready = False
    assert s.get('local', bot)['configured'] and not s.get('local', bot)['ready']
    with pytest.raises(ValueError): start(s, bot, sid)


def test_one_controller_is_bound_to_actor_installation_scope_and_main_conversation(runtime):
    s, bot, sid, _, _ = configured(runtime)
    session = start(s, bot, sid)
    assert start(s, bot, sid)['id'] == session['id']
    with pytest.raises(ValueError): start(s, bot, sid, 'b' * 32)
    for principal in (replace(P(), actor_user_id='stranger'), replace(P(), installation_id='other'), replace(P(), client_scope='other')):
        with pytest.raises(PermissionError): s.touch(principal, bot, session['id'], 'a' * 32)
    with pytest.raises(PermissionError): s.touch(P(), bot, session['id'], 'b' * 32)
    with pytest.raises(ValueError): s.save('local', bot, s.get('local', bot), 1)
    s.close(P(), bot, session['id'], 'a' * 32)
    s.close(P(), bot, session['id'], 'a' * 32)
    with pytest.raises(ValueError): s.touch(P(), bot, session['id'], 'a' * 32)
    assert start(s, bot, sid, 'b' * 32)['id'] != session['id']


def test_final_speech_reuses_durable_bot_receiver_and_close_keeps_the_run(runtime):
    s, bot, sid, _, _ = configured(runtime)
    session = start(s, bot, sid)
    result = s.submit(P(), bot, session['id'], 'a' * 32, 'turn-one', 'Please help')
    assert s.submit(P(), bot, session['id'], 'a' * 32, 'turn-one', 'Please help') == result
    with pytest.raises(ValueError): s.submit(P(), bot, session['id'], 'a' * 32, 'turn-one', 'Changed input')
    run = runtime.agents.get_run(result['dialogue_run_id'])
    s.close(P(), bot, session['id'], 'a' * 32)
    assert runtime.agents.get_run(run.id).status == run.status
    with pytest.raises(ValueError): s.submit(P(), bot, session['id'], 'a' * 32, 'late', 'late transcript')
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM messager_dialogue_turns WHERE session_id=?', (sid,)).fetchone()[0] == 1


def test_expiry_and_server_restart_do_not_resurrect_a_lease(runtime, monkeypatch):
    import ai2apps.messager.realtime as module
    s, bot, sid, _, _ = configured(runtime)
    session = start(s, bot, sid)
    monkeypatch.setattr(module.time, 'time', lambda: 10**12)
    from ai2apps.messager.realtime import BotRealtime
    recovered = BotRealtime(runtime.messager_dialogue)
    with pytest.raises(ValueError): recovered.touch(P(), bot, session['id'], 'a' * 32)
    assert start(recovered, bot, sid, 'b' * 32)['id'] != session['id']


@pytest.mark.asyncio
async def test_http_owner_origin_guards_and_strict_bodies(runtime):
    _, bot, sid, _, _ = configured(runtime)
    app = FastAPI()
    app.include_router(create_messager_router(lambda: runtime, P), prefix='/v1/platform')
    path = '/v1/platform/messager/bots/' + bot + '/realtime'
    body = {'session_id': sid, 'controller': 'a' * 32, 'revision': 1, 'model': 'fixture'}
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
        assert (await c.post(path + '/sessions', json=body)).status_code == 403
        assert (await c.post(path + '/sessions', json={**body, 'approve': True}, headers={'origin': 'http://test'})).status_code == 422
        response = await c.post(path + '/sessions', json=body, headers={'origin': 'http://test'})
        assert response.status_code == 200, response.text
        ref = response.json()['id']
        assert (await c.post(path + '/sessions/' + ref + '/touch', json={'controller': 'b' * 32}, headers={'origin': 'http://test'})).status_code == 404
        assert (await c.get('/v1/platform/messager/bots/foreign/realtime/settings')).status_code == 404


@pytest.mark.asyncio
async def test_voice_creates_real_bot_work_and_closing_does_not_cancel_approval(runtime):
    import json
    from test_app_interactions import wait
    service, bot, sid, _, _ = configured(runtime)
    async def model(request):
        system='\n'.join(m['content'] for m in request['messages'] if m.get('role')=='system')
        if not request.get('tools') and 'Decide quickly' in system:
            return response(text=json.dumps({'kind':'task','text':'Queued; you can keep chatting.','title':'Voice requested work'}))
        results=[json.loads(m['content']) for m in request['messages'] if m.get('role')=='tool']
        if any(x.get('created') for x in results): return response(text='Job finished')
        if not any(x.get('providers') for x in results): return response('app.describe',{'capability':'fixture.paint'})
        return response('fixture.paint',{'prompt':'requested by voice'})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        session=start(service,bot,sid)
        result=service.submit(P(),bot,session['id'],'a'*32,'real-work','Please create the fixture')
        await wait(runtime,result['dialogue_run_id'],'completed')
        job=await job_wait(runtime,result['dialogue_run_id'],'running')
        run=await wait(runtime,job['worker_run'],'waiting_capability')
        assert run.id != result['dialogue_run_id']
        service.close(P(),bot,session['id'],'a'*32)
        assert runtime.agents.get_run(run.id).status.value == 'waiting_capability'
        pending=next(v for v in runtime.messager_dialogue.snapshot(P(),bot,sid)['runs'] if v['id']==run.id)['interactions'][0]
        access=runtime.messager_bot_app_access
        review=access.request('local',bot,run.id,pending['id'])
        assert access.allow('local',bot,run.id,pending['id'],review['request_hash'])['continued']
        await wait(runtime,run.id,'completed')
        await job_wait(runtime,result['dialogue_run_id'],'completed')
        assert len(service._test_calls)==1
        assert any(m['content']=='Job finished' for m in runtime.app_chat.message_page(P(),sid)['items'])
    finally:
        await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_reference_voice_playback_is_owner_version_bound_and_transient(runtime):
    from fastapi.responses import Response
    from ai2apps.api.readaloud import create_readaloud_router
    from ai2apps.readaloud.repository import ReadAloudRepository
    repository=ReadAloudRepository(runtime.database,runtime.events)
    profile=repository.save_design_profile('local',None,name='Fixture voice',model_id='speech',description='Warm voice',text='Hello')
    repository.attach_design_preview('local',profile['id'],('speech','Warm voice','Hello'),{'fixture':True})
    profile=repository.get_voice_profile('local',profile['id'])
    generated=[];saved=[]
    model=NS(id='speech',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={'tts':{'named_voices':{'voices':['one']}}})
    async def invoke(*args,**kwargs):
        generated.append(args)
        return Response(b'RIFF-fixture',media_type='audio/wav')
    runtime.model_invocations=NS(model=lambda mid:model if mid=='speech' else None,
        context_for_actor=lambda *a,**k:None,invoke_foreground_json=invoke)
    runtime.readaloud_tasks=NS(save_quick_audio=lambda *a,**k:(saved.append(a),'/fixture/download')[1])
    app=FastAPI();app.include_router(create_readaloud_router(lambda:runtime,principal_provider=P),prefix='/v1/platform')
    path='/v1/platform/readaloud/voice-profiles/'+profile['id']+'/speech'
    body={'text':'Hello','model_id':'speech','expected_updated_at':profile['updated_at']}
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response=await client.post(path,json=body)
        assert response.status_code==200,response.text
        assert response.content==b'RIFF-fixture' and response.headers['cache-control']=='no-store'
        assert 'x-ai2apps-download-url' not in response.headers and not saved
        assert generated[-1][2]['instructions']=='Warm voice'
        assert (await client.post(path,json={**body,'expected_updated_at':'stale'})).status_code==409
        assert (await client.post(path.replace(profile['id'],'foreign'),json=body)).status_code==404
        assert len(generated)==1
        regular=await client.post('/v1/platform/readaloud/quick-read',json={'text':'Hello','model_id':'speech','voice':'one'})
        assert regular.status_code==200 and len(saved)==1
        assert regular.headers['x-ai2apps-download-url']=='/fixture/download'
