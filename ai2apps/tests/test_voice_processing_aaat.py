"""Voice owner integration; inference fixtures, real IDs/queue/publication."""
import asyncio
from dataclasses import replace
import io
import json
from pathlib import Path
from types import SimpleNamespace as NS
import zipfile
import pytest
from fastapi.responses import Response,JSONResponse
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.services import ToolCallContext
from ai2apps.studio import voice_aaat as owner
from ai2apps.studio.capability_broker import StudioCapabilityBroker,MountedMiniApp
from ai2apps.studio.video_jobs import submit_package
from legacy_package_backend_fixture import runtime


def setup(runtime,tmp_path,monkeypatch):
    principal=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='voice')
    ctx=replace(ToolCallContext.from_principal(principal,caller_id='test',session_id=thread.session.id),invocation_id='audio-1')
    path=tmp_path/'input.wav';path.write_bytes(b'audio fixture')
    attachment=runtime.documents.create_reference(thread.session.id,path,media_type='audio/wav')
    monkeypatch.setattr(owner,'readiness',lambda _:({'vocals_instrumental','dialogue_background'},{'timbre_fast'},True))
    def declaration(app,mini,principal):return {'package_id':'fixture.suite'},{'id':mini,'version':'1','requirements':{'capabilities':[owner.SEPARATE,owner.REPLACE,owner.TRANSCRIBE,owner.DIARIZE,'audio.voice_conversion']}}
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',declaration)
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda app,**kw:(NS(id=app),None,None))
    return ctx,path,attachment


def publish(runtime,tmp_path,content,name,media):
    url=runtime.readaloud_tasks.save_studio_output('local',content,mini_app_id=owner.REPLACE_MINI,filename=name,media_type=media)
    return {'id':'job-analysis','run_id':'run-analysis','status':'succeeded','result':{'downloadUrl':url}}


@pytest.mark.asyncio
async def test_separation_uses_owned_original_path_and_shared_output(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch);seen=[]
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as z:z.writestr('vocals.wav',b'fixture')
    result_job=publish(runtime,tmp_path,archive.getvalue(),'stems.zip','application/zip')
    track=publish(runtime,tmp_path,b'fixture wav','vocals.wav','audio/wav')
    result_job['result']['tracks']=[{'downloadUrl':track['result']['downloadUrl']}]
    def submit(*args,**kwargs):seen.append((args,kwargs));return result_job
    monkeypatch.setattr('ai2apps.studio.video_jobs.submit_package',submit)
    # The handler must never load source bytes at submission time.
    original=Path.read_bytes
    def no_source(self):
        if self==path:raise AssertionError('source whole-file read')
        return original(self)
    monkeypatch.setattr(Path,'read_bytes',no_source)
    result=await runtime.app_capability_router.invoke('voice.separate',{'media_id':item.id},ctx)
    assert result['app_id']==owner.APP and result['mini_app_id']==owner.SEPARATE_MINI
    assert seen[0][0][5]==path and seen[0][0][4]=={'profile':'vocals_instrumental'}
    assert seen[0][1]['key']=='aaat:audio-1' and result['files'][0]['media_type']=='application/zip'
    assert result['files'][1]['media_type']=='audio/wav'
    assert runtime.workspace.get_artifact(ctx.session_id,result['files'][1]['artifact_id']).name.endswith('vocals.wav')
    other,_=ChatRepository(runtime.database,runtime.events).create_thread(title='other')
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('voice.separate',{'media_id':item.id},replace(ctx,session_id=other.session.id))
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('voice.separate',{'media_id':item.id,'profile':'invented'},ctx)
    assert len(seen)==1


@pytest.mark.asyncio
async def test_analyze_then_replace_requires_exact_evidence_consent_and_reference(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch);seen=[]
    data={'segments':[{'start':0,'end':1,'speaker':'SPEAKER_00','text':'Hello'}, {'start':1,'end':2,'speaker':'SPEAKER_01','text':'Hi'}]}
    def submit(*args,**kwargs):
        seen.append((args,kwargs))
        return publish(runtime,tmp_path,json.dumps(data).encode(),'speakers.json','application/json') if args[4]['action']=='analyze' else publish(runtime,tmp_path,b'fixture wav','mixed.wav','audio/wav')
    monkeypatch.setattr('ai2apps.studio.video_jobs.submit_package',submit)
    result=await runtime.app_capability_router.invoke('voice.replace_speaker',{'media_id':item.id,'action':'analyze'},ctx)
    assert [s['id'] for s in result['speakers']]==['SPEAKER_00','SPEAKER_01']
    reference=tmp_path/'ref.wav';reference.write_bytes(b'reference fixture')
    ref=runtime.documents.create_reference(ctx.session_id,reference,media_type='audio/wav')
    args={'media_id':item.id,'action':'replace','analysis_id':result['analysis_id'],'target_speaker':'SPEAKER_01','reference_id':ref.id,'consent':True}
    for bad in [{'consent':False},{'target_speaker':'made_up'},{'analysis_id':'foreign'}]:
        with pytest.raises(Exception):await runtime.app_capability_router.invoke('voice.replace_speaker',{**args,**bad},replace(ctx,invocation_id='replace'))
    assert len(seen)==1
    replaced=await runtime.app_capability_router.invoke('voice.replace_speaker',args,replace(ctx,invocation_id='replace'))
    assert seen[-1][0][5]==path and seen[-1][0][8]==reference
    assert seen[-1][0][4]['target_speaker']=='SPEAKER_01' and replaced['files'][0]['media_type']=='audio/wav'
    foreign=replace(ctx,session_id='other')
    with pytest.raises(Exception):owner.observation(runtime,foreign,result['analysis_id'],{'media_id':item.id,'reference':owner.describe_source(path)})
    path.write_bytes(b'changed input')
    with pytest.raises(Exception,match='changed'):await runtime.app_capability_router.invoke('voice.replace_speaker',args,ctx)
    assert len(seen)==2


@pytest.mark.asyncio
async def test_missing_models_preserve_setup_and_reject_before_submit(runtime,tmp_path,monkeypatch):
    ctx,path,item=setup(runtime,tmp_path,monkeypatch)
    monkeypatch.setattr(owner,'readiness',lambda _:(set(),set(),False))
    for replacement in (False,True):
        d=await owner.descriptor(runtime,RequestPrincipal.legacy_local(),replacement=replacement)
        assert d['configuration_required'] and d['install']['appId']==owner.APP
        assert d['effective_schema']['properties']['media_id']['x-ai2apps-asset']['references']
    with pytest.raises(Exception,match='configuration'):await runtime.app_capability_router.invoke('voice.separate',{'media_id':item.id},ctx)
    with pytest.raises(Exception):await owner.execute(runtime,{'media_id':item.id},replace(ctx,invocation_id=None))


@pytest.mark.asyncio
@pytest.mark.parametrize('action',['analyze','replace','separate'])
async def test_background_original_references_publication_idempotence_and_source_changes(runtime,tmp_path,monkeypatch,action):
    # Real Studio queue and shared output, no mount or client after acceptance.
    principal=RequestPrincipal.legacy_local()
    host,_,_=runtime.extension_manager.launch_app(owner.APP,principal=principal)
    cap=owner.SEPARATE if action=='separate' else owner.REPLACE
    declaration={'id':owner.SEPARATE_MINI if action=='separate' else owner.REPLACE_MINI,'version':'1','requirements':{'capabilities':[cap]}}
    mounted=MountedMiniApp({'app_instance_id':host.id,'context':{'studioInstanceId':host.id}},declaration,frozenset({cap}))
    path=tmp_path/'source.wav';path.write_bytes(b'original')
    reference=tmp_path/'reference.wav';reference.write_bytes(b'reference')
    gate=asyncio.Event();calls=[]
    async def process(self,*a,**kw):
        calls.append(kw)
        assert kw['content']==path
        if action=='replace':assert kw['reference']==reference
        await gate.wait()
        if action=='analyze':return JSONResponse({'segments':[{'speaker':'SPEAKER_00','text':'Hello'}]})
        import wave
        buf=io.BytesIO()
        with wave.open(buf,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*160)
        if action=='separate':
            z=io.BytesIO()
            with zipfile.ZipFile(z,'w') as out:out.writestr('vocals.wav',buf.getvalue());out.writestr('instrumental.wav',buf.getvalue())
            return Response(z.getvalue())
        return Response(buf.getvalue(),media_type='audio/wav')
    monkeypatch.setattr(StudioCapabilityBroker,'source_separation' if action=='separate' else 'audio_speaker_replacement',process)
    options={'profile':'vocals_instrumental'} if action=='separate' else {'action':action}
    kw=dict(key='voice-reference-'+action,studio_id=owner.APP)
    ref=reference if action=='replace' else None
    job=submit_package(runtime,principal,mounted,cap,options,path,path.name,'audio/wav',ref,**kw)
    assert submit_package(runtime,principal,mounted,cap,options,path,path.name,'audio/wav',ref,**kw)['id']==job['id']
    with runtime.database.transaction() as db:payload=json.loads(db.execute('SELECT request_json FROM studio_background_jobs WHERE id=?',(job['id'],)).fetchone()[0])
    assert not (Path(payload['root'])/'source').exists() and not (Path(payload['root'])/'reference').exists()
    await runtime.studio_jobs.startup()
    try:
        for _ in range(300):
            if calls:break
            await asyncio.sleep(.01)
        gate.set()
        for _ in range(300):
            final=runtime.studio_jobs.get(job['id'],principal)
            if final['status'] in ('succeeded','failed','publish_failed'):break
            await asyncio.sleep(.01)
        assert final['status']=='succeeded',final
        assert len(calls)==1
        history=runtime.readaloud_tasks.output_history('local')
        assert history and all(h['miniAppId'].startswith('ai2apps.media-voice.') for h in history)
        if action=='analyze':assert any(h['mediaType']=='application/json' for h in history)
        path.write_bytes(b'changed after submit')
        with pytest.raises(ValueError,match='different'):submit_package(runtime,principal,mounted,cap,options,path,path.name,'audio/wav',ref,**kw)
    finally:await runtime.studio_jobs.shutdown()

@pytest.mark.asyncio
@pytest.mark.parametrize('changed',['source','reference'])
async def test_changed_reference_during_execution_never_publishes_success(runtime,tmp_path,monkeypatch,changed):
    principal=RequestPrincipal.legacy_local()
    host,_,_=runtime.extension_manager.launch_app(owner.APP,principal=principal)
    declaration={'id':owner.REPLACE_MINI,'requirements':{'capabilities':[owner.REPLACE]}}
    mounted=MountedMiniApp({'app_instance_id':host.id,'context':{'studioInstanceId':host.id}},declaration,frozenset({owner.REPLACE}))
    path=tmp_path/'source.wav';path.write_bytes(b'original')
    reference=tmp_path/'ref.wav';reference.write_bytes(b'reference')
    async def process(self,*args,**kw):
        (path if changed=='source' else reference).write_bytes(b'modified')
        return Response(b'generated')
    monkeypatch.setattr(StudioCapabilityBroker,'audio_speaker_replacement',process)
    job=submit_package(runtime,principal,mounted,owner.REPLACE,{'action':'replace'},path,path.name,'audio/wav',reference,key='changed-'+changed,studio_id=owner.APP)
    await runtime.studio_jobs.startup()
    try:
        for _ in range(300):
            final=runtime.studio_jobs.get(job['id'],principal)
            if final['status'] in ('succeeded','failed','publish_failed'):break
            await asyncio.sleep(.01)
        assert final['status']=='failed' and 'changed' in str(final['error'])
        assert not runtime.readaloud_tasks.output_history('local')
    finally:await runtime.studio_jobs.shutdown()
