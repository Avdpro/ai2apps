from __future__ import annotations

import io
import json
import wave
import zipfile
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from ai2apps.api.studio_mini_apps import _content_url, create_studio_mini_app_router
from ai2apps.identity import RequestPrincipal
from ai2apps.studio.capability_broker import (
    StudioCapabilityBroker,
    StudioCapabilityError,
)

STUDIO_ID = "ai2apps.readaloud"
MOUNT_ID = "mount_test_detailed"
MINI_APP_ID = "ai2apps.media-voice.transcription"


def _wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 1_600)
    return output.getvalue()


class FakeExtensionManager:
    def mount_entry(self, mount_id, *, principal=None):
        assert principal is not None
        if mount_id != MOUNT_ID:
            raise AssertionError("unexpected mount")
        return {
            "id": MOUNT_ID,
            "app_instance_id": "app_provider_instance",
            "app_key": "ai2apps.media-voice-studio-suite",
            "effective_digest": "sha256:package",
            "entry_source": "mini_entry",
            "context": {"studioId": STUDIO_ID, "miniAppId": MINI_APP_ID},
        }

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        assert studio_id == STUDIO_ID
        assert principal is not None
        return (
            {
                "id": MINI_APP_ID,
                "requirements": {
                    "capabilities": [
                        "audio.detailed_transcription",
                        "audio.speaker_diarization",
                    ]
                },
                "provider": {
                    "appId": "ai2apps.media-voice-studio-suite",
                    "digest": "sha256:package",
                },
            },
        )


class CatalogExtensionManager(FakeExtensionManager):
    def require_instance_access(self, instance_id, principal):
        assert instance_id == "studio_instance"
        assert principal is not None

    def instance_entry(self, instance_id, *, principal=None):
        assert instance_id == "studio_instance"
        assert principal is not None
        return {"app_key": STUDIO_ID}

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
        declaration["source"] = "package"
        return (declaration,)


class SeparationExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = "ai2apps.media-voice.source-separation"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(super().list_studio_mini_apps(studio_id, principal=principal)[0])
        declaration["id"] = "ai2apps.media-voice.source-separation"
        declaration["requirements"] = {
            "capabilities": ["audio.source_separation"]
        }
        return (declaration,)


class VideoSubtitleExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = "ai2apps.media-voice.video-subtitles"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(super().list_studio_mini_apps(studio_id, principal=principal)[0])
        declaration["id"] = "ai2apps.media-voice.video-subtitles"
        declaration["requirements"] = {
            "capabilities": [
                "media.video_subtitles",
                "audio.detailed_transcription",
                "text.translation",
                "media.subtitle.export",
                "media.video.subtitle_burn_in",
            ]
        }
        return (declaration,)


class AudioReplacementExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = (
            "ai2apps.media-voice.audio-speaker-replacement"
        )
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(super().list_studio_mini_apps(studio_id, principal=principal)[0])
        declaration["id"] = "ai2apps.media-voice.audio-speaker-replacement"
        declaration["requirements"] = {
            "capabilities": [
                "audio.speaker_voice_replacement",
                "audio.detailed_transcription",
                "audio.speaker_diarization",
                "audio.source_separation",
                "audio.voice_conversion",
            ]
        }
        return (declaration,)


class VideoReplacementExtensionManager(AudioReplacementExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = (
            "ai2apps.media-voice.video-speaker-replacement"
        )
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(super().list_studio_mini_apps(studio_id, principal=principal)[0])
        declaration["id"] = "ai2apps.media-voice.video-speaker-replacement"
        declaration["requirements"] = {
            "capabilities": [
                "media.video_speaker_voice_replacement",
                "audio.speaker_voice_replacement",
                "media.audio.extract",
                "media.video.audio_mux",
                "audio.detailed_transcription",
                "audio.speaker_diarization",
                "audio.source_separation",
                "audio.voice_conversion",
            ]
        }
        return (declaration,)


class FakeInvocations:
    def __init__(self):
        self.call = None

    def model(self, _model_id):
        return None

    async def invoke_foreground_multipart(
        self, model_id, operation, *, data, files, request_id, context
    ):
        self.call = {
            "model_id": model_id,
            "operation": operation,
            "data": data,
            "files": files,
            "request_id": request_id,
            "context": context,
        }
        if operation == "audio_process":
            return Response(
                b"PK\x03\x04test",
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="demucs-stems.zip"'},
            )
        return JSONResponse(
            {
                "schema": "ai2apps.detailed-transcription-result/v1",
                "language": "zh",
                "duration": 0.1,
                "text": "你好",
                "segments": [
                    {"start": 0, "end": 0.1, "text": "你好", "speaker": "SPEAKER_00"}
                ],
                "features": {},
            }
        )


def _model(*, ready=True):
    return SimpleNamespace(
        id="ai2apps.model.detailed-transcription-mlx/compact",
        display_name="Detailed Transcription Compact",
        model_type="audio_detailed_transcription",
        metadata={"profile": "compact"},
        checkpoint_ready=ready,
        endpoint=None,
    )


def _separation_model(*, ready=True):
    return SimpleNamespace(
        id="ai2apps.model.demucs-mlx/default",
        display_name="MLX Demucs HTDemucs",
        model_type="audio_processing",
        metadata={"family": "demucs"},
        audio_capabilities={
            "operations": ["audio_process"],
            "processing": {
                "separation": {
                    "mode": "native",
                    "profiles": [
                        {"id": "vocals_instrumental"},
                        {"id": "dialogue_background"},
                        {"id": "music_4stem"},
                    ],
                }
            },
        },
        checkpoint_ready=ready,
        endpoint=None,
    )


def _voice_model(*, ready=True):
    return SimpleNamespace(
        id="ai2apps.model.seed-vc-v2-mlx/default",
        display_name="MLX Seed-VC v2",
        model_type="audio_processing",
        metadata={"family": "seed-vc-v2"},
        audio_capabilities={
            "operations": ["audio_process"],
            "processing": {
                "voice_conversion": {
                    "mode": "native",
                    "target_sources": ["reference_audio"],
                    "profiles": [
                        {
                            "id": "timbre_quality",
                            "inference_mode": "timbre",
                            "diffusion_steps": 30,
                        }
                    ],
                }
            },
        },
        checkpoint_ready=ready,
        endpoint=None,
    )


class ReplacementInvocations(FakeInvocations):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def invoke_foreground_multipart(
        self, model_id, operation, *, data, files, request_id, context
    ):
        self.calls.append({"model_id": model_id, "operation": operation, "data": data})
        if operation == "audio_detailed_transcription":
            return await super().invoke_foreground_multipart(
                model_id,
                operation,
                data=data,
                files=files,
                request_id=request_id,
                context=context,
            )
        if model_id == "ai2apps.model.demucs-mlx/default":
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr("dialogue.wav", _wav())
                output.writestr("background.wav", _wav())
            return Response(archive.getvalue(), media_type="application/zip")
        return Response(_wav(), media_type="audio/wav")


def _runtime(*, extension_manager=None):
    return SimpleNamespace(
        extension_manager=extension_manager or FakeExtensionManager(),
        model_invocations=FakeInvocations(),
    )


def _replacement_runtime():
    return SimpleNamespace(
        extension_manager=AudioReplacementExtensionManager(),
        model_invocations=ReplacementInvocations(),
    )


def test_mount_bound_probe_reports_only_declared_capabilities(monkeypatch):
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    result = StudioCapabilityBroker(_runtime()).probe(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )

    assert result["miniAppId"] == MINI_APP_ID
    assert {item["capability"] for item in result["items"]} == {
        "audio.detailed_transcription",
        "audio.speaker_diarization",
    }
    assert all(item["ready"] for item in result["items"])


def test_catalog_probe_reports_declaration_without_creating_mount(monkeypatch):
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    declaration = FakeExtensionManager().list_studio_mini_apps(
        STUDIO_ID, principal=RequestPrincipal.legacy_local()
    )[0]

    result = StudioCapabilityBroker(_runtime()).probe_declaration(
        STUDIO_ID, declaration
    )

    assert result["miniAppId"] == MINI_APP_ID
    assert "mountId" not in result
    assert all(item["implemented"] and item["ready"] for item in result["items"])


@pytest.mark.asyncio
async def test_catalog_endpoint_probes_every_installed_package_mini_app(monkeypatch):
    runtime = _runtime(extension_manager=CatalogExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/studios/{STUDIO_ID}/mini-app-capabilities",
            headers={"X-AI2Apps-App-Instance": "studio_instance"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "ai2apps.studio-capability-catalog/v1"
    assert [item["miniAppId"] for item in payload["items"]] == [MINI_APP_ID]


def test_probe_marks_optional_capability_without_blocking_required_readiness(
    monkeypatch,
):
    manager = VideoSubtitleExtensionManager()
    declaration = manager.list_studio_mini_apps(
        STUDIO_ID, principal=RequestPrincipal.legacy_local()
    )[0]
    declaration["requirements"]["capabilities"] = [
        {"capability": "text.translation", "optional": True}
        if item == "text.translation"
        else item
        for item in declaration["requirements"]["capabilities"]
    ]
    manager.list_studio_mini_apps = lambda *_args, **_kwargs: (declaration,)
    runtime = _runtime(extension_manager=manager)
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )

    result = StudioCapabilityBroker(runtime).probe(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )
    translation = next(
        item for item in result["items"] if item["capability"] == "text.translation"
    )

    assert translation["ready"] is False
    assert translation["required"] is False


def test_video_replacement_probe_implements_voice_and_host_media_dependencies(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoReplacementExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(), _separation_model(), _voice_model()),
    )

    result = StudioCapabilityBroker(runtime).probe(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )
    items = {item["capability"]: item for item in result["items"]}

    for capability in (
        "audio.voice_conversion",
        "media.audio.extract",
        "media.video.audio_mux",
    ):
        assert items[capability]["implemented"] is True
        assert items[capability]["ready"] is True


def test_mounted_content_url_carries_only_opaque_mount_and_studio_context():
    url = _content_url(
        {
            "app_instance_id": "app_instance_1",
            "id": MOUNT_ID,
            "renderer": "sandbox",
            "resource": "web/transcription.html",
            "context": {"studioId": STUDIO_ID, "miniAppId": MINI_APP_ID},
        }
    )

    assert f"mount_id={MOUNT_ID}" in url
    assert f"studio_id={STUDIO_ID}" in url
    assert MINI_APP_ID not in url


@pytest.mark.asyncio
async def test_broker_invokes_detailed_transcription_with_server_derived_identity(
    monkeypatch,
):
    runtime = _runtime()
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    response = await StudioCapabilityBroker(runtime).detailed_transcription(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        content=_wav(),
        filename="meeting.wav",
        media_type="audio/wav",
        profile="compact",
        language="zh",
        word_timestamps=True,
        diarization=True,
    )

    assert response.status_code == 200
    call = runtime.model_invocations.call
    assert call["operation"] == "audio_detailed_transcription"
    assert call["data"]["diarization"] == "true"
    assert call["files"]["file"][2] == "audio/wav"
    assert call["context"].app_instance_id == "app_provider_instance"
    assert call["context"].consumer_app_id == MINI_APP_ID


@pytest.mark.asyncio
async def test_broker_fails_closed_when_capability_is_not_declared(monkeypatch):
    runtime = _runtime()
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    declaration = runtime.extension_manager.list_studio_mini_apps(
        STUDIO_ID, principal=RequestPrincipal.legacy_local()
    )[0]
    declaration["requirements"]["capabilities"] = ["audio.detailed_transcription"]
    runtime.extension_manager.list_studio_mini_apps = lambda *_args, **_kwargs: (
        declaration,
    )

    with pytest.raises(StudioCapabilityError) as error:
        await StudioCapabilityBroker(runtime).detailed_transcription(
            STUDIO_ID,
            MOUNT_ID,
            principal=RequestPrincipal.legacy_local(),
            content=_wav(),
            filename="meeting.wav",
            media_type="audio/wav",
            profile="compact",
            language=None,
            word_timestamps=True,
            diarization=True,
        )
    assert error.value.code == "capability_not_declared"
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_broker_invokes_source_separation_and_returns_zip(monkeypatch):
    runtime = _runtime(extension_manager=SeparationExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_separation_model(),),
    )

    response = await StudioCapabilityBroker(runtime).source_separation(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        content=_wav(),
        filename="meeting.wav",
        media_type="audio/wav",
        profile="dialogue_background",
    )

    assert response.status_code == 200
    assert response.media_type == "application/zip"
    call = runtime.model_invocations.call
    assert call["operation"] == "audio_process"
    assert call["data"]["task"] == "source_separation"
    assert call["data"]["profile"] == "dialogue_background"
    assert call["context"].consumer_app_id == (
        "ai2apps.media-voice.source-separation"
    )


def test_source_separation_probe_reports_demucs_ready(monkeypatch):
    runtime = _runtime(extension_manager=SeparationExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_separation_model(),),
    )

    result = StudioCapabilityBroker(runtime).probe(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )

    assert result["items"] == [
        {
            "capability": "audio.source_separation",
            "implemented": True,
            "ready": True,
            "required": True,
            "providers": [
                {
                    "modelId": "ai2apps.model.demucs-mlx/default",
                    "name": "MLX Demucs HTDemucs",
                    "checkpointReady": True,
                    "workerRunning": False,
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_broker_packages_video_subtitle_and_transcript(monkeypatch):
    runtime = _runtime(extension_manager=VideoSubtitleExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    request = Request({"type": "http", "app": FastAPI(), "headers": []})

    response = await StudioCapabilityBroker(runtime).video_subtitles(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        request=request,
        content=_wav(),
        filename="sample.mp4",
        media_type="video/mp4",
        source_language="zh",
        target_language=None,
        subtitle_format="srt",
        bilingual=False,
        burn_in=False,
        speaker_labels=True,
    )

    assert response.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        assert set(archive.namelist()) == {"subtitles.srt", "transcript.json"}
        assert "你好" in archive.read("subtitles.srt").decode("utf-8")


@pytest.mark.asyncio
async def test_subtitle_translation_batches_through_configured_cloud_route():
    app = FastAPI()
    calls = []

    @app.post("/v1/chat/completions")
    async def complete(payload: dict):
        calls.append(payload)
        texts = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
        return {
            "choices": [
                {"message": {"content": json.dumps([f"译:{text}" for text in texts])}}
            ]
        }

    runtime = _runtime()
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda purpose: (
            "cloud/openai/standard" if purpose == "work_standard" else None
        )
    )
    mounted = StudioCapabilityBroker(runtime).mounted_mini_app(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )
    request = Request({"type": "http", "app": app, "headers": []})

    result = await StudioCapabilityBroker(runtime)._translate_segments(
        [{"text": f"line {index}"} for index in range(45)],
        target_language="zh",
        principal=RequestPrincipal.legacy_local(),
        mounted=mounted,
        request=request,
    )

    assert len(calls) == 2
    assert result[0] == "译:line 0"
    assert result[-1] == "译:line 44"


@pytest.mark.asyncio
async def test_broker_replaces_only_declared_speaker_pipeline(monkeypatch):
    runtime = _replacement_runtime()
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(), _separation_model(), _voice_model()),
    )

    response = await StudioCapabilityBroker(runtime).audio_speaker_replacement(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        content=_wav(),
        filename="meeting.wav",
        media_type="audio/wav",
        action="replace",
        target_speaker="SPEAKER_00",
        reference=_wav(),
        reference_filename="reference.wav",
        reference_media_type="audio/wav",
        conversion_profile="timbre_quality",
        consent=True,
    )

    assert response.media_type == "audio/wav"
    assert response.body.startswith(b"RIFF")
    calls = runtime.model_invocations.calls
    assert [item["operation"] for item in calls] == [
        "audio_detailed_transcription",
        "audio_process",
        "audio_process",
    ]
    assert calls[1]["data"]["profile"] == "dialogue_background"
    assert calls[2]["data"]["task"] == "voice_conversion"
    assert calls[2]["data"]["mode"] == "timbre"


@pytest.mark.asyncio
async def test_broker_replaces_video_audio_after_speaker_pipeline(monkeypatch):
    runtime = SimpleNamespace(
        extension_manager=VideoReplacementExtensionManager(),
        model_invocations=ReplacementInvocations(),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(), _separation_model(), _voice_model()),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.replace_video_audio",
        lambda video, audio: b"video-with-replaced-audio" if video and audio else b"",
    )

    response = await StudioCapabilityBroker(runtime).video_speaker_replacement(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        content=_wav(),
        filename="meeting.mp4",
        media_type="video/mp4",
        action="replace",
        target_speaker="SPEAKER_00",
        reference=_wav(),
        reference_filename="reference.wav",
        reference_media_type="audio/wav",
        conversion_profile="timbre_quality",
        consent=True,
    )

    assert response.media_type == "video/mp4"
    assert response.body == b"video-with-replaced-audio"


@pytest.mark.asyncio
async def test_capability_router_accepts_multipart_only_for_a_valid_mount(monkeypatch):
    runtime = _runtime()
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/capabilities/"
            "audio.detailed_transcription/invoke",
            data={
                "profile": "compact",
                "language": "zh",
                "word_timestamps": "true",
                "diarization": "true",
            },
            files={"file": ("meeting.wav", _wav(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.json()["segments"][0]["speaker"] == "SPEAKER_00"


@pytest.mark.asyncio
async def test_capability_router_returns_source_separation_archive(monkeypatch):
    runtime = _runtime(extension_manager=SeparationExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_separation_model(),),
    )
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: runtime,
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/capabilities/"
            "audio.source_separation/invoke",
            data={"profile": "vocals_instrumental"},
            files={"file": ("song.wav", _wav(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content.startswith(b"PK")
