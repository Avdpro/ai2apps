from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.responses import Response

from ai2apps.events import EventNotificationBus, EventStore
from ai2apps.readaloud import ReadAloudRepository, ReadAloudTaskManager
from ai2apps.readaloud.tasks import ReadAloudRenderError
from ai2apps.storage import PlatformDatabase


def _fixture(tmp_path: Path, *, gateway=None):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database, EventNotificationBus())
    repository = ReadAloudRepository(database, events)
    project = repository.create_project(
        "user-1",
        title="Chapter one",
        purpose="private",
        source_rights="user_owned",
        source_text="",
    )
    first = repository.create_segment(
        "user-1",
        project["id"],
        speaker_id=None,
        text="First line",
        emotion="neutral",
        emotion_strength=1,
        speed=1,
        pause_after_ms=200,
    )
    second = repository.create_segment(
        "user-1",
        project["id"],
        speaker_id=None,
        text="Second line",
        emotion="calm",
        emotion_strength=1,
        speed=0.9,
        pause_after_ms=300,
    )
    model = SimpleNamespace(
        id="example.tts/default",
        upstream_id="example-upstream",
        model_type="audio_tts",
        checkpoint_ready=True,
        service_key="example.tts",
        endpoint="http://127.0.0.1:8100",
        metadata={},
        endpoints={"audio_speech": "/v1/audio/speech"},
        internal_headers={},
    )

    class Manager(ReadAloudTaskManager):
        def _model(self, model_id):
            if model_id != model.id:
                raise ReadAloudRenderError("model_not_found", "missing", status_code=404)
            return model

        async def _invoke(self, job_id, segment_id, _model, request, _owner_user_id):
            if gateway is not None:
                return await super()._invoke(
                    job_id, segment_id, _model, request, _owner_user_id
                )
            target = self.root / job_id / f"{segment_id}.wav"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(request["input"].encode())
            return target

    manager = Manager(
        runtime=SimpleNamespace(model_invocations=gateway),
        database=database,
        root=tmp_path / "renders",
    )
    return database, project, (first, second), manager


@pytest.mark.asyncio
async def test_batch_render_uses_transparent_background_model_gateway(tmp_path):
    captured = []

    class Gateway:
        async def invoke_background_json(
            self, model_id, operation, payload, *, request_id=None
        ):
            captured.append(
                {
                    "model_id": model_id,
                    "operation": operation,
                    "payload": payload,
                    "request_id": request_id,
                }
            )
            return Response(content=payload["input"].encode())

    _database, project, segments, manager = _fixture(
        tmp_path, gateway=Gateway()
    )
    await manager.startup()
    created = await manager.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    for _ in range(100):
        job = manager.get(created["id"], owner_user_id="user-1")
        if job["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Read Aloud render did not finish")

    assert job["project_revision"] == 3
    assert job["completed_segments"] == 2
    assert [item["status"] for item in job["segments"]] == ["succeeded", "succeeded"]
    assert len(captured) == 2
    assert all(item["operation"] == "audio_speech" for item in captured)
    assert all(item["model_id"] == "example.tts/default" for item in captured)
    assert [
        (manager.root / item["output_path"]).read_text() for item in job["segments"]
    ] == [segment["text"] for segment in segments]
    await manager.shutdown()


@pytest.mark.asyncio
async def test_cancelled_render_cancels_queued_scheduler_attempt(tmp_path):
    queued = asyncio.Event()
    cancelled = {}

    class Gateway:
        async def invoke_background_json(self, *_args, **_options):
            queued.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled["value"] = True
                raise

    _database, project, _segments, manager = _fixture(
        tmp_path, gateway=Gateway()
    )
    await manager.startup()
    created = await manager.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    await asyncio.wait_for(queued.wait(), timeout=1)

    job = await manager.cancel(created["id"], owner_user_id="user-1")

    assert cancelled["value"] is True
    assert job["status"] == "cancelled"
    assert {item["status"] for item in job["segments"]} == {"cancelled"}
    await manager.shutdown()


@pytest.mark.asyncio
async def test_restart_resumes_incomplete_render_from_segment_boundary(tmp_path):
    database, project, _segments, creator = _fixture(tmp_path)
    created = await creator.create(
        owner_user_id="user-1",
        project_id=project["id"],
        model_id="example.tts/default",
    )
    with database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE readaloud_render_jobs SET status='running' WHERE id=?",
            (created["id"],),
        )
        connection.execute(
            "UPDATE readaloud_render_segments SET status='running' "
            "WHERE job_id=? AND ordinal=0",
            (created["id"],),
        )
    resumed = type(creator)(
        runtime=creator.runtime,
        database=database,
        root=creator.root,
    )
    await resumed.startup()
    for _ in range(100):
        job = resumed.get(created["id"], owner_user_id="user-1")
        if job["status"] == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        pytest.fail("Recovered Read Aloud render did not finish")
    assert job["completed_segments"] == 2
    await resumed.shutdown()


@pytest.mark.asyncio
async def test_render_delete_removes_outputs_but_preserves_project(tmp_path):
    from ai2apps.core import ResourceNotFoundError
    database, project, segments, manager = _fixture(tmp_path)
    created = await manager.create(owner_user_id='user-1',project_id=project['id'],model_id='example.tts/default')
    with pytest.raises(ReadAloudRenderError) as error:
        manager.delete(created['id'],owner_user_id='user-1')
    assert error.value.status_code==409
    with database.transaction(write=True) as connection:
        connection.execute("UPDATE readaloud_render_jobs SET status='failed' WHERE id=?",(created['id'],))
    root=manager.root/created['id'];root.mkdir(exist_ok=True);(root/'sample.wav').write_bytes(b'audio')
    with pytest.raises(ResourceNotFoundError):
        manager.delete(created['id'],owner_user_id='other')
    manager.delete(created['id'],owner_user_id='user-1')
    assert not root.exists()
    with database.transaction() as connection:
        assert connection.execute('SELECT id FROM readaloud_projects WHERE id=?',(project['id'],)).fetchone()
    with pytest.raises(ResourceNotFoundError):
        manager.get(created['id'],owner_user_id='user-1')


@pytest.mark.asyncio
async def test_audiobook_uses_bound_clone_model_and_private_merged_reference(tmp_path):
    from io import BytesIO
    import wave
    from ai2apps.readaloud.materials import VoiceMaterials
    captured=[]
    class Gateway:
        async def invoke_background_multipart(self, model_id, operation, *, data, files, **options):
            captured.append((model_id,data,files))
            return Response(content=b'audio')
    database,project,segments,manager=_fixture(tmp_path,gateway=Gateway())
    manager.runtime.config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path/'artifacts'))
    base_model=manager._model('example.tts/default')
    clone=SimpleNamespace(id='clone/base',audio_capabilities={'tts':{'voice_profiles':{'mode':'native','reference_transcript':'required'}}},weights={})
    manager._model=lambda model_id: clone if model_id=='clone/base' else base_model
    output=BytesIO()
    with wave.open(output,'wb') as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000);wav.writeframes(b'\0\0'*1600)
    store=VoiceMaterials(database,tmp_path/'artifacts')
    samples=[]
    for text in ['First reference','Second reference']:
        asset=store.save('user-1',output.getvalue(),'reference.wav','audio/wav')
        samples.append({'asset_id':asset['id'],'transcript':text,'selected':True,'confirmed':True})
    repo=ReadAloudRepository(database)
    voice=repo.create_voice_profile('user-1',name='Clone',source_type='self_voice',model_id=clone.id,provider_voice_id=None,reference_transcript='First reference',rights_scope={},training={'samples':samples,'model_revision':''})
    speaker=repo.create_character('user-1',project['id'],name='Speaker',description='',voice_profile_id=voice['id'])
    repo.update_segment('user-1',project['id'],segments[0]['id'],{'speaker_id':speaker['id'],'speed':1.5,'emotion':'happy'})
    await manager.startup()
    try:
        created=await manager.create(owner_user_id='user-1',project_id=project['id'],model_id=base_model.id,segment_ids=[segments[0]['id']])
        for _ in range(100):
            job=manager.get(created['id'],owner_user_id='user-1')
            if job['status'] in {'failed','succeeded'}:break
            await asyncio.sleep(.01)
        assert job['status']=='succeeded',job
        model,data,files=captured[0]
        assert model==clone.id
        assert 'speed' not in data
        assert 'style' not in data
        assert 'emotion' not in data
        assert data['ref_text']=='First reference\nSecond reference'
        with wave.open(BytesIO(files['reference_audio'][1])) as wav:assert wav.getnframes()==3200
        assert job['segments'][0]['request']['model']==clone.id
    finally:
        await manager.shutdown()


def test_studio_render_artifact_does_not_reference_agent_run(tmp_path):
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.chat import ChatRepository
    import json

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / 'runtime'))
    runtime.start()
    try:
        session = ChatRepository(runtime.database, runtime.events).create_thread(title='Audio artifact test')[0].session
        model = SimpleNamespace(service_key='audio.speech_generation')
        manager = ReadAloudTaskManager(runtime=runtime, database=runtime.database,
                                      root=tmp_path / 'renders', workspace=runtime.workspace)
        manager._artifact_session = lambda owner: session.id
        manager._model = lambda model_id: model
        output = tmp_path / 'output.wav'
        output.write_bytes(b'RIFF-test-audio')
        job = {'id': 'strun_render_test', 'owner_user_id': 'local',
               'model_id': 'test/tts', 'model_revision': 'rev1',
               'mini_app_id': 'audiobook', 'placement': 'main'}
        artifact = manager._materialize_artifact(job, {'ordinal': 0, 'segment_id': 'segment-test'}, output)
        with runtime.database.transaction() as connection:
            row = connection.execute('SELECT run_id, metadata_json FROM artifacts WHERE id=?', (artifact.id,)).fetchone()
            assert row['run_id'] is None
            assert json.loads(row['metadata_json'])['runId'] == job['id']
            assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
        assert artifact.session_id == session.id
    finally:
        runtime.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize('emotion,expected', [('whisper', None), ('angry', {'emotion': 'angry', 'emotion_strength': 1.0}), ('neutral', None)])
async def test_unsupported_emotion_uses_natural_delivery(tmp_path, emotion, expected):
    captured = []
    class Gateway:
        async def invoke_background_json(self, model_id, operation, payload, **options):
            captured.append(payload)
            return Response(content=b'audio')
    _, _, _, manager = _fixture(tmp_path, gateway=Gateway())
    model = manager._model('example.tts/default')
    model.audio_capabilities = {'tts': {'emotion': {'mode': 'native', 'values': ['angry']}}}
    request = {'input': 'Hello', 'speed': 1, 'emotion': emotion}
    await manager._invoke('job-emotion', 'segment-emotion', model, request, 'user-1')
    assert captured[0].get('style') == expected
    assert request['emotion'] == emotion


@pytest.mark.asyncio
async def test_line_audio_cache_matches_configuration_and_survives_reload(tmp_path):
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    from ai2apps.chat import ChatRepository
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / 'runtime'))
    runtime.start()
    try:
        session = ChatRepository(runtime.database, runtime.events).create_thread(title='Audio cache')[0].session
        repo = ReadAloudRepository(runtime.database, runtime.events)
        project = repo.create_project('local', title='Book', purpose='private', source_rights='user_owned', source_text='')
        line = repo.create_segment('local', project['id'], speaker_id=None, text='Hello', emotion='neutral', emotion_strength=1, speed=1, pause_after_ms=300)
        model = SimpleNamespace(id='test/tts', service_key='audio.speech_generation', metadata={}, revision='v1')
        manager = ReadAloudTaskManager(runtime=runtime, database=runtime.database, root=tmp_path/'renders', workspace=runtime.workspace)
        manager._artifact_session = lambda owner: session.id
        manager._model = lambda model_id: model
        async def synth(job_id, segment_id, model, request, owner):
            output = manager.root/job_id/(segment_id+'.wav')
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b'audio')
            return output
        manager._invoke = synth
        job = await manager.create(owner_user_id='local', project_id=project['id'], model_id=model.id)
        await manager._run(job['id'])
        args = ('local', project['id'], line['id'], model.id)
        assert manager.cached_segment(*args)['url'].endswith('model_id=test%2Ftts')
        repo.update_segment('local', project['id'], line['id'], {'speed': 1.2})
        assert manager.cached_segment(*args) is None
        repo.update_segment('local', project['id'], line['id'], {'speed': 1})
        assert manager.cached_segment(*args)
        model.revision = 'v2'
        assert manager.cached_segment(*args) is None
        model.revision = 'v1'
        artifact_id = manager.get(job['id'], owner_user_id='local')['segments'][0]['artifact_id']
        runtime.workspace.retire_artifact(session.id, artifact_id)
        assert manager.cached_segment(*args)
        manager.delete(job['id'], owner_user_id='local')
        assert not (manager.root/job['id']).exists()
        assert manager.cached_segment(*args)
        assert manager.line_audio_path(*args).read_bytes() == b'audio'
        assert manager._matching_output('local', project['id'], line['id'], manager._segment_request(dict(line, voice_model_id=None, voice_training_json='{}', provider_voice_id=None, speaker_revision=None), model.id)).is_file()
        cast = repo.create_character('local', project['id'], name='Narrator', description='', voice_profile_id=None)
        repo.update_segment('local', project['id'], line['id'], {'speaker_id': cast['id']})
        job = await manager.create(owner_user_id='local', project_id=project['id'], model_id=model.id)
        await manager._run(job['id'])
        assert manager.cached_segment(*args)
        updated = repo.edit_character('local', project['id'], cast['id'], changes={'name':'Renamed', 'description':'Warm', 'voice_profile_id':None})
        assert updated['segments'][0]['review_status'] == 'needs_review'
        assert manager.cached_segment(*args) is None
        repo.update_segment('local', project['id'], line['id'], {'review_status':'approved'})
        job = await manager.create(owner_user_id='local', project_id=project['id'], model_id=model.id)
        await manager._run(job['id'])
        assert manager.cached_segment(*args)
        from ai2apps.core import RepositoryError
        with pytest.raises(RepositoryError):
            repo.edit_character('other', project['id'], cast['id'], delete=True)
        deleted = repo.edit_character('local', project['id'], cast['id'], delete=True)
        assert not deleted['characters']
        assert deleted['segments'][0]['speaker_id'] is None
        assert deleted['segments'][0]['review_status'] == 'needs_review'
        assert manager.cached_segment(*args) is None

    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_dialogue_merges_pauses_reuses_lines_and_hides_intermediates(tmp_path):
    import wave
    database, project, lines, manager = _fixture(tmp_path)
    imports, calls, published = [], [], []
    def import_artifact(session_id, output, name, **kwargs):
        imports.append(name)
        return SimpleNamespace(id='merged-artifact', session_id=session_id)
    manager.workspace = SimpleNamespace(import_artifact=import_artifact)
    manager._record_studio_artifact = lambda job, segment, artifact: published.append((job['id'], artifact.id))
    manager._artifact_session = lambda owner: 'test-session'
    async def synth(job_id, segment_id, model, request, owner):
        calls.append(segment_id)
        path = manager.root/job_id/(segment_id+'.wav')
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), 'wb') as output:
            output.setnchannels(1); output.setsampwidth(2); output.setframerate(24000)
            output.writeframes(b'\1\0' * 2400)
        return path
    manager._invoke = synth
    async def generate():
        job = await manager.create(owner_user_id='user-1', project_id=project['id'], model_id='example.tts/default', merge_output=True)
        await manager._run(job['id'])
        result = manager.get(job['id'], owner_user_id='user-1')
        assert result['status'] == 'succeeded', result['error']
        assert result['mergedAudio'].endswith('/merged-artifact/download')
        assert all(not line.get('artifact_id') for line in result['segments'])
        return job
    job = await generate()
    assert len(calls) == 2 and imports == [job['id'] + '-dialogue.wav']
    assert published == [(job['id'], 'merged-artifact')]
    with wave.open(str(manager.root/job['id']/'dialogue.wav')) as output:
        assert output.getnframes() == 9600  # .1 + .2 pause + .1; no final pause
    await generate()
    assert len(calls) == 2
    with database.transaction(write=True) as connection:
        connection.execute('UPDATE readaloud_segments SET text=? WHERE id=?', ('Changed', lines[1]['id']))
    await generate()
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_twenty_run_retention_keeps_line_audio(tmp_path):
    from ai2apps.studio import StudioRepository
    database, project, lines, manager = _fixture(tmp_path)
    studio = StudioRepository(database)
    scope = dict(actor_id='user-1', installation_id='install', app_instance_id='app', studio_id='ai2apps.readaloud')
    runs = []
    for index in range(21):
        run = studio.create_run(**scope, mini_app_id='ai2apps.audio.audiobook', mini_app_version='1', placement='ai2apps.readaloud', title=str(index), input_data={})
        runs.append(run['id'])
        await manager.create(owner_user_id='user-1', project_id=project['id'], model_id='example.tts/default', run_id=run['id'])
        await manager._run(run['id'])
    assert len(studio.list_runs(**scope)) == 20
    assert not (manager.root/runs[0]).exists()
    with database.transaction() as connection:
        assert connection.execute('SELECT COUNT(*) FROM readaloud_segments WHERE project_id=?', (project['id'],)).fetchone()[0] == 2
    line_dir = manager._line_cache_dir('user-1', project['id'], lines[0]['id'])
    assert len(list(line_dir.glob('*.wav'))) == 1
    assert manager.cached_segment('user-1', project['id'], lines[0]['id'], 'example.tts/default')


def test_separation_artifacts_persist_tracks_and_zip_separately(tmp_path):
    import io, wave, zipfile
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / 'runtime'))
    runtime.start()
    try:
        audio = io.BytesIO()
        with wave.open(audio, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\x00\x00' * 1600)
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, 'w') as archive:
            archive.writestr('vocals.wav', audio.getvalue())
            archive.writestr('instrumental.wav', audio.getvalue())
            archive.writestr('separation.json', '{}')
        manager = runtime.readaloud_tasks
        result = manager.save_separation_output('user-a', bundle.getvalue(), 'episode.mp4')
        assert len(result['tracks']) == 2
        assert result['downloadUrl'].endswith('/download') and result['filename'].endswith('.zip')
        assert {item['title'] for item in result['tracks']} == {'episode · vocals', 'episode · instrumental'}
        fresh = ReadAloudTaskManager(runtime=runtime, database=runtime.database, root=tmp_path/'fresh', workspace=runtime.workspace)
        mini_app = 'ai2apps.media-voice.source-separation'
        assert len(fresh.quick_history('user-a', mini_app_id=mini_app)) == 2
        assert fresh.quick_history('user-b', mini_app_id=mini_app) == []
        assert fresh.quick_history('user-a') == []
        broken = io.BytesIO()
        with zipfile.ZipFile(broken, 'w') as archive:
            archive.writestr('first.wav', audio.getvalue())
            archive.writestr('broken.wav', b'bad')
        with pytest.raises((wave.Error, EOFError)):
            manager.save_separation_output('user-a', broken.getvalue(), 'broken.mp4')
        assert len(fresh.quick_history('user-a', mini_app_id=mini_app)) == 2
    finally:
        runtime.stop()


def test_shared_output_history_across_producers_and_retention(tmp_path):
    from ai2apps.config import PlatformConfig
    from ai2apps.platform_runtime import PlatformRuntime
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / 'runtime'))
    runtime.start()
    try:
        manager = runtime.readaloud_tasks
        for index in range(23):
            manager.save_studio_output('owner', b'content', mini_app_id=['ai2apps.audio.quick-read', 'ai2apps.audio.voice-design', 'ai2apps.media-voice.transcription'][index % 3], filename=f'{index}.json', media_type='application/json')
        items = manager.output_history('owner')
        assert len(items) == 20
        assert {item['miniAppId'] for item in items} == {'ai2apps.audio.quick-read', 'ai2apps.audio.voice-design', 'ai2apps.media-voice.transcription'}
        assert items[0]['title'] == '22.json'
        assert manager.output_history('other') == []
        session = manager._artifact_session('owner')
        private = manager.root / 'private-line.wav'
        private.write_bytes(b'private-cache')
        runtime.workspace.retire_artifact(session, items[0]['id'])
        assert len(manager.output_history('owner')) == 19
        assert private.read_bytes() == b'private-cache'
    finally:
        runtime.stop()


@pytest.mark.asyncio
async def test_audiobook_indextts_uses_background_asr_and_persists_warning(tmp_path, monkeypatch):
    import io
    import wave
    import json
    from ai2apps.model_providers import list_package_models
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b'\x00\x10' * 240)
    calls = []
    class Gateway:
        async def invoke_background_json(self, model_id, operation, payload, **kwargs):
            calls.append((operation, kwargs['request_id']))
            return Response(buffer.getvalue())
        async def invoke_background_multipart(self, model_id, operation, **kwargs):
            assert model_id == 'test/asr' and kwargs['files']['file'][1] == buffer.getvalue()
            calls.append((operation, kwargs['request_id']))
            return Response(json.dumps({'text': 'completely different'}))
    _, project, rows, manager = _fixture(tmp_path, gateway=Gateway())
    monkeypatch.setattr('ai2apps.model_providers.list_package_models', lambda runtime: [
        SimpleNamespace(id='test/asr', model_type='audio_stt', checkpoint_ready=True)])
    model = SimpleNamespace(id='ai2apps.model.indextts25/fp16', audio_capabilities={})
    request = {'input': '你好世界。', 'speed': 1, 'emotion': 'neutral', 'asrVerification': True, 'asrModelId': 'test/asr'}
    target = await manager._invoke('job', rows[0]['id'], model, request, 'user-1')
    assert [op for op, _ in calls] == ['audio_speech', 'audio_transcription'] * 3
    assert len({key for _, key in calls}) == 6
    assert manager._audio_warnings(target)
    cached = manager._save_line_audio('user-1', project['id'], rows[0]['id'], request, target)
    assert manager._audio_warnings(cached) == manager._audio_warnings(target)
    monkeypatch.setattr('ai2apps.model_providers.list_package_models', lambda runtime: [])
    target = await manager._invoke('job2', rows[0]['id'], model, request, 'user-1')
    assert any('未找到可用 ASR' in item for item in manager._audio_warnings(target))
    request['asrVerification'] = False
    calls.clear()
    target = await manager._invoke('job3', rows[0]['id'], model, request, 'user-1')
    assert [op for op, _ in calls] == ['audio_speech']
    assert manager._audio_warnings(target) == []



def test_project_asr_settings_persist_and_invalidate_line_cache(tmp_path):
    from ai2apps.readaloud import ReadAloudRepository
    database, project, rows, manager = _fixture(tmp_path)
    events = EventStore(database, EventNotificationBus())
    repository = ReadAloudRepository(database, events)
    assert repository.get_project('user-1', project['id'])['asr_verification'] is True
    saved = repository.update_project('user-1', project['id'], {'asr_verification': False, 'asr_model_id': 'chosen/asr'})
    assert saved['asr_verification'] is False and saved['asr_model_id'] == 'chosen/asr'

    row = dict(rows[0], voice_model_id=None, voice_training_json='{}', provider_voice_id=None, speaker_revision=None)
    before = manager._segment_request(row, 'example.tts/default')
    assert before['asrVerification'] is False and before['asrModelId'] == ''
    repository.update_project('user-1', project['id'], {'asr_verification': True})
    after = manager._segment_request(row, 'example.tts/default')
    assert after['asrVerification'] is True and after['asrModelId'] == 'chosen/asr'
    assert before != after
