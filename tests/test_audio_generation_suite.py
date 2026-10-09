from pathlib import Path
from types import SimpleNamespace
import asyncio
import json
import wave
import pytest
import yaml
import httpx
from fastapi import FastAPI

from ai2apps.packages.contract_v1 import build_package
from ai2apps.extensions.archive import InteractiveArchive
from ai2apps.extensions.models import UnitKind
from ai2apps.identity import RequestPrincipal
from ai2apps.studio import audio_generation as generation
from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError
from ai2apps.api.studio_mini_apps import create_studio_mini_app_router
from ai2apps.provisioning.profiles import CapabilityProfileRegistry
from test_ai2apps_studio_capability_broker import FakeExtensionManager, STUDIO_ID, MOUNT_ID

SOURCE=Path(__file__).resolve().parents[1]/'packages/ai2apps-audio-generation-suite'
CAP='audio.music_generation'
class Extensions(FakeExtensionManager):
    variant = "music"
    capability = CAP
    def mount_entry(self, mount_id, *, principal=None):
        value=super().mount_entry(mount_id,principal=principal)
        value['context']['miniAppId']='ai2apps.audio-generation.'+self.variant
        return value
    def list_studio_mini_apps(self,studio_id,*,principal=None):
        value=dict(super().list_studio_mini_apps(studio_id,principal=principal)[0])
        value['id']='ai2apps.audio-generation.'+self.variant
        value['requirements']={'capabilities':[self.capability]}
        return (value,)


def test_atomic_package_and_profiles(tmp_path):
    manifest=yaml.safe_load((SOURCE/'app.yaml').read_text())
    files={p.relative_to(SOURCE).as_posix() for p in SOURCE.rglob('*') if p.is_file()}
    InteractiveArchive._validate_manifest(UnitKind.APP,manifest,files)
    one=build_package(SOURCE,tmp_path/'one.ai2app')
    two=build_package(SOURCE,tmp_path/'two.ai2app')
    assert one.sha256==two.sha256
    assert len(one.manifest['miniApps'])==3
    assert manifest['navigation']['launcher'] is False
    profiles=CapabilityProfileRegistry()
    assert ('ai2apps.readaloud',CAP) in profiles._capabilities
    assert ('ai2apps.readaloud','audio.sound_effects_generation') in profiles._capabilities
    assert not one.manifest['dependencies']


def fixture(monkeypatch,*,fail=False,song=False,english=True):
    async def completion(self, prompt, **kw):
        assert kw["purpose"] == "work_simple"
        return json.dumps({"prompt": "Polished: " + json.loads(prompt)["description"]})
    monkeypatch.setattr(StudioCapabilityBroker, "_translation_completion", completion)
    model=SimpleNamespace(id='model/music',display_name='Music',model_type='audio_generation',endpoint=None,
        checkpoint_ready=True,endpoints={'audio_generate':'/v1/audio/generations'},metadata={'audio_generation':{'task':'music','minimum_duration':1,'maximum_duration':120,'lyrics':False}})
    monkeypatch.setattr(generation,'list_package_models',lambda runtime:(model,))
    if song:
        model.metadata['audio_generation'].update(lyrics=True,workflow='ai2apps.song-generation/v1',planning_modes=['full','melody','off'],max_semantic_tokens=3000)
    if english:
        model.metadata['audio_generation']['preferred_prompt_language']='en'
    extensions=Extensions()
    if song:
        extensions.variant='song';extensions.capability='audio.song_generation'
    saved=[];invoked=[]
    async def invoke(model_id,operation,payload,target,**kw):
        invoked.append((model_id,operation,payload,kw))
        if kw.get('progress'):
            for phase in ('plan','semantic','synthesis','decode'):
                kw['progress']({'phase':phase})
        if fail:
            from ai2apps.model_invocation import ModelInvocationError
            raise ModelInvocationError('generation_cancelled','cancelled')
        with wave.open(str(target),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b'\0'*176400)
    def save(*args,**kw):
        saved.append((args,kw));return '/v1/platform/sessions/test/artifacts/audio/download'
    runtime=SimpleNamespace(extension_manager=extensions,model_invocations=SimpleNamespace(invoke_background_to_file=invoke),readaloud_tasks=SimpleNamespace(save_studio_output=save))
    app=FastAPI();app.include_router(create_studio_mini_app_router(lambda:runtime,lambda:RequestPrincipal.legacy_local()))
    return app,saved,invoked

@pytest.mark.asyncio
async def test_mount_bound_generation_publishes_host_output(monkeypatch):
    app,saved,invoked=fixture(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        base=f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}'
        models=await c.get(base+'/audio-generation-models',params={'capability':CAP})
        assert models.status_code==200 and models.json()['items'][0]['ready']
        payload={'capability':CAP,'model':'model/music','prompt':'Rain','duration':1.0}
        r=await c.post(base+'/audio-generation',json=payload)
        assert r.status_code==200,r.text
        assert saved[0][1]['mini_app_id']=='ai2apps.audio-generation.music'
        assert invoked[0][1]=='audio_generate'
        for change,status in [({'capability':'audio.sound_effects_generation'},403),({'lyrics':'not supported'},422),({'duration':121},422),({'model':'other'},409),({'output_path':'/tmp/bypass'},422)]:
            r=await c.post(base+'/audio-generation',json=payload|change)
            assert r.status_code==status,r.text
        assert len(saved)==1 and len(invoked)==1

@pytest.mark.asyncio
async def test_cancelled_generation_never_publishes(monkeypatch):
    app,saved,invoked=fixture(monkeypatch,fail=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        r=await c.post(f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/audio-generation',json={'capability':CAP,'model':'model/music','prompt':'Rain','duration':1.0})
        assert r.status_code==499
        assert not saved

@pytest.mark.parametrize('development',[True,False])
def test_actual_suite_source_isolation_and_refresh(tmp_path,monkeypatch,development):
    import shutil
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    repo=tmp_path/'source';(repo/'ai2apps').mkdir(parents=True);(repo/'ai2apps/__init__.py').write_text('')
    source=repo/'packages/audio-suite';shutil.copytree(SOURCE,source,ignore=shutil.ignore_patterns('dist','__pycache__'))
    monkeypatch.setenv('AI2APPS_DEVELOPMENT_SOURCE_ROOT',str(repo))
    if development:monkeypatch.setenv('AI2APPS_ALLOW_DEVELOPMENT_RUNTIME','1')
    else:monkeypatch.delenv('AI2APPS_ALLOW_DEVELOPMENT_RUNTIME',raising=False)
    runtime=PlatformRuntime(PlatformConfig.from_base_path(tmp_path/'data'));runtime.start()
    try:
        mini=[m for m in runtime.extension_manager.list_studio_mini_apps(STUDIO_ID) if m['id'].startswith('ai2apps.audio-generation.')]
        assert len(mini)==(3 if development else 0)
        assert runtime.extension_repository.installed(UnitKind.APP,'ai2apps.audio-generation-suite')==()
        if development:
            for m in mini:
                mount=runtime.extension_manager.mount_studio_mini_app(STUDIO_ID,m['id'])
                instance=mount['app_instance_id']
                path=m['entry']['resource']
                target=runtime.extension_manager.resolve_app_resource(instance,path)
                target.write_text(target.read_text()+'\n<!-- refresh-test -->')
                assert 'refresh-test' in runtime.extension_manager.resolve_app_resource(instance,path).read_text()
    finally:runtime.stop()

@pytest.mark.asyncio
async def test_disconnect_requests_native_cancel_without_output(monkeypatch):
    app,saved,invoked=fixture(monkeypatch)
    runtime=SimpleNamespace(extension_manager=Extensions(),readaloud_tasks=SimpleNamespace(save_studio_output=lambda *a,**k:saved.append(a)))
    observed=[]
    async def invoke(*args,**kwargs):
        for _ in range(20):
            if kwargs['cancel_requested']():
                observed.append(True)
                from ai2apps.model_invocation import ModelInvocationError
                raise ModelInvocationError('generation_cancelled','cancelled')
            await asyncio.sleep(.01)
        raise AssertionError('Disconnect did not request cancellation')
    runtime.model_invocations=SimpleNamespace(invoke_background_to_file=invoke)
    class Disconnected:
        async def is_disconnected(self):return True
    with pytest.raises(StudioCapabilityError) as error:
        await generation.generate(StudioCapabilityBroker(runtime),STUDIO_ID,MOUNT_ID,
            principal=RequestPrincipal.legacy_local(),request=Disconnected(),capability=CAP,
            payload={'model':'model/music','prompt':'Rain','duration':1})
    assert error.value.status_code==499 and not saved

SONG = {'capability':'audio.song_generation','schema':'ai2apps.audio-generation/v2',
        'duration_mode':'auto','model':'model/music','prompt':'Piano song','lyrics':'[Verse]\nHello',
        'generation':{'planning_mode':'full','max_semantic_tokens':250}}

@pytest.mark.asyncio
async def test_song_mount_progress_and_shared_output(monkeypatch):
    app,saved,invoked=fixture(monkeypatch,song=True)
    base=f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        models=await c.get(base+'/audio-generation-models',params={'capability':'audio.song_generation'})
        assert models.json()['items'][0]['planningModes']==['full','melody','off']
        start=await c.post(base+'/invocations',json={'capability':'audio.song_generation'})
        assert start.status_code==201,start.text
        rid=start.json()['id']
        out=await c.post(base+'/audio-generation',json=SONG,headers={'X-AI2Apps-Invocation-ID':rid})
        assert out.status_code==200,out.text
        assert invoked[0][2]['steps']==32 and 'duration' not in invoked[0][2]
        assert saved[0][1]['mini_app_id']=='ai2apps.audio-generation.song'
        assert out.json()['filename']=='song.wav' and out.json()['reachedLimit'] is False
        events=await c.get(base+f'/invocations/{rid}/events')
        assert '"phaseIndex": 3' in events.text and '"status": "completed"' in events.text
        replay=await c.post(base+'/audio-generation',json=SONG,headers={'X-AI2Apps-Invocation-ID':rid})
        assert replay.status_code==404
        for change in ({'duration':30}, {'generation':{'planning_mode':'full','max_semantic_tokens':3001}},
                       {'generation':{'planning_mode':'full'}}, {'generation':{'planning_mode':'off','abc':'X:1','max_semantic_tokens':250}},
                       {'schema':'ai2apps.audio-generation/v1'}, {'capability':CAP}):
            response=await c.post(base+'/audio-generation',json=SONG|change)
            assert response.status_code in (403,422),response.text
        assert len(saved)==1

@pytest.mark.asyncio
async def test_song_limit_warning_and_foreign_progress_rejected(monkeypatch):
    app,saved,invoked=fixture(monkeypatch,song=True)
    base=f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        response=await c.post(base+'/audio-generation',json=SONG,headers={'X-AI2Apps-Invocation-ID':'0'*32})
        assert response.status_code==404 and not invoked
        response=await c.post(base+'/audio-generation',json=SONG|{'generation':{'max_semantic_tokens':25}})
        assert response.status_code==200 and response.json()['reachedLimit']


def test_song_filter_and_acpf_targets(monkeypatch):
    fixture(monkeypatch)
    assert generation.generation_models(None,'audio.song_generation')==()
    fixture(monkeypatch,song=True)
    assert generation.generation_models(None,CAP)==()
    profile=yaml.safe_load((SOURCE.parents[1]/'ai2apps/provisioning/profiles/audio-generation.yaml').read_text())['capabilities']['audio.song_generation']
    assert len(profile['profiles'])==1
    assert profile['profiles'][0]['stack']['provider']['package_id']=='ai2apps/model-yue2-mlx'
    assert profile['profiles'][0]['stack']['runtime']['version']=='>=1.8.10,<2.0.0'

@pytest.mark.asyncio
async def test_prompt_preparation_every_request_and_lyrics_preserved(monkeypatch):
    app, saved, invoked = fixture(monkeypatch, song=True)
    calls = []
    async def completion(self, prompt, **kw):
        calls.append((json.loads(prompt), kw['purpose']))
        return json.dumps({'prompt': 'A large crowd applauding enthusiastically.'})
    monkeypatch.setattr(StudioCapabilityBroker, '_translation_completion', completion)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        for prompt in ('雷鸣般的掌声', 'Loud applause'):
            response = await c.post(f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/audio-generation', json=SONG|{'prompt':prompt})
            assert response.status_code == 200, response.text
            assert response.json()['preparedPrompt'] == 'A large crowd applauding enthusiastically.'
    assert len(calls) == 2 and all(x[1] == 'work_simple' for x in calls)
    assert [x[0]['description'] for x in calls] == ['雷鸣般的掌声','Loud applause']
    assert all(x[2]['lyrics'] == SONG['lyrics'] for x in invoked)
    assert all(x[2]['prompt'] == 'A large crowd applauding enthusiastically.' for x in invoked)

@pytest.mark.asyncio
@pytest.mark.parametrize('response', ['broken', '{}', '{"prompt":""}', json.dumps({'prompt':'x'*2001})])
async def test_invalid_preparation_never_invokes_audio(monkeypatch, response):
    app, saved, invoked = fixture(monkeypatch)
    async def completion(*args, **kw): return response
    monkeypatch.setattr(StudioCapabilityBroker, '_translation_completion', completion)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        r=await c.post(f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/audio-generation',json={'capability':CAP,'model':'model/music','prompt':'Rain','duration':1})
    assert r.status_code == 502 and not invoked and not saved

@pytest.mark.asyncio
async def test_cancel_during_prompt_preparation(monkeypatch):
    cancelled=asyncio.Event();started=asyncio.Event();finished=asyncio.Event()
    async def completion(*args, **kw):
        started.set()
        try: await asyncio.Event().wait()
        finally: finished.set()
    job=asyncio.create_task(generation.prepare_prompt(SimpleNamespace(_translation_completion=completion), 'Rain',task=CAP, principal=None,mounted=None,request=None,cancelled=cancelled))
    await started.wait();cancelled.set()
    with pytest.raises(StudioCapabilityError) as error: await job
    assert error.value.status_code == 499 and finished.is_set()

@pytest.mark.asyncio
async def test_simple_task_missing_configuration_is_explicit():
    purposes=[]
    def resolve(purpose): purposes.append(purpose); return None
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=Extensions(), model_manager=SimpleNamespace(resolve_default_model=resolve)))
    with pytest.raises(StudioCapabilityError) as error:
        await broker._translation_completion('test',system='test',principal=None,mounted=None,request=None,purpose='work_simple')
    assert purposes == ['work_simple'] and error.value.status_code == 409

@pytest.mark.asyncio
async def test_task_failure_does_not_fall_back_to_original(monkeypatch):
    app,saved,invoked=fixture(monkeypatch)
    async def completion(*args, **kw):
        raise StudioCapabilityError('translation_not_ready','Configure Simple Task',status_code=409)
    monkeypatch.setattr(StudioCapabilityBroker,'_translation_completion',completion)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        r=await c.post(f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/audio-generation',json={'capability':CAP,'model':'model/music','prompt':'Rain','duration':1})
    assert r.status_code == 409 and not invoked and not saved

@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 502])
async def test_simple_task_real_asgi_gateway_contract(status):
    from fastapi import Request
    from fastapi.responses import JSONResponse
    seen=[]
    app=FastAPI()
    @app.post('/v1/chat/completions')
    async def completion(request:Request):
        seen.append(await request.json())
        if status == 502:
            return JSONResponse({'detail':{'code':'AI_PROVIDER_ERROR','message':'private upstream diagnostic'}},status_code=502)
        return {'choices':[{'message':{'content':'{"prompt":"Enthusiastic applause"}'}}]}
    broker=StudioCapabilityBroker(SimpleNamespace(extension_manager=Extensions(),model_manager=SimpleNamespace(resolve_default_model=lambda p:'cloud/openai/gpt-5.6-luna')))
    request=SimpleNamespace(app=app,headers={})
    if status == 502:
        with pytest.raises(StudioCapabilityError) as error:
            await broker._translation_completion('雷鸣般的掌声',system='Translate',principal=None,mounted=None,request=request,purpose='work_simple')
        assert 'AI_PROVIDER_ERROR' in str(error.value)
        assert 'private upstream diagnostic' not in str(error.value)
    else:
        result=await broker._translation_completion('雷鸣般的掌声',system='Translate',principal=None,mounted=None,request=request,purpose='work_simple')
        assert json.loads(result)['prompt']=='Enthusiastic applause'
    assert seen[0]['model']=='cloud/openai/gpt-5.6-luna'
    assert 'temperature' not in seen[0]

@pytest.mark.asyncio
async def test_model_without_language_preference_preserves_chinese(monkeypatch):
    app,saved,invoked=fixture(monkeypatch,english=False)
    async def forbidden(*args,**kwargs): raise AssertionError('Should not call a Task model')
    monkeypatch.setattr(StudioCapabilityBroker,'_translation_completion',forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        r=await c.post(f'/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/audio-generation',json={'capability':CAP,'model':'model/music','prompt':'舒缓的中文民谣','duration':1})
    assert r.status_code==200,r.text
    assert invoked[0][2]['prompt']=='舒缓的中文民谣'
    assert r.json()['preparedPrompt']=='舒缓的中文民谣'
