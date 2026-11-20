"""Owner model setup contracts; no model inference or installation is performed."""
from types import SimpleNamespace as NS

import pytest

from ai2apps.studio import package_sdk, package_generation_aaat, subtitle_aaat, voice_aaat


@pytest.mark.asyncio
@pytest.mark.parametrize('host,mode,capability', [
    ('ai2apps.readaloud','separate','audio.source_separation'),
    ('ai2apps.readaloud','replace_audio','audio.speaker_voice_replacement'),
    ('ai2apps.video-studio','separate','audio.source_separation'),
    ('ai2apps.video-studio','replace_video','media.video_speaker_voice_replacement'),
])
async def test_media_setup_stays_with_validated_placement(monkeypatch,host,mode,capability):
    monkeypatch.setattr(voice_aaat,'readiness',lambda runtime:(set(),set(),True))
    if mode=='replace_video':
        from ai2apps.studio import video_localization_aaat
        async def video_descriptor(runtime,principal,model=None,*,replacement=False):
            assert replacement and model=='replace'
            return await voice_aaat.descriptor(runtime,principal,replacement=True,action=model)
        monkeypatch.setattr(video_localization_aaat,'descriptor',video_descriptor)
    descriptor=await package_sdk.media_descriptor(None,None,'replace' if mode.startswith('replace') else None,
        {'id':'fixture.mini'},{'host':host,'options':{'mode':mode}})
    assert descriptor['install']=={'appId':host,'capability':capability,'requirements':{}}
    assert descriptor['configuration_required']
    if mode.startswith('replace'):
        assert descriptor['model_field']=='action'
        assert descriptor['missing_requirements']==['dialogue_background_separation','voice_conversion']


@pytest.mark.asyncio
async def test_frozen_time_checks_selected_geometry_and_meridian(monkeypatch):
    from ai2apps.studio.frozen_time_pipeline import DEPTH_MODELS,MERIDIAN
    ready={DEPTH_MODELS['da'],MERIDIAN}
    runtime=NS(model_invocations=NS(model=lambda identifier:NS(
        checkpoint_ready=identifier in ready,
        capabilities=['depth_estimation'] if identifier in DEPTH_MODELS.values() else ['video_generation'])))
    default=await package_generation_aaat.frozen_descriptor(runtime,None)
    da=await package_generation_aaat.frozen_descriptor(runtime,None,'da')
    assert default['configuration_required']
    assert default['missing_requirements']==['geometry:vggt']
    assert default['install']['capability']=='image.frozen_time.vggt'
    assert da['model_field']=='depth' and not da['configuration_required']
    assert da['install']['capability']=='image.frozen_time.da'


@pytest.mark.asyncio
async def test_subtitle_missing_route_does_not_offer_speech_install(monkeypatch):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    monkeypatch.setattr(StudioCapabilityBroker,'_detailed_model_for_profile',lambda self,profile:NS())
    monkeypatch.setattr('ai2apps.task_llm.resolve_task_model',lambda *a,**kw:None)
    result=await subtitle_aaat.descriptor(NS(extension_manager=NS()),None)
    assert result['configuration_required']
    assert result['missing_requirements']==['standard_task_model_route']
    assert result['install'] is None


def test_dubbing_catalog_initializes_real_broker(monkeypatch):
    from ai2apps.studio import video_localization_aaat
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    monkeypatch.setattr(StudioCapabilityBroker,'character_catalog',lambda self,**kw:{'items':[{'id':'voice','ready':True,'name':'Voice'}]})
    monkeypatch.setattr(StudioCapabilityBroker,'clone_model_catalog',lambda self:{'items':[{'id':'clone','ready':True,'name':'Clone'}]})
    monkeypatch.setattr(voice_aaat,'readiness',lambda runtime:({'dialogue_background'},set(),True))
    monkeypatch.setattr('ai2apps.task_llm.resolve_task_model',lambda *a,**kw:'fixture.model')
    characters,clones,ready=video_localization_aaat.catalog(NS(extension_manager=NS()),None)
    assert ready and characters[0]['id']=='voice' and clones[0]['id']=='clone'


@pytest.mark.asyncio
async def test_speaker_analysis_installs_only_transcription(monkeypatch):
    monkeypatch.setattr(voice_aaat,'readiness',lambda runtime:(set(),set(),False))
    for host,mode in [('ai2apps.readaloud','replace_audio'),('ai2apps.video-studio','replace_video')]:
        if mode=='replace_video':
            from ai2apps.studio import video_localization_aaat
            async def video_descriptor(runtime,principal,model=None,*,replacement=False):
                return await voice_aaat.descriptor(runtime,principal,replacement=replacement,action=model)
            monkeypatch.setattr(video_localization_aaat,'descriptor',video_descriptor)
        result=await package_sdk.media_descriptor(None,None,'analyze',{'id':'fixture.mini'},
            {'host':host,'options':{'mode':mode}})
        assert result['install']['appId']==host
        assert result['install']['capability']=='audio.detailed_transcription'
        assert result['missing_requirements']==['detailed_transcription']


def test_studio_text_probe_reflects_standard_route(monkeypatch):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    runtime=NS(extension_manager=NS())
    declaration={'id':'fixture.video','requirements':{'capabilities':['llm.text']}}
    broker=StudioCapabilityBroker(runtime)
    monkeypatch.setattr('ai2apps.task_llm.resolve_task_model',lambda *a,**kw:None)
    missing=broker.probe_declaration('ai2apps.video-studio',declaration)
    assert missing['items'][0]['ready'] is False
    monkeypatch.setattr('ai2apps.task_llm.resolve_task_model',lambda *a,**kw:'fixture.model')
    configured=broker.probe_declaration('ai2apps.video-studio',declaration)
    assert configured['items'][0]['ready'] is True
