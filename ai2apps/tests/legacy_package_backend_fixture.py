"""Explicit SDK/back-end unit fixtures, not installed Package acceptance.

Historical owner tests exercise durable native queues with controlled inference.
They opt into the former adapters here only; production startup never registers
these declarations. Signed Package discovery/lifecycle is tested independently.
"""
import pytest
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime

@pytest.fixture
def runtime(tmp_path,monkeypatch):
    from ai2apps.services import builtin_apps
    original=builtin_apps.install;captured=[]
    def capture(runtime):
        register=original(runtime);captured.append(register);return register
    monkeypatch.setattr(builtin_apps,'install',capture)
    value=PlatformRuntime(PlatformConfig.from_base_path(tmp_path));value.start()
    register=captured[0]
    original_providers=set(value.app_capability_router.providers)
    from ai2apps.studio import package_generation_aaat,voice_aaat,video_localization_aaat,subtitle_aaat,package_hosts
    from ai2apps.browser import shopping_aaat,travel_aaat
    for owner in (package_generation_aaat,voice_aaat,video_localization_aaat,subtitle_aaat,shopping_aaat,travel_aaat):
        owner.install(value,register)
    from ai2apps.services.builtin_apps import detailed_transcription, obj, string
    schema=obj({'audio_artifact_id':{**string(), 'x-ai2apps-asset':{'storage':'artifact','accept':'audio/*,video/*','references':True}},
        'profile':{'enum':['compact','quality'],'default':'compact'},'language':{'type':'string','maxLength':32},
        'word_timestamps':{'type':'boolean','default':True},'diarization':{'type':'boolean','default':True},
        'output_format':{'enum':['json','markdown','srt'],'default':'json'}},['audio_artifact_id'])
    register('voice.detailed_transcription','ai2apps.readaloud','详细转写 / Detailed transcription','Fixture SDK transcription',schema,
        lambda a,c:detailed_transcription(value,a,c),mini='ai2apps.media-voice.transcription',effects=('artifact.create',),selection_required=True,field_labels={k:{'zh':z,'en':e} for k,z,e in [('audio_artifact_id','音频或视频','Audio or video'),('profile','转写方案','Transcription profile'),('language','语言','Language'),('word_timestamps','逐词时间戳','Word timestamps'),('diarization','区分说话人','Speaker diarization'),('output_format','输出格式','Output format')]},form_summary={'zh':'SDK 转写测试','en':'SDK transcription fixture'})
    package_hosts.install(value)
    from ai2apps.research.search_form import install as search_form
    search_form(value)
    yield value
    for key in set(value.app_capability_router.providers)-original_providers:
        value.app_capability_router.unregister(key)
    value.stop()
