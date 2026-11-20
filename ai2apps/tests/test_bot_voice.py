from types import SimpleNamespace as NS
import pytest
from ai2apps.messager.bots import install
from ai2apps.messager.voice import BotVoice
from ai2apps.readaloud.repository import ReadAloudRepository
from test_app_interactions import runtime


def setup(runtime):
    install(runtime)
    models={
        'named':NS(id='named',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={'tts':{'named_voices':{'voices':['one','two']}}}),
        'ref':NS(id='ref',model_type='audio_tts',checkpoint_ready=True,audio_capabilities={'tts':{'voice_profiles':{'reference_audio':True}}}),
        'missing':NS(id='missing',model_type='audio_tts',checkpoint_ready=False,audio_capabilities={}),
    }
    runtime.model_invocations=NS(model=models.get)
    directory=runtime.messager_bots
    first=directory.create('local','First','Answer')
    second=directory.create('local','Second','Answer')
    return BotVoice(directory,runtime),first['id'],second['id'],models


def test_voice_is_durable_per_bot_owned_and_revision_guarded(runtime):
    voice,first,second,_=setup(runtime)
    assert voice.get('local',first)['mode']=='default'
    settings={'mode':'model','model_id':'named','voice':'two','profile_id':None}
    value=voice.save('local',first,settings,0)
    assert value['revision']==1 and voice.get('local',second)['mode']=='default'
    assert BotVoice(runtime.messager_bots,runtime).get('local',first)==value
    with pytest.raises(PermissionError):voice.get('stranger',first)
    with pytest.raises(PermissionError):voice.save('stranger',first,settings,0)
    with pytest.raises(RuntimeError):voice.save('local',first,settings,0)
    assert voice.save('local',first,{'mode':'default'},1)['model_id'] is None


def test_model_requirements_and_voice_are_checked(runtime):
    voice,first,_,_=setup(runtime)
    for model,preset in [('missing',None),('ref',None),('named','invalid')]:
        with pytest.raises(ValueError):voice.save('local',first,{'mode':'model','model_id':model,'voice':preset},0)
    with pytest.raises(ValueError):voice.save('local',first,{'mode':'default','model_id':'named'},0)


def test_voice_studio_character_ownership_ready_and_missing_model(runtime):
    voice,first,_,models=setup(runtime)
    profiles=ReadAloudRepository(runtime.database,runtime.events)
    profile=profiles.create_voice_profile('local',name='Character',source_type='synthetic_designed',model_id='named',provider_voice_id=None,reference_transcript='',rights_scope={})
    profiles.save_design_profile('local',profile['id'],name='Character',model_id='named',description='Warm voice',text='Hello')
    profiles.attach_design_preview('local',profile['id'],('named','Warm voice','Hello'),{'fixture':True})
    value=voice.save('local',first,{'mode':'profile','profile_id':profile['id']},0)
    assert value['profile_id']==profile['id']
    models['named'].checkpoint_ready=False
    with pytest.raises(ValueError):voice.save('local',first,{'mode':'profile','profile_id':profile['id']},1)
    foreign=profiles.create_voice_profile('stranger',name='Private',source_type='synthetic_designed',model_id='named',provider_voice_id=None,reference_transcript='',rights_scope={})
    from ai2apps.core import RepositoryError
    with pytest.raises(RepositoryError):voice.save('local',first,{'mode':'profile','profile_id':foreign['id']},1)

@pytest.mark.asyncio
async def test_voice_api_validates_and_preserves_revision(runtime):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.messager import create_messager_router
    from ai2apps.identity import RequestPrincipal
    voice,first,second,_=setup(runtime)
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,RequestPrincipal.legacy_local),prefix='/v1/platform')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        path='/v1/platform/messager/bots/'+first+'/voice'
        assert (await c.get(path)).json()['mode']=='default'
        payload={'mode':'model','model_id':'named','voice':'two','revision':0}
        assert (await c.put(path,json=payload)).status_code==200
        assert (await c.get(path+'/playback')).json()['candidates'][0]['source']=='selected'
        assert (await c.post(path+'/used',json={'revision':1})).json()['recorded'] is True
        assert (await c.post(path+'/used',json={'revision':0})).json()['recorded'] is False
        assert (await c.put(path,json=payload)).status_code==409
        assert (await c.put(path,json={**payload,'revision':1,'voice':'invalid'})).status_code==422
        assert (await c.put(path,json={**payload,'revision':1,'endpoint':'https://invalid'})).status_code==422
        assert (await c.get('/v1/platform/messager/bots/foreign/voice')).status_code==404
        assert (await c.get('/v1/platform/messager/bots/'+second+'/voice')).json()['mode']=='default'


def test_playback_prefers_valid_selected_then_last_success_then_default(runtime):
    voice,first,_,models=setup(runtime)
    base={'mode':'model','model_id':'named','voice':'one'}
    voice.save('local',first,base,0)
    assert voice.used('local',first,0)=={'recorded':False}
    assert voice.used('local',first,1)=={'recorded':True}
    voice.save('local',first,{**base,'voice':'two'},1)
    plan=voice.playback('local',first)['candidates']
    assert [c['source'] for c in plan]==['selected','previous','default']
    assert plan[1]['settings']['voice']=='one'
    models['named'].audio_capabilities={'tts':{'named_voices':{'voices':['one']}}}
    plan=voice.playback('local',first)['candidates']
    assert [c['source'] for c in plan]==['previous','default']
    models['named'].checkpoint_ready=False
    assert [c['source'] for c in voice.playback('local',first)['candidates']]==['default']
    with pytest.raises(PermissionError):voice.playback('stranger',first)
    with pytest.raises(PermissionError):voice.used('stranger',first,2)


def test_messager_acpf_declares_only_direct_tts_install_profiles():
    from ai2apps.provisioning.profiles import CapabilityProfileRegistry
    registry=CapabilityProfileRegistry()
    entry=registry.capability('ai2apps.messager','audio.speech_generation')
    assert entry and entry['requirements']['operations']==['speech_generation']
    assert all('/custom-voice-' in p['stack']['checkpoint']['model_id'] for p in entry['profiles'])
    device={'os':'macos','architecture':'arm64','system_memory_gib':128,'accelerator':{'vendor':'apple','api':'metal','unified_memory_gib':128}}
    assert registry.candidates('ai2apps.messager','audio.speech_generation',device,recommended=True)
    assert registry.capability('ai2apps.messager','llm.text') is None
