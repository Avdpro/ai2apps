import asyncio
import io
import json
import wave
from types import SimpleNamespace
import pytest
from fastapi.responses import Response
from ai2apps.studio.repository import StudioRepository
from ai2apps.studio.video_jobs import submit_media, submit_package, STUDIO_ID
from test_studio_background_jobs import publication_service, principal, wait_status


def setup(tmp_path, mini='ai2apps.video.extract-audio'):
    manager, app = publication_service(tmp_path, STUDIO_ID)
    runtime = manager.runtime;runtime.studio_jobs=manager
    from ai2apps.storage.repositories import SessionRepository
    session=SessionRepository(manager.database).create(app_instance_id=app,title='Video')
    runtime.video_tasks=SimpleNamespace(artifact_session=lambda:session.id)
    runtime.extension_manager=SimpleNamespace(require_instance_access=lambda *a:None)
    scope=dict(actor_id='owner',installation_id='installation',app_instance_id=app,studio_id=STUDIO_ID)
    run=StudioRepository(manager.database).create_run(**scope,mini_app_id=mini,mini_app_version='1',placement='inline',title='Test',input_data={})
    return manager,scope,run


def wav():
    data=io.BytesIO()
    with wave.open(data,'wb') as stream:
        stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(8000);stream.writeframes(b'\0\0'*800)
    return data.getvalue()


async def test_closed_page_with_valid_original_reference_still_publishes_and_reopens(tmp_path):
    manager,scope,run=setup(tmp_path)
    source=tmp_path/'source.wav';source.write_bytes(wav())
    job=submit_media(manager.runtime,principal(),scope,run,operation='extract',
        payload={'filename':'extracted.wav','kind':'audio','media_type':'audio/wav'},sources={'source':({},source)})
    # Closing the page does not remove the original referenced input.
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        reopened=StudioRepository(manager.database).list_runs(**scope)
        assert len(reopened)==1 and len(reopened[0]['artifacts'])==1
        artifact=reopened[0]['artifacts'][0]
        assert artifact['kind']=='audio'
        ref=artifact['metadata']
        saved=manager.runtime.workspace.get_artifact(ref['workspaceSessionId'],ref['workspaceArtifactId'])
        assert manager.runtime.workspace.artifact_path(saved).read_bytes().startswith(b'RIFF')
        assert not (manager.root/('video-input-'+run['id'])).exists()
    finally:await manager.shutdown()


async def test_publication_retry_never_renders_twice(tmp_path,monkeypatch):
    manager,scope,run=setup(tmp_path)
    source=tmp_path/'source.wav';source.write_bytes(wav());calls=[]
    def render(source,target):calls.append(source);target.write_bytes(wav());return {}
    monkeypatch.setattr('ai2apps.video.audio_extraction.extract_audio_to_wav',render)
    job=submit_media(manager.runtime,principal(),scope,run,operation='extract',
        payload={'filename':'output.wav','kind':'audio','media_type':'audio/wav'},sources={'source':({},source)})
    publish=manager.publish
    manager.publish=lambda *a,**k:(_ for _ in ()).throw(OSError('disk full'))
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'publish_failed')
        manager.publish=publish;manager.retry(job['id'],principal())
        await wait_status(manager,job['id'],'succeeded')
        assert len(calls)==1
        assert len(StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts'])==1
    finally:await manager.shutdown()


async def test_package_mount_gone_publishes_to_host_scope(tmp_path,monkeypatch):
    manager,scope,_=setup(tmp_path)
    from ai2apps.studio.capability_broker import MountedMiniApp, StudioCapabilityBroker
    mounted=MountedMiniApp({'id':'mount','app_instance_id':scope['app_instance_id'],
        'context':{'studioInstanceId':scope['app_instance_id']}},
        {'id':'package.dubbing','version':'1'},frozenset({'media.video_audio_translation'}))
    captured=[]
    async def render(self,studio,mount,**options):
        captured.append(self.mounted_mini_app(studio,mount,principal=options['principal']))
        assert not await options['request'].is_disconnected()
        return Response(b'fake mp4',media_type='video/mp4')
    monkeypatch.setattr(StudioCapabilityBroker,'video_audio_translation',render)
    job=submit_package(manager.runtime,principal(),mounted,'media.video_audio_translation',{},b'input','video.mp4','video/mp4')
    manager.runtime.extension_manager.mount_entry=lambda *a,**k:(_ for _ in ()).throw(AssertionError('mount gone'))
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        run=StudioRepository(manager.database).get_run(job['run_id'],**scope)
        assert run['miniAppId']=='package.dubbing' and run['status']=='succeeded'
        assert run['artifacts'][0]['mediaType']=='video/mp4'
        assert len(captured)==1
        with pytest.raises(KeyError):manager.get(job['id'],principal('other'))
    finally:await manager.shutdown()


async def test_join_clips_is_persistent_and_publishes_one_shared_output(tmp_path):
    from test_ai2apps_video_composer import media_file
    manager,scope,run=setup(tmp_path,'ai2apps.video.composer')
    first=tmp_path/'first.mp4';second=tmp_path/'second.mp4'
    media_file(first);media_file(second,color=160)
    job=submit_media(manager.runtime,principal(),scope,run,operation='join',
        payload={'filename':'joined.mp4','kind':'video','media_type':'video/mp4'},
        sources={'0':({},first),'1':({},second)})
    # Referenced clips remain at their original paths; no staging copies.
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        result=StudioRepository(manager.database).get_run(run['id'],**scope)
        assert len(result['artifacts'])==1 and result['artifacts'][0]['kind']=='video'
        ref=result['artifacts'][0]['metadata']
        artifact=manager.runtime.workspace.get_artifact(ref['workspaceSessionId'],ref['workspaceArtifactId'])
        import av
        with av.open(str(manager.runtime.workspace.artifact_path(artifact))) as video:
            assert len(list(video.decode(video.streams.video[0])))>12
    finally:await manager.shutdown()


async def test_subtitle_preview_and_zip_are_both_durable_and_idempotent(tmp_path,monkeypatch):
    import zipfile
    manager,scope,_=setup(tmp_path)
    from ai2apps.studio.capability_broker import MountedMiniApp, StudioCapabilityBroker
    mounted=MountedMiniApp({'id':'gone','app_instance_id':scope['app_instance_id'],
        'context':{'studioInstanceId':scope['app_instance_id']}},
        {'id':'package.subtitles','version':'1'},frozenset({'media.video_subtitles'}))
    async def render(*a,**k):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('subtitled-video.mp4',b'video');z.writestr('subtitles.srt','hello')
        return Response(out.getvalue())
    monkeypatch.setattr(StudioCapabilityBroker,'video_subtitles',render)
    args=(manager.runtime,principal(),mounted,'media.video_subtitles',{'burn_in':True},b'input','in.mp4','video/mp4')
    job=submit_package(*args,key='request-123')
    assert submit_package(*args,key='request-123')['id']==job['id']
    with pytest.raises(ValueError):submit_package(*args[:-3],b'changed','in.mp4','video/mp4',key='request-123')
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        run=StudioRepository(manager.database).get_run(job['run_id'],**scope)
        assert [a['kind'] for a in run['artifacts']]==['video','file']
        assert manager.get(job['id'],principal())['result']['downloadUrl'].endswith('/download')
    finally:await manager.shutdown()


async def test_queued_video_cancel_can_explicitly_retry_frozen_input(tmp_path):
    manager,scope,run=setup(tmp_path)
    source=tmp_path/'source.wav';source.write_bytes(wav())
    job=submit_media(manager.runtime,principal(),scope,run,operation='extract',
        payload={'filename':'retry.wav','kind':'audio','media_type':'audio/wav'},sources={'source':({},source)})
    manager.cancel(job['id'],principal())
    assert manager.get(job['id'],principal())['status']=='cancelled'
    manager.retry(job['id'],principal())
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        assert len(StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts'])==1
    finally:await manager.shutdown()


@pytest.mark.parametrize('capability,method,content,options,expected',[
 ('audio.source_separation','source_separation',b'zip',{'profile':'quality'},'application/zip'),
 ('audio.detailed_transcription','detailed_transcription',b'{"segments":[{"start":0,"end":1,"text":"hello"}]}',{'output_format':'srt'},'application/json'),
])
async def test_video_audio_tools_publish_without_live_frame(tmp_path,monkeypatch,capability,method,content,options,expected):
    manager,scope,_=setup(tmp_path)
    from ai2apps.studio.capability_broker import MountedMiniApp, StudioCapabilityBroker
    mounted=MountedMiniApp({'id':'gone','app_instance_id':scope['app_instance_id'],
        'context':{'studioInstanceId':scope['app_instance_id']}},{'id':'package.audio','version':'1'},frozenset({capability}))
    async def render(*a,**k):return Response(content)
    monkeypatch.setattr(StudioCapabilityBroker,method,render)
    job=submit_package(manager.runtime,principal(),mounted,capability,options,b'input','in.mp4','video/mp4')
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'succeeded')
        run=StudioRepository(manager.database).get_run(job['run_id'],**scope)
        assert run['artifacts'][-1]['mediaType']==expected
        if method=='detailed_transcription':assert run['artifacts'][0]['name']=='transcript.srt'
    finally:await manager.shutdown()


async def test_identical_media_outputs_have_independent_retention(tmp_path):
    manager,scope,run=setup(tmp_path)
    source=tmp_path/'source.wav';source.write_bytes(wav())
    repository=StudioRepository(manager.database)
    other=repository.create_run(**scope,mini_app_id=run['miniAppId'],mini_app_version='1',placement='inline',title='Other',input_data={})
    jobs=[submit_media(manager.runtime,principal(),scope,item,operation='extract',
        payload={'filename':'same.wav','kind':'audio','media_type':'audio/wav'},sources={'source':({},source)}) for item in (run,other)]
    await manager.startup()
    try:
        for job in jobs:await wait_status(manager,job['id'],'succeeded')
        outputs=[repository.get_run(item['id'],**scope)['artifacts'][0] for item in (run,other)]
        assert outputs[0]['sourceId'] != outputs[1]['sourceId']
        repository.delete_run(run['id'],workspace=manager.runtime.workspace,**scope)
        metadata=outputs[1]['metadata']
        artifact=manager.runtime.workspace.get_artifact(metadata['workspaceSessionId'],metadata['workspaceArtifactId'])
        assert manager.runtime.workspace.artifact_path(artifact).exists()
    finally:await manager.shutdown()


async def test_removed_original_reference_fails_explicitly_without_output(tmp_path):
    manager,scope,run=setup(tmp_path)
    source=tmp_path/'source.wav';source.write_bytes(wav())
    job=submit_media(manager.runtime,principal(),scope,run,operation='extract',
        payload={'filename':'removed.wav','kind':'audio','media_type':'audio/wav'},sources={'source':({},source)})
    source.unlink()
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'failed')
        final=manager.get(job['id'],principal())
        assert 'unavailable' in str(final.get('error')) or 'moved' in str(final.get('error'))
        assert StudioRepository(manager.database).get_run(run['id'],**scope)['artifacts']==[]
    finally:await manager.shutdown()
