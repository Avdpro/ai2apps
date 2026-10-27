from pathlib import Path
from dataclasses import replace
import io
import wave
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.api.documents import create_document_router
from ai2apps.chat import ChatRepository
from ai2apps.core import ResourceNotFoundError
from ai2apps.identity import RequestPrincipal
from test_app_interactions import runtime


def session(runtime):return ChatRepository(runtime.database,runtime.events).create_thread(title='References')[0].session.id


def test_sparse_large_reference_never_reads_hashes_or_copies_source(runtime,tmp_path,monkeypatch):
    sid=session(runtime);source=tmp_path/'large.mp4'
    with source.open('wb') as output:output.truncate(3*1024**3)
    def forbidden(*a,**kw):raise AssertionError('whole-file loading forbidden')
    monkeypatch.setattr(Path,'read_bytes',forbidden)
    item=runtime.documents.create_reference(sid,source,media_type='video/mp4')
    assert item.size_bytes==3*1024**3 and item.sha256==''
    assert runtime.documents.source_path(sid,item.id)==source
    assert source.stat().st_blocks<100
    assert all(p.stat().st_size<4096 for p in runtime.documents.root.rglob('*') if p.is_file())
    assert str(source) not in str(item.metadata)
    with pytest.raises(ResourceNotFoundError):runtime.documents.source_path(session(runtime),item.id)
    with pytest.raises(ValueError,match='compatible App'):runtime.documents.blocks(sid,item.id)
    assert runtime.documents.reference_status(sid,item.id)['available']


def test_reference_survives_reopen_and_detects_modification_move_and_symlink(runtime,tmp_path):
    from ai2apps.documents import DocumentRepository
    sid=session(runtime);source=tmp_path/'notes.txt';source.write_text('alpha')
    item=runtime.documents.create_reference(sid,source)
    reopened=DocumentRepository(runtime.database,runtime.config.paths)
    assert reopened.source_path(sid,item.id)==source
    assert 'alpha' in '\n'.join(b.text for b in reopened.blocks(sid,item.id))
    source.write_text('bravo')
    assert not reopened.reference_status(sid,item.id)['available']
    with pytest.raises(ValueError,match='changed'):reopened.blocks(sid,item.id)
    fresh=reopened.create_reference(sid,source);source.rename(tmp_path/'moved.txt')
    assert not reopened.reference_status(sid,fresh.id)['available']
    target=tmp_path/'moved.txt';link=tmp_path/'selected.txt';link.symlink_to(target)
    linked=reopened.create_reference(sid,link)
    other=tmp_path/'other.txt';other.write_text('other');link.unlink();link.symlink_to(other)
    with pytest.raises(ValueError,match='changed'):reopened.source_path(sid,linked.id)


@pytest.mark.asyncio
async def test_reference_api_owner_scope_remote_denial_and_stream_upload(runtime,tmp_path):
    principal=RequestPrincipal.legacy_local();sid=session(runtime)
    app=FastAPI();app.include_router(create_document_router(lambda:runtime,lambda:principal),prefix='/v1/platform')
    path=tmp_path/'a.bin';path.write_bytes(b'fixture')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        base=f'/v1/platform/sessions/{sid}/attachments'
        r=await client.post(base+'/reference',json={'source_path':str(path)})
        assert r.status_code==201,r.text
        identifier=r.json()['id'];assert str(path) not in r.text
        assert (await client.get(base+'/'+identifier+'/content')).content==b'fixture'
        uploaded=await client.post(base+'/upload',files={'file':('clip.mp4',b'uploaded-once','video/mp4')})
        assert uploaded.status_code==201,uploaded.text
        record=runtime.documents.get(sid,uploaded.json()['id'])
        assert record.size_bytes==13 and record.metadata['storage']=='reference'
        principal=replace(principal,client_scope='mobile')
        denied=await client.post(base+'/reference',json={'source_path':str(path)})
        assert denied.status_code==403
        path.write_bytes(b'changed')
        assert (await client.get(base+'/'+identifier+'/content')).status_code==409


def test_audio_reference_decodes_by_path_without_read_bytes(tmp_path,monkeypatch):
    from ai2apps.audio_codecs import decode_audio_to_wav
    source=tmp_path/'audio.wav'
    with wave.open(str(source),'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(b'\x00\x00'*160)
    monkeypatch.setattr(Path,'read_bytes',lambda *a: (_ for _ in ()).throw(AssertionError('must stream source')))
    result=decode_audio_to_wav(source,input_format='wav')
    assert result.startswith(b'RIFF')


def test_studio_reference_rejects_changed_source_without_copy(tmp_path):
    from ai2apps.studio.source_reference import describe,resolve
    source=tmp_path/'video.mp4';source.write_bytes(b'input')
    ref=describe(source);assert resolve(ref)==source
    source.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):resolve(ref)


def test_video_job_submission_preserves_native_source_without_staging_copy(runtime,tmp_path,monkeypatch):
    from types import SimpleNamespace
    from ai2apps.studio.video_jobs import submit_media
    root=tmp_path/'jobs';root.mkdir();source=tmp_path/'selected.mp4'
    with source.open('wb') as output:output.truncate(2*1024**3)
    seen=[]
    jobs=SimpleNamespace(root=root,submit=lambda **kw:seen.append(kw) or kw,for_run=lambda *a:None)
    monkeypatch.setattr(runtime,'studio_jobs',jobs)
    result=submit_media(runtime,RequestPrincipal.legacy_local(),{'app_instance_id':'studio-instance'},{'id':'run','miniAppId':'video'},operation='extract',payload={},sources={'source':({'name':'selected'},source)})
    assert not list(root.rglob('*.mp4'))
    assert result['payload']['sources']['source']['reference']['path']==str(source)
    assert not any(p.is_file() for p in root.rglob('*'))
