"""Real Session/Gallery/queue contracts; model inference is a fixture."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
import zipfile
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.api.documents import create_document_router
from ai2apps.chat import ChatRepository
from ai2apps.identity import RequestPrincipal
from ai2apps.gallery import GalleryRepository
from ai2apps.studio import subtitle_aaat as subtitles
from ai2apps.services import ToolCallContext
from test_app_interactions import runtime


def client(runtime,principal):
    app=FastAPI();app.include_router(create_document_router(lambda:runtime,lambda:principal),prefix='/v1/platform')
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://local')


@pytest.mark.asyncio
async def test_upload_gallery_adoption_progress_scope_idempotence_and_deletion(runtime,monkeypatch):
    principal=RequestPrincipal.legacy_local()
    thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='Large video')
    base=f'/v1/platform/sessions/{thread.session.id}/attachments/uploads'
    async with client(runtime,principal) as c:
        start=await c.post(base,json={'filename':'video.mp4','media_type':'video/mp4','size_bytes':6*1024**2})
        assert start.status_code==201,start.text
        uid=start.json()['id'];piece=b'v'*(3*1024**2)
        first=await c.put(base+'/'+uid+'?offset=0',content=piece)
        assert first.json()['received_bytes']==len(piece)
        assert (await c.put(base+'/'+uid+'?offset=0',content=piece)).status_code==409
        assert (await c.post(base+'/'+uid+'/complete')).status_code==409
        assert (await c.put(base+'/'+uid+'?offset='+str(len(piece)),content=piece)).json()['received_bytes']==2*len(piece)
        staging=runtime.documents.root/'pending-uploads'/uid/'source';inode=staging.stat().st_ino
        monkeypatch.setattr(Path,'read_bytes',lambda *args:(_ for _ in ()).throw(AssertionError('whole-file read')))
        result=await c.post(base+'/'+uid+'/complete');assert result.status_code==200,result.text
        item=result.json();assert item['size_bytes']==6*1024**2 and 'path' not in result.text
        assert (await c.post(base+'/'+uid+'/complete')).json()['id']==item['id']
        repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
        asset,path=repo.asset_path(principal.actor_user_id,item['metadata']['gallery_asset_id'])
        assert path.stat().st_ino==inode and not staging.exists()
        assert runtime.documents.source_path(thread.session.id,item['id'])==path
        with runtime.database.transaction(write=True) as db:db.execute("UPDATE gallery_assets SET status='trashed' WHERE id=?",(asset['id'],))
        with pytest.raises(ValueError,match='deleted'):runtime.documents.source_path(thread.session.id,item['id'])
    foreign=replace(principal,actor_user_id='other')
    async with client(runtime,foreign) as c:
        assert (await c.put(base+'/'+uid+'?offset=0',content=b'bad')).status_code in (403,404)


@pytest.mark.asyncio
async def test_upload_bounds_cancel_and_session_fence(runtime):
    principal=RequestPrincipal.legacy_local();chat=ChatRepository(runtime.database,runtime.events)
    one,_=chat.create_thread(title='one');two,_=chat.create_thread(title='two')
    base=f'/v1/platform/sessions/{one.session.id}/attachments/uploads'
    async with client(runtime,principal) as c:
        assert (await c.post(base,json={'filename':'huge.mp4','size_bytes':9*1024**3})).status_code==422
        uid=(await c.post(base,json={'filename':'x.mp4','size_bytes':20})).json()['id']
        assert (await c.put(base+'/'+uid+'?offset=0',content=b'x'*21)).status_code==413
        assert (runtime.documents.root/'pending-uploads'/uid/'source').stat().st_size==0
        wrong=base.replace(one.session.id,two.session.id)
        assert (await c.put(wrong+'/'+uid+'?offset=0',content=b'x')).status_code==404
        assert (await c.post(base+'/'+uid+'/cancel')).json()['status']=='cancelled'
        assert (await c.post(base+'/'+uid+'/complete')).status_code==404


def test_upload_exact_mobile_routes():
    from ai2apps.web.mobile_agent_gateway import business_target,public_path
    from ai2apps.web.owner_agent_gateway import allowed
    uid='a'*32
    for verb,suffix in [('POST',''),('PUT','/'+uid),('POST','/'+uid+'/complete'),('POST','/'+uid+'/cancel')]:
        route='/chat/threads/session/uploads'+suffix
        assert business_target(verb,route)=='/sessions/session/attachments/uploads'+suffix
        assert public_path(verb,'/v1/mobile/agent'+route)
        assert allowed(verb,'/v1/mobile/owner-agent'+route)
    for suffix in ['/'+uid+'/delete','/../../file','/bad']:
        assert business_target('POST','/chat/threads/s/uploads'+suffix) is None


@pytest.mark.asyncio
async def test_subtitle_owner_preserves_missing_configuration_and_uses_path(runtime,monkeypatch,tmp_path):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    monkeypatch.setattr(StudioCapabilityBroker,'_detailed_model_for_profile',lambda *a:None)
    d=await subtitles.descriptor(runtime,RequestPrincipal.legacy_local())
    assert d['configuration_required'] and d['install']['appId']==subtitles.APP
    principal=RequestPrincipal.legacy_local();thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='subtitle')
    path=tmp_path/'source.mp4';path.write_bytes(b'video-fixture')
    attachment=runtime.documents.create_reference(thread.session.id,path,media_type='video/mp4')
    assert subtitles.source(runtime,principal,thread.session.id,attachment.id)[0]==path
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):subtitles.source(runtime,principal,thread.session.id,attachment.id)
    # Without its installed Package, the owner must not be pre-registered by Host.
    assert 'ai2apps.video-studio.video.subtitles' not in runtime.app_capability_router.providers


@pytest.mark.asyncio
async def test_subtitle_submission_uses_durable_queue_and_output_reference(runtime,monkeypatch,tmp_path):
    from ai2apps.studio import video_jobs
    principal=RequestPrincipal.legacy_local();thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='subtitle')
    path=tmp_path/'input.mp4';path.write_bytes(b'fixture')
    attachment=runtime.documents.create_reference(thread.session.id,path,media_type='video/mp4')
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda *a:({'package_id':'fixture.package'}, {'id':subtitles.MINI,'requirements':{'capabilities':[subtitles.CAPABILITY,'audio.detailed_transcription','media.subtitle.export','llm.text']}}))
    monkeypatch.setattr(runtime.extension_manager,'launch_app',lambda *a,**kw:(NS(id='fixture-instance'),None,None))
    workspace=tmp_path/'subtitle.zip'
    with zipfile.ZipFile(workspace,'w') as archive:archive.writestr('subtitles.srt','1\n00:00:00,000 --> 00:00:01,000\n你好\n')
    session=runtime.video_tasks.artifact_session()
    output=runtime.workspace.import_artifact(session,workspace,name='subtitles.zip',media_type='application/zip')
    calls=[]
    def submit(*args,**kwargs):
        calls.append((args,kwargs));return {'id':'job_fixture','run_id':'run_fixture','status':'succeeded','result':{'downloadUrl':f'/v1/platform/sessions/{session}/artifacts/{output.id}/download'}}
    monkeypatch.setattr(video_jobs,'submit_package',submit)
    context=replace(ToolCallContext.from_principal(principal,caller_id='test',session_id=thread.session.id),invocation_id='invocation')
    result=await subtitles.execute(runtime,{'video_id':attachment.id,'target_language':'zh','subtitle_format':'srt','bilingual':True,'burn_in':False},context)
    assert calls[0][0][5]==path and calls[0][1]['key']=='aaat:invocation'
    assert result['status']=='completed' and result['files'][0]['url'].startswith(f'/v1/platform/sessions/{thread.session.id}/')
    assert runtime.workspace.get_artifact(thread.session.id,result['files'][0]['artifact_id']).media_type=='application/zip'


@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['fixture.alpha','package.beta'])
async def test_mobile_generated_file_requires_owned_recorded_success(runtime,monkeypatch,tmp_path,provider):
    from ai2apps.web.mobile_agent_gateway import generated_file
    from fastapi import HTTPException
    principal=RequestPrincipal.legacy_local();thread,_=ChatRepository(runtime.database,runtime.events).create_thread(title='generic output')
    source=tmp_path/'output.srt';source.write_text('subtitle')
    artifact=runtime.workspace.import_artifact(thread.session.id,source,name='output.srt',media_type='application/x-subrip')
    record={'artifact_id':artifact.id,'url':f'/v1/platform/sessions/{thread.session.id}/artifacts/{artifact.id}/download'}
    monkeypatch.setattr(runtime.agents,'get_run',lambda _:NS(id='run',session_id=thread.session.id))
    steps=[NS(kind='tool',status=NS(value='completed'),output={'provider':provider,'files':[record]})]
    monkeypatch.setattr(runtime.agents,'list_steps',lambda _:steps)
    response=await generated_file(runtime,principal,'/files/run/'+artifact.id)
    assert Path(response.path)==runtime.workspace.artifact_path(artifact)
    steps[0].status.value='failed'
    with pytest.raises(HTTPException):await generated_file(runtime,principal,'/files/run/'+artifact.id)
    steps[0].status.value='completed';record['url']='/v1/platform/sessions/foreign/artifacts/'+artifact.id+'/download'
    with pytest.raises(HTTPException):await generated_file(runtime,principal,'/files/run/'+artifact.id)
    with pytest.raises(HTTPException):await generated_file(runtime,replace(principal,actor_user_id='foreign'),'/files/run/'+artifact.id)


def test_subtitle_video_path_validates_and_burns_without_input_whole_read(tmp_path,monkeypatch):
    import importlib.util
    spec=importlib.util.spec_from_file_location('media_fixture',Path(__file__).resolve().parents[2]/'tests/test_ai2apps_studio_media_workflows.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    _video=module._video
    from ai2apps.studio.media_workflows import validate_video_media,burn_subtitles
    source=tmp_path/'video.mp4';source.write_bytes(_video())
    monkeypatch.setattr(Path,'read_bytes',lambda *a:(_ for _ in ()).throw(AssertionError('whole source read')))
    validate_video_media(source)
    result=burn_subtitles(source,[{'start':0,'end':0.8,'text':'hello'}],translations=['你好'],bilingual=True)
    assert result and len(result)>100


@pytest.mark.asyncio
async def test_real_background_subtitle_job_survives_without_client(runtime,monkeypatch,tmp_path):
    import asyncio,json,importlib.util
    from fastapi.responses import JSONResponse
    from ai2apps.studio.capability_broker import StudioCapabilityBroker,MountedMiniApp
    from ai2apps.studio.video_jobs import submit_package
    from ai2apps.studio.repository import StudioRepository
    spec=importlib.util.spec_from_file_location('media_fixture',Path(__file__).resolve().parents[2]/'tests/test_ai2apps_studio_media_workflows.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    principal=RequestPrincipal.legacy_local()
    host,_,_=runtime.extension_manager.launch_app(subtitles.APP,principal=principal)
    declaration={'id':subtitles.MINI,'version':'1','requirements':{'capabilities':[subtitles.CAPABILITY,'audio.detailed_transcription','media.subtitle.export','llm.text']}}
    mounted=MountedMiniApp({'app_instance_id':host.id,'context':{'studioInstanceId':host.id}},declaration,frozenset(declaration['requirements']['capabilities']))
    source=tmp_path/'source.mp4';source.write_bytes(module._video())
    gate=asyncio.Event()
    async def transcription(self,*args,**kw):
        assert kw['content']==source and isinstance(kw['content'],Path)
        await gate.wait()
        return JSONResponse({'segments':[{'start':0,'end':0.8,'text':'Hello'}]})
    async def translation(self,segments,**kw):return ['你好']
    monkeypatch.setattr(StudioCapabilityBroker,'detailed_transcription',transcription)
    monkeypatch.setattr(StudioCapabilityBroker,'_translate_segments',translation)
    job=submit_package(runtime,principal,mounted,subtitles.CAPABILITY,{
        'source_language':None,'target_language':'zh','subtitle_format':'srt','bilingual':True,
        'burn_in':False,'speaker_labels':False,'llm_policy':subtitles.POLICY},source,source.name,'video/mp4',key='background-subtitle')
    await runtime.studio_jobs.startup()
    try:
        for _ in range(100):
            if runtime.studio_jobs.get(job['id'],principal)['status']=='running':break
            await asyncio.sleep(.01)
        # The client and mount are not needed to release/finish this durable worker.
        gate.set()
        for _ in range(300):
            result=runtime.studio_jobs.get(job['id'],principal)
            if result['status'] in ('succeeded','failed','publish_failed'):break
            await asyncio.sleep(.01)
        assert result['status']=='succeeded',result
        with runtime.database.transaction() as db:
            payload=json.loads(db.execute('select request_json from studio_background_jobs where id=?',(job['id'],)).fetchone()[0])
        assert payload['source_reference']['path']==str(source) and not (Path(payload['root'])/'source').exists()
        identifier=result['result']['downloadUrl'].split('/')[-2]
        output=runtime.workspace.get_artifact(runtime.video_tasks.artifact_session(),identifier)
        with zipfile.ZipFile(runtime.workspace.artifact_path(output)) as archive:
            assert '你好' in archive.read('subtitles.srt').decode()
    finally:await runtime.studio_jobs.shutdown()
