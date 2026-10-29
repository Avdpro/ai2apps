"""Owner adapter/real queue regressions. Model inference is explicitly a fixture."""
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
from types import SimpleNamespace as NS
import wave
import av
import pytest
from fastapi.responses import JSONResponse,Response
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext
from ai2apps.chat import ChatRepository
from ai2apps.studio import video_localization_aaat as owner
from ai2apps.studio.capability_broker import StudioCapabilityBroker
from legacy_package_backend_fixture import runtime
from test_video_processing_aaat import video


def setup(runtime,tmp_path,monkeypatch):
    principal=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Video localization')
    ctx=replace(ToolCallContext.from_principal(principal,caller_id='test',session_id=thread.session.id),invocation_id='video-analysis')
    path=tmp_path/'source.mp4';video(path)
    item=runtime.documents.create_reference(ctx.session_id,path,media_type='video/mp4')
    caps={owner.DUB,owner.REPLACE,owner.voice_aaat.REPLACE,owner.voice_aaat.TRANSCRIBE,owner.voice_aaat.DIARIZE,'audio.voice_conversion','audio.source_separation','audio.speech_generation','audio.voice_clone','llm.text','media.audio.extract','media.video.audio_mux'}
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda app,mini,principal:({'package_id':'fixture.suite'},{'id':mini,'version':'1','requirements':{'capabilities':sorted(caps)}}))
    monkeypatch.setattr(owner.voice_aaat,'readiness',lambda _:({'dialogue_background'},{'timbre_fast'},True))
    monkeypatch.setattr(owner,'catalog',lambda *a:([{'id':'character','name':'Owned','ready':True}],[{'id':'clone','name':'Declared','ready':True}],True))
    monkeypatch.setattr(StudioCapabilityBroker,'_character_profile_and_model',lambda self,id,**kw: ({},None) if id=='character' else (_ for _ in ()).throw(ValueError('Not owned')))
    # Real host launch creates the scope needed by submit_package; provider can use that host.
    original=runtime.extension_manager.launch_app
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda app,**kw:original(owner.APP if app=='fixture.suite' else app,**kw))
    return ctx,path,item


@pytest.mark.asyncio
@pytest.mark.parametrize('mode',['dub','analyze','replace'])
async def test_real_queue_original_refs_shared_output_and_exact_replay(runtime,tmp_path,monkeypatch,mode):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch);calls=[]
    refpath=tmp_path/'ref.wav';refpath.write_bytes(b'reference fixture')
    ref=runtime.documents.create_reference(ctx.session_id,refpath,media_type='audio/wav')
    async def infer(self,*a,**kw):
        calls.append(kw);assert kw['content']==path
        if kw.get('action')=='analyze':return JSONResponse({'segments':[{'speaker':'speaker_0','text':'Hello'}]})
        if mode=='replace':assert kw['reference']==refpath
        # Model fixture returns a real decodable video, queue and publication are real.
        return Response(path.read_bytes(),media_type='video/mp4')
    monkeypatch.setattr(StudioCapabilityBroker,'video_audio_translation',infer)
    monkeypatch.setattr(StudioCapabilityBroker,'video_speaker_replacement',infer)
    await runtime.studio_jobs.startup()
    try:
        if mode=='dub':
            tool='video.dub';args={'video_id':item.id,'target_language':'zh','voice_profile_id':owner.ORIGINAL,'voice_clone_model_id':'clone','single_narrator':True,'consent':True}
        else:
            tool='video.replace_speaker';args={'media_id':item.id,'action':'analyze'}
            if mode=='replace':
                analyzed=await runtime.app_capability_router.invoke(tool,args,ctx)
                assert analyzed['speakers']==[{'id':'speaker_0','sample':'Hello','segments':1}]
                args.update(action='replace',analysis_id=analyzed['analysis_id'],target_speaker='speaker_0',reference_id=ref.id,consent=True)
                ctx=replace(ctx,invocation_id='video-replace')
        result=await runtime.app_capability_router.invoke(tool,args,ctx)
        again=await runtime.app_capability_router.invoke(tool,args,ctx)
        assert result['studio_job_id']==again['studio_job_id']
        assert len(calls)==(2 if mode=='replace' else 1)
        expected='application/json' if mode=='analyze' else 'video/mp4'
        assert result['files'][0]['media_type']==expected
        artifact=runtime.workspace.get_artifact(ctx.session_id,result['files'][0]['artifact_id'])
        if mode!='analyze':
            with av.open(str(runtime.workspace.artifact_path(artifact))) as media:assert len(list(media.decode(video=0)))==10
        with runtime.database.transaction() as db:
            payload=json.loads(db.execute('SELECT request_json FROM studio_background_jobs WHERE id=?',(result['studio_job_id'],)).fetchone()[0])
        published=runtime.studio_jobs.get(result['studio_job_id'],RequestPrincipal.legacy_local())
        assert runtime.video_tasks.artifact_session() in published['result']['downloadUrl']
        assert payload['source_reference'] and not (Path(payload['root'])/'source').exists()
        if mode=='replace':assert payload['reference_reference'] and not (Path(payload['root'])/'reference').exists()
        path.write_bytes(b'changed source')
        with pytest.raises(Exception):await runtime.app_capability_router.invoke(tool,args,ctx)
    finally:await runtime.studio_jobs.shutdown()


@pytest.mark.asyncio
async def test_preflight_consent_model_scope_and_missing_configuration(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch)
    args={'video_id':item.id,'target_language':'en','voice_profile_id':'character','single_narrator':True,'consent':True}
    for bad in [{'consent':False},{'single_narrator':False},{'voice_profile_id':owner.ORIGINAL},{'voice_clone_model_id':'clone'},{'voice_profile_id':'foreign'}]:
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.dub',{**args,**bad},ctx)
    other,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Other')
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.dub',args,replace(ctx,session_id=other.session.id))
    available=await owner.descriptor(runtime,RequestPrincipal.legacy_local())
    assert not available['configuration_required']
    voice=next(f for f in available['fields'] if f['key']=='voice_profile_id')
    assert voice['options'][0]['label']=='Owned'
    assert voice['options'][-1]['label']['zh']=='临时克隆原声'
    monkeypatch.setattr(owner,'catalog',lambda *a:([],[],False))
    d=await owner.descriptor(runtime,RequestPrincipal.legacy_local())
    assert d['configuration_required'] and d['install']['appId']==owner.APP
    assert d['effective_schema']['properties']['video_id']['x-ai2apps-asset']['references']
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.dub',args,ctx)
    with runtime.database.transaction() as db:assert db.execute('SELECT COUNT(*) FROM studio_background_jobs').fetchone()[0]==0


def test_path_remux_preserves_frames_and_adds_audio(tmp_path):
    from ai2apps.studio.media_workflows import replace_video_audio
    path=tmp_path/'source.mp4';video(path)
    buf=io.BytesIO()
    with wave.open(buf,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(48000);w.writeframes(b'\0\0'*48000)
    result=replace_video_audio(path,buf.getvalue())
    with av.open(io.BytesIO(result)) as media:
        assert len(list(media.decode(video=0)))==10
    with av.open(io.BytesIO(result)) as media:assert sum(f.samples for f in media.decode(audio=0))>=48000

@pytest.mark.asyncio
async def test_video_evidence_is_source_session_and_workflow_bound(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch)
    from ai2apps.studio import voice_aaat
    voice_aaat.observation_table(runtime)
    identity={'media_id':item.id,'reference':voice_aaat.describe_source(path)}
    with runtime.database.transaction() as db:
        db.execute('INSERT INTO voice_speaker_observations VALUES (?,?,?,?,?,?)',('audio-analysis',ctx.actor_user_id,ctx.installation_id,ctx.session_id,json.dumps(identity),json.dumps([{'id':'speaker_0'}])))
    refpath=tmp_path/'reference.wav';refpath.write_bytes(b'reference')
    ref=runtime.documents.create_reference(ctx.session_id,refpath,media_type='audio/wav')
    args={'media_id':item.id,'action':'replace','analysis_id':'audio-analysis','target_speaker':'speaker_0','reference_id':ref.id,'consent':True}
    with pytest.raises(Exception,match='changed'):await runtime.app_capability_router.invoke('video.replace_speaker',args,ctx)
    identity['workflow']='video-speaker-replacement'
    with runtime.database.transaction() as db:db.execute('UPDATE voice_speaker_observations SET source=? WHERE id=?',(json.dumps(identity),'audio-analysis'))
    for bad in [{'target_speaker':'invented'},{'consent':False},{'analysis_id':'missing'}]:
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('video.replace_speaker',{**args,**bad},ctx)
    path.write_bytes(b'source changed')
    with pytest.raises(Exception,match='changed'):await runtime.app_capability_router.invoke('video.replace_speaker',args,ctx)
    with runtime.database.transaction() as db:assert db.execute('SELECT COUNT(*) FROM studio_background_jobs').fetchone()[0]==0


@pytest.mark.asyncio
@pytest.mark.parametrize('changed',['source','reference'])
async def test_media_changed_during_video_job_never_publishes(runtime,tmp_path,monkeypatch,changed):
    from ai2apps.studio.capability_broker import MountedMiniApp
    from ai2apps.studio.video_jobs import submit_package
    ctx,path,item=setup(runtime,tmp_path,monkeypatch)
    principal=RequestPrincipal.legacy_local()
    host,_,_=runtime.extension_manager.launch_app(owner.APP,principal=principal)
    declaration={'id':owner.REPLACE_MINI,'requirements':{'capabilities':[owner.REPLACE]}}
    mount=MountedMiniApp({'app_instance_id':host.id,'context':{'studioInstanceId':host.id}},declaration,frozenset({owner.REPLACE}))
    reference=tmp_path/'reference.wav';reference.write_bytes(b'reference')
    async def process(self,*a,**kw):
        (path if changed=='source' else reference).write_bytes(b'changed')
        return Response(b'generated video')
    monkeypatch.setattr(StudioCapabilityBroker,'video_speaker_replacement',process)
    job=submit_package(runtime,principal,mount,owner.REPLACE,{'action':'replace'},path,path.name,'video/mp4',reference,key='changed-'+changed,studio_id=owner.APP)
    await runtime.studio_jobs.startup()
    try:
        for _ in range(300):
            final=runtime.studio_jobs.get(job['id'],principal)
            if final['status'] in ('succeeded','failed','publish_failed'):break
            await asyncio.sleep(.01)
        assert final['status']=='failed' and 'changed' in str(final['error'])
        assert not final.get('result',{}).get('downloadUrl')
    finally:await runtime.studio_jobs.shutdown()


@pytest.mark.asyncio
async def test_missing_conversion_is_form_preflight_not_uncertain_execution(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch)
    monkeypatch.setattr(owner.voice_aaat,'readiness',lambda _:({'dialogue_background'},set(),True))
    descriptor=await owner.descriptor(runtime,RequestPrincipal.legacy_local(),replacement=True)
    assert not descriptor['configuration_required']  # Analysis needs no converter.
    assert descriptor['effective_schema']['properties']['action']['enum']==['analyze']
    assert descriptor['install']['capability']==owner.REPLACE
    assert len(descriptor['warnings'])==2
    with pytest.raises(Exception) as error:
        await runtime.app_capability_router.invoke('video.replace_speaker',{'media_id':item.id,'action':'replace','analysis_id':'saved','target_speaker':'speaker_0','reference_id':'saved-reference','consent':True},ctx)
    assert error.value.details['phase']=='prepare'
    assert error.value.code=='parameter_contract_mismatch'
    with runtime.database.transaction() as db:assert db.execute('SELECT COUNT(*) FROM studio_background_jobs').fetchone()[0]==0
