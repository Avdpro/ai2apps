import io,json,zipfile
from types import SimpleNamespace
import pytest
from fastapi.responses import Response
from ai2apps.studio.capability_broker import StudioCapabilityBroker,MountedMiniApp
from ai2apps.studio.video_jobs import submit_package
from test_studio_background_jobs import publication_service,principal,wait_status
from test_video_background_jobs import wav

@pytest.mark.parametrize('capability,method', [('audio.source_separation','source_separation'),('audio.detailed_transcription','detailed_transcription'),('audio.speaker_voice_replacement','audio_speaker_replacement')])
async def test_voice_media_survives_unmount_and_publish_retry(tmp_path,monkeypatch,capability,method):
    manager,app=publication_service(tmp_path,'ai2apps.readaloud');runtime=manager.runtime;runtime.studio_jobs=manager
    runtime.extension_manager=SimpleNamespace(require_instance_access=lambda *a:None)
    mini='package.'+method
    mounted=MountedMiniApp({'app_instance_id':app,'context':{'studioInstanceId':app}}, {'id':mini,'version':'1'},frozenset({capability}))
    content=wav()
    if method=='source_separation':
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('vocals.wav',content);z.writestr('background.wav',content)
        content=archive.getvalue()
    elif method=='detailed_transcription':content=json.dumps({'text':'hello','segments':[]}).encode()
    calls=[]
    async def render(self,studio,mount,**kwargs):
        assert studio=='ai2apps.readaloud'
        assert self.mounted_mini_app(studio,mount,principal=kwargs['principal']).declaration['id']==mini
        assert kwargs['content']==b'original input'
        if method=='audio_speaker_replacement':assert kwargs['reference']==b'reference'
        calls.append(1);return Response(content,media_type='application/json' if method=='detailed_transcription' else 'application/octet-stream')
    monkeypatch.setattr(StudioCapabilityBroker,method,render)
    options={'output_format':'markdown'} if method=='detailed_transcription' else {}
    job=submit_package(runtime,principal(),mounted,capability,options,b'original input','sample.wav','audio/wav',b'reference',key='same-request',studio_id='ai2apps.readaloud')
    assert submit_package(runtime,principal(),mounted,capability,options,b'original input','sample.wav','audio/wav',b'reference',key='same-request',studio_id='ai2apps.readaloud')['id']==job['id']
    runtime.extension_manager.mount_entry=lambda *a,**k: (_ for _ in ()).throw(AssertionError('mount destroyed'))
    publish=manager.publish;first=True
    def failing(*args,**kwargs):
        nonlocal first
        result=publish(*args,**kwargs)
        if first:first=False;raise OSError('after publication')
        return result
    manager.publish=failing
    await manager.startup()
    try:
        await wait_status(manager,job['id'],'publish_failed');manager.retry(job['id'],principal())
        await wait_status(manager,job['id'],'succeeded')
        assert calls==[1]
        history=runtime.readaloud_tasks.output_history('owner')
        assert len(history)==(2 if method=='source_separation' else 1)
        assert runtime.readaloud_tasks.output_history('other')==[]
        assert all(x['downloadUrl'] for x in history)
        if method=='detailed_transcription':
            result=manager.get(job['id'],principal())['result']
            assert result['responseUrl'] != result['downloadUrl']
            assert history[0]['mediaType']=='text/markdown'
        with pytest.raises(KeyError):manager.get(job['id'],principal('other'))
    finally:await manager.shutdown()

@pytest.mark.parametrize('capability', ['audio.source_separation','audio.detailed_transcription','audio.speaker_voice_replacement'])
async def test_async_route_accepts_voice_and_validates_consent(monkeypatch,capability):
    import httpx
    from fastapi import FastAPI
    from ai2apps.api.studio_mini_apps import create_studio_mini_app_router
    from test_ai2apps_studio_capability_broker import _runtime
    runtime=_runtime();runtime.studio_jobs=object()
    caps={capability,'audio.detailed_transcription','audio.speaker_diarization','audio.source_separation','audio.voice_conversion'}
    mounted=MountedMiniApp({'app_instance_id':'provider','context':{'studioInstanceId':'host'}},{'id':'package.test','version':'1'},frozenset(caps))
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**kw:mounted)
    submitted=[]
    def submit(*a,**kw):submitted.append((a,kw));return {'id':'job','status':'queued','run_id':'run'}
    monkeypatch.setattr('ai2apps.studio.video_jobs.submit_package',submit)
    app=FastAPI();app.include_router(create_studio_mini_app_router(lambda:runtime,principal_provider=principal))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        url=f'/studios/ai2apps.readaloud/mini-app-mounts/mount/capabilities/{capability}/invoke'
        headers={'Prefer':'respond-async','Idempotency-Key':'voice-test-key'}
        files={'file':('input.wav',wav(),'audio/wav'),'reference':('ref.wav',wav(),'audio/wav')}
        data={'action':'replace','target_speaker':'SPEAKER_00','consent':'true'}
        if capability=='audio.speaker_voice_replacement':
            denied=await client.post(url,headers=headers,files=files,data={**data,'consent':'false'})
            assert denied.status_code==403 and not submitted
        response=await client.post(url,headers=headers,files=files,data=data)
        assert response.status_code==202,response.text
        assert submitted[0][1]['studio_id']=='ai2apps.readaloud'
