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

from ai2apps.api.studio_mini_apps import (
    _content_url,
    _phase_percent,
    _publish_video_studio_output,
    create_studio_mini_app_router,
)
from ai2apps.identity import RequestPrincipal
from ai2apps.studio.capability_broker import (
    StudioCapabilityBroker,
    StudioCapabilityError,
    _speech_text_similarity,
)

STUDIO_ID = "ai2apps.readaloud"
MOUNT_ID = "mount_test_detailed"
MINI_APP_ID = "ai2apps.media-voice.transcription"


def test_video_audio_translation_progress_uses_six_phase_ranges():
    capability = "media.video_audio_translation"

    assert _phase_percent(capability, 3, "queued", 50) == 0
    assert _phase_percent(capability, 3, "running", 60) == 40
    assert _phase_percent(capability, 3, "completed", 75) == 100
    assert _phase_percent(capability, 5, "running", 94) == 50


def test_speech_text_similarity_ignores_case_spacing_and_punctuation():
    assert _speech_text_similarity("Hello, world!", "hello world") == 1.0
    assert _speech_text_similarity("这是一次测试。", "这是一次测试") == 1.0
    assert _speech_text_similarity("那款起价54.99。", "那款起价五十四点九九。") == 1.0
    assert _speech_text_similarity("总共1024GB。", "总共一千零二十四 GB") == 1.0
    assert _speech_text_similarity("发布于2026年。", "发布于二零二六年") == 1.0
    assert _speech_text_similarity("正常语音", "") == 0.0


def _wav() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x00\x00" * 1_600)
    return output.getvalue()


async def _async_value(value):
    return value


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
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
        declaration["id"] = "ai2apps.media-voice.source-separation"
        declaration["requirements"] = {"capabilities": ["audio.source_separation"]}
        return (declaration,)


class VideoSubtitleExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = "ai2apps.media-voice.video-subtitles"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
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


class VideoAudioTranslationExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = "ai2apps.media-voice.video-audio-translation"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
        declaration["id"] = "ai2apps.media-voice.video-audio-translation"
        declaration["requirements"] = {
            "capabilities": [
                "media.video_audio_translation",
                "audio.detailed_transcription",
                "text.translation",
                "audio.source_separation",
                "audio.speech_generation",
                {"capability": "audio.voice_clone", "optional": True},
                "media.audio.extract",
                "media.video.audio_mux",
            ]
        }
        return (declaration,)


class AudioReplacementExtensionManager(FakeExtensionManager):
    def mount_entry(self, mount_id, *, principal=None):
        mount = super().mount_entry(mount_id, principal=principal)
        mount["context"]["miniAppId"] = "ai2apps.media-voice.audio-speaker-replacement"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
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
        mount["context"]["miniAppId"] = "ai2apps.media-voice.video-speaker-replacement"
        return mount

    def list_studio_mini_apps(self, studio_id, *, principal=None):
        declaration = dict(
            super().list_studio_mini_apps(studio_id, principal=principal)[0]
        )
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
                headers={
                    "Content-Disposition": 'attachment; filename="demucs-stems.zip"'
                },
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


def _punctuation_model(*, ready=True):
    return SimpleNamespace(
        id="ai2apps.model.punctuation-restorer/default",
        display_name="Punctuation Restorer",
        model_type="llm",
        metadata={"internal": True},
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


def _tts_model(*, ready=True):
    return SimpleNamespace(
        id="ai2apps.model.qwen3-tts-1.7b/base-5bit",
        display_name="Qwen3 TTS Base",
        model_type="audio_tts",
        metadata={},
        audio_capabilities={
            "tts": {
                "speed": {"mode": "native", "minimum": 0.5, "maximum": 2.0},
                "voice_profiles": {
                    "mode": "native",
                    "reference_audio": True,
                    "reference_transcript": "optional",
                    "reference_requirements": {"min_samples": 1, "max_samples": 1, "max_seconds": 15},
                },
            }
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


def test_video_audio_translation_probe_requires_media_stack_and_character_tts(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    runtime.model_manager = SimpleNamespace(
        resolve_default_model=lambda profile: "standard-model"
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(), _separation_model(), _tts_model()),
    )

    result = StudioCapabilityBroker(runtime).probe(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )
    items = {item["capability"]: item for item in result["items"]}

    assert items["media.video_audio_translation"]["ready"] is True
    assert items["audio.speech_generation"]["ready"] is True
    assert items["audio.voice_clone"]["ready"] is True
    assert items["text.translation"]["ready"] is True


def test_voice_clone_model_catalog_exposes_only_request_scoped_reference_models(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_tts_model(),),
    )

    result = StudioCapabilityBroker(runtime).voice_clone_models(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )

    assert result["items"] == [
        {
            "id": "ai2apps.model.qwen3-tts-1.7b/base-5bit",
            "name": "Qwen3 TTS Base",
            "ready": True,
            "minimumReferenceSeconds": None,
            "maximumReferenceSeconds": 15,
            "referenceTranscript": "optional",
        }
    ]


@pytest.mark.asyncio
async def test_video_audio_translation_uses_one_character_and_preserves_background(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    broker = StudioCapabilityBroker(runtime)
    segments = [{"start": 0.2, "end": 0.8, "text": "Hello."}]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("background.wav", _wav())
    calls = {}
    progress_events = []

    async def progress(phase_index, status, percent, detail):
        progress_events.append((phase_index, status, percent, detail))

    async def transcription(*_args, **options):
        calls["transcription"] = options
        return JSONResponse({"segments": segments})

    async def punctuate(value, **_options):
        return value

    async def translate(value, **options):
        calls["translation"] = options
        return ["你好。"]

    async def separation(*_args, **options):
        calls["separation"] = options
        return Response(archive.getvalue(), media_type="application/zip")

    async def speech(text, **options):
        calls["speech"] = {"text": text, **options}
        return _wav()

    monkeypatch.setattr(broker, "detailed_transcription", transcription)
    monkeypatch.setattr(broker, "_punctuate_segments", punctuate)
    monkeypatch.setattr(broker, "_translate_segments", translate)
    monkeypatch.setattr(broker, "source_separation", separation)
    monkeypatch.setattr(broker, "_character_speech", speech)
    monkeypatch.setattr(
        broker, "_character_speed_limit", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.mix_dubbed_segments",
        lambda background, speech_parts, timeline: (
            calls.update(mix=(background, speech_parts, timeline)) or b"dubbed wav"
        ),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.replace_video_audio",
        lambda video, audio: calls.update(remux=(video, audio)) or b"translated mp4",
    )

    response = await broker.video_audio_translation(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        request=SimpleNamespace(),
        content=b"source mp4",
        filename="lesson.mp4",
        media_type="video/mp4",
        source_language="en",
        target_language="zh",
        voice_profile_id="voice-1",
        progress=progress,
    )

    assert bytes(response.body) == b"translated mp4"
    assert calls["transcription"]["diarization"] is False
    assert calls["speech"]["text"] == "你好。"
    assert calls["speech"]["voice_profile_id"] == "voice-1"
    assert calls["separation"]["profile"] == "dialogue_background"
    assert calls["mix"][2] == segments
    assert calls["remux"] == (b"source mp4", b"dubbed wav")
    assert [event[:3] for event in progress_events if event[1] == "completed"] == [
        (1, "completed", 35),
        (2, "completed", 50),
        (3, "completed", 75),
        (4, "completed", 88),
    ]
    assert progress_events[-1][:3] == (5, "running", 94)


@pytest.mark.asyncio
async def test_video_audio_translation_clones_original_voice_without_character(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    broker = StudioCapabilityBroker(runtime)
    segments = [{"start": 1.0, "end": 2.0, "text": "Original narration."}]
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("background.wav", _wav())
    clone_calls = []
    clone_model = _tts_model()

    monkeypatch.setattr(
        broker,
        "detailed_transcription",
        lambda *_args, **_kwargs: _async_value(JSONResponse({"segments": segments})),
    )
    monkeypatch.setattr(
        broker, "_punctuate_segments", lambda value, **_kwargs: _async_value(value)
    )
    monkeypatch.setattr(
        broker, "_translate_segments", lambda *_args, **_kwargs: _async_value(["原始旁白。"])
    )
    monkeypatch.setattr(
        broker,
        "_voice_clone_model",
        lambda model_id: (
            clone_model,
            {"minSeconds": None, "maxSeconds": 15, "executable": True},
        ),
    )
    monkeypatch.setattr(
        broker,
        "_temporary_clone_speech",
        lambda text, **options: (
            clone_calls.append({"text": text, **options}) or _async_value(_wav())
        ),
    )
    monkeypatch.setattr(
        broker,
        "_character_speech",
        lambda *_args, **_kwargs: pytest.fail("temporary cloning must not read a Character"),
    )
    monkeypatch.setattr(
        broker,
        "source_separation",
        lambda *_args, **_kwargs: _async_value(
            Response(archive.getvalue(), media_type="application/zip")
        ),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.decode_audio_to_wav", lambda *_args, **_kwargs: _wav()
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.select_voice_clone_reference",
        lambda *_args, **_kwargs: (
            b"temporary reference",
            "Original narration.",
            {"start": 1.0, "end": 11.0},
        ),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.mix_dubbed_segments", lambda *_args: b"dubbed wav"
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.replace_video_audio", lambda *_args: b"translated mp4"
    )

    response = await broker.video_audio_translation(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        request=SimpleNamespace(),
        content=b"source mp4",
        filename="lesson.mp4",
        media_type="video/mp4",
        source_language="en",
        target_language="zh",
        voice_profile_id="__original_voice__",
        voice_clone_model_id=clone_model.id,
    )

    assert bytes(response.body) == b"translated mp4"
    assert len(clone_calls) == 1
    assert clone_calls[0]["reference_audio"] == b"temporary reference"
    assert clone_calls[0]["reference_text"] == "Original narration."
    assert clone_calls[0]["model"].id == clone_model.id


@pytest.mark.asyncio
async def test_video_audio_translation_retries_shorter_text_then_model_speed(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    broker = StudioCapabilityBroker(runtime)
    segment = {"start": 0.0, "end": 0.5, "text": "A verbose explanation."}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("background.wav", _wav())
    speech_calls = []

    async def speech(text, **options):
        speech_calls.append({"text": text, **options})
        return f"speech-{len(speech_calls)}".encode()

    monkeypatch.setattr(
        broker,
        "detailed_transcription",
        lambda *_args, **_kwargs: _async_value(JSONResponse({"segments": [segment]})),
    )
    monkeypatch.setattr(
        broker, "_punctuate_segments", lambda value, **_kwargs: _async_value(value)
    )
    monkeypatch.setattr(
        broker,
        "_translate_segments",
        lambda *_args, **_kwargs: _async_value(["这是一个很冗长的解释。"]),
    )
    monkeypatch.setattr(
        broker,
        "_shorten_translation",
        lambda *_args, **_kwargs: _async_value("简短解释。"),
    )
    monkeypatch.setattr(
        broker,
        "source_separation",
        lambda *_args, **_kwargs: _async_value(
            Response(archive.getvalue(), media_type="application/zip")
        ),
    )
    monkeypatch.setattr(broker, "_character_speech", speech)
    monkeypatch.setattr(broker, "_character_speed_limit", lambda *_args, **_kwargs: 2.0)
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.audio_duration",
        lambda value: {b"speech-1": 1.2, b"speech-2": 0.9, b"speech-3": 0.44}[value],
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.mix_dubbed_segments",
        lambda *_args: b"dubbed wav",
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.replace_video_audio",
        lambda *_args: b"translated mp4",
    )

    response = await broker.video_audio_translation(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        request=SimpleNamespace(),
        content=b"source mp4",
        filename="lesson.mp4",
        media_type="video/mp4",
        source_language="en",
        target_language="zh",
        voice_profile_id="voice-1",
    )

    assert bytes(response.body) == b"translated mp4"
    assert [call["text"] for call in speech_calls] == [
        "这是一个很冗长的解释。",
        "简短解释。",
        "简短解释。",
    ]
    assert "speed" not in speech_calls[0]
    assert "speed" not in speech_calls[1]
    assert speech_calls[2]["speed"] == pytest.approx(1.836, rel=0.01)


@pytest.mark.asyncio
async def test_video_audio_translation_retries_tts_until_asr_back_listening_passes(
    monkeypatch,
):
    runtime = _runtime(extension_manager=VideoAudioTranslationExtensionManager())
    broker = StudioCapabilityBroker(runtime)
    segment = {"start": 0.0, "end": 0.5, "text": "Hello."}
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("background.wav", _wav())
    speech_calls = []
    verified = []
    mixed = {}

    async def speech(text, **options):
        speech_calls.append({"text": text, **options})
        return f"speech-{len(speech_calls)}".encode()

    async def back_listen(value, **options):
        verified.append((value, options))
        return (0.1, "错误") if value == b"speech-1" else (0.95, "你好")

    monkeypatch.setattr(
        broker,
        "detailed_transcription",
        lambda *_args, **_kwargs: _async_value(JSONResponse({"segments": [segment]})),
    )
    monkeypatch.setattr(
        broker, "_punctuate_segments", lambda value, **_kwargs: _async_value(value)
    )
    monkeypatch.setattr(
        broker,
        "_translate_segments",
        lambda *_args, **_kwargs: _async_value(["你好。"]),
    )
    monkeypatch.setattr(
        broker,
        "source_separation",
        lambda *_args, **_kwargs: _async_value(
            Response(archive.getvalue(), media_type="application/zip")
        ),
    )
    monkeypatch.setattr(broker, "_character_speech", speech)
    monkeypatch.setattr(broker, "_back_listen_character_speech", back_listen)
    monkeypatch.setattr(broker, "_character_speed_limit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.audio_duration", lambda _value: 0.3
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.mix_dubbed_segments",
        lambda _background, speech_parts, _timeline: (
            mixed.update(speech_parts=speech_parts) or b"dubbed wav"
        ),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.replace_video_audio",
        lambda *_args: b"translated mp4",
    )

    response = await broker.video_audio_translation(
        STUDIO_ID,
        MOUNT_ID,
        principal=RequestPrincipal.legacy_local(),
        request=SimpleNamespace(),
        content=b"source mp4",
        filename="lesson.mp4",
        media_type="video/mp4",
        source_language="en",
        target_language="zh",
        voice_profile_id="voice-1",
        asr_verification=True,
    )

    assert bytes(response.body) == b"translated mp4"
    assert len(speech_calls) == 2
    assert [item[0] for item in verified] == [b"speech-1", b"speech-2"]
    assert mixed["speech_parts"] == [b"speech-2"]


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
    assert "float32_wav" not in call["data"]
    assert call["context"].consumer_app_id == ("ai2apps.media-voice.source-separation")


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
    progress = []

    async def report(phase_index, status, percent, detail):
        progress.append((phase_index, status, percent, detail))

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
        progress=report,
    )

    assert response.media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        assert set(archive.namelist()) == {"subtitles.srt", "transcript.json"}
        assert "你好" in archive.read("subtitles.srt").decode("utf-8")
    assert [(item[0], item[1], item[2]) for item in progress] == [
        (0, "running", 0),
        (0, "completed", 15),
        (1, "running", 15),
        (1, "completed", 45),
        (2, "completed", 70),
        (3, "running", 70),
        (3, "completed", 90),
        (4, "running", 90),
        (4, "running", 98),
    ]


@pytest.mark.asyncio
async def test_broker_restores_source_punctuation_before_cue_splitting(monkeypatch):
    class PunctuationInvocations(FakeInvocations):
        async def invoke_foreground_json(
            self, model_id, operation, payload, *, request_id, context
        ):
            assert model_id == "ai2apps.model.punctuation-restorer/default"
            assert operation == "chat_completions"
            assert request_id.startswith("mini-punctuation-")
            assert context.consumer_app_id == "ai2apps.media-voice.transcription"
            source = payload["messages"][0]["content"]
            return JSONResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": source.replace(
                                    "you know what the scariest part is",
                                    "You know what the scariest part is?",
                                )
                                + "."
                            }
                        }
                    ]
                }
            )

    runtime = _runtime()
    runtime.model_invocations = PunctuationInvocations()
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(), _punctuation_model()),
    )
    broker = StudioCapabilityBroker(runtime)
    mounted = broker.mounted_mini_app(
        STUDIO_ID, MOUNT_ID, principal=RequestPrincipal.legacy_local()
    )

    restored = await broker._punctuate_segments(
        [
            {
                "start": 0.0,
                "end": 7.0,
                "text": "you know what the scariest part is there is only one woman",
            }
        ],
        principal=RequestPrincipal.legacy_local(),
        mounted=mounted,
    )

    assert restored[0]["text"] == (
        "You know what the scariest part is? there is only one woman."
    )


@pytest.mark.asyncio
async def test_broker_burns_subtitles_off_the_event_loop(monkeypatch):
    runtime = _runtime(extension_manager=VideoSubtitleExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _runtime: (_model(),),
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.validate_video_media", lambda _content: None
    )
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.burn_subtitles",
        lambda content, segments, **options: b"burned-video",
    )
    thread_calls = []

    async def to_thread(function, *args, **kwargs):
        thread_calls.append((function, args, kwargs))
        return function(*args, **kwargs)

    monkeypatch.setattr("ai2apps.studio.capability_broker.asyncio.to_thread", to_thread)
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
        burn_in=True,
        speaker_labels=False,
        subtitle_font_size="extra_large",
        subtitle_background="box",
    )

    assert len(thread_calls) == 2
    assert thread_calls[1][1][0] == _wav()
    assert thread_calls[1][2]["font_size"] == "extra_large"
    assert thread_calls[1][2]["background_style"] == "box"
    with zipfile.ZipFile(io.BytesIO(response.body)) as archive:
        assert archive.read("subtitled-video.mp4") == b"burned-video"


def test_burned_subtitle_video_is_published_as_video_studio_artifact(
    monkeypatch, tmp_path
):
    calls = []

    class Repository:
        def create_run(self, **options):
            calls.append(("create_run", options))
            return {"id": "run_subtitles"}

        def update_run(self, run_id, **options):
            calls.append(("update_run", {"run_id": run_id, **options}))

        def create_artifact(self, run_id, **options):
            calls.append(("create_artifact", {"run_id": run_id, **options}))

        def prune_output_history(self, workspace, **scope):
            calls.append(("prune", scope))

    class Workspace:
        def import_artifact(self, session_id, source, name, **options):
            assert session_id == "session_video"
            assert source.read_bytes() == b"subtitled mp4"
            calls.append(("workspace", {"name": name, **options}))
            return SimpleNamespace(id="artifact_video", name=name)

    monkeypatch.setattr(
        "ai2apps.api.studio_mini_apps.StudioRepository", lambda _database: Repository()
    )
    mounted = SimpleNamespace(
        mount={"context": {"studioInstanceId": "appi_video"}},
        declaration={"id": "ai2apps.media-voice.video-subtitles", "version": "0.1.3"},
        capabilities={"media.video_subtitles"},
    )
    runtime = SimpleNamespace(
        database=object(),
        workspace=Workspace(),
        video_tasks=SimpleNamespace(artifact_session=lambda: "session_video"),
        config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)),
    )

    output = _publish_video_studio_output(
        runtime,
        RequestPrincipal.legacy_local(),
        mounted,
        b"subtitled mp4",
        "episode-01.mp4",
    )

    assert output == {
        "downloadUrl": "/v1/platform/sessions/session_video/artifacts/artifact_video/download",
        "runId": "run_subtitles",
        "filename": "episode-01-subtitled.mp4",
    }
    artifact = next(options for kind, options in calls if kind == "create_artifact")
    assert artifact["kind"] == "video" and artifact["media_type"] == "video/mp4"
    assert [options["status"] for kind, options in calls if kind == "update_run"] == [
        "running",
        "succeeded",
    ]


@pytest.mark.asyncio
async def test_video_subtitle_invoke_exposes_burned_video_to_host_output(monkeypatch):
    video = b"burned subtitle video"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("subtitles.srt", "1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        output.writestr("transcript.json", "{}")
        output.writestr("subtitled-video.mp4", video)

    async def subtitles(self, studio_id, mount_id, **options):
        assert studio_id == "ai2apps.video-studio" and options["burn_in"] is True
        assert options["subtitle_font_size"] == "extra_large"
        assert options["subtitle_background"] == "box"
        await options["progress"](0, "running", 0, "extracting")
        await options["progress"](0, "completed", 15, "extracted")
        await options["progress"](1, "running", 15, "transcribing")
        return Response(archive.getvalue(), media_type="application/zip")

    mounted = SimpleNamespace(
        mount={"context": {"studioInstanceId": "appi_video"}},
        declaration={"id": "ai2apps.media-voice.video-subtitles", "version": "0.1.3"},
        capabilities={"media.video_subtitles"},
    )
    monkeypatch.setattr(StudioCapabilityBroker, "video_subtitles", subtitles)
    monkeypatch.setattr(
        StudioCapabilityBroker, "mounted_mini_app", lambda *args, **kwargs: mounted
    )
    monkeypatch.setattr(
        "ai2apps.api.studio_mini_apps._publish_video_studio_output",
        lambda runtime, principal, selected, content, filename, **kwargs: (
            {
                "downloadUrl": "/v1/platform/sessions/video/artifacts/subtitled/download",
                "runId": "run_subtitled",
                "filename": "sample-subtitled.mp4",
            }
            if content == video
            else (_ for _ in ()).throw(AssertionError("wrong video"))
        ),
    )
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: SimpleNamespace(extension_manager=object()),
            principal_provider=RequestPrincipal.legacy_local,
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            "/studios/ai2apps.video-studio/mini-app-mounts/mount/invocations",
            json={"capability": "media.video_subtitles"},
        )
        assert created.status_code == 201
        invocation = created.json()
        response = await client.post(
            "/studios/ai2apps.video-studio/mini-app-mounts/mount/capabilities/media.video_subtitles/invoke",
            headers={"X-AI2Apps-Invocation-ID": invocation["id"]},
            data={
                "burn_in": "true",
                "subtitle_font_size": "extra_large",
                "subtitle_background": "box",
            },
            files={"file": ("sample.mp4", b"source video", "video/mp4")},
        )
        events = await client.get(invocation["eventsUrl"].removeprefix("/v1/platform"))

    assert response.status_code == 200
    assert response.headers["x-ai2apps-download-url"].endswith("/subtitled/download")
    assert response.headers["x-ai2apps-studio-run-id"] == "run_subtitled"
    assert events.status_code == 200
    assert "event: progress" in events.text
    assert '"status": "completed"' in events.text
    assert '"percent": 100' in events.text
    assert '"phasePercent": 0' in events.text
    assert '"phasePercent": 100' in events.text
    assert (
        events.text.index('"detail": "extracting"')
        < events.text.index('"detail": "extracted"')
        < events.text.index('"detail": "transcribing"')
    )


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
                {
                    "message": {
                        "content": json.dumps(
                            [f"译:{text.removesuffix('.')}" for text in texts]
                        )
                    }
                }
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
        [{"text": f"line {index}."} for index in range(45)],
        target_language="zh",
        principal=RequestPrincipal.legacy_local(),
        mounted=mounted,
        request=request,
    )

    assert len(calls) == 2
    assert "full-width Chinese punctuation" in calls[0]["messages"][1]["content"]
    assert result[0] == "译:line 0。"
    assert result[-1] == "译:line 44。"


@pytest.mark.asyncio
async def test_subtitle_translation_recovers_when_model_changes_batch_item_count():
    app = FastAPI()
    batch_sizes = []

    @app.post("/v1/chat/completions")
    async def complete(payload: dict):
        texts = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
        batch_sizes.append(len(texts))
        translated = [f"译:{text.removesuffix('.')}" for text in texts]
        if len(texts) == 4:
            translated.pop()
        return {"choices": [{"message": {"content": json.dumps(translated)}}]}

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
        [{"text": f"line {index}."} for index in range(4)],
        target_language="zh",
        principal=RequestPrincipal.legacy_local(),
        mounted=mounted,
        request=request,
    )

    assert batch_sizes == [4, 2, 2]
    assert result == [f"译:line {index}。" for index in range(4)]


@pytest.mark.asyncio
async def test_subtitle_translation_rejoins_single_item_split_by_model():
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def complete(_payload: dict):
        return {"choices": [{"message": {"content": json.dumps(["前半句", "后半句"])}}]}

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
        [{"text": "One complete sentence."}],
        target_language="zh",
        principal=RequestPrincipal.legacy_local(),
        mounted=mounted,
        request=request,
    )

    assert result == ["前半句 后半句。"]


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
@pytest.mark.parametrize(
    "output_format, filename, mime",
    [
        ("json", "transcript.json", "application/json"),
        ("markdown", "transcript.md", "text/markdown"),
        ("srt", "transcript.srt", "application/x-subrip"),
    ],
)
async def test_capability_router_accepts_multipart_only_for_a_valid_mount(
    monkeypatch, output_format, filename, mime
):
    runtime = _runtime()
    saved = []

    def save(*args, **kwargs):
        saved.append((args, kwargs))
        return "/v1/platform/sessions/s/artifacts/a/download"

    runtime.readaloud_tasks = SimpleNamespace(save_studio_output=save)
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
                "output_format": output_format,
                "language": "zh",
                "word_timestamps": "true",
                "diarization": "true",
            },
            files={"file": ("meeting.wav", _wav(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.json()["segments"][0]["speaker"] == "SPEAKER_00"

    assert saved[0][1]["filename"] == filename
    assert saved[0][1]["media_type"] == mime
    assert response.headers["X-AI2Apps-Download-URL"].endswith("/a/download")
    if output_format == "markdown":
        assert saved[0][0][1].decode().startswith("# 录音文本记录")
    elif output_format == "srt":
        assert " --> " in saved[0][0][1].decode()


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


@pytest.mark.asyncio
async def test_media_upload_limits_are_separate_and_enforced(monkeypatch):
    from ai2apps.api import studio_mini_apps as api

    assert api.MAX_CAPABILITY_UPLOAD_BYTES == 1024**3
    assert api.MAX_REFERENCE_UPLOAD_BYTES == 100 * 1024**2
    monkeypatch.setattr(api, "MAX_CAPABILITY_UPLOAD_BYTES", 16)
    received = []

    async def separate(self, *args, **kwargs):
        received.append(kwargs["content"])
        return Response(b"ok")

    monkeypatch.setattr(api.StudioCapabilityBroker, "source_separation", separate)
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: _runtime(), principal_provider=RequestPrincipal.legacy_local
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        for size, status in [(0, 400), (16, 200), (17, 413)]:
            response = await client.post(
                f"/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/capabilities/audio.source_separation/invoke",
                files={"file": ("episode.mp4", b"x" * size, "video/mp4")},
            )
            assert response.status_code == status
    assert received == [b"x" * 16]


@pytest.mark.asyncio
async def test_separation_json_response_persists_host_outputs(monkeypatch):
    runtime = _runtime(extension_manager=SeparationExtensionManager())
    monkeypatch.setattr(
        "ai2apps.studio.capability_broker.list_package_models",
        lambda _: (_separation_model(),),
    )
    saved = []

    def save(owner, content, filename):
        saved.append((owner, content, filename))
        return {
            "downloadUrl": "/v1/platform/sessions/test/artifacts/zip/download",
            "tracks": [{"id": "track"}],
        }

    runtime.readaloud_tasks = SimpleNamespace(save_separation_output=save)
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: runtime, principal_provider=RequestPrincipal.legacy_local
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/capabilities/audio.source_separation/invoke",
            headers={"Accept": "application/json"},
            data={"profile": "vocals_instrumental"},
            files={"file": ("episode.mp4", _wav(), "video/mp4")},
        )
    assert response.status_code == 200
    assert response.json()["tracks"] == [{"id": "track"}]
    assert saved[0][0] == RequestPrincipal.legacy_local().actor_user_id
    assert saved[0][1].startswith(b"PK") and saved[0][2] == "episode.mp4"


@pytest.mark.asyncio
async def test_text_export_validates_mount_and_json_and_publishes_current_edits():
    runtime = _runtime()
    original_mount = runtime.extension_manager.mount_entry

    def checked_mount(mount_id, **kwargs):
        if mount_id != MOUNT_ID:
            from ai2apps.core import ResourceNotFoundError

            raise ResourceNotFoundError("mount", mount_id)
        return original_mount(mount_id, **kwargs)

    runtime.extension_manager.mount_entry = checked_mount

    saved = []

    def save(owner, content, **options):
        saved.append((owner, content, options))
        return "/v1/platform/sessions/session/artifacts/export/download"

    runtime.readaloud_tasks = SimpleNamespace(save_studio_output=save)
    app = FastAPI()
    app.include_router(
        create_studio_mini_app_router(
            lambda: runtime, principal_provider=RequestPrincipal.legacy_local
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        url = f"/studios/{STUDIO_ID}/mini-app-mounts/{MOUNT_ID}/exports"
        content = '{"segments":[{"text":"Corrected text","speaker":"SPEAKER_01"}]}'
        response = await client.post(
            url, json={"filename": "transcript.json", "content": content}
        )
        assert response.status_code == 200
        assert response.json()["downloadUrl"].endswith("/export/download")
        assert saved[0][1] == content.encode()
        assert saved[0][2]["media_type"] == "application/json"
        for filename, value in [
            ("../bad.json", "{}"),
            ("bad.html", "text"),
            ("bad.json", "{broken"),
        ]:
            assert (
                await client.post(url, json={"filename": filename, "content": value})
            ).status_code == 422
        assert len(saved) == 1
        response = await client.post(
            url.replace(MOUNT_ID, "missing"),
            json={"filename": "transcript.json", "content": "{}"},
        )
        assert response.status_code in (403, 404)
        assert len(saved) == 1
