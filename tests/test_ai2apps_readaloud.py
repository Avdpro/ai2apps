# SPDX-License-Identifier: Apache-2.0
"""Voice Studio persistence, isolation, and API contract tests."""

from __future__ import annotations

import copy
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.readaloud import create_readaloud_router
from ai2apps.events import EventStore
from ai2apps.gallery import GalleryRepository
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.provisioning.profiles import CapabilityProfileRegistry
from ai2apps.readaloud import ReadAloudRepository
from ai2apps.storage import PlatformDatabase

WEB_ROOT = Path(__file__).parents[1] / "ai2apps" / "web"


def test_readaloud_gallery_mini_entry_recovers_from_stale_host_bridge():
    script = (WEB_ROOT / "static/js/readaloud.js").read_text()

    assert "GALLERY_MINI_FALLBACK_URL" in script
    assert "AI2Apps Host did not respond|Unsupported host mount" in script
    assert "if (this.leftView === 'assets') this.mountGalleryMini()" in script
    assert "if (force) { this.galleryMiniUrl = ''; this.galleryMiniMountId = ''; }" in script


def _principal(user_id: str) -> RequestPrincipal:
    return RequestPrincipal(
        actor_user_id=user_id,
        installation_id="installation-1",
        organization_id="organization-1",
        billing_account_id="billing-1",
        role=MemberRole.CORE,
        membership_epoch=1,
    )


def _repository(tmp_path):
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    events = EventStore(database)
    return database, events, ReadAloudRepository(database, events)


def test_project_script_and_voice_profile_round_trip(tmp_path):
    _, events, repository = _repository(tmp_path)
    project = repository.create_project(
        "owner-1",
        title="第一回",
        purpose="noncommercial",
        source_rights="licensed",
        source_text="钱塘江浩浩江水。",
    )
    voice = repository.create_voice_profile(
        "owner-1",
        name="沉稳男声",
        source_type="synthetic_designed",
        model_id="fish/s2-pro",
        provider_voice_id=None,
        reference_transcript="",
        rights_scope={"commercial": False},
        reference_asset_id="gallery-audio-1",
    )
    character = repository.create_character(
        "owner-1",
        project["id"],
        name="旁白",
        description="沉稳",
        voice_profile_id=voice["id"],
    )
    repository.create_segment(
        "owner-1",
        project["id"],
        speaker_id=character["id"],
        text="故事从这里开始。",
        emotion="calm",
        emotion_strength=0.8,
        speed=0.95,
        pause_after_ms=500,
    )

    loaded = repository.get_project("owner-1", project["id"])
    assert loaded["revision"] == 3
    assert loaded["characters"][0]["voice_profile_id"] == voice["id"]
    assert loaded["segments"][0]["speaker_id"] == character["id"]
    assert loaded["segments"][0]["emotion"] == "calm"
    assert voice["rights_scope"] == {"commercial": False}
    assert voice["reference_asset_id"] == "gallery-audio-1"

    recorded = events.list_after(subject_id=project["id"], limit=10)
    assert [event.type for event in recorded] == ["readaloud.project.created"]
    assert "钱塘江" not in json.dumps(recorded[0].payload, ensure_ascii=False)


def test_api_isolates_projects_and_rejects_cross_project_speakers(tmp_path):
    database, events, _ = _repository(tmp_path)
    current = {"principal": _principal("owner-1")}
    runtime = SimpleNamespace(database=database, events=events)
    app = FastAPI()
    app.include_router(
        create_readaloud_router(
            lambda: runtime,
            principal_provider=lambda: current["principal"],
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    first = client.post(
        "/v1/platform/readaloud/projects",
        json={
            "title": "项目一",
            "purpose": "private",
            "source_rights": "user_owned",
            "source_text": "私有原文",
        },
    )
    second = client.post(
        "/v1/platform/readaloud/projects",
        json={"title": "项目二"},
    )
    assert first.status_code == 201
    assert second.status_code == 201

    character = client.post(
        f"/v1/platform/readaloud/projects/{second.json()['id']}/characters",
        json={"name": "旁白"},
    )
    assert character.status_code == 201
    invalid = client.post(
        f"/v1/platform/readaloud/projects/{first.json()['id']}/segments",
        json={"speaker_id": character.json()["id"], "text": "跨项目引用"},
    )
    assert invalid.status_code == 404
    assert invalid.json()["error"]["code"] == "not_found"

    current["principal"] = _principal("owner-2")
    assert client.get("/v1/platform/readaloud/projects").json() == {"items": []}
    hidden = client.get(
        f"/v1/platform/readaloud/projects/{first.json()['id']}"
    )
    assert hidden.status_code == 404


def test_real_voice_profile_stays_unverified_and_provider_strategy_is_local(tmp_path):
    database, events, _ = _repository(tmp_path)
    runtime = SimpleNamespace(database=database, events=events)
    app = FastAPI()
    app.include_router(
        create_readaloud_router(
            lambda: runtime,
            principal_provider=lambda: _principal("owner-1"),
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    created = client.post(
        "/v1/platform/readaloud/voice-profiles",
        json={
            "name": "授权样本",
            "source_type": "authorized_person",
            "reference_transcript": "这是一段已授权参考录音的逐字稿。",
            "rights_scope": {
                "evidence": "contract-42",
                "consent_confirmed": True,
                "usage_rights_confirmed": True,
                "prohibited_impersonation_acknowledged": True,
            },
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "unverified"
    assert created.json()["rightsScope"]["evidence"] == "contract-42"
    assert created.json()["rightsScope"]["policy_version"] == "ai2apps.voice-rights/v1"

    rejected = client.post(
        "/v1/platform/readaloud/voice-profiles",
        json={"name": "没有授权", "source_type": "authorized_person"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "readaloud_request_invalid"

    providers = client.get("/v1/platform/readaloud/providers")
    assert providers.status_code == 200
    assert providers.json()["strategy"] == {
        "ideal": "ai2apps.model.fish-s2-pro/bf16",
        "fallbacks": [
            "ai2apps.model.cosyvoice3-0.5b/4bit",
            "ai2apps.model.cosyvoice3-0.5b/8bit",
            "ai2apps.model.qwen3-tts-1.7b/custom-voice-8bit",
        ],
        "cloudApiEnabled": False,
    }


def test_character_training_profile_references_owned_gallery_audio(tmp_path):
    database, events, _ = _repository(tmp_path)
    artifact_path = tmp_path / "artifacts"
    gallery = GalleryRepository(database, artifact_path / "gallery", events)
    audio, _ = gallery.import_stream(
        "owner-1",
        BytesIO(b"RIFF-reference-audio"),
        name="reference.wav",
        media_type="audio/wav",
        source_app_id="ai2apps.readaloud",
    )
    runtime = SimpleNamespace(
        database=database,
        events=events,
        config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=artifact_path)),
    )
    app = FastAPI()
    app.include_router(
        create_readaloud_router(
            lambda: runtime,
            principal_provider=lambda: _principal("owner-1"),
        ),
        prefix="/v1/platform",
    )

    created = TestClient(app).post(
        "/v1/platform/readaloud/voice-profiles",
        json={
            "name": "训练角色",
            "source_type": "self_voice",
            "reference_asset_id": audio["id"],
            "reference_transcript": "这是一段角色训练录音。",
            "rights_scope": {
                "consent_confirmed": True,
                "usage_rights_confirmed": True,
                "prohibited_impersonation_acknowledged": True,
            },
        },
    )

    assert created.status_code == 201
    assert created.json()["referenceAssetId"] == audio["id"]
    assert created.json()["status"] == "unverified"


def test_render_job_api_uses_principal_scoped_durable_manager(tmp_path):
    database, events, repository = _repository(tmp_path)
    project = repository.create_project(
        "owner-1",
        title="Batch",
        purpose="private",
        source_rights="user_owned",
        source_text="",
    )
    captured = {}
    job = {
        "id": "rar_fixture",
        "owner_user_id": "owner-1",
        "project_id": project["id"],
        "project_revision": 1,
        "model_id": "example.tts/default",
        "status": "queued",
        "total_segments": 1,
        "completed_segments": 0,
        "segments": [],
    }

    class Manager:
        async def create(self, **values):
            captured.update(values)
            return copy.deepcopy(job)

        def get(self, job_id, *, owner_user_id):
            assert job_id == job["id"]
            assert owner_user_id == "owner-1"
            return copy.deepcopy(job)

        async def cancel(self, job_id, *, owner_user_id):
            value = self.get(job_id, owner_user_id=owner_user_id)
            value["status"] = "cancelled"
            return value

    runtime = SimpleNamespace(
        database=database,
        events=events,
        readaloud_tasks=Manager(),
    )
    app = FastAPI()
    app.include_router(
        create_readaloud_router(
            lambda: runtime,
            principal_provider=lambda: _principal("owner-1"),
        ),
        prefix="/v1/platform",
    )
    client = TestClient(app)

    created = client.post(
        f"/v1/platform/readaloud/projects/{project['id']}/render",
        json={"model_id": "example.tts/default"},
    )
    assert created.status_code == 202
    assert created.json()["projectRevision"] == 1
    assert captured["owner_user_id"] == "owner-1"
    assert client.get(
        "/v1/platform/readaloud/render-jobs/rar_fixture"
    ).status_code == 200
    cancelled = client.post(
        "/v1/platform/readaloud/render-jobs/rar_fixture/cancel"
    )
    assert cancelled.json()["status"] == "cancelled"


def test_readaloud_uses_first_party_ai2apps_visual_tokens():
    stylesheet = (WEB_ROOT / "static/css/readaloud.css").read_text()
    template = (WEB_ROOT / "templates/system_apps/readaloud.html").read_text()
    script = (WEB_ROOT / "static/js/readaloud.js").read_text()
    provisioning = (WEB_ROOT / "static/js/capability_provisioning.js").read_text()
    locales = {
        language: json.loads((WEB_ROOT / "i18n" / f"{language}.json").read_text())
        for language in ("en", "zh")
    }

    assert 'data-app-id="ai2apps.readaloud"' in template
    assert 'data-client-environment=' in template
    assert "ra-studio-sidebar" in template
    assert "ra-pipeline-workspace" in template
    assert "ra-render-workspace" in template
    assert "Gallery Mini Entry" in template
    assert "capability_provisioning.js" in template
    assert "AI2AppsCapabilities.ensure" in script
    assert "AI2AppsCapabilities.probe" in script
    assert "AI2AppsCapabilities?.resume" in script
    assert "AI2AppsCapabilities.acknowledge" in script
    assert "completionPolicy: 'configure_only'" in script
    assert "const effectiveResumeToken = resumeToken || globalThis.crypto?.randomUUID?.()" in script
    assert "resumeToken: effectiveResumeToken" in script
    assert "resumeToken: resumeToken || null" not in script
    assert "'audio.speech_generation'" in script
    assert "'audio.speech_recognition'" in script
    assert "'audio.voice_clone'" in script
    assert "'speech_recognition' : 'speech_generation'" in script
    assert "ai2apps.audio.character-training" in script
    assert "MediaRecorder" in script
    assert "/v1/audio/transcriptions" in script
    assert "/v1/platform/gallery/assets/import" in script
    assert "/training/profiles" in script
    assert "asset_id:item.assetId" in script
    assert 'class="ra-pipeline-header studio-mini-header"' in template
    assert "await this.saveSegment(segment)" in script
    assert "if (capability.configured)" in script
    assert "/capabilities/ensure" in provisioning
    assert "readaloud.pipeline.quick.name" in locales["en"]
    assert "readaloud.pipeline.quick.name" in locales["zh"]
    assert "朗读工坊" not in template
    assert locales["en"]["readaloud.title"] == "Voice Studio"
    assert locales["zh"]["readaloud.title"] == "语音工坊"
    assert 'class="ra-header studio-header"' in template
    assert "Voice Studio ·" not in template
    assert "Read Aloud ·" not in template
    assert "--ra-ink:#171717" in stylesheet
    assert "--ra-line:#e7e5e4" in stylesheet
    assert "background:var(--ra-accent)" in stylesheet
    assert "Georgia" not in stylesheet
    assert "#b84a2c" not in stylesheet


def test_readaloud_acpf_profiles_split_speech_and_voice_clone():
    registry = CapabilityProfileRegistry()
    speech = registry.capability("ai2apps.readaloud", "audio.speech_generation")
    recognition = registry.capability("ai2apps.readaloud", "audio.speech_recognition")
    voice = registry.capability("ai2apps.readaloud", "audio.voice_clone")

    assert speech is not None and recognition is not None and voice is not None
    assert speech["requirements"] == {"operations": ["speech_generation"]}
    assert recognition["requirements"] == {"operations": ["speech_recognition"]}
    assert voice["requirements"] == {"operations": ["voice_cloning"]}
    assert speech["trigger"] == recognition["trigger"] == voice["trigger"] == "on_feature_request"
    assert all(
        "voice" not in profile["id"] or "custom-voice" in profile["id"]
        for profile in speech["profiles"] if profile.get("recommended", True)
    )
    assert all("voice-clone" in profile["id"] for profile in voice["profiles"])


def test_project_mini_app_scope_survives_reload_and_validates_api(tmp_path):
    database, events, repository = _repository(tmp_path)
    app = FastAPI()
    app.include_router(create_readaloud_router(
        lambda: SimpleNamespace(database=database, events=events),
        principal_provider=lambda: _principal("owner-1"),
    ), prefix="/v1/platform")
    client = TestClient(app)
    base = "/v1/platform/readaloud/projects"
    for mini_app in ("quick-read", "audiobook", "ensemble-drama"):
        scope = "ai2apps.audio." + mini_app
        response = client.post(base, json={"title": mini_app, "mini_app_id": scope})
        assert response.status_code == 201
        project = response.json()
        assert project["miniAppId"] == scope
        assert client.get(base + "/" + project["id"]).json()["miniAppId"] == scope
        assert ReadAloudRepository(database).get_project("owner-1", project["id"])["mini_app_id"] == scope
    assert len(client.get(base).json()["items"]) == 3
    assert client.post(base, json={"title": "invalid", "mini_app_id": "ai2apps.audio.voice-design"}).status_code == 422
    assert client.post(base, json={"title": "legacy client"}).json()["miniAppId"] == "ai2apps.audio.audiobook"


def test_project_scope_migration_preserves_legacy_text(tmp_path):
    import sqlite3
    from ai2apps.storage.migrations import MIGRATIONS, apply_migrations
    path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(path)
    apply_migrations(connection, MIGRATIONS[:-1])
    connection.execute("INSERT INTO readaloud_projects (id,owner_user_id,title,purpose,source_rights,source_text,status,revision,created_at,updated_at) VALUES ('old','owner','Legacy','private','user_owned','Original text','draft',1,'now','now')")
    connection.commit()
    apply_migrations(connection)
    assert connection.execute("SELECT source_text,mini_app_id FROM readaloud_projects WHERE id='old'").fetchone() == ("Original text", "ai2apps.audio.audiobook")
    connection.close()


def test_quick_read_generates_without_creating_projects(tmp_path, monkeypatch):
    from fastapi.responses import Response
    database, events, repository = _repository(tmp_path)
    calls = []
    model = SimpleNamespace(id="speech", model_type="audio_tts", checkpoint_ready=True,
        audio_capabilities={"tts": {"named_voices": {"voices": ["alice", "bob"]}}})
    class Invocations:
        def model(self, model_id):
            return model if model_id == "speech" else None
        def context_for_actor(self, actor, *, session_id, consumer_app_id):
            assert actor == "owner-1"
            assert session_id.startswith("quick-read-")
            assert consumer_app_id == "ai2apps.readaloud"
            return "context"
        async def invoke_foreground_json(self, model_id, operation, payload, **kwargs):
            calls.append(payload)
            assert operation == "audio_speech"
            assert kwargs["context"] == "context"
            return Response(b"RIFF-test-wave", media_type="audio/wav")
    def save_quick_audio(owner, content, **metadata):
        assert owner == "owner-1" and content == b"RIFF-test-wave"
        return "/v1/platform/sessions/session/artifacts/audio/download"
    runtime = SimpleNamespace(database=database, events=events, model_invocations=Invocations(),
        readaloud_tasks=SimpleNamespace(save_quick_audio=save_quick_audio))
    app = FastAPI()
    app.include_router(create_readaloud_router(lambda: runtime,
        principal_provider=lambda: _principal("owner-1")), prefix="/v1/platform")
    client = TestClient(app)
    endpoint = "/v1/platform/readaloud/quick-read"
    response = client.post(endpoint, json={"text": " Hello ", "model_id": "speech", "voice": "bob"})
    assert response.status_code == 200
    assert response.content == b"RIFF-test-wave"
    assert response.headers["X-AI2Apps-Download-URL"] == "/v1/platform/sessions/session/artifacts/audio/download"
    assert response.headers["content-type"] == "audio/wav"
    assert calls[-1]["voice"] == "bob" and calls[-1]["input"] == "Hello"
    assert repository.list_projects("owner-1") == ()
    assert client.post(endpoint, json={"text": "Hi", "model_id": "speech"}).status_code == 200
    assert calls[-1]["voice"] == "alice"
    tempo_calls = []
    monkeypatch.setattr('ai2apps.audio_codecs.change_speech_tempo', lambda content, speed: (tempo_calls.append(speed), content)[1])
    assert client.post(endpoint, json={'text':'Hi','model_id':'speech','speed':0.5}).status_code == 200
    assert tempo_calls == [0.5] and 'speed' not in calls[-1]
    model.audio_capabilities['tts']['speed'] = {'mode':'native','minimum':0.5,'maximum':2.0}
    assert client.post(endpoint, json={'text':'Hi','model_id':'speech','speed':2}).status_code == 200
    assert calls[-1]['speed'] == 2 and tempo_calls == [0.5]
    for invalid in (0.49, 2.01):
        assert client.post(endpoint, json={'text':'Hi','model_id':'speech','speed':invalid}).status_code == 422
    del calls[-2:]
    del model.audio_capabilities['tts']['speed']

    for data in [
        {"text": "   ", "model_id": "speech"},
        {"text": "Hi", "model_id": "missing"},
        {"text": "Hi", "model_id": "speech", "voice": "unknown"},
        {"text": "x" * 10001, "model_id": "speech"},
    ]:
        assert client.post(endpoint, json=data).status_code == 422
    profile_args = dict(name='Alice', source_type='synthetic_designed', model_id='speech', provider_voice_id=None,
                        reference_transcript='reference', rights_scope={}, training={'design': {'description': 'Warm voice'}})
    profile = repository.create_voice_profile('owner-1', **profile_args)
    response = client.post(endpoint, json={'text':'Character words','model_id':'ignored','voice_profile_id':profile['id']})
    assert response.status_code == 200
    assert calls[-1]['instructions'] == 'Warm voice'
    assert 'voice' not in calls[-1]
    foreign = repository.create_voice_profile('other-owner', **profile_args)
    assert client.post(endpoint,json={'text':'Hi','model_id':'speech','voice_profile_id':foreign['id']}).status_code == 404
    assert client.post(endpoint,json={'text':'Hi','model_id':'speech','voice_profile_id':'missing'}).status_code == 404
    clone = repository.create_voice_profile('owner-1', **{**profile_args, 'training': {'samples':[{'asset_id':'ref'}], 'model_revision':'r1'}})
    runtime.config = SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path/'materials'))
    monkeypatch.setattr('ai2apps.api.readaloud.prepare_training', lambda *args, **kwargs: ({'executable':True,'revision':'r1'}, [], []))
    monkeypatch.setattr('ai2apps.api.readaloud.combined_reference', lambda *args: (b'reference-audio','Reference words'))
    async def multipart(model_id, operation, *, data, files, **options):
        assert files['reference_audio'][1] == b'reference-audio'
        assert data['ref_text'] == 'Reference words' and data['input'] == 'Clone words'
        assert 'voice' not in data
        return Response(b'RIFF-test-wave', media_type='audio/wav')
    runtime.model_invocations.invoke_foreground_multipart = multipart
    assert client.post(endpoint,json={'text':'Clone words','model_id':'ignored','voice_profile_id':clone['id']}).status_code == 200
    monkeypatch.setattr('ai2apps.api.readaloud.list_package_models', lambda runtime: [SimpleNamespace(id='other-asr', model_type='audio_stt', checkpoint_ready=True), SimpleNamespace(id='asr', model_type='audio_stt', checkpoint_ready=True)])
    checks=[]
    async def transcribe(model_id, operation, *, data, files, **options):
        assert model_id=='asr' and operation=='audio_transcription'
        assert files['file'][1]==b'RIFF-test-wave'
        checks.append(options['request_id'])
        return Response(b'{"text":"Hello"}',media_type='application/json')
    runtime.model_invocations.invoke_foreground_multipart=transcribe
    assert client.post(endpoint,json={'text':'Hello','model_id':'speech','asr_verification':True,'asr_model_id':'asr'}).status_code==200
    assert len(checks)==1
    model.checkpoint_ready = False
    assert client.post(endpoint, json={"text": "Hi", "model_id": "speech"}).status_code == 503
    assert len(calls) == 4


def test_line_order_soft_delete_and_character_selection(tmp_path):
    import pytest
    from ai2apps.core import ResourceNotFoundError
    database, _, repo = _repository(tmp_path)
    project = repo.create_project('owner', title='Book', purpose='private', source_rights='user_owned', source_text='')
    pid = project['id']
    character = repo.create_character('owner', pid, name='Alice', description='', voice_profile_id=None)
    lines = [repo.create_segment('owner', pid, speaker_id=character['id'], text=str(i), emotion='neutral', emotion_strength=1, speed=1, pause_after_ms=750) for i in range(3)]
    saved = repo.get_project('owner', pid)['segments']
    assert all(x['speaker_id'] == character['id'] and x['pause_after_ms'] == 750 for x in saved)
    with pytest.raises(ResourceNotFoundError):
        repo.change_segment_position('other', pid, lines[0]['id'], action='delete')
    changed = repo.change_segment_position('owner', pid, lines[2]['id'], action='up')
    assert [x['id'] for x in changed['segments']] == [lines[i]['id'] for i in [0, 2, 1]]
    changed = repo.change_segment_position('owner', pid, lines[0]['id'], action='down')
    assert [x['id'] for x in changed['segments']] == [lines[i]['id'] for i in [2, 0, 1]]
    changed = repo.change_segment_position('owner', pid, lines[0]['id'], action='delete')
    assert [x['ordinal'] for x in changed['segments']] == [0, 1]
    with database.transaction() as connection:
        assert connection.execute('SELECT deleted_at FROM readaloud_segments WHERE id=?', (lines[0]['id'],)).fetchone()[0]
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    assert repo.list_projects('owner')[0]['segment_count'] == 2


def test_project_asr_api_returns_ui_fields_after_save_and_reload(tmp_path):
    database, events, _ = _repository(tmp_path)
    runtime = SimpleNamespace(database=database, events=events)
    app = FastAPI()
    app.include_router(create_readaloud_router(lambda: runtime,
        principal_provider=lambda: _principal('owner-1')), prefix='/v1/platform')
    client = TestClient(app)
    root = '/v1/platform/readaloud/projects'
    created = client.post(root, json={'title': 'ASR book'})
    assert created.status_code == 201
    project = created.json()
    assert project['asrVerification'] is True
    assert project['asrModelId'] == ''
    endpoint = root + '/' + project['id']
    for enabled in (False, True):
        saved = client.patch(endpoint, json={'asr_verification': enabled, 'asr_model_id': 'chosen/asr'})
        assert saved.status_code == 200
        for body in (saved.json(), client.get(endpoint).json()):
            assert body['asrVerification'] is enabled
            assert body['asrModelId'] == 'chosen/asr'
            assert 'asr_verification' not in body and 'asr_model_id' not in body
