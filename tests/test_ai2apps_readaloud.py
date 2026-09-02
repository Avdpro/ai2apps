# SPDX-License-Identifier: Apache-2.0
"""Read Aloud persistence, isolation, and API contract tests."""

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
    assert "'audio.speech_generation'" in script
    assert "'audio.speech_recognition'" in script
    assert "'audio.voice_clone'" in script
    assert "'speech_recognition' : 'speech_generation'" in script
    assert "ai2apps.audio.character-training" in script
    assert "MediaRecorder" in script
    assert "/v1/audio/transcriptions" in script
    assert "/v1/platform/gallery/assets/import" in script
    assert "reference_asset_id" in script
    assert "CHARACTER VOICE TRAINING" in template
    assert "await this.saveSegment(segment)" in script
    assert "if (capability.configured)" in script
    assert "/capabilities/ensure" in provisioning
    assert "readaloud.pipeline.quick.name" in locales["en"]
    assert "readaloud.pipeline.quick.name" in locales["zh"]
    assert "朗读工坊" not in template
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
        for profile in speech["profiles"]
    )
    assert all("voice-clone" in profile["id"] for profile in voice["profiles"])
